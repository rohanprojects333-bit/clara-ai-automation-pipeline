import re
import json
import uuid
import sys
import os


def extract_company_name(text):
    pattern = re.compile(r'(?im)^(?:company\s+name|company|client)[:\-]\s*(.+)$')
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def extract_business_hours(text):
    result = {"days": "", "start": "", "end": "", "timezone": ""}

    match = re.search(r'(?im)business hours[:\-]?\s*(.+)', text)
    if not match:
        return result

    info = match.group(1)

    tz = re.search(r'\b([A-Z]{2,4})\b', info)
    if tz:
        result["timezone"] = tz.group(1)

    times = re.search(
        r'(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*[-–]\s*'
        r'(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)',
        info,
        re.I
    )
    if times:
        result["start"] = times.group(1)
        result["end"] = times.group(2)

    days = re.search(
        r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\s*[-–]\s*'
        r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*',
        info,
        re.I
    )
    if days:
        result["days"] = days.group(0)

    return result


def extract_services(text):
    match = re.search(r'(?im)services[:\-]\s*(.+)', text)
    if not match:
        return []
    services = re.split(r'[;,]\s*', match.group(1))
    return [s.strip() for s in services if s.strip()]


def extract_section(text, heading):
    pattern = re.compile(
        rf'(?im){heading}[:\-]?\s*(.*?)(?:\n\s*\n|$)'
    )
    match = pattern.search(text)
    return match.group(1).strip().replace('\n', ' ') if match else ""


def generate_summary(text):
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return " ".join(sentences[:2]).strip()


def main():
    if len(sys.argv) != 2:
        print("Usage: python extractor.py <transcript.txt>")
        sys.exit(1)

    filepath = sys.argv[1]

    if not os.path.isfile(filepath):
        print("File not found.")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as file:
        text = file.read()

    data = {
        "account_id": str(uuid.uuid4()),
        "company_name": extract_company_name(text),
        "business_hours": extract_business_hours(text),
        "services_supported": extract_services(text),
        "emergency_routing_rules": extract_section(text, "emergency routing rules"),
        "non_emergency_routing_rules": extract_section(text, "non[- ]?emergency routing rules"),
        "call_transfer_rules": extract_section(text, "call transfer rules"),
        "integration_constraints": extract_section(text, "integration constraints"),
        "after_hours_flow_summary": extract_section(text, "after hours flow summary"),
        "office_hours_flow_summary": extract_section(text, "office hours flow summary"),
        "notes": generate_summary(text),
    }

    print(json.dumps(data, indent=4))


if __name__ == "__main__":
    main()