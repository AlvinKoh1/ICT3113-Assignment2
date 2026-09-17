# Test Environment — ICT3113 Group P2-9

Slide 7. Fill from the actual machines. Commands to get each figure are given.

---

## Machines

> The load generator **must** be on a different machine from the service and
> Ollama. A co-hosted load generator steals CPU from the service and produces
> latency numbers that are fiction. State plainly that they were separate.

### M1 — Service + Ollama (system under test)

| Property | Value | How to get it |
|---|---|---|
| Make / model | | |
| CPU model | | `lscpu \| grep "Model name"` · macOS: `sysctl -n machdep.cpu.brand_string` |
| Physical cores / threads | | `lscpu \| grep -E "^CPU\(s\)\|Thread"` |
| Base / boost clock | | `lscpu` |
| RAM | | `free -h` · macOS: `sysctl hw.memsize` |
| Swap configured | | `swapon --show` — **if the model swaps, the numbers are void** |
| Disk | | SSD/NVMe, model |
| OS + kernel | | `uname -a` |
| Docker version | | `docker --version` |
| Ollama version | | `ollama --version` |
| GPU present | | **must be none in use** — state how you confirmed |
| CPU limit applied to Ollama | | `OLLAMA_CPUS` in `.env` |
| `OLLAMA_NUM_PARALLEL` | | `docker logs triage-ollama \| grep -i parallel` |
| `OLLAMA_MAX_LOADED_MODELS` | | same |
| Power / thermal profile | | laptop on battery throttles; say so if applicable |

### M2 — Load generator

| Property | Value |
|---|---|
| CPU / cores | |
| RAM | |
| OS | |
| Java version | `java -version` |
| JMeter version | `jmeter --version` — **must be ≥ 5.5** for Open Model Thread Group |
| JMeter heap | `HEAP` env var |

### Network between them

| Property | Value | How |
|---|---|---|
| Link | | e.g. 1 GbE switched / shared Wi-Fi |
| RTT | | `ping -c 100 <svc>` — report min/avg/max/mdev |
| Bandwidth | | `iperf3` if available |
| Other traffic on the link | | |

> If the link is Wi-Fi, say so. Wi-Fi jitter lands directly in your p99 and can
> be mistaken for server-side queueing. `reconcile.py` prints the gap between
> client and server latency — that gap is your network, and it belongs on
> Slide 7.

## GPU exclusion

The client permits CPU only. Evidence:

- `docker-compose.yml` maps no GPU device and sets no `--gpus` flag.
- `docker logs triage-ollama` reports <the CPU-only line it prints>.
- <Any other check, e.g. `nvidia-smi` shows no process, or the host has no GPU.>

## Threats to validity

Be honest here; it is marked.

- **Model warm-up.** First request after load pays model load time. We discard
  <n> warm-up requests (P5) and set `OLLAMA_KEEP_ALIVE=30m` so the model is not
  evicted mid-run.
- **Thermal throttling.** <Did you check? Consumer hardware sustaining 100% CPU
  for 10 minutes will clock down, and run 3 may be slower than run 1 for reasons
  unrelated to the system. The spread across your three runs is where this shows.>
- **Shared machine.** <Anything else running?>
- **Dataset cap.** Narratives are capped at 2000 chars; real complaints are
  longer, so our latency figures are optimistic.
- **Single host.** The client would deploy on server-class hardware with more
  cores and likely more Ollama replicas. §Scaling below.
- **SQLite growth.** `GET /search` does a full scan. Search latency at 200 stored
  tickets is not search latency at 200,000. <Did you measure at a realistic
  table size? If not, say so — this is a real limitation of the baseline result.>

## Scaling to the client's deployment

How do results here map to production?

- **Throughput** scales roughly with total cores available to Ollama, until
  memory bandwidth saturates. Our box has __ cores; the client's assumed server
  has __. Predicted scaling factor: __×, and what makes that prediction shaky.
- **Latency** does *not* improve with more cores beyond the point where one
  request already saturates the memory bus. Single-request latency is roughly
  what the client would see per instance.
- **What would need re-measuring on client hardware:** <...>
