import re
import json
from typing import Dict, List, Any, Tuple
from datetime import time as dt_time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConfidenceTracker:
    """Tracks confidence levels for extracted fields."""

    # Confidence thresholds
    HIGH_CONFIDENCE = 0.85
    MEDIUM_CONFIDENCE = 0.65
    LOW_CONFIDENCE = 0.5

    def __init__(self):
        self.scores: Dict[str, float] ={}
        self.extraction_methods: Dict[str, str] = {} #Track how each filed was extracted
        self.details: Dict[str, str]= {} # Additional details about extraction 
    
    def record_score(self, field_name: str, score: float, method: str = "", details: str = ""):
        """Record confidence score for a filed."""
        self.scores[field_name] = score
        self.extraction_methods[field_name] = method
        self.details[field_name] = details

        confidence_level = "HIGH" if score >= self.HIGH_CONFIDENCE else "MEDIUM" if score >= self.MEDIUM_CONFIDENCE else "LOW"
        logger.info(f"    {field_name}: {confidence_level}  ({score:.2f}) - {method}")

    def get_low_confidence_fields(self) -> List[Dict[str, Any]]:
        """Get list of fields with low confidence."""
        low_confidence_fields = []
        for field, score in self.scores.items():
            if score < self.MEDIUM_CONFIDENCE:
                low_confidence_fields.append({
                    "field": field,
                    "confidence_score": score,
                    "extraction_method": self.extraction_methods.get(field, ""),
                    "details": self.details.get(field, "")
                })
        return sorted(low_confidence_fields, key=lambda x: x["confidence"])
    
    def get_report(self) -> Dict[str, Any]:
        """Get full confidence report."""
        total_fields = len(self.scores)
        high = sum(1 for s in self.scores.values() if s >= self.HIGH_CONFIDENCE)
        medium = sum(1 for s in self.scores.values() if s >= self.MEDIUM_CONFIDENCE and s < self.HIGH_CONFIDENCE)
        low = sum(1 for s in self.scores.values() if s < self.MEDIUM_CONFIDENCE)

        return {
            "total_fields_extracted" : total_fields,
            "field_confidence_distribution" : {
                "high": high,
                "medium": medium,
                "low": low
            },
            "average_confidence": sum(self.scores.values()) / total_fields if total_fields > 0 else 0.0,
            "low_confidence_fields": self.get_low_confidence_fields(),
            "field_scores": self.scores
        }

