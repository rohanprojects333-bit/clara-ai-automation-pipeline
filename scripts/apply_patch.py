import json
import os
from typing import Dict, Any, List
from deepdiff import DeepDiff
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VersionManager:
    """Manage versioning and patches for account memos and agent specs."""

    def __init__(self, outputs_dir: str, changelog_dir: str):
        self.outputs_dir = outputs_dir
        self.changelog_dir = changelog_dir
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure necessary directories exist."""
        os.makedirs(self.outputs_dir, exist_ok=True)
        os.makedirs(self.changelog_dir, exist_ok=True)

    def save_memo(self, account_id: str, memo: Dict[str, Any], version: str = "v1") -> str:
        """Save memo to versioned location."""
        account_dir = os.path.join(self.outputs_dir, "accounts", account_id, version)
        os.makedirs(account_dir, exist_ok=True)
        
        memo_path = os.path.join(account_dir, "account_memo.json")
        
        with open(memo_path, 'w') as f:
            json.dump(memo, f, indent=2)
        
        logger.info(f"Saved memo to {memo_path}")
        return memo_path

    def save_agent_spec(self, account_id: str, spec: Dict[str, Any], version: str = "v1") -> str:
        """Save agent spec to versioned location."""
        account_dir = os.path.join(self.outputs_dir, "accounts", account_id, version)
        os.makedirs(account_dir, exist_ok=True)
        
        spec_path = os.path.join(account_dir, "agent_spec.json")
        
        with open(spec_path, 'w') as f:
            json.dump(spec, f, indent=2)
        
        logger.info(f"Saved agent spec to {spec_path}")
        return spec_path

    def load_memo(self, account_id: str, version: str = "v1") -> Dict[str, Any]:
        """Load existing memo."""
        memo_path = os.path.join(self.outputs_dir, "accounts", account_id, version, "account_memo.json")
        
        if os.path.exists(memo_path):
            with open(memo_path, 'r') as f:
                return json.load(f)
        return {}

    def load_agent_spec(self, account_id: str, version: str = "v1") -> Dict[str, Any]:
        """Load existing agent spec."""
        spec_path = os.path.join(self.outputs_dir, "accounts", account_id, version, "agent_spec.json")
        
        if os.path.exists(spec_path):
            with open(spec_path, 'r') as f:
                return json.load(f)
        return {}

    def detect_changes(self, old_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect changes between versions using DeepDiff."""
        diff = DeepDiff(old_data, new_data, ignore_order=True)
        
        return {
            "values_changed": dict(diff.get("values_changed", {})),
            "items_added": dict(diff.get("items_added", {})),
            "items_removed": dict(diff.get("items_removed", {})),
            "type_changes": dict(diff.get("type_changes", {})),
            "has_changes": len(diff) > 0
        }

    def generate_changelog(self, account_id: str, v1_memo: Dict[str, Any], v2_memo: Dict[str, Any], 
                          v1_spec: Dict[str, Any], v2_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive changelog for version transition."""
        memo_changes = self.detect_changes(v1_memo, v2_memo)
        spec_changes = self.detect_changes(v1_spec, v2_spec)
        
        changelog = {
            "account_id": account_id,
            "version_transition": "v1_to_v2",
            "timestamp": self._get_timestamp(),
            "summary": {
                "memo_changed": memo_changes["has_changes"],
                "spec_changed": spec_changes["has_changes"],
                "total_changes": len(memo_changes["values_changed"]) + len(spec_changes["values_changed"])
            },
            "memo_changes": {
                "values_changed": self._humanize_changes(memo_changes.get("values_changed", {})),
                "items_added": list(memo_changes.get("items_added", {}).keys()),
                "items_removed": list(memo_changes.get("items_removed", {}).keys())
            },
            "agent_spec_changes": {
                "values_changed": self._humanize_changes(spec_changes.get("values_changed", {})),
                "items_added": list(spec_changes.get("items_added", {}).keys()),
                "items_removed": list(spec_changes.get("items_removed", {}).keys())
            },
            "impact_assessment": self._assess_impact(memo_changes, spec_changes)
        }
        
        return changelog

    def _humanize_changes(self, changes: Dict[str, Any]) -> Dict[str, str]:
        """Convert DeepDiff changes to human-readable format."""
        humanized = {}
        
        for key, value in changes.items():
            if isinstance(value, dict) and "old_value" in value and "new_value" in value:
                old = value["old_value"]
                new = value["new_value"]
                humanized[key] = {
                    "previous": old if not isinstance(old, (dict, list)) else f"{type(old).__name__}(...)",
                    "updated": new if not isinstance(new, (dict, list)) else f"{type(new).__name__}(...)"
                }
            else:
                humanized[key] = str(value)
        
        return humanized

    def _assess_impact(self, memo_changes: Dict[str, Any], spec_changes: Dict[str, Any]) -> Dict[str, Any]:
        """Assess impact of changes on operations."""
        impact = {
            "severity": "low",
            "affected_areas": [],
            "recommendations": []
        }
        
        critical_fields = [
            "emergency_definition", "emergency_routing_rules", 
            "business_hours", "account_id", "company_name"
        ]
        
        for field in critical_fields:
            if field in str(memo_changes.get("values_changed", {})):
                impact["severity"] = "high"
                impact["affected_areas"].append(f"Critical field changed: {field}")
        
        if memo_changes.get("values_changed"):
            impact["affected_areas"].append("Account information updated")
            impact["recommendations"].append("Review and re-train emergency protocols")
        
        if spec_changes.get("values_changed"):
            impact["affected_areas"].append("Agent behavior specifications modified")
            impact["recommendations"].append("Test agent with common call scenarios")
        
        if not impact["affected_areas"]:
            impact["severity"] = "none"
            impact["affected_areas"].append("No significant changes detected")
        elif len(impact["affected_areas"]) > 3:
            impact["severity"] = "critical"
            impact["recommendations"].append("Schedule comprehensive testing before deployment")
        
        return impact

    def save_changelog(self, account_id: str, changelog: Dict[str, Any]) -> str:
        """Save changelog to file."""
        os.makedirs(self.changelog_dir, exist_ok=True)
        
        changelog_path = os.path.join(self.changelog_dir, f"{account_id}_v1_to_v2_changelog.json")
        
        with open(changelog_path, 'w') as f:
            json.dump(changelog, f, indent=2)
        
        logger.info(f"Saved changelog to {changelog_path}")
        return changelog_path

    def apply_patch(self, account_id: str, base_memo: Dict[str, Any], 
                   patches: Dict[str, Any]) -> Dict[str, Any]:
        """Apply patches to memo to create v2."""
        patched = json.loads(json.dumps(base_memo))
        patched["version"] = "v2"
        
        for path, value in patches.items():
            keys = path.split(".")
            current = patched
            
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            current[keys[-1]] = value
        
        return patched

    def create_tracking_artifact(self, account_id: str, memo: Dict[str, Any], 
                                spec: Dict[str, Any], version: str = "v1") -> str:
        """Create tracking artifact for the account."""
        tracking = {
            "account_id": account_id,
            "tracking_version": version,
            "company": memo.get("company_name", "Unknown"),
            "status": "active",
            "created_at": self._get_timestamp(),
            "memo_path": f"outputs/accounts/{account_id}/{version}/account_memo.json",
            "spec_path": f"outputs/accounts/{account_id}/{version}/agent_spec.json",
            "emergency_mode": "enabled" if memo.get("emergency_definition") else "disabled",
            "business_hours_configured": bool(memo.get("business_hours")),
            "transfer_ready": bool(memo.get("call_transfer_rules")),
            "compliance": {
                "hipaa_ready": "hipaa_compliant_required" in memo.get("integration_constraints", []),
                "unknowns_resolved": len(memo.get("questions_or_unknowns", [])) == 0
            },
            "next_steps": self._generate_next_steps(memo, version)
        }
        
        account_dir = os.path.join(self.outputs_dir, "accounts", account_id, version)
        os.makedirs(account_dir, exist_ok=True)
        
        tracking_path = os.path.join(account_dir, "tracking.json")
        with open(tracking_path, 'w') as f:
            json.dump(tracking, f, indent=2)
        
        logger.info(f"Created tracking artifact at {tracking_path}")
        return tracking_path

    def _generate_next_steps(self, memo: Dict[str, Any], version: str) -> List[str]:
        """Generate next steps based on memo state."""
        steps = []
        
        if version == "v1":
            steps.append("Monitor call patterns from demo")
            steps.append("Validate emergency routing works as intended")
            steps.append("Scheduled onboarding call to create v2")
        else:
            steps.append("Verify changes didn't break routing")
            steps.append("Update training for any new features")
            steps.append("Schedule compliance review")
        
        unknown_count = len(memo.get("questions_or_unknowns", []))
        if unknown_count > 0:
            steps.append(f"Resolve {unknown_count} outstanding questions")
        
        return steps

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()


def process_onboarding_call(account_id: str, new_memo: Dict[str, Any], 
                           outputs_dir: str, changelog_dir: str) -> Dict[str, Any]:
    """Process onboarding call: load v1, create v2, generate changelog."""
    manager = VersionManager(outputs_dir, changelog_dir)
    
    v1_memo = manager.load_memo(account_id, "v1")
    v1_spec = manager.load_agent_spec(account_id, "v1")
    
    v2_memo = json.loads(json.dumps(new_memo))
    v2_memo["version"] = "v2"
    
    from generate_agent import generate_agent_spec
    v2_spec = generate_agent_spec(v2_memo, "v2")
    
    changelog = manager.generate_changelog(account_id, v1_memo, v2_memo, v1_spec, v2_spec)
    
    manager.save_memo(account_id, v2_memo, "v2")
    manager.save_agent_spec(account_id, v2_spec, "v2")
    manager.save_changelog(account_id, changelog)
    manager.create_tracking_artifact(account_id, v2_memo, v2_spec, "v2")
    
    return {
        "account_id": account_id,
        "v1_created": True,
        "v2_created": True,
        "changelog_generated": True,
        "changelog": changelog
    }
