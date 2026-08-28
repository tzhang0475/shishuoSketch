# HGE1 A+B coverage diagnosis

The immutable growth series now contains `baseline → HGE1-WA → HGE1-WB`.
Wave-A scalar values are carried forward unchanged; Wave-B values and marginal
derivatives are appended by deterministic Python projection.

Across the two candidate-only waves, Stories increased from 143 to 187 and
candidate Persons from 13 to 57.  Existing Persons reached by the new waves
remained zero in both runs, while candidate Person–Story links increased by 44
and safe graph edges increased by 44.  The largest pre-existing component
remained 342; the additional candidate observations created separate small
components rather than densifying the known graph.  Relation candidates still
grew (27 in Wave A and 34 in Wave B), but unresolved endpoints prevent those
observations from being treated as existing-node graph edges.

The current provisional diagnosis is:

**continuing_node_expansion**

That diagnosis is intentionally limited.  It says only that the observed
candidate-node yield is still positive and that these two waves do not show
existing-node densification.  It does not estimate corpus saturation.  Wave B
had a provider interruption during 33 Temporal calls, so its temporal metrics
must be treated as incomplete-live diagnostics and the pending units are
preserved in the run artifact.

The adaptive channel comparison shows relation-rich and underrepresented
exploitation with the highest relation-observation yield per Story, while all
channels produced one candidate Person target per Story and one review item per
Story.  Random control did not reveal a materially different node yield in this
small sample.  There is therefore not enough evidence to abandon coverage, but
the next controlled decision should favor a mixed coverage/relation-rich wave
after HDA2 review has clarified identity endpoints.  No Wave C is started by
this artifact.
