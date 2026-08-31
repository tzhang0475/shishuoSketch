"""SFH2.2-A0R: an isolated, contract-safe review orchestration pilot.

The package deliberately does not replace the historical SFH2/A0 pipeline.
It reuses the frozen A0 evidence packets and tests a safer review protocol:
LLM records are validated, reviewers return decisions or narrow patches, and
Python copies selected records instead of asking a model to regenerate them.
"""

