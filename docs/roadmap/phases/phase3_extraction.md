# Phase 3 - LLM Extraction

Goal: extract geographic mentions.

Tasks:

3.1 Create extractor service

`services/extractor/`

---

3.2 Connect to Ollama API

Support configurable model selection:

- default: `gpt-oss:20b`
- configurable: `EXTRACTOR_MODEL`

---

3.3 Implement extraction prompt

Task:

extract geographic mentions with anti-hallucination guidance.

---

3.4 Parse JSON output

---

3.5 Validate JSON schema

---

3.6 Insert extraction_runs

---

3.7 Insert location_mentions

Include `confidence` per mention.

---

3.8 Handle invalid JSON responses

Retry extraction.

---

3.9 Add extraction logging

Include request/response timing diagnostics for Ollama calls.
