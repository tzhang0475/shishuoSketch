# SRM0.2B — Blind Rich-Story Discovery Pilot

SRM0.2B is an observational, generated-only experiment for
`03-zhengshi-005`. The model receives exactly the canonical processed Story
main text and its ten Liu annotation blocks. It receives no Person cards,
Era orientation, PersonStory links, facts, relations, Gold annotations,
previous SRM state, or retrieval results.

The model returns only three weak discovery surfaces:

- up to three text-triggered research questions;
- up to five observed person connections, without a relation taxonomy;
- up to five attributed or uncertain person appraisals.

This stage does not select an active question, search, retrieve evidence,
create Research Memory, resolve identities, or write canonical data. Empty
connection and appraisal arrays are valid. Trigger text must be an exact
substring of the supplied Story or Liu annotation text.

Run the one-completion pilot with:

```bash
export DEEPSEEK_API_KEY="..."
python3 scripts/run_srm0_2b.py --story 03-zhengshi-005
python3 scripts/validate_srm0_2b.py
```

Inspect the generated candidate at:

```text
data/generated/srm0/03-zhengshi-005/discovery/
```

Manual review is separate:

```text
data/annotation/srm0-2b-discovery-review.json
```

The packet builder is deterministic. Live model output is intentionally not
treated as byte-deterministic and is never promoted to canonical or prior
SRM data.
