# SFH2.2-A2OSP — Gold Alignment Promotion and Residual Qualification

SFH2.2-A2OSP is an offline successor to the frozen A2OS target-alignment
audit. It promotes exactly the two high-confidence human Gold corrections
identified there and re-evaluates the already-frozen A2OR outputs. No provider
call, model rerun, prompt change, or semantic-output regeneration is allowed.

## Controlled promotion

The active occurrence Gold changed in exactly two records:

- `sfh2-a0r-l-challenge-f245371d8f0cdf9c8773` (`顧`): the pinned opening
  occurrence at offsets `0–1` is a participant inside `顧長康`; the later
  `顧` in `顧曰` is the speaker occurrence.
- `sfh2-a0-57d1fc3c0492b21ee1f4` (`齊桓公`): the occurrence inside the
  explanatory `史記` material is a reference to the ruler; the invoked
  historical comparison is the surrounding `管仲/管夷吾` example.

The previous Gold bytes are identified by SHA256 in the human authority and
reviewed delta artifacts. The other 24 records are byte/semantically
unchanged. The authority is human review, not model agreement, and has no
canonical write-back authority.

## Offline re-evaluation

The A2OR semantic records and projections are read as immutable inputs. Against
the pre-promotion Gold, the frozen A2OR result is `22/26`. Against the
promoted Gold it is `24/26` (`92.31%`), with `6/6` reviewed role cases and
`18/20` challenge cases correct. Resolution coverage, provenance, and frozen
identity preservation remain `26/26`.

The two remaining wrong records are `康伯` and `文度` in
`09-pinzao-063`. Both exact targets and Gold labels align, provider records are
valid, identity is preserved, and no target ambiguity remains. Both are
high-confidence instances of the same generic boundary error:
`reference_to_participant_overreach`. The overall pilot score is adequate, but
the single historian is not fully qualified because this systematic residual
family remains.

## Prospective selection integrity

The historical selector remains unchanged for provenance. Future semantic
targets must be pinned by `mention_id`, `source_evidence_id`, `source_start`,
`source_end`, and `surface`. `story_id + surface + source_evidence_id` is not
sufficient when repeated or nested occurrences are possible. Python may verify
the exact occurrence identity and reject unresolved ambiguity; it must not infer
semantic function from offsets.

## Decision

The next controlled experiment is `SFH2.2-A2OV`: test an independent semantic
reviewer against the clean residual set. A2OSP does not start that stage, a
provider, or the 188-Story production run.

Machine-readable records are in
`data/generated/sfh2-a2osp/`, with human authority in
`data/annotation/sfh2-a2osp-human-semantic-authority.json`.
