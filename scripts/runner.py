#!/usr/bin/env python3
"""
Complete automation pipeline runner for Clara AI account processing.

Processes demo and onboarding transcripts through extraction, agent generation,
and versioning pipeline. Fully idempotent with comprehensive error handling.
"""

import os
import json
import sys
import glob
from pathlib import Path
import logging
from typing import Dict, List, Any

from extract_memo import extract_from_file
from generate_agent import generate_agent_spec
from apply_patch import VersionManager, process_onboarding_call

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CLARAIPipeline:
    """Main orchestration for Clara AI automation pipeline."""

    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.dataset_dir = os.path.join(root_dir, "dataset")
        self.outputs_dir = os.path.join(root_dir, "outputs")
        self.changelog_dir = os.path.join(root_dir, "changelog")
        self.workflows_dir = os.path.join(root_dir, "workflows")
        
        self.version_manager = VersionManager(self.outputs_dir, self.changelog_dir)
        self._ensure_structure()

    def _ensure_structure(self):
        """Ensure all required directories exist."""
        required_dirs = [
            self.dataset_dir,
            os.path.join(self.dataset_dir, "demo_calls"),
            os.path.join(self.dataset_dir, "onboarding_calls"),
            self.outputs_dir,
            self.changelog_dir,
            self.workflows_dir,
            os.path.join(self.outputs_dir, "accounts")
        ]
        
        for dir_path in required_dirs:
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Ensured directory: {dir_path}")

    def process_demo_calls(self) -> Dict[str, Any]:
        """Process all demo call transcripts (generating v1)."""
        logger.info("=" * 60)
        logger.info("PIPELINE A: Processing Demo Calls (v1)")
        logger.info("=" * 60)
        
        demo_dir = os.path.join(self.dataset_dir, "demo_calls")
        transcript_files = glob.glob(os.path.join(demo_dir, "*.txt"))
        
        if not transcript_files:
            logger.warning(f"No demo transcripts found in {demo_dir}")
            return {"status": "no_files", "count": 0}
        
        results = {
            "status": "processing",
            "demo_calls_found": len(transcript_files),
            "accounts_created": [],
            "errors": []
        }
        
        for transcript_path in transcript_files:
            try:
                logger.info(f"\nProcessing: {os.path.basename(transcript_path)}")
                
                memo = extract_from_file(transcript_path, version="v1")
                if not memo:
                    results["errors"].append(f"Extraction failed: {transcript_path}")
                    continue
                
                account_id = memo.get("account_id")
                
                existing_memo = self.version_manager.load_memo(account_id, "v1")
                if existing_memo:
                    logger.info(f"Account {account_id} already exists - skipping (idempotent)")
                    results["accounts_created"].append(account_id)
                    continue
                
                agent_spec = generate_agent_spec(memo, version="v1")
                if not agent_spec:
                    results["errors"].append(f"Agent generation failed: {account_id}")
                    continue
                
                self.version_manager.save_memo(account_id, memo, "v1")
                self.version_manager.save_agent_spec(account_id, agent_spec, "v1")
                self.version_manager.create_tracking_artifact(account_id, memo, agent_spec, "v1")
                
                logger.info(f"✓ Created v1 for account {account_id} ({memo.get('company_name')})")
                results["accounts_created"].append(account_id)
                
            except Exception as e:
                error_msg = f"Error processing {transcript_path}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
        
        results["status"] = "complete"
        return results

    def process_onboarding_calls(self) -> Dict[str, Any]:
        """Process all onboarding call transcripts (generating v2)."""
        logger.info("\n" + "=" * 60)
        logger.info("PIPELINE B: Processing Onboarding Calls (v2)")
        logger.info("=" * 60)
        
        onboarding_dir = os.path.join(self.dataset_dir, "onboarding_calls")
        transcript_files = glob.glob(os.path.join(onboarding_dir, "*.txt"))
        
        if not transcript_files:
            logger.warning(f"No onboarding transcripts found in {onboarding_dir}")
            return {"status": "no_files", "count": 0}
        
        results = {
            "status": "processing",
            "onboarding_calls_found": len(transcript_files),
            "accounts_versioned": [],
            "errors": []
        }
        
        for transcript_path in transcript_files:
            try:
                logger.info(f"\nProcessing: {os.path.basename(transcript_path)}")
                
                new_memo = extract_from_file(transcript_path, version="v2")
                if not new_memo:
                    results["errors"].append(f"Extraction failed: {transcript_path}")
                    continue
                
                account_id = new_memo.get("account_id")
                
                v1_memo = self.version_manager.load_memo(account_id, "v1")
                if not v1_memo:
                    logger.warning(f"No v1 found for {account_id} - skipping onboarding")
                    continue
                
                existing_v2 = self.version_manager.load_memo(account_id, "v2")
                if existing_v2:
                    logger.info(f"v2 already exists for {account_id} - skipping (idempotent)")
                    results["accounts_versioned"].append(account_id)
                    continue
                
                v2_result = process_onboarding_call(
                    account_id, new_memo,
                    self.outputs_dir, self.changelog_dir
                )
                
                logger.info(f"✓ Created v2 and changelog for account {account_id}")
                logger.info(f"  Severity: {v2_result['changelog']['impact_assessment']['severity']}")
                results["accounts_versioned"].append(account_id)
                
            except Exception as e:
                error_msg = f"Error processing {transcript_path}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
        
        results["status"] = "complete"
        return results

    def generate_summary_report(self, demo_results: Dict[str, Any], 
                               onboarding_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive summary report."""
        report = {
            "pipeline_execution": {
                "timestamp": self._get_timestamp(),
                "status": "complete"
            },
            "demo_pipeline": {
                "accounts_created": demo_results.get("accounts_created", []),
                "count": len(demo_results.get("accounts_created", [])),
                "errors": demo_results.get("errors", [])
            },
            "onboarding_pipeline": {
                "accounts_versioned": onboarding_results.get("accounts_versioned", []),
                "count": len(onboarding_results.get("accounts_versioned", [])),
                "errors": onboarding_results.get("errors", [])
            },
            "summary": {
                "total_accounts": len(set(
                    demo_results.get("accounts_created", []) +
                    onboarding_results.get("accounts_versioned", [])
                )),
                "v1_created": len(demo_results.get("accounts_created", [])),
                "v2_created": len(onboarding_results.get("accounts_versioned", [])),
                "changelogs_generated": len(onboarding_results.get("accounts_versioned", []))
            },
            "output_structure": self._scan_output_structure()
        }
        
        return report

    def _scan_output_structure(self) -> Dict[str, Any]:
        """Scan and document output structure."""
        structure = {
            "root": self.root_dir,
            "account_dirs": [],
            "total_memos": 0,
            "total_specs": 0,
            "total_changelogs": 0
        }
        
        accounts_dir = os.path.join(self.outputs_dir, "accounts")
        if os.path.exists(accounts_dir):
            for account_id in os.listdir(accounts_dir):
                account_path = os.path.join(accounts_dir, account_id)
                if os.path.isdir(account_path):
                    versions = {}
                    for version in ["v1", "v2"]:
                        v_path = os.path.join(account_path, version)
                        if os.path.exists(v_path):
                            v_files = {
                                "memo": os.path.exists(os.path.join(v_path, "account_memo.json")),
                                "spec": os.path.exists(os.path.join(v_path, "agent_spec.json")),
                                "tracking": os.path.exists(os.path.join(v_path, "tracking.json"))
                            }
                            versions[version] = v_files
                            if v_files["memo"]:
                                structure["total_memos"] += 1
                            if v_files["spec"]:
                                structure["total_specs"] += 1
                    
                    structure["account_dirs"].append({
                        "account_id": account_id,
                        "versions": versions
                    })
        
        changelog_dir = os.path.join(self.root_dir, "changelog")
        if os.path.exists(changelog_dir):
            structure["total_changelogs"] = len(glob.glob(os.path.join(changelog_dir, "*.json")))
        
        return structure

    def save_summary_report(self, report: Dict[str, Any]) -> str:
        """Save summary report."""
        report_path = os.path.join(self.root_dir, "PIPELINE_EXECUTION_REPORT.json")
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"\nExecution report saved to {report_path}")
        return report_path

    def print_summary(self, report: Dict[str, Any]):
        """Print human-readable summary."""
        summary = report.get("summary", {})
        
        print("\n" + "=" * 60)
        print("CLARA AI PIPELINE EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Total Accounts Processed: {summary.get('total_accounts', 0)}")
        print(f"  • v1 Created (Demo): {summary.get('v1_created', 0)}")
        print(f"  • v2 Created (Onboarding): {summary.get('v2_created', 0)}")
        print(f"  • Changelogs Generated: {summary.get('changelogs_generated', 0)}")
        
        output_structure = report.get("output_structure", {})
        print(f"\nOutput Files:")
        print(f"  • Account Memos: {output_structure.get('total_memos', 0)}")
        print(f"  • Agent Specs: {output_structure.get('total_specs', 0)}")
        print(f"  • Changelogs: {output_structure.get('total_changelogs', 0)}")
        
        if report.get("demo_pipeline", {}).get("errors"):
            print(f"\nDemo Pipeline Errors: {len(report['demo_pipeline']['errors'])}")
            for error in report['demo_pipeline']['errors']:
                print(f"  • {error}")
        
        if report.get("onboarding_pipeline", {}).get("errors"):
            print(f"\nOnboarding Pipeline Errors: {len(report['onboarding_pipeline']['errors'])}")
            for error in report['onboarding_pipeline']['errors']:
                print(f"  • {error}")
        
        print("\n" + "=" * 60)
        print("Pipeline execution complete!")
        print("=" * 60 + "\n")

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()


def main():
    """Entry point."""
    if len(sys.argv) < 2:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(script_dir)
    else:
        root_dir = sys.argv[1]
    
    logger.info(f"Starting Clara AI Pipeline from: {root_dir}")
    
    pipeline = CLARAIPipeline(root_dir)
    
    demo_results = pipeline.process_demo_calls()
    onboarding_results = pipeline.process_onboarding_calls()
    
    report = pipeline.generate_summary_report(demo_results, onboarding_results)
    pipeline.save_summary_report(report)
    pipeline.print_summary(report)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
