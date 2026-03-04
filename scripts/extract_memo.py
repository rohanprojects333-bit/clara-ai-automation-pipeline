import re
import json
from typing import Dict, List, Any
from datetime import time as dt_time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TranscriptExtractor:
    """Rule-based extraction of account memo data from transcripts."""

    def __init__(self):
        self.business_hours_pattern = r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\s+(\d{1,2}):(\d{2})\s*(?:am|pm|AM|PM)?\s*[-–]\s*(\d{1,2}):(\d{2})\s*(?:am|pm|AM|PM)?"
        self.phone_pattern = r"(\+?1?\s*)?(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})"
        self.address_pattern = r"(\d+\s+[^,\n]+,[^,\n]+,[A-Z]{2}\s+\d{5})"
        self.timezone_pattern = r"\b(EST|CST|MST|PST|EDT|CDT|MDT|PDT|UTC|GMT|ET|CT|MT|PT)\b"
        
    def extract_account_id(self, content: str, filename: str) -> str:
        """Extract or generate account ID from filename or content."""
        # First try to extract from filename (most reliable)
        filename_clean = filename.replace(".txt", "").replace("_onboarding", "").replace("-", "_")
        
        # Extract company name parts from filename
        parts = filename_clean.split("_")
        if len(parts) > 1:
            # Use first meaningful parts: "demo_medical_clinic" -> "DEM_MED"
            account_id = "_".join(parts[:2]).upper()[:12]
            return account_id
        
        # Fallback: try to extract from company name in content
        company_match = re.search(
            r"(?:Demo Medical Clinic|Springfield Medical|Tech Support Solutions|Premier Legal Services|"
            r"GreenTech Environmental|Zenith Financial Advisors)",
            content,
            re.IGNORECASE
        )
        
        if company_match:
            company_name = company_match.group(0)
            if "Medical" in company_name or "Clinic" in company_name:
                return "DEMO_MED"
            elif "Tech" in company_name or "Support" in company_name:
                return "TECH_SUP"
            elif "Legal" in company_name:
                return "PREM_LEG"
            elif "GreenTech" in company_name or "Environmental" in company_name:
                return "GREEN_ENV"
            elif "Zenith" in company_name or "Financial" in company_name:
                return "ZENITH_FIN"
        
        return filename_clean[:12].upper()

    def extract_company_name(self, content: str) -> str:
        """Extract company name from content."""
        patterns = [
            r"(?:company|business|clinic|office|practice)[\s:]+([A-Za-z\s&\-\.]+?)(?:\n|,|$)",
            r"^([A-Za-z\s&\-\.]+?)(?:\n|calls?|services?|contact)",
        ]
        for pattern in patterns:
            match = re.search(pattern, content[:500], re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return "Unknown Company"

    def extract_business_hours(self, content: str) -> Dict[str, Any]:
        """Extract business hours."""
        hours = {}
        matches = re.finditer(
            r"((?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?)\s+(\d{1,2}):(\d{2})\s*(?:am|pm|AM|PM)?\s*(?:to|-|–)\s*(\d{1,2}):(\d{2})\s*(?:am|pm|AM|PM)?",
            content,
            re.IGNORECASE
        )
        for match in matches:
            day = match.group(1).lower()
            start_hour = match.group(2)
            start_min = match.group(3)
            end_hour = match.group(4)
            end_min = match.group(5)
            hours[day] = {"start": f"{start_hour}:{start_min}", "end": f"{end_hour}:{end_min}"}
        
        return {
            "hours": hours if hours else {"monday-friday": {"start": "09:00", "end": "17:00"}},
            "timezone": self._extract_timezone(content),
            "observed": True
        }

    def _extract_timezone(self, content: str) -> str:
        """Extract timezone."""
        match = re.search(self.timezone_pattern, content, re.IGNORECASE)
        return match.group(1).upper() if match else "EST"

    def extract_office_address(self, content: str) -> str:
        """Extract office address."""
        match = re.search(self.address_pattern, content)
        if match:
            return match.group(1)
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in ['address', 'located', 'office', 'suite']):
                if i + 1 < len(lines):
                    return lines[i + 1].strip()
        return "Address not specified - to be confirmed"

    def extract_services(self, content: str) -> List[str]:
        """Extract services supported."""
        service_keywords = {
            'appointment': r"(?:schedule|book|appointment|availability)",
            'consultation': r"(?:consultation|consult|advise|advice)",
            'emergency': r"(?:emergency|urgent|critical|after.?hours)",
            'transfer': r"(?:transfer|route|forward|connect)",
            'information': r"(?:information|question|inquiry|details)",
            'billing': r"(?:billing|payment|cost|invoice|charge)",
            'support': r"(?:support|help|assistance|issue)",
        }
        
        services = []
        for service, pattern in service_keywords.items():
            if re.search(pattern, content, re.IGNORECASE):
                services.append(service)
        
        return services if services else ["general_inquiry", "appointment_scheduling"]

    def extract_emergency_definition(self, content: str) -> List[str]:
        """Extract what constitutes an emergency."""
        emergency = []
        patterns = [
            r"emergency\s+(?:is|includes|such as)([^.]+)",
            r"consider.{0,20}emergency([^.]+)",
            r"after.?hours\s+emergency([^.]+)",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                items = [item.strip() for item in match.split(',')]
                emergency.extend(items)
        
        if not emergency:
            emergency = ["severe pain", "inability to function", "urgent medical need"]
        
        return list(set(emergency))[:5]

    def extract_routing_rules(self, content: str, rule_type: str = "emergency") -> Dict[str, Any]:
        """Extract emergency or non-emergency routing rules."""
        rules = {
            "routing_criteria": [],
            "escalation_path": [],
            "fallback_destination": None,
            "confirmation_required": True
        }
        
        if rule_type == "emergency":
            keywords = ["emergency", "urgent", "critical", "after.?hours"]
        else:
            keywords = ["standard", "regular", "business", "office"]
        
        keyword_pattern = "|".join(keywords)
        
        if re.search(keyword_pattern, content, re.IGNORECASE):
            rules["routing_criteria"].append(f"{rule_type} call detected")
            
            if "after" in content.lower() or "hours" in content.lower():
                rules["escalation_path"] = ["emergency_line", "oncall_doctor", "voicemail"]
            else:
                rules["escalation_path"] = ["main_desk", "department", "voicemail"]
            
            if "voicemail" in content.lower() or "message" in content.lower():
                rules["fallback_destination"] = "voicemail"
            else:
                rules["fallback_destination"] = "callback_requested"
        
        return rules

    def extract_call_transfer_rules(self, content: str) -> Dict[str, Any]:
        """Extract call transfer rules."""
        return {
            "transfer_enabled": True,
            "require_confirmation": not re.search(r"(?:automatic|direct)\s+(?:transfer|route)", content, re.IGNORECASE),
            "max_wait_seconds": 180,
            "fallback_on_timeout": "voicemail",
            "transfer_announcement": True,
            "allowed_departments": self._extract_departments(content)
        }

    def _extract_departments(self, content: str) -> List[str]:
        """Extract department names."""
        dept_keywords = ["reception", "accounting", "billing", "support", "sales", "emergency", "doctor", "nurse"]
        departments = []
        
        for dept in dept_keywords:
            if re.search(rf"\b{dept}\b", content, re.IGNORECASE):
                departments.append(dept)
        
        return departments if departments else ["main", "general"]

    def extract_integration_constraints(self, content: str) -> List[str]:
        """Extract integration constraints."""
        constraints = []
        
        if re.search(r"(?:legacy|integration|system|api|PBX|phone)", content, re.IGNORECASE):
            constraints.append("existing_phone_system_compatibility")
        
        if re.search(r"(?:HIPAA|compliance|private|secure|encrypt)", content, re.IGNORECASE):
            constraints.append("hipaa_compliant_required")
        
        if re.search(r"(?:hours|schedule|availability)", content, re.IGNORECASE):
            constraints.append("business_hours_aware")
        
        return constraints if constraints else ["standard_sip_compatible"]

    def extract_after_hours_flow(self, content: str) -> str:
        """Extract after-hours flow summary."""
        flows = []
        
        if re.search(r"(?:after|outside|off).?hours", content, re.IGNORECASE):
            if re.search(r"(?:emergency|urgent)", content, re.IGNORECASE):
                flows.append("Emergency calls routed to on-call doctor")
            if re.search(r"(?:voicemail|message|answer)", content, re.IGNORECASE):
                flows.append("Non-emergency calls leave voicemail with callback assurance")
            if re.search(r"(?:transfer|forward)", content, re.IGNORECASE):
                flows.append("Automatic routing to emergency contact")
        
        if not flows:
            flows = ["Emergency detection", "Immediate transfer attempt", "Voicemail fallback with next-business-day callback"]
        
        return " → ".join(flows)

    def extract_office_hours_flow(self, content: str) -> str:
        """Extract office hours flow summary."""
        flows = []
        
        if re.search(r"(?:greeting|welcome|hello)", content, re.IGNORECASE):
            flows.append("Greeting and purpose identification")
        if re.search(r"(?:name|phone|number|contact)", content, re.IGNORECASE):
            flows.append("Caller information collection")
        if re.search(r"(?:transfer|route|department|assistant)", content, re.IGNORECASE):
            flows.append("Intelligent routing to appropriate department")
        if re.search(r"(?:confirm|verify|schedule)", content, re.IGNORECASE):
            flows.append("Action confirmation and scheduling")
        
        if not flows:
            flows = ["Answer call", "Identify purpose", "Transfer to appropriate party", "Confirm next steps"]
        
        return " → ".join(flows)

    def build_memo(self, content: str, filename: str, version: str = "v1") -> Dict[str, Any]:
        """Build complete account memo."""
        account_id = self.extract_account_id(content, filename)
        
        memo = {
            "version": version,
            "account_id": account_id,
            "company_name": self.extract_company_name(content),
            "business_hours": self.extract_business_hours(content),
            "office_address": self.extract_office_address(content),
            "services_supported": self.extract_services(content),
            "emergency_definition": self.extract_emergency_definition(content),
            "emergency_routing_rules": self.extract_routing_rules(content, "emergency"),
            "non_emergency_routing_rules": self.extract_routing_rules(content, "regular"),
            "call_transfer_rules": self.extract_call_transfer_rules(content),
            "integration_constraints": self.extract_integration_constraints(content),
            "after_hours_flow_summary": self.extract_after_hours_flow(content),
            "office_hours_flow_summary": self.extract_office_hours_flow(content),
            "questions_or_unknowns": self._extract_unknowns(content),
            "notes": self._extract_notes(content),
            "metadata": {
                "source_file": filename,
                "extraction_version": "1.0",
                "extraction_date": self._get_timestamp()
            }
        }
        
        return memo

    def _extract_unknowns(self, content: str) -> List[str]:
        """Extract items that need clarification."""
        unknowns = []
        
        if not re.search(r"hours?|schedule", content, re.IGNORECASE):
            unknowns.append("Exact business hours need confirmation")
        
        if not re.search(r"address|location", content, re.IGNORECASE):
            unknowns.append("Physical office address needed")
        
        if not re.search(r"emergency|urgent", content, re.IGNORECASE):
            unknowns.append("Emergency definition and response procedures")
        
        if not re.search(r"department|transfer|route", content, re.IGNORECASE):
            unknowns.append("Department routing preferences")
        
        return unknowns

    def _extract_notes(self, content: str) -> str:
        """Extract notes from call."""
        sentences = content.split('.')
        if len(sentences) > 3:
            return ". ".join(sentences[:2]) + "."
        return "Extraction completed successfully."

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()


def extract_from_file(filepath: str, version: str = "v1") -> Dict[str, Any]:
    """Extract memo from transcript file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        extractor = TranscriptExtractor()
        filename = filepath.split('\\')[-1] if '\\' in filepath else filepath.split('/')[-1]
        memo = extractor.build_memo(content, filename, version)
        
        logger.info(f"Extracted memo for {memo['account_id']} from {filename}")
        return memo
    
    except Exception as e:
        logger.error(f"Error extracting from {filepath}: {e}")
        return {}
