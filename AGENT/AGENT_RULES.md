# AI Development Rules

The AI agent must:

- implement the project incrementally
- follow the architecture described in the docs
- keep commits small
- write tests
- keep services independent
- run services using docker-compose
- keep documentation synchronized with implementation
- treat stale or contradictory documentation as a repository defect
- update README and all impacted spec/docs files in the same task when behavior, interfaces, schema, runtime, or operations change

## Markdown Authority

Project markdown files are authoritative instructions.

- `GPT-5.4` may create and modify project markdown files when specs, tasks, contracts, or execution guidance must be updated.
- other models, including `gpt-5.3-codex`, must treat project markdown files as fixed instructions and may only execute the work described in them.
- non-`GPT-5.4` models must not modify project markdown files unless the user explicitly overrides this rule.

The agent has access to:

filesystem
docker
git
database
