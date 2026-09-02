# WP1A — Frozen/Current Boundary Audit

## Conclusion

Decision: NO_MIGRATION_NEEDED.

WP1 is a small, tracked sample/projection with historical provenance. It is
also an input to current build-time projections, especially the current SC1
builder. The two isolated current rebuilds were deterministic and had exactly
the same parsed JSON content as the committed WP1 bundle. They differed only
in object-key insertion order. There is no material frozen/current semantic
split requiring a WPM migration at this baseline.

The literal bytes are not currently identical:

| artifact | committed SHA256 | isolated rebuild A/B SHA256 |
| --- | --- | --- |
| data/derived/wp1-site.json | 2f7f9de12a46649d8719efb1dffe814a5e7e8c4c67b8452f4c4452dc70dc37b4 | 0f0133d15cf69cda172b50f4db29e6a045441b4ff488b08acbd9d5f9b7baf6f6 |
| site/src/generated/wp1-site.json | 2f7f9de12a46649d8719efb1dffe814a5e7e8c4c67b8452f4c4452dc70dc37b4 | 0f0133d15cf69cda172b50f4db29e6a045441b4ff488b08acbd9d5f9b7baf6f6 |

Rebuild A equals rebuild B, while neither equals the committed bytes. The
semantic comparison found zero record or field changes. The only difference is
the insertion order of keys in stories[0].reading; both generated copies show
the same order-only change.

## Scope and method

The audit was performed from baseline
9f5d7d17dc4c4aaea8610fb52f72ded1323bbcf9 without running a builder in the
main worktree. scripts/build_wp1_sample.py was run once in each of two
disposable clones. Both clones reported:

~~~
built WP1 sample: 06-yaliang-019; 7 people; 8 mentions
~~~

Each clone changed only:

~~~
data/derived/wp1-site.json
site/src/generated/wp1-site.json
~~~

scripts/validate_wp1.py --mode portable passed in both clones. The current
input files and the two observed R3B builder side effects were byte-identical
before and after each rebuild.

The normalized semantic bundle contains:

| section | count |
| --- | ---: |
| stories | 1 |
| people | 7 |
| mentions | 8 |
| relations | 7 |
| eras | 1 |
| evidence | 394 |
| sources | 2 |

The canonical sorted-content SHA256 of the committed and rebuilt JSON is
2918d3c84a0cec43210c7b92d74036589d7a8da3f8f3c41ec030fdede34c4abc.
There are no added, removed, or changed records, and no identity, alias,
story, relation, source-registration, or provenance-value changes.

The key order difference is:

~~~
committed:
entry_id, status, punctuation_record_id, base_canonical_entry_sha256,
conversion, main_text, annotations, labels, person_display, mention_display,
source_display, relation_display, evidence_display, display_overrides

rebuilt:
entry_id, status, punctuation_record_id, base_canonical_entry_sha256,
conversion, main_text, annotations, mention_display, display_overrides,
labels, person_display, source_display, relation_display, evidence_display
~~~

This is classified as ORDER_ONLY, not a semantic delta.

## Artifact and dependency boundary

The WP1 set consists of the six reviewed annotation inputs, registered
evidence and source inputs, the milestone manifest, and the two generated
bundle copies:

| path | role | current use |
| --- | --- | --- |
| data/annotation/wp1-eras.json | reviewed WP1 input | WP1 validation |
| data/annotation/wp1-mentions.json | reviewed WP1 input | WP1 validation |
| data/annotation/wp1-people.json | reviewed WP1 input | WP1 validation |
| data/annotation/wp1-punctuation.json | shared reviewed reading input | current reading, story-chain, HNG/HDB, expansion, and SC1 builders |
| data/annotation/wp1-relations.json | shared reviewed relation input | current graph, expansion, and SC1 builders |
| data/annotation/wp1-stories.json | reviewed WP1 input | WP1 validation |
| data/evidence/wp1-evidence.json | registered evidence input | current SC1, graph, HNG0, person/story, and expansion builders |
| data/sources/wp1-sources.json | registered source input | current expansion and selection paths |
| data/manifest/milestone-1.json | milestone provenance | WP1 validation/provenance |
| data/derived/wp1-site.json | generated WP1 sample bundle | current SC1/person-story inputs and validation |
| site/src/generated/wp1-site.json | generated mirror | bundle-pair validation/legacy fixture checks |

The builder also writes
data/derived/person-relations-r3b.json and
docs/person-relation-review-r3b.md. They were observed as unchanged side
effects in both isolated rebuilds and are not WP1 bundle contents.

The production frontend does not directly import WP1. site/src/data.ts imports
site/src/generated/sc1-current-site.json. WP1 remains a current build-time
input because scripts/build_sc1_frontend_data.py reads the WP1 bundle as its
preserved sample/base projection, and scripts/build_person_story_index.py also
reads it. This is an algorithm/build dependency, not a direct published WP1
runtime dependency.

The current Pages workflow still runs build_wp1_sample.py and validates the
result before building SC1 current. That rebuild is not independently needed
by the frontend, but the current SC1 build still needs the WP1 bundle present.
The workflow step can therefore be considered stale/redundant as a separate
publication step, while removing it requires a later compatibility cleanup.
It currently can mutate the two tracked WP1 bundle copies through the
order-only serialization drift observed here.

## Historical boundary

The wp1-baseline tag at 26c309f and Git history preserve earlier WP1 versions.
The bundle history includes the baseline and later sample expansion commits
through 06b5220. Current repository references to an exact WP1 hash were found
only in:

* data/derived/large-frozen-payload-audit-c2.json
* data/derived/git-object-storage-audit-c2-1.json

Those are provenance/storage observations, not active builder or identity
contracts. data/derived/repository-retirement-inventory-c1.json records a
protected path scope, not an exact WP1 byte hash. Thus the historical
dependency is recoverable through Git/tag provenance, but current code does
not have to reproduce every historical WP1 version byte-for-byte.

The first generic source of the current order-only drift is commit
3c7dd31d77e0f01abc137f444dcee99a867f867f, “Implement D1.1 — Runtime Display
Map Deduplication”. Its scripts/reading_layers.py change constructs shared
display fields with dict.update, which changes insertion order without
changing values. The latest WP1 bundle content change is 06b5220 (“R3 + S1.1
— person ID correction”); no reviewed identity or alias delta was found
between the committed and current isolated rebuild.

## Answers to the boundary questions

1. The production frontend directly consuming WP1: No. It consumes SC1
   current.
2. SC1 current consuming WP1 at build time: Yes.
3. A current algorithm consuming WP1: Yes, including the current SC1 and
   person/story projection paths.
4. Pages needing to rebuild WP1: Not independently for frontend publication;
   current workflow does so and current SC1 requires the bundle as an input.
5. WP1 being only a historical sample/prototype: No. Its annotations and
   evidence are still shared current inputs, although the generated sample is
   not a direct runtime artifact.
6. WP1 still part of the current runtime contract: Indirectly at build time,
   not as a frontend-loaded runtime bundle.

## Safety and validation

The following were verified without mutating the main worktree:

* git diff --check: pass.
* WP1 isolated rebuild A/B: deterministic.
* WP1 portable validator: pass in both disposable rebuilds.
* npm run test:current: pass, 557 tests.
* SC1 frozen validator: pass.
* SC1 current validator: pass in portable mode.
* C3 growth guard: pass with no new policy violations.
* main worktree builders were not run.
* protected SC1 frozen/current hashes remained:
  cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8 and
  b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a.

The requested semantic-delta file was not created because the semantic delta
count is zero. The machine-readable audit is
data/derived/wp1-boundary-audit.json.

## Recommended next step

Do not implement WPM. Preserve the WP1 baseline tag and Git history. A future
small contract-cleanup task may either stabilize WP1 serialization order or
stop Pages from rebuilding the research-side WP1 pair when only SC1 current is
published. That cleanup should not change WP1 semantic inputs or introduce a
new frozen/current namespace unless a genuine semantic divergence or exact
historical WP1 hash contract is later discovered.
