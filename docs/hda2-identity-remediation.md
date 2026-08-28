# HDA2 — Identity remediation

HDA2 is an additive, candidate-only follow-up to the HDA1 audit.  It freezes a
risk-ranked slice of HDA1 findings, builds blind remediation packets, asks the
independent verifier to inspect only the supplied source evidence, and then
grounds any proposed alternative in Python.  The HDA1 verdict is retained for
audit provenance but is not presented to the verifier as an answer.

The frozen run selected 32 of 543 flagged HDA1 claims.  The live provider pass
completed 32 remediation calls with no transport retry or provider failure:

| outcome | count |
| --- | ---: |
| retained existing claim | 24 |
| suppressed existing claim | 2 |
| alternative proposed | 2 |
| alternative grounded to one existing Person | 2 |
| insufficient / invalid provider result | 4 |

The resulting overlay has 24 retain actions, two suppress actions, one
replacement candidate action, and five human-review actions.  It remains
candidate-only (`canonical_write_back: false`); the canonical Person registry,
facts, and HDB2-F artifacts are not rewritten.  A literal provider `"null"`
alternative is normalized to absence in the offline projection layer, so it
cannot become an identity surface.

High-risk remediation includes the source-local contradiction around `仲文`,
which is not reintroduced as a `朱伺` profile form, and the independently
grounded `王蒙` alternative mapping.  The ungrounded alternatives `殷仲文`
and `桓謙` remain reviewable rather than being promoted to production Persons.

The overlay is an input for later human review only.  HGE1-WB records its
effect separately and does not use the overlay as a shortcut for unrelated
research Stories.
