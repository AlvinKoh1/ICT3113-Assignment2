# JMeter test plans

## Before your first run

1. **JMeter 5.5 or newer.** `Open Model Thread Group` was added in 5.5. Check
   with `jmeter --version`.
2. **Open `triage_load_test.jmx` in the JMeter GUI once** and confirm both thread
   groups load as *Open Model Thread Group*. This file is hand-written; JMeter's
   XML serialisation shifts slightly between versions, and the GUI is the
   authoritative check. If an element fails to load, recreate it in the GUI and
   re-save — do not run a plan you have not seen load cleanly.
3. **Generate the feed files** (on the load generator machine):
   ```
   python3 tools/prepare_jmeter_data.py
   ```
   This is not optional. Narratives contain commas, quotes and embedded
   newlines; JMeter's CSV Data Set Config is line-based and would silently
   mangle them.

## Why open-loop

The brief: *"Closed-loop traffic self-throttles when the server slows down and
hides queue buildup. Results from closed-loop tests will not be accepted as
evidence against throughput or latency requirements."*

A normal Thread Group with N threads is closed-loop: each thread waits for a
response before sending again, so when the service slows down, offered load
drops with it and you never see the queue grow. Open Model Thread Group issues
arrivals on a schedule regardless of whether previous requests have returned —
which is how the client's complaint intake actually behaves.

`rate(0.5/sec) random_arrivals(10 min)` = Poisson arrivals at 0.5 req/s for ten
minutes. Poisson, not evenly spaced, because real intake is bursty and evenly
spaced arrivals understate queueing.

## Running

```bash
cd jmeter
./run_matrix.sh 192.168.1.10 llama3.2:1b "0.25 0.5 1.0 2.0"
```

Parameters (all `-J` overridable):

| Property | Default | Meaning |
|---|---|---|
| `host` / `port` | `192.168.1.10` / `8000` | the service, **on another machine** |
| `ticketRate` | `0.5` | POST /tickets arrivals per second |
| `searchRate` | `0.1` | GET /search arrivals per second |
| `durationMin` | `10` | run length |
| `seed` | `1` | arrival-process seed; the script uses the run number |
| `jtl` | `../results/jtl/run.jtl` | raw results |

Pick your rates from your workload model, not from this table. Include at least
one rate above your expected peak so the curve shows where it bends.

## Keep-alive is off

`Connection: close` and `use_keepalive=false`, so every request pays a fresh
connection. That matches an intake that posts one ticket per event, and it stops
connection reuse from masking accept-queue behaviour under overload. If you
change this, say so on Slide 8 — it materially changes the numbers.

## After every run

```bash
python3 tools/analyze_jtl.py results/jtl/<model>_rate<R>_run*.jtl \
    --config-name "<model> @ <R> req/s"
python3 tools/reconcile.py --jtl results/jtl/<one run>.jtl \
    --log results/logs/requests.jsonl --run-id <TAG>
```

Commit the `.jtl` files. They are the evidence base for Slide 9.

## Stress test

`run_matrix.sh` is for the load tests. For the stress test, drive one model up
in steps until something breaks, and define "breaks" in advance — for example:
p99 exceeds 2× your requirement, error rate exceeds 1%, or achieved throughput
stops rising as offered load rises. Use the same plan with a rising `ticketRate`
and a shorter `durationMin`, and record the rate at which your stated failure
condition first holds. Say what the failure *was*: connection refused at the
accept queue, Ollama OOM, request timeout, or unbounded latency growth.
