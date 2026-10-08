# Load test reconciliation, 8 Oct 2026 (36 runs)

Per-run outputs: `reconcile_<tag>.txt`, one section per endpoint. Each was
produced by:

```
python3 tools/reconcile.py --jtl results/jtl/<tag>.jtl --log results/logs/requests.jsonl \
    --run-id <tag> --endpoint "<endpoint>" --jtl-label "<endpoint>"
```

`--jtl-label` is required with mixed load. Without it, the playbook's command
compares every JMeter sample (tickets + searches) against the service's
`POST /tickets` lines only, so every run fails.

## Summary

| Check | Result |
|---|---|
| `GET /search`: counts, errors, client ≥ server latency | Reconciled in 35 of 36 runs. The exception is `llama3.2_1b_rate0.0667_run3` (network drop, below). |
| `POST /tickets`: request counts | Match in 35 of 36 runs, counting service lines of every status (200 + 502). The exception is the same run. |
| `POST /tickets`: error counts | Differ in the runs listed under "Drain cut-off" |
| `POST /tickets`: client ≥ server latency | Fails in every run, because Machine A's timer runs ~10 % fast (below) |

## 1. Machine A's timer runs about 10 % fast

For every `POST /tickets`, pairing each JMeter sample with its service log line
in time order gives server `latency_ms` / client `elapsed` ≈ **1.08–1.10**
(median 1.09 across all clean runs). The ratio tends to 1.10 on long requests,
where network overhead is negligible. Ollama's own `ollama_total_ms` is higher
than the client-side time by the same amount. A real queue or network delay
would make the client time longer than the server time, never shorter.

Machine B's clock is consistent: each run's schedule (600 s of arrivals +
120 s drain, timed by JMeter) took 12:00 of wall-clock time, for example
00:09:26 → 00:21:26 for `qwen2.5_0.5b_rate0.0167_run1`. Wall-clock timestamps
on the two machines agree to within ~0.1 s over a run, so only Machine A's
duration timer (`time.perf_counter()` inside the WSL 2 / Docker VM, and
Ollama's timers in the same VM) runs fast.

The 300 s Ollama timeout confirms it. Requests that hit that timeout on
Machine A took ~273 s by JMeter's clock (p50 272.9 s in
`qwen2.5_7b_rate0.0667_run1`), and 300 / 1.1 ≈ 273.

**Consequence:** report latency from the `.jtl` files (Machine B), as
`analyze_jtl.py` already does. Server-side durations in `requests.jsonl` are
inflated by ~10 %, but their ratios (e.g. prompt-eval share of
`ollama_total_ms`) are unaffected. Counts and statuses are unaffected.

## 2. Network drop in `llama3.2_1b_rate0.0667_run3`

38 requests (11 tickets, 27 searches) failed with
`ConnectTimeoutException` between **04:00:30 and 04:02:38** SGT. Requests
before and after succeeded, and the service log has no lines for the failed
ones (they never arrived). The Tailscale link between the two machines
dropped for about 2 minutes. This is not a property of the system under
test. **This run should be redone under a new run id.** Until then, it is
excluded from any reported figure.

## 3. Drain cut-off: JMeter errors the service did not see

`java.net.SocketException: Socket closed` (78 ticket requests in
`llama3.2_3b_rate0.0667_*` and all `qwen2.5_7b_*` runs). These requests were
still queued when the 120 s drain ended, so JMeter closed the sockets. The
service still finished them and logged them (status 200 or 502), so JMeter
counts more errors than the service. These are not service failures. The
queue had not cleared by the end of the run window: offered load exceeded
capacity, and these requests' latency is at least the time recorded.

## 4. Genuine service errors: 502 after 300 s

All 148 `502 Bad Gateway` responses in the service log are
`ReadTimeout: timed out` from the service's call to Ollama
(`OLLAMA_TIMEOUT_S=300`):

| Configuration | 502s |
|---|---|
| `llama3.2_3b_rate0.0667` | 1 |
| `qwen2.5_7b_rate0.0167` | 4 |
| `qwen2.5_7b_rate0.0333` | 28 |
| `qwen2.5_7b_rate0.0667` | 115 |

Requests waited in Ollama's queue longer than the service's own backend
timeout. This is a real limit of the baseline under load and belongs on
Slide 9.
