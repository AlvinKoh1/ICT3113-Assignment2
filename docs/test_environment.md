# Test Environment — ICT3113 Group P2-9

> **Assignment 2:** this page describes the Assignment 1 machines. For A2, **Machine A changed** (the i9-10900K below was no longer available): it is now an AMD Ryzen 7 7700 (8C/16T, 32 GB) running the same Ollama 0.5.7 container (4 CPUs, 8 GiB), settings and model digests. Machine B is unchanged. Side-by-side comparison and consequences: `docs/a2/machine_change.md`; machine facts: `docs/a2/machine_a2.json`; recorded settings per run: `results/a2/env/preflight_*.txt`.

Slide 7. Fill from the actual machines. Commands to get each figure are given.

---

## Machines

> The load generator **must** be on a different machine from the service and
> Ollama. A co-hosted load generator steals CPU from the service and produces
> latency numbers that are fiction. State plainly that they were separate.

### M1 — Service + Ollama (system under test)

| Property | Value | How to get it |
|---|---|---|
| Make / model | Custom-built desktop (Irfan's PC), MSI MPG Z490 GAMING PLUS (MS-7C75) motherboard | `Win32_ComputerSystem`, `Win32_BaseBoard` |
| CPU model | Intel Core i9-10900K @ 3.70 GHz (Comet Lake, AVX2) | `lscpu \| grep "Model name"` · macOS: `sysctl -n machdep.cpu.brand_string` |
| Physical cores / threads | 10 cores / 20 threads (1 socket); all 20 visible inside WSL | `lscpu \| grep -E "^CPU\(s\)\|Thread"` |
| Base / boost clock | 3.70 GHz base (Windows reports 3,696 MHz); max turbo 5.3 GHz per Intel's specification, not measured under load | `lscpu` |
| RAM | Host: 48 GB DDR4-2667 (3 × 16 GB; an odd number of DIMMs, so not fully dual-channel). WSL 2 VM capped at 12 GB in `%UserProfile%\.wslconfig` (about 11.7 GiB visible). Ollama container capped at 8 GB (`OLLAMA_MEM=8g`) | `free -h` · macOS: `sysctl hw.memsize` |
| Swap configured | WSL 2 swap partition, 3 GiB, 0 B used at setup. The largest model (`qwen2.5:7b`, 4.68 GB) fits inside the 8 GB container cap | `swapon --show` — **if the model swaps, the numbers are void** |
| Disk | Samsung SSD 970 EVO Plus 2 TB, NVMe (holds C:, WSL and Docker data). Second disk, Samsung 870 QVO 2 TB SATA SSD, not used | SSD/NVMe, model |
| OS + kernel | Windows 11 Pro 10.0.26200 (build 26200.9457), WSL 3.0.1, Ubuntu 24.04.5 LTS, kernel `6.18.40.1-microsoft-standard-WSL2` x86_64 | `uname -a` |
| Docker version | Docker Desktop 4.94.0 (WSL 2 backend, per-user install), Docker Engine 29.8.2, Compose v5.5.1; default runtime `runc` | `docker --version` |
| Ollama version | 0.5.7, image `ollama/ollama:0.5.7` (reports `0.5.7-0-ga420a45-dirty`) | `ollama --version` |
| GPU present | NVIDIA GeForce RTX 3090 (24 GB) is installed but **not used**. No GPU is passed to any container. See [GPU exclusion](#gpu-exclusion) for how this was confirmed | **must be none in use** — state how you confirmed |
| CPU limit applied to Ollama | `OLLAMA_CPUS=4`: a CFS CPU quota of 4 CPUs (`NanoCpus=4000000000`), not pinned to specific cores. Observed at about 395 % CPU in `docker stats` while classifying | `OLLAMA_CPUS` in `.env` |
| Ollama runner threads | `--threads 10` (Ollama's default: the host's physical core count), so 10 threads share a 4-CPU quota. Left as-is in the baseline (no pre-optimisation) | `docker logs triage-ollama \| grep -- --threads` |
| `OLLAMA_NUM_PARALLEL` | Not set (`0` = auto). Ollama chose `--parallel 4` (runner `--ctx-size 8192` = 4 slots × 2048) | `docker logs triage-ollama \| grep -i parallel` |
| `OLLAMA_MAX_LOADED_MODELS` | Not set (`0` = auto). `OLLAMA_KEEP_ALIVE=30m` | same |
| Power / thermal profile | Desktop on mains power (no battery). Windows power plan "Balanced". Sleep and hibernate on AC disabled on 7 Oct before the tests (`powercfg /change standby-timeout-ac 0`, `hibernate-timeout-ac 0`); Windows Update paused for 1 week | laptop on battery throttles; say so if applicable |

### M2 — Load generator

| Property | Value |
|---|---|
| Make / model | Lenovo laptop (Uwais's), a separate machine from M1 |
| CPU / cores | AMD Ryzen 7 8845HS, 8 cores / 16 threads |
| RAM | 16 GB (15,677 MB reported by Windows) |
| OS | Windows 11 Home 10.0.26200; JMeter run from Git Bash |
| Java version | Oracle Java SE 21.0.5 LTS (HotSpot 64-bit), `JAVA_HOME=C:\Program Files\Java\jdk-21` |
| JMeter version | Apache JMeter 5.6.3 (≥ 5.5, so Open Model Thread Group is available) |
| JMeter heap | Default `-Xms1g -Xmx1g` (`HEAP` not overridden) |

### Network between them

| Property | Value | How |
|---|---|---|
| Link | Not a LAN: the two machines are in different homes, joined by a **Tailscale** (WireGuard) overlay across two home broadband connections. Both machines on **wired Ethernet** to their home routers for all reported runs (Machine B: Realtek USB GbE adapter, 1 Gbps; Wi-Fi off). No VPN other than Tailscale (ProtonVPN on Machine A was quit) | Machine A reached at Tailscale IP `100.88.74.36`; adapters from `Get-NetAdapter` |
| Path | **Direct** peer-to-peer, not relayed through a Tailscale DERP server (`tailscale ping` → `pong ... via <public ip>:<port> in 12ms`, 8 Oct) | `tailscale ping 100.88.74.36` |
| RTT | 100 packets, **0 % loss**; min **7** / avg **8.8** / max **17** ms, sd 1.7 ms, p95 12 ms (Windows `ping -n 100` from Machine B, 7 Oct). Raw output: `results/network/ping_machineB_to_A_2026-10-07.txt` | `ping -n 100 100.88.74.36` |
| RTT during the load tests | TCP connect time in the `.jtl` files, 3,166 successful requests over 36 runs (excluding the dropped run): median **10** ms, p95 13 ms, p99 44 ms, max 1,024 ms | `Connect` column of `results/jtl/*.jtl` |
| Bandwidth | Not measured (`iperf3` not available). Requests are small: ≤ 2,000-character tickets, < 1 kB responses, at most ~0.27 requests/s | |
| Other traffic on the link | Home broadband on both sides, shared with other household use that we could not control | |
| Outages | One: ~2 min (04:00:30–04:02:38 SGT, 8 Oct) during `llama3.2_1b_rate0.0667_run3`. 38 requests failed with `ConnectTimeoutException` and never reached the service. That run was redone as `run3b`; see `results/logs/reconcile_notes.md` | `.jtl` timestamps |

> If the link is Wi-Fi, say so. Wi-Fi jitter lands directly in your p99 and can
> be mistaken for server-side queueing. `reconcile.py` prints the gap between
> client and server latency — that gap is your network, and it belongs on
> Slide 7.

## GPU exclusion

The client permits CPU only. Evidence:

- `docker-compose.yml` maps no GPU device and sets no `--gpus` flag. `docker inspect triage-ollama` shows `DeviceRequests=null` and `Runtime=runc`, not the `nvidia` runtime that Docker Desktop also ships.
- `docker logs triage-ollama` reports `msg="no compatible GPUs were discovered"` and `msg="inference compute" id=0 library=cpu variant=avx2`. On every model load it reports `msg="offload to cpu" ... layers.offload=0`, meaning no model layer is placed on a GPU.
- `nvidia-smi` (7 Oct 2026, during three back-to-back `llama3.2:1b` requests): no Ollama or Docker VM process in the GPU process list. GPU memory stayed flat at about 1,375 MiB and utilisation stayed at the idle desktop level (about 31 %), while `docker stats` showed the Ollama container at about 395 % CPU.
- The Ollama Windows app is not installed. Ollama runs only from our compose file. Docker Desktop's own "Docker Model Runner" is switched off.

## Threats to validity

Be honest here; it is marked.

- **Model warm-up.** First request after load pays model load time. We discard
  3 warm-up requests per model (P5, `tools/warmup.py`, non-golden rows, tagged
  `run_id=warmup` in the log) and set `OLLAMA_KEEP_ALIVE=30m` so the model is not
  evicted mid-run. For the load tests, `tools/overnight_switch.sh` warms each
  model before Machine B starts and keeps it loaded until the first run arrives.
- **Thermal throttling.** Not measured directly: CPU temperature and clock speed
  were not logged on Machine A. Indirect check from the service log
  (`results/logs/requests.jsonl`), POST /tickets p50 for runs 1 / 2 / 3 of the
  overnight matrix, which ran back to back:
  - `qwen2.5:0.5b`: 3.1 / 2.4 / 1.9 s at 1/min; 2.8 / 3.3 / 2.7 s at 2/min
  - `llama3.2:1b`: 5.5 / 5.7 / 5.5 s at 1/min; 7.3 / 7.2 / 7.6 s at 2/min
  - `llama3.2:3b`: 26.7 / 26.1 / 30.9 s at 1/min; 38.2 / 45.9 / 35.4 s at 2/min
  - `qwen2.5:7b`: 50.9 / 65.8 / 98.6 s at 1/min

  0.5B to 3B show no steady slowdown from run 1 to run 3. 7B's rise coincides
  with backlog carried between runs (4 tickets from run 1 were still in flight
  when run 2 started), so thermal effects cannot be ruled out for 7B. These are
  service-log figures; the reported ones come from the `.jtl` files.
- **Shared machine.** Machine A is Irfan's everyday desktop. At setup on 7 Oct, other apps were running: Chrome, Spotify, EA Desktop, Riot Vanguard (anti-cheat, runs at boot), Razer App Engine, ProtonVPN, VS Code and the Claude app. They use some CPU and, through the desktop, about 31 % of the GPU.
  - **Load tests (from 8 Oct 2026, ~00:00 SGT):** ProtonVPN disconnected and quit (Tailscale stays on; it carries the test traffic). Closed: Chrome, Spotify, EA Desktop (and its helper processes), Razer App Engine, Riot Client, Windows Settings. Still running because they need admin rights to stop: EA Background Service, Razer Elevation Service and Razer Game Manager Service (idle background services), and Riot Vanguard's kernel driver `vgk` (starts at boot; cannot be stopped without a reboot). VS Code, the Claude app, Docker Desktop, Tailscale and a terminal window for `tools/overnight_switch.sh` were open. Windows Update paused for 1 week; sleep and hibernate on AC disabled.
  - **Accuracy tests (8 Oct 2026, 09:06–12:22 SGT, `tools/accuracy_all.sh`):** same setup, except Chrome had been reopened: it was running when the test started (09:05) and was closed by about 12:30; when exactly is not recorded. Single-request latencies from this run may include some contention from it.
  - **Docker Desktop stopped unexpectedly at about 08:58 SGT on 8 Oct**, between tests: the load re-run had finished at 08:52 and the accuracy test had not started. Nobody closed it; Windows Error Reporting logged a burst of events at 08:58:35. It was restarted at 09:06; both volumes (models, ticket store) were intact, and the accuracy script's first launch at 09:04:56 aborted safely because the Docker daemon was unreachable (`model_switch.log`). No reported run was affected.
- **Dataset cap.** Narratives are capped at 2000 chars; real complaints are
  longer, so our latency figures are optimistic.
- **Single host.** The client would deploy on server-class hardware with more
  cores and likely more Ollama replicas. §Scaling below.
- **SQLite growth.** `GET /search` does a full scan. Search latency at 200 stored
  tickets is not search latency at 200,000. **Not measured at a realistic table
  size.** Each model's load matrix started with an empty ticket store
  (`tools/overnight_switch.sh`) and held at most 210 tickets by its last run
  (3 warm-ups + 207 tickets). The search figures on Slide 9 hold for that table
  size only.

## Scaling to the client's deployment

How do results here map to production?

- **What we measured is one 4-CPU Ollama instance** (`OLLAMA_CPUS=4`) on a
  10-core desktop CPU (i9-10900K, up to 5.3 GHz boost). Its capacity is
  μ ≈ 60 / S tickets/min, with S the single-request p50 from the sequential
  accuracy run (`results/accuracy/summary_<model>.json`): 0.5B 2.5 s → 24.2/min,
  1B 5.7 s → 10.5/min, 3B 16.2 s → 3.7/min, 7B 34.1 s → 1.8/min.
- **The client's servers are not specified** beyond "commodity CPU servers with
  no GPUs" (brief), so we give no scaling factor. Throughput should scale with
  the number of such instances (replicas behind a load balancer), each with its
  own cores and memory. Server cores are usually clocked lower than a desktop
  CPU's boost, so S per instance may be higher there. This is an assumption,
  not a measurement.
- **Latency** of one request does not shrink by adding replicas; it depends on
  the per-core speed and the cores given to one instance.
- **What would need re-measuring on client hardware:** S for the chosen model on
  one client server (sequential, as in Test C), then the stress test (Test D)
  on that server to find its limit. Divide the client's required rate by the
  measured per-instance limit to size the deployment.
