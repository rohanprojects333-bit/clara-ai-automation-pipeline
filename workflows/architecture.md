# Workflow Architecture Diagram

## Pipeline A (Demo → v1)

Demo Transcript
    ↓
Extraction Engine (extract_memo.py)
    ↓
Account Memo v1 (JSON)
    ↓
Agent Spec Generator (generate_agent.py)
    ↓
Agent Spec v1 (JSON)
    ↓
Tracking + Execution Report

---

## Pipeline B (Onboarding → v2)

Onboarding Transcript
    ↓
Extraction Engine
    ↓
New Memo Draft (v2 candidate)
    ↓
Version Manager (apply_patch.py)
    ↓
DeepDiff Comparison (v1 → v2)
    ↓
Account Memo v2
    ↓
Agent Spec v2
    ↓
Changelog Generation