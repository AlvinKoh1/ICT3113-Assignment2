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
| Power / thermal profile | Desktop on mains power (no battery). Windows power plan "Balanced". Sleep and hibernate on AC to be disabled before test runs (handoff §6 step 7) | laptop on battery throttles; say so if applicable |

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
- **Thermal throttling.** <Did you check? Consumer hardware sustaining 100% CPU
  for 10 minutes will clock down, and run 3 may be slower than run 1 for reasons
  unrelated to the system. The spread across your three runs is where this shows.>
- **Shared machine.** Machine A is Irfan's everyday desktop. At setup on 7 Oct, other apps were running: Chrome, Spotify, EA Desktop, Riot Vanguard (anti-cheat, runs at boot), Razer App Engine, ProtonVPN, VS Code and the Claude app. They use some CPU and, through the desktop, about 31 % of the GPU.
  - **Load tests (from 8 Oct 2026, ~00:00 SGT):** ProtonVPN disconnected and quit (Tailscale stays on; it carries the test traffic). Closed: Chrome, Spotify, EA Desktop (and its helper processes), Razer App Engine, Riot Client, Windows Settings. Still running because they need admin rights to stop: EA Background Service, Razer Elevation Service and Razer Game Manager Service (idle background services), and Riot Vanguard's kernel driver `vgk` (starts at boot; cannot be stopped without a reboot). VS Code, the Claude app, Docker Desktop, Tailscale and a terminal window for `tools/overnight_switch.sh` were open. Windows Update paused for 1 week; sleep and hibernate on AC disabled.
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
