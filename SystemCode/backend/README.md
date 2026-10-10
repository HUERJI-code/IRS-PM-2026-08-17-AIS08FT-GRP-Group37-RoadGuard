# Backend - planned

Planned stack: Python, FastAPI and SQLite.

Implement these modules incrementally:

1. Configuration, application startup and health endpoint.
2. Inspection upload and a clearly labelled demo vision adapter.
3. Confidence-based review, severity/priority rules and decision traces.
4. Task and crew management, with four crews as the default scenario.
5. Travel-time matrix provider, greedy baseline and a group-built GA.
6. Queue-change replanning and route metrics.
7. Proposal-stage GPT/RAG explanations using calculated route facts.

Keep API credentials in local environment variables. Do not call external services from the GA fitness loop. Define API contracts and install dependencies when this module is implemented.
