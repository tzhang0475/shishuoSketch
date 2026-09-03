# SFH2.2-A2O — Occurrence Semantics Qualification Handoff

This is a design handoff only. A2O is not implemented by SFH2.2-A2GR.

The A2GR identity qualification shows that identity and occurrence semantics
must be evaluated separately. In the frozen regression evidence, `滔` resolves
to 伏滔 and `嘏` resolves to 傅嘏, but the model assigns the annotation
narratives a main-scene `scene_participant` role rather than the reviewed
`annotation_person` role. `王師` remains a collective entity while role
selection can drift between collective and generic scene-reference values.

The next hypothesis should test decomposing the current single
`occurrence_role` field into two orthogonal semantic axes:

* `evidence_layer`: `main_text`, `liu_annotation`, `citation`,
  `other_commentary`, and future evidence layers as needed;
* `narrative_function`: `participant`, `reference`, `speaker`, `addressee`,
  `collective_reference`, `person_attribute`, `source_author`,
  `historical_exemplum`, and other reviewed functions.

This note does not finalize that ontology, add lexical rules, or prescribe
Python identity behavior. The A2O experiment should let the LLM interpret both
axes, while Python validates only schema, evidence provenance, logical
compatibility, and storage permissions.
