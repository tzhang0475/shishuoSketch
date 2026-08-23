# SRM0.4C transport recovery

SRM0.4C resumes only the four SRM0.4B Stories whose live request ended at the
transport boundary: `19-xianyuan-010`, `01-dexing-040`, `09-pinzao-038`, and
`33-youhui-012`. `25-paidiao-007` and `02-yanyu-053` are read-only preserved
results and are never rerun by this stage.

The runner performs one authenticated preflight before touching continuation
execution. Live mode must therefore be run with the Codex network permission
approved. A failed preflight exits as `live_network_unavailable`; it is not a
Story protocol or semantic finding.

`scripts/srm0_4c_transport.py` uses a persistent HTTP session when the local
`requests` runtime is available and falls back to the existing standard
library client otherwise. Requests use a 15-second connect timeout and
180-second read timeout. A call may have its original request plus one retry,
and only transport failures (TLS/connection/timeout/transient 5xx) are
retryable. HTTP authentication/rate-limit failures and model protocol or
semantic failures are not retried.

Old `round-*-input.json` and `round-*-output.json` files are immutable. New
attempts are stored under each run's `continuation/attempts/`; the selected
response and Python projection are stored under `continuation/`. The
continuation manifest hashes the preserved old round artifacts. Batch
question-level metrics and transport metrics are reported separately in
`data/generated/srm0/srm0-4b-live-summary.json`.

Fixture artifacts remain under the SRM0.4B fixture namespace and are never
included in live metrics.
