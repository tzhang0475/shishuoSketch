# Portable CI contract

GitHub Pages runs the repository test suite with:

```text
GITHUB_PAGES=true
WP1_PROVENANCE_MODE=portable
SHISHUO_SKIP_SOURCE_PAYLOAD_TESTS=1
```

Portable CI validates committed canonical data, provenance metadata, derived
artifacts, deterministic builders, frontend projections, typechecking, the
production build, and published-artifact scope.

The default test command is the registry-driven `npm run test:current` (also
available as `npm test`). Historical reproducibility, source-payload, and live
network contracts are opt-in through their separate suite commands.

Live-provider experiments are not part of the normal Pages/portable command.
They are explicitly opt-in; when run in an environment without network
access, their preflight records the transport classification and the
offline/replay validator remains the CI path.  A reachable provider's schema
or transport failure is still reported and is never converted into a
successful semantic result.

Tests that rebuild artifacts from ignored raw source payloads may skip only
when all three conditions hold:

1. portable provenance mode is active;
2. source-payload skipping is explicitly enabled; and
3. the named physical payload is actually absent.

The skip is test-local and reports the exact missing path.  Full local mode,
when the payload exists, continues to execute the rebuild and byte-stability
checks.  Validators, committed-artifact checks, provenance locks, schema
checks, semantic consistency checks, and canonical-data protection checks
never use this skip.

HDB1 W1/W2 selection rebuilds additionally use their frozen versioned
selection contract.  Later HNG2 files may extend the live exclusion scanner,
but cannot change the historical HDB1 selection serializer or its embedded
exclusion snapshot.
