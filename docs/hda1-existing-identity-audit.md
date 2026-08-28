# HDA1 — Existing identity claim audit

HDA1 is an isolated, candidate-only audit of identity claims already present
in the repository. It does not repair, delete, or promote a Person identity.
The audit packet is blind to the prior status, confidence, reviewer decision,
PSL score, and resolved Person ID; the verifier sees only the claimed Person
label, target surface, source pointers, exact span, and short context.

## Audit universe

The frozen input contains 577 deduplicated claims:

| source | claims |
| --- | ---: |
| HDB2-F identity-claim integrity audit | 266 |
| registered alias witnesses | 224 |
| Person-registry source evidence | 87 |

The claim universe covers 75 canonical Persons and 68 candidate identities
represented in HDB1/HDB2 research artifacts. The candidate identities remain
candidate-only. Every packet carries an evidence reference and the exact
source text used to test it; a non-contiguous witness is retained as an
evidence limitation rather than repaired.

The frozen input hashes are recorded in
`data/generated/hda1/manifest.json`. The HDA1 snapshot was prepared before the
HGE1-WA baseline and selection.

## Live verification result

The configured `deepseek-v4-flash` provider was reachable for preflight and
the audit began. The provider then became connection-refused for most later
requests. The run is therefore preserved as a partial live audit, not as a
complete claim verdict:

| result | count |
| --- | ---: |
| support | 35 |
| contradict | 2 |
| ambiguous | 0 |
| insufficient evidence | 24 |
| validated responses | 61 |
| fail-closed provider/parse results | 516 |
| claims lacking a contiguous adequate evidence anchor | 4 |

Among the 61 validated responses, support was 57.377%, contradiction 3.279%,
ambiguity 0%, and insufficient evidence 39.344%. Across all 577 claims,
including the fail-closed provider results, the corresponding rates were
6.066%, 0.347%, 0%, and 4.159%; the remainder is explicitly unavailable
provider output rather than a verdict.

The two validated contradictions identify a claim for `謙` as 卞範之 where
the annotation names 桓謙, and a `王蒙`/王濛 catalogue claim where the
supplied annotation identifies 桓伊's childhood name. These are review
findings, not automatic corrections. The known `仲文`/朱伺 case remains in
the audited claim and review artifacts, but its later request was not
validated after provider loss; it must not be interpreted as support.

Operationally the run used 1,097 API attempts including 520 permitted
transport/parse retries, 102,542 billed response tokens, and no canonical
write. Raw responses and the fail-closed result for every claim are under
`data/generated/hda1/live/hda1-final-live-network/`.

## Review and limitations

Contradictions are ranked first, then ambiguous and inadequate-evidence
claims, with high-frequency surfaces and high-degree Persons prioritized.
Invalid provider output never becomes a positive identity assertion. HDA1
does not infer historical truth from surface equality, co-occurrence, or a
title alone. A complete audit requires a stable provider run for the 516
claims whose live responses were unavailable; no offline substitute is
treated as an LLM verdict.
