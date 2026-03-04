# Clara AI Automation Pipeline

Zero-cost, fully reproducible automation system for processing call transcripts into structured account memos, AI agent specifications, and version-controlled documentation.

---

## Architecture Overview

This pipeline implements a two-stage automation system designed to convert raw call transcripts into structured AI receptionist configurations.

### PIPELINE A: Demo Call Processing (v1)

- Input: Demo call transcripts
- Extract: Structured account information via rule-based parsing
- Generate: Account memo JSON + Retell agent spec v1
- Store: Versioned artifacts in structured filesystem
- Track: Execution report and metadata

### PIPELINE B: Onboarding Call Processing (v2)

- Input: Onboarding call transcripts
- Extract: Updated account information
- Compare: v1 → v2 structured diff
- Generate:
  - Updated memo (v2)
  - Updated agent spec (v2)
  - Changelog file
- Store: Versioned artifacts with clear traceability

---

## Orchestration Design

This pipeline intentionally uses a Python-based orchestration layer (`scripts/runner.py`) instead of n8n or Zapier.

### Why Python Instead of SaaS Automation?

The assignment requires:
- Zero spend
- Fully reproducible execution
- No paid API usage

Using a local Python orchestrator ensures:

- No external SaaS dependency
- Fully offline execution
- Deterministic, repeatable runs
- No API keys required
- Easy reviewer reproduction

### What `runner.py` Handles

- Dataset scanning (demo + onboarding folders)
- Account ID normalization
- v1 creation for demo calls
- v2 detection and update for onboarding calls
- Idempotency checks (skip existing versions safely)
- Changelog generation using DeepDiff
- Execution reporting (PIPELINE_EXECUTION_REPORT.json)

This replaces a traditional no-code orchestrator with a fully local automation engine.

---

## Directory Structure
