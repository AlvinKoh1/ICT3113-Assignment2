# Evidence

Everything in this directory is **evidence** and must be committed.

- `jtl/` — raw JMeter result files, one per run, named `<model>_rate<R>_run<N>.jtl`
- `logs/` — `requests.jsonl` from the service (one JSON object per request), plus
  reconciliation output and resource snapshots
- `accuracy/` — `predictions_<model>.csv` and `summary_<model>.json`

> "Every number in your final document must reconcile with them; a number that
> cannot be traced to a log entry is treated as unsupported, and you may be asked
> to produce and explain your logs."

`requests.jsonl` accumulates across runs. Set `RUN_ID` on the service before each
run so entries can be separated afterwards with
`tools/reconcile.py --run-id <tag>`, or archive and truncate the file between
runs — but never delete a log for a run you intend to report.