class TranscriptExtractor:
    """Rule-based extraction of account memo data from transcripts."""

    def __init__(self):
        self.business_hours_pattern = r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\s+(\d{1,2}):(\d{2})\s*(?:am|pm|AM|PM)?\s*[-–]\s*(\d{1,2}):(\d{2})\s*(?:am|pm|AM|PM)?"
        self.phone_pattern = r"(\+?1?\s*)?(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})"
        self.address_pattern = r"(\d+\s+[^,\n]+,[^,\n]+,[A-Z]{2}\s+\d{5})"
        self.timezone_pattern = r"\b(EST|CST|MST|PST|EDT|CDT|MDT|PDT|UTC|GMT|ET|CT|MT|PT)\b"
        self.confidence = ConfidenceTracker()

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

    def extract_company_name(self, content: str) -> Tuple[str, float]:
        """Extract company name from content. Returns (company_name, confidence_score)"""
        # Standard company anme patterns (high confidence)

        standard_companies = {
            "Demo Medical Clinic": r"demo\s+medical\s+clinic",
            "GreenTech Environmental": r"greentech\s+environmental",            
            "Premier Legal Services": r"premier\s+legal\s+services",
            "Tech Support Solutions": r"tech\s+support\s+solutions",            
            "Zenith Financial Advisors": r"zenith\s+financial\s+advisors"
        }

        for company_name, pattern in standard_companies.items():
            if re.search(pattern, content, re.IGNORECASE):
                self.confidence.record_score("company_name", 0.95, "standard_company_pattern", f"Matched standard company name: {company_name}")
                return company_name, 0.95
            
        # Try extraction patterns (medium confidence)
        patterns = [
            r"(?:company|business|clinic|office|practice)[\s:]+([A-Za-z\s&\-\.]+?)(?:\n|,|$)",
            r"calling\s+([A-Za-z\s&\-\.]+?)(?:\.|,|\n)",
            r"Thank you for calling ([A-Za-z\s&\-\.]+?)(?:\.|,|!|\n)"
        ]
        for pattern in patterns:
            match = re.search(pattern, content[:500], re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                if len(company) >3: # Filter out very short matches
                    self.confidence.record_score("company_name", 0.78, "content_pattern_match")
                    return company, 0.78

            # Fallback to filename based heuristic (low confidence)
            self.confidence.record_score("company_name", 0.45, "filename_fallback")
            return "Unknown Company"

    def extract_business_hours(self, content: str) -> Tuple[Dict[str, Any], float]:
        """Extract business hours. Returns (hours, confidence_score)"""
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

        if hours:
            confidence = min(0.95, 0.7 + (len(hours) * 0.05))
            self.confidence.record_score("business_hours", confidence, f"regex_match ({len(hours)} days)")

        else:
            # Using defaults
            hours = {"monday-friday": {"start": "09:00", "end": "17:00"}}
            self.confidence.record_score("business_hours", 0.4, "default_monday_friday")

        # Get timezone with its confidence
        timezone, tz_confidence = self._extract_timezone(content)
        self.confidence.record_score("timezone", tz_confidence, "explicit_pattern_match" if tz_confidence > 0.8 else "default_EST")

        result = {
            "hours": hours, 
            "timezone": timezone,
            "observed": True
        }
    
        # Return confidence of the hours extraction (not timezone)
        conf_score = self.confidence.get("business_hours", 0.4)
        return result, conf_score

    def _extract_timezone(self, content: str) -> Tuple[str, float]:

        """Extract timezone. Returns (timezone, confidence_score)."""
        match = re.search(self.timezone_pattern, content, re.IGNORECASE)
        if match:
            tz = match.group(1).upper()
            self.confidence.record_score("timezone", 0.88, "explicit_pattern_match")
            return tz, 0.88
        else:
            self.confidence.record_score("timezone", 0.3, "default_EST")
            return "EST", 0.3

    def extract_office_address(self, content: str) -> Tuple[str, float]:
        """Extract office address. Return (address, confidence_score)"""
        match = re.search(self.address_pattern, content)
        if match:
            self.confidence.record_score("office_address", 0.92, "regex_pattern_match")
            return match.group(1), 0.92

        lines = content.split('\n')
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in ['address', 'located', 'office', 'suite']):
                if i + 1 < len(lines):
                    addr = lines[i + 1].strip()
                    if len(addr) > 10: # Filter out very short matches
                        self.confidence.record_score("office_address", 0.68, "keyword_contextual_match")
                        return addr, 0.68
                    
        # Last resort: try to find any address- like pattern in text
        if re.search(r"\d+\s+[\w\s]+,\s+[\w\s]+\s*,\s*[A-Z]{2}", content):
            match = re.search(r"(\d+\s+[\w\s]+,\s+[\w\s]+\s*,\s*[A-Z]{2},\s*\d{5})", content)
            if match:
                self.confidence.record_score("office_address", 0.75, "address_partial_pattern_match")
                return match.group(0), 0.7
            
        # Not found - mark as unknown
        self.confidence.record_score("office_address", 0.02, "not_found_default")
        return "", 0.2

    def extract_services(self, content: str) -> Tuple[str, float]:
        """Extract services supported. Returns (services, confidence_score)"""
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
        matches_found = 0

        for service, pattern in service_keywords.items():
            if re.search(pattern, content, re.IGNORECASE):
                services.append(service)
                matches_found += 1

        if services:
            # Confidance based on nimber of services found (more = more reliable extraction)
            confidance = min(0.95, 0.6 + (matches_found * 0.08))
            self.confidence.record_score("services_supported", confidance, f"keyword_pattern_match ({matches_found} patterns)")

            return services, confidance
        else:
            # Default fallback
            self.confidence.record_score("services_supported", 0.35, "default_fallback")
            return ["general_inquiry", "appointment_scheduling"], 0.35
        

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
        """Build complete account memo. with confidence scores."""
        account_id = self.extract_account_id(content, filename)

        # Extract with confidence scores
        company_name, company_confidence = self.extract_company_name(content)
        business_hours, hours_confidence = self.extract_business_hours(content)
        office_address, address_confidence = self.extract_office_address(content)
        services, services_confidence = self.extract_services(content)

        # Extract other fields (they log theri own confidence internally)
        emergency_def = self.extract_emergency_definition(content)
        emergency_rules = self.extract_routing_rules(content, "emergency")
        non_emergency_rules = self.extract_routing_rules(content, "regular")
        transfer_rules = self.extract_call_transfer_rules(content)
        constraints = self.extract_integration_constraints(content)
        after_hours_flow = self.extract_after_hours_flow(content)
        office_hours = self.extract_office_hours_flow(content)

        unknowns = self._extract_unknowns_with_confidence(content)

        memo = {
            "version": version,
            "account_id": account_id,
            "company_name": company_name,
            "business_hours": business_hours,
            "office_address": office_address,
            "services_supported": services,
            "emergency_definition": emergency_def,
            "emergency_routing_rules": emergency_rules,
            "non_emergency_routing_rules": non_emergency_rules,
            "call_transfer_rules": transfer_rules,
            "integration_constraints": constraints,
            "after_hours_flow_summary": after_hours_flow,
            "office_hours_flow_summary": office_hours,
            "questions_or_unknowns": unknowns,
            "notes": self._extract_notes(content),
            "metadata": {
                "source_file": filename,
                "extraction_version": "2.0",
                "extraction_date": self._get_timestamp(),
                "extraction_confidence": self.confidence.get_report()
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

    def _extract_unknowns_with_confidence(self, content: str) -> List[str]:

        """Extract unknowns based on both content analysis and low-confidence field extractions."""
        unknowns = []       

        # Add confidence-based unknowns
        low_conf_fields = self.confidence.get_low_confidence_fields()

        for field_info in low_conf_fields:
            field = field_info["field"]
            confidence = field_info["confidence"]

          
            if field == "office_address":
                unknowns.append(f"Office address not reliably found ({confidence:.1%} confidence)")
            elif field == "company_name":
                unknowns.append(f"Company name extraction unreliable ({confidence:.1%} confidence) - verify from content")
            elif field == "business_hours":
                unknowns.append(f"Business hours not explicitly stated ({confidence:.1%} confidence) - using defaults")
            elif field == "services_supported":
                unknowns.append(f"Service offerings inferred from context ({confidence:.1%} confidence) - verify complete list")
            elif field == "timezone":
                unknowns.append(f"Timezone not specified ({confidence:.1%} confidence) - using {field_info.get('details', 'EST')}")

        # Add pattern-based unknowns
        if not re.search(r"emergency|urgent", content, re.IGNORECASE):
            unknowns.append("No explicit emergency definition found in transcript")

        if not re.search(r"department|transfer|route|extension", content, re.IGNORECASE):
            unknowns.append("Department routing details need clarification")
 
        if not re.search(r"callback|voicemail|message", content, re.IGNORECASE):
            unknowns.append("After-hours callback procedures need confirmation")

        return unknowns if unknowns else ["All key information extracted with acceptable confidence"]


    
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

    """Extract memo from transcript file with confidence tracking."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        extractor = TranscriptExtractor()
        filename = filepath.split('\\')[-1] if '\\' in filepath else filepath.split('/')[-1]

        logger.info(f"\n{'='*60}")
        logger.info(f"EXTRACTION: {filename} (version {version})")
        logger.info(f"{'='*60}")

        memo = extractor.build_memo(content, filename, version)

        # Log confidence summary
        conf_report = memo["metadata"]["extraction_confidence"]
        logger.info(f"\nConfidence Summary for {memo['account_id']}:")
        logger.info(f"  Average confidence: {conf_report['average_confidence']:.2%}")
        logger.info(f"  Distribution: {conf_report['field_confidence_distribution']}")

        if conf_report["low_confidence_fields"]:
            logger.warning(f"  ⚠️  {len(conf_report['low_confidence_fields'])} fields with low confidence:")
            for field_info in conf_report["low_confidence_fields"]:
                logger.warning(f"     - {field_info['field']}: {field_info['confidence']:.1%} ({field_info['method']})")
       
        logger.info(f"Extracted memo for {memo['account_id']} from {filename}")
        return memo
    
    except Exception as e:
        logger.error(f"Error extracting from {filepath}: {e}")
        return {}
