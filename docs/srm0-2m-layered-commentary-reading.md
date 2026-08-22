# SRM0.2M — Layered Commentary Reading Pilot

SRM0.2M is an isolated A/B reading experiment for
`03-zhengshi-005`. It keeps the Story main text as the primary research
object and supplies the ten canonical Liu annotation blocks plus the local
S1/Jianshu assertion blocks for the same Story as explicitly labelled
commentary.

The local S1 assertion layer resolves 14 Jianshu-linked blocks totaling 1,629
characters, so the one-completion pilot uses `jianshu_mode: full`. Existing
speaker attribution and layer fields are retained in the local material
resolution; the model packet does not include source paths, hashes, Person
IDs, graph data, or prior experiment output.

The output separates:

- main-text-anchored `reading_questions`;
- commentary-only `commentary_issues`;
- cautious `person_connections`;
- source-attributed `appraisals`.

Connection normalization downgrades unsupported strength claims and removes
an authorship-attribution conflict when it is presented as a person relation.
No search, active-question selection, Research Memory update, canonical
write-back, or frontend change is performed.

Run the single completion with:

```bash
export DEEPSEEK_API_KEY="..."
python3 scripts/run_srm0_2m.py --story 03-zhengshi-005
python3 scripts/validate_srm0_2m.py
```

The frozen SRM0.2B baseline remains at:

```text
data/generated/srm0/03-zhengshi-005/discovery/
```

The layered experiment is stored separately at:

```text
data/generated/srm0/03-zhengshi-005/layered-commentary/
```
