# Coding Conventions

This document defines coding standards for the DocMap project.

The AI agent must follow these rules when writing code.

---

# Language

Primary language:

Python

Minimum version:

Python 3.11+

---

# Project Structure

Services must be placed in:

services/

Example:

services/
    crawler/
    extractor/
    geocoder/
    pipeline/

Each service should be self-contained.

---

# Python Style

Follow PEP8.

Use type hints everywhere.

Example:

def download_page(url: str) -> str:
    ...

---

# File Size

Avoid large files.

Maximum recommended size:

500 lines per file.

Split logic into modules.

## Reasoning

Use reasoning effort conservatively.

- low: mechanical edits, straightforward doc sync, small localized changes
- medium: default for ordinary feature implementation and refactoring
- high: only for complex orchestration, schema-affecting work, tricky invariants, or high-risk debugging

Do not keep reasoning higher than necessary once the implementation path is clear.

---

# Logging

All services must use structured logging.

Example fields:

timestamp  
service  
operation  
status  

Example log message:

crawler.download_success url=scp-173

---

# Error Handling

Services must not crash due to single failures.

Examples:

crawler retries  
LLM JSON validation  
geocoder fallback  

Always handle exceptions.

---

# HTTP Clients

Use:

requests

Timeouts must be specified.

Example:

timeout=10

---

# Database Access

Use:

psycopg or sqlalchemy.

Avoid raw SQL scattered in code.

Centralize queries where possible.

---

# Docker

All services must run in Docker.

Use docker-compose.

Containers must be stateless.

---

# Configuration

All configuration must come from environment variables.

Example:

DATABASE_URL  
OLLAMA_HOST  
GEOCODER_URL  

---

# Tests

Tests should be used where they materially improve confidence.

Typical useful coverage areas:

crawler  
extractor  
geocoder  

Tests are primarily an implementation self-check mechanism for the agent.
The agent may choose unit tests, integration tests, or no new tests depending on the change.
If an existing test already covers the changed logic, update it together with the implementation.

When tests are written, they should be placed in:

tests/

---

# Commit Messages

Use conventional commits.

Examples:

feat: implement crawler downloader  
feat: add geocoding service  
fix: handle invalid LLM JSON  

Avoid vague messages.

---

# Documentation

If code behavior changes, update documentation:

ARCHITECTURE.md  
DATA_MODEL.md  
PIPELINE.md  

Documentation must remain consistent with code.
