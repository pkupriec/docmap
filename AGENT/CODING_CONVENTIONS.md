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

Basic tests should exist for:

crawler  
extractor  
geocoder  

Tests should be placed in:

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