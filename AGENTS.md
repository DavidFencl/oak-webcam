# Agent notes (Luxonis)

This project targets OAK4 D Pro with DepthAI v3 and a standalone OAK App.
Verify APIs through Luxonis MCP/current examples and CLI flags through installed oakctl help.
Never compile DepthAI from source; use a prebuilt SDK. Never run competing camera processes.
Use an isolated Python environment for Python tooling. Prefer oakctl run-script for host scripts.
Read docs/brief.md and docs/plans/current.md before implementation.
Hardware notes are hints; live observations are authoritative.
Keep evidence outside docs/. A running process does not prove video delivery.
Do not update firmware, flash, reset, publish, or use sudo without authorization.

Pointers: docs/glossary.md; docs/brief.md; docs/plans/current.md.
