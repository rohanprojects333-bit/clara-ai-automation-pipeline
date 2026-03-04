import json
from typing import Dict, Any, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RetellAgentSpecGenerator:
    """Generate Retell AI agent specs from account memos."""

    def __init__(self, memo: Dict[str, Any]):
        self.memo = memo
        self.account_id = memo.get("account_id", "UNKNOWN")

    def generate_spec(self, version: str = "v1") -> Dict[str, Any]:
        """Generate complete agent specification."""
        spec = {
            "version": version,
            "agent_metadata": {
                "agent_name": self._generate_agent_name(),
                "account_id": self.account_id,
                "company_name": self.memo.get("company_name", "Unknown"),
                "created_from_memo_version": self.memo.get("version", "v1")
            },
            "agent_config": {
                "voice_style": self._determine_voice_style(),
                "language": "english",
                "speaking_rate": 1.0
            },
            "system_prompt": self._generate_system_prompt(),
            "key_variables": self._extract_key_variables(),
            "call_flow": {
                "business_hours": self._generate_business_hours_flow(),
                "after_hours": self._generate_after_hours_flow()
            },
            "call_transfer_protocol": self._generate_transfer_protocol(),
            "fallback_protocol": self._generate_fallback_protocol(),
            "intents": self._generate_intents(),
            "safety_constraints": self._generate_safety_constraints(),
            "metadata": {
                "generation_version": "1.0",
                "generation_date": self._get_timestamp()
            }
        }
        
        return spec

    def _generate_agent_name(self) -> str:
        """Generate professional agent name."""
        company = self.memo.get("company_name", "Company").split()[0]
        return f"{company}_AI_Assistant"

    def _determine_voice_style(self) -> Dict[str, Any]:
        """Determine appropriate voice style."""
        if "medical" in self.memo.get("company_name", "").lower() \
           or "doctor" in self.memo.get("company_name", "").lower():
            tone = "professional_medical"
        elif "emergency" in str(self.memo.get("emergency_definition", [])).lower():
            tone = "calm_reassuring"
        else:
            tone = "professional_friendly"
        
        return {
            "tone": tone,
            "personality": "helpful, efficient, professional",
            "accent": "neutral"
        }

    def _generate_system_prompt(self) -> str:
        """Generate comprehensive system prompt covering all flows."""
        business_hours = self._format_business_hours()
        emergency_def = self._format_emergency_definition()
        services = self._format_services()
        
        prompt = f"""You are a professional AI receptionist for {self.memo.get('company_name', 'the company')}.

BUSINESS HOURS: {business_hours}
TIMEZONE: {self.memo.get('business_hours', {}).get('timezone', 'EST')}

OFFICE HOURS PROTOCOL:
1. Greet the caller warmly: "Hi, thank you for calling {self.memo.get('company_name', 'us')}. How can I help you today?"
2. Listen to their purpose and identify their needs
3. Collect their name and phone number for us to call them back if needed
4. Route them appropriately:
   - If appointment needed: "I'll connect you with our scheduling team"
   - If general inquiry: "Let me get the right person for you"
   - If transfer available: "One moment while I connect you"
5. Before transferring, confirm: "I'm going to transfer you to [Department]. Is that okay?"
6. After resolution, ask: "Is there anything else I can help you with today?"
7. End professionally: "Thank you for calling. Have a great day!"

AFTER-HOURS PROTOCOL:
1. Answer professionally: "Thank you for calling {self.memo.get('company_name', 'us')}. Our office is currently closed."
2. Determine if emergency: "Is this an emergency or urgent matter?"
   - Emergency indicators: {emergency_def}
3. If emergency:
   - Immediately say: "I understand. I'm connecting you with our emergency line now."
   - Collect their name, phone number, and address urgently
   - Attempt immediate transfer to emergency contact
   - "An emergency responder will call you shortly. Stay on the line."
4. If non-emergency:
   - Say: "I can take a message with your name and phone number. We'll call you back during business hours."
   - Collect details and confirm message
   - "We'll be back in touch first thing. Thank you for calling."

SERVICES PROVIDED: {services}

CRITICAL RULES:
- Never ask unnecessary questions beyond name, phone, and purpose
- Don't mention internal systems, tools, or function calls
- Be concise and respectful of caller's time
- If transfer fails, immediately acknowledge and offer voicemail
- Always reassure about follow-up timing
- Don't make appointments - collect info and transfer/confirm
- For emergency: prioritize speed over information collection

ROUTEABLE DEPARTMENTS: {', '.join(self.memo.get('call_transfer_rules', {}).get('allowed_departments', ['main', 'general']))}

SOURCE: Extracted from transcripts for {self.account_id}
GENERATED: AI Receptionist Configuration v{self.memo.get('version', 'v1')}"""
        
        return prompt

    def _format_business_hours(self) -> str:
        """Format business hours for prompt."""
        hours = self.memo.get("business_hours", {}).get("hours", {})
        if isinstance(hours, dict) and hours:
            formatted = []
            for day, times in hours.items():
                start = times.get("start", "09:00") if isinstance(times, dict) else times
                end = times.get("end", "17:00") if isinstance(times, dict) else "17:00"
                formatted.append(f"{day.title()}: {start}-{end}")
            return "; ".join(formatted)
        return "Monday-Friday 9AM-5PM"

    def _format_emergency_definition(self) -> str:
        """Format emergency definitions."""
        emergency = self.memo.get("emergency_definition", [])
        if isinstance(emergency, list) and emergency:
            return ", ".join(emergency[:3])
        return "severe symptoms, unable to wait, life-threatening situation"

    def _format_services(self) -> str:
        """Format services for prompt."""
        services = self.memo.get("services_supported", [])
        if isinstance(services, list) and services:
            return ", ".join([s.replace("_", " ").title() for s in services[:5]])
        return "General inquiries, scheduling, information"

    def _extract_key_variables(self) -> Dict[str, Any]:
        """Extract key variables for the agent."""
        return {
            "company_name": self.memo.get("company_name", "Unknown"),
            "account_id": self.account_id,
            "business_hours": self.memo.get("business_hours", {}),
            "timezone": self.memo.get("business_hours", {}).get("timezone", "EST"),
            "emergency_definition": self.memo.get("emergency_definition", []),
            "transfer_destinations": self.memo.get("call_transfer_rules", {}).get("allowed_departments", []),
            "office_address": self.memo.get("office_address", "Not specified"),
            "after_hours_behavior": "collect_info_and_callback" if "voicemail" in str(self.memo) else "transfer_to_emergency"
        }

    def _generate_business_hours_flow(self) -> Dict[str, Any]:
        """Generate business hours call flow."""
        return {
            "initial_greeting": "Thank you for calling. How can I help you today?",
            "information_collection": {
                "required_fields": ["caller_name", "phone_number", "call_purpose"],
                "optional_fields": ["callback_email", "preferred_callback_time"]
            },
            "routing_logic": {
                "appointment_request": "Transfer to scheduling",
                "emergency_during_hours": "Transfer to emergency contact",
                "general_inquiry": "Transfer to appropriate department",
                "unknown_purpose": "Ask for clarification before routing"
            },
            "confirmation_step": "Confirm transfer destination before connecting",
            "closing": "Is there anything else I can help with? Thank you for calling.",
            "fallback": "If transfer fails, offer voicemail and callback"
        }

    def _generate_after_hours_flow(self) -> Dict[str, Any]:
        """Generate after-hours call flow."""
        return {
            "initial_greeting": "Thank you for calling. Our office is currently closed.",
            "emergency_detection": {
                "prompt": "Is this an emergency or urgent matter?",
                "emergency_indicators": self.memo.get("emergency_definition", [])
            },
            "emergency_branch": {
                "confirmation": "I understand. I'm connecting you with our emergency line.",
                "information_collection": ["name", "phone_number", "address"],
                "transfer": "Immediate transfer to emergency contact",
                "fallback": "Leave voicemail with urgent callback assurance"
            },
            "non_emergency_branch": {
                "message_taking": "I'll take a message and someone will call you back during business hours.",
                "information_collection": ["name", "phone_number", "message"],
                "closing": "We'll be back in touch shortly. Thank you."
            },
            "fallback": "Voicemail with business hours and emergency instructions"
        }

    def _generate_transfer_protocol(self) -> Dict[str, Any]:
        """Generate transfer protocol."""
        return {
            "pre_transfer_confirmation": True,
            "transfer_announcement": "Transferring you now to our team",
            "max_wait_time_seconds": 180,
            "ring_back_alternative": "voicemail",
            "transfer_failure_behavior": "offer_voicemail",
            "allowed_departments": self.memo.get("call_transfer_rules", {}).get("allowed_departments", []),
            "require_caller_confirmation": True,
            "supported_transfer_types": ["department", "individual", "emergency"]
        }

    def _generate_fallback_protocol(self) -> Dict[str, Any]:
        """Generate fallback protocol."""
        return {
            "transfer_failure": {
                "action": "offer_voicemail",
                "message": "I'm having trouble connecting you right now. May I take a message?"
            },
            "no_answer": {
                "action": "voicemail_or_callback",
                "message": "No one is available at the moment. Would you prefer to leave a message or receive a callback?"
            },
            "system_error": {
                "action": "escalate_to_voicemail",
                "message": "I apologize, I'm experiencing a technical issue. Let me make sure we don't miss your message."
            },
            "after_hours_default": {
                "action": "voicemail_with_reassurance",
                "message": "Our team will get back to you first thing during business hours."
            },
            "max_retries_before_fallback": 2,
            "fallback_timeout_seconds": 30
        }

    def _generate_intents(self) -> List[Dict[str, Any]]:
        """Generate conversation intents."""
        return [
            {
                "intent_name": "appointment_scheduling",
                "triggers": ["schedule", "appointment", "book", "availability"],
                "required_info": ["date", "time", "purpose"],
                "action": "transfer_to_scheduling"
            },
            {
                "intent_name": "emergency",
                "triggers": ["emergency", "urgent", "critical", "help", "ambulance"],
                "required_info": ["caller_location", "caller_phone"],
                "action": "emergency_transfer"
            },
            {
                "intent_name": "general_inquiry",
                "triggers": ["information", "question", "help", "hours", "address"],
                "required_info": ["caller_name", "caller_phone"],
                "action": "transfer_or_provide_info"
            },
            {
                "intent_name": "callback_request",
                "triggers": ["call", "back", "return", "reach", "contact"],
                "required_info": ["caller_name", "caller_phone", "message"],
                "action": "schedule_callback"
            },
            {
                "intent_name": "billing_or_payment",
                "triggers": ["billing", "payment", "cost", "invoice", "charge"],
                "required_info": ["caller_id", "account_info"],
                "action": "transfer_to_billing"
            }
        ]

    def _generate_safety_constraints(self) -> List[str]:
        """Generate safety constraints."""
        constraints = [
            "Never provide medical advice - always transfer to medical professional",
            "Do not make promises about availability or response times beyond business hours",
            "Do not store or process sensitive data - collect minimal information",
            "Always reassure emergency callers about rapid response",
            "Never dismiss urgent-sounding concerns - escalate if uncertain",
            "Maintain professional, respectful tone at all times",
            "If HIPAA compliance required, inform of privacy practices",
            "Do not attempt diagnosis or triage medical situations"
        ]
        
        if "emergency" in str(self.memo.get("emergency_definition", [])).lower():
            constraints.append("Emergency protocol: immediate transfer, then fallback to voicemail")
        
        return constraints

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()


def generate_agent_spec(memo: Dict[str, Any], version: str = "v1") -> Dict[str, Any]:
    """Generate agent spec from memo."""
    try:
        generator = RetellAgentSpecGenerator(memo)
        spec = generator.generate_spec(version)
        logger.info(f"Generated agent spec v{version} for {memo.get('account_id', 'unknown')}")
        return spec
    except Exception as e:
        logger.error(f"Error generating spec: {e}")
        return {}
