# ADR 0001: Static-first WP1 architecture

## Decision

Milestone 1 uses React + Vite + TypeScript with static JSON/Markdown data.
The browser does not require a backend, database, Neo4j, online LLM, or
runtime API.

## Consequences

Source, annotation, derived, and site data remain separate. Build scripts
produce deterministic bundles, while the canonical Shishuo and Jinshu source
trees remain untouched. Later data changes can be reviewed as JSON/Markdown
changes and deployed through a static host.

