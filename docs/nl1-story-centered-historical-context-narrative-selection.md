# NL1 — Story-Centered Historical Context & Narrative Selection Corpus

NL1 is a reviewed annotation milestone for deciding what historical context
may enter a future Story Sketch and what should remain outside it. It is not a
new canonical historical layer, a language model, or a narrative generator.

The pipeline is:

```text
existing Story / HR0 / HR0.1 / reviewed facts
        ↓
reviewed NarrativeContext
        ↓
NarrativeSelectionGold
        ↓
future NL1-E two-pass evaluation
```

The review spec is [nl1-narrative-review.json](../data/annotation/nl1-narrative-review.json).
The two derived corpus documents are:

- [nl1-narrative-context.json](../data/derived/nl1-narrative-context.json)
- [nl1-narrative-selection-gold.json](../data/derived/nl1-narrative-selection-gold.json)

## Pilot scope

The pilot contains 30 existing reader-ready Stories:

- all 19 reviewed HR0/HR0.1 Stories;
- 11 additional existing evidence-rich Stories selected as contrastive
  controls and narrative-type coverage: family, life-stage, retrospective,
  political, later-fate, strong-scene, and low-context controls.

The extra Stories are not a corpus expansion. They are annotation records over
existing Story IDs and existing evidence IDs. No Story, Person, Mention,
PersonStory, Relation, or HistoricalFact was added.

The selected IDs are frozen in the review spec and copied into both derived
documents. The source hashes and the protection manifest make the selection
and input boundary reproducible.

For Stories that have them, existing S1 Jianshu assertion and citation IDs are
retained in `grounded_inputs`. They are lineage and source-discovery references,
not automatic narrative claims: 26/30 pilot Stories have 122 S1 assertion IDs
and 21/30 have 107 citation IDs. NL1 does not promote those records or cited
works into canonical facts.

## NarrativeContext v0

Each Story has a reviewed `NarrativeContext` with:

- `current_scene`: source text, a short scene description, episode IDs, and
  explicit participant/reference states;
- `historical_stakes`: only context reviewed as useful for entering the scene;
- `person_states`: observed or already-reviewed state descriptions, with
  modality retained;
- `relationship_context`: story context or reviewed fact context, explicitly
  marked when it is not a new direct Relation;
- `prior_events` and `later_events`: only when the Story evidence directly
  supports the sequence;
- `key_source_spans`: compact locators and source layers, without copying a
  full source corpus;
- `uncertainties`: unresolved identity, presence, semantic, and temporal
  boundaries.

The base Story text remains the reading source. The context annotation does
not turn a derived Story date or a candidate scene projection into an answer.
Unknown and relative chronology remain unknown or relative.

## NarrativeSelectionGold v0

Every Story exposes all five narrative roles:

| Role | Meaning |
| --- | --- |
| `background` / 底色 | prior or contextual information needed to enter the scene |
| `in_scene` / 入画 | people and actions actually present in the current episode |
| `off_scene` / 画外 | directly relevant people/events mentioned but not present |
| `person_glimpse` / 人物一瞥 | a short action, phrase, or observed response |
| `resonance` / 余韵 | a later fact or later event that reflects back on the scene |

Each role contains separate candidate rows with one of:

- `selected`: may enter the future narrative projection;
- `rejected`: explicitly retained as an overreach/omission guard;
- `abstained`: no safe selection was made.

Rejected rows are deliberate. They record common failure modes such as
turning references into scene participants, converting an ambiguous title into
a global identity rule, adding exact dates that the source does not give,
turning comparative language into a global ranking, and writing generic
“historical atmosphere.” Rejection does not say that the underlying source is
false; it says that the proposed narrative use is not supported or is not
needed here.

The current derived counts are:

```text
Stories                         30
NarrativeContext records        30
role slots                      150
selected candidates              91
rejected guard candidates       150
abstained candidates             59
uncertainties                    48
```

Role distribution by Story:

```text
                 selected   abstained   rejected guards
底色/background       14          16          30
入画/in_scene         28           2          30
画外/off_scene        17          13          30
人物一瞥              28           2          30
余韵/resonance         4          26          30
```

The low `resonance` rate is intentional. NL1 does not force a later-fate
after-note onto a Story. The two comparative/title-ambiguous controls also
abstain from `person_glimpse` because their available phrase is not a safe
stand-alone character glimpse.

## Evidence and participant discipline

Every context item and every selection candidate has one or more existing
Story evidence IDs. The validator checks that each ID belongs to the selected
Story and that each source span has a relative locator.

The corpus keeps the distinctions already established by HR0/HR0.1:

```text
in-scene participant ≠ referenced person
reported subject ≠ current actor
annotation-only person ≠ hard participant
ambiguous title ≠ globally resolved identity
story context ≠ new direct Relation
```

The known NL0 boundary cases are included in the pilot: `明帝`/`温太真`,
the `谢公`/`王右军` title surfaces, retrospective `嵇康`/`阮籍` references,
political-background annotation, event context, and non-informative dates.

## Deterministic build and protection

Run:

```bash
python3 scripts/build_nl1_narrative_corpus.py
python3 scripts/validate_nl1.py
python3 -m unittest tests.test_nl1
```

The builder sorts Story IDs, evidence IDs, source layers, and all derived
collections before serialization. It emits no wall-clock fields or absolute
paths. Rebuilding from unchanged inputs is byte-identical.

The policy is explicit:

```text
canonical_data_write_back = false
canonical_fact_materialization = false
llm = false
rag = false
automatic_narrative_materialization = false
```

The protection manifest covers SC1, HR0, HR0.1, H0C facts, the X1.2R-F
extension, the NL0 Gold input, and the existing S1 Jianshu
assertion/citation artifacts. Existing historical and frontend data are
read-only for NL1.

## Recurring annotation patterns

The review shows five useful patterns for later evaluation:

1. A scene nucleus is usually safe when it follows the base text's action and
   episode order; 28/30 Stories have an `入画` selection.
2. `底色` is selective. Context is useful for political crisis, family
   arrangements, office setting, or a prior/later episode, but not as a
   generic era paragraph.
3. `画外` is where participant/reference errors are most likely. Annotation
   people and recalled/deceased figures remain outside the current scene.
4. `人物一瞥` should be a small observed phrase, not a personality profile.
5. `余韵` is rare and should be abstained from unless a later event is already
   directly present in the Story evidence.

## Unresolved issues

- Several surfaces remain without a safe canonical Person endpoint. The
  annotation keeps `person_id: null` rather than inventing an identity.
- Most Stories have unknown or relative chronology; NL1 does not manufacture
  exact dates.
- Some existing source/evidence rows remain candidate at their historical
  source-status layer. NL1's `reviewed` status means the narrative annotation
  was reviewed, not that the annotation silently upgrades the underlying
  canonical fact.
- Rejected candidates are boundary tests and should remain in future
  evaluation; deleting them would hide omission errors.

## NL1-E readiness

The corpus is ready for `NL1-E — LLM Narrative Selection Experiment` without a
schema redesign. It supports:

- context understanding from the `NarrativeContext` record;
- selection evaluation over the five role-specific candidate sets;
- omission/rejection evaluation using explicit guard rows;
- abstention evaluation where no role is safe to fill;
- evidence-grounding checks for every proposed selection.

NL1-E must consume this as a benchmark and must not write model output back to
canonical history. NL1 does not implement NL1-E, LLM calls, RAG, or automatic
narrative materialization.
