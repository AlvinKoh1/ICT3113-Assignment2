# Workload Model — ICT3113 Group P2-9

**Signed off:** Alvin (M2), 6 Oct 2026.

Slide 3. Owner: **Alvin (M2)**. Every figure is either **cited** [n] or marked
**ESTIMATE** with its method. `tools/workload_model.py` recomputes every
derived number below and draws `docs/workload.png`.

---

## 1. Client profile

- **Institution size assumed:** one large retail bank, the size of **Barclays Bank UK PLC**.
- **Basis:** Barclays publishes its complaint volume half-yearly. **70,569 complaints opened, July–December 2024** [3]. That is a real, citable volume for a single retail institution, so we don't have to invent a customer count and a complaints-per-customer rate.
- **Geography / regulator:** the client's tickets look like CFPB (US) narratives, and US data gives us the *timing* pattern (§3) [2]. The *volume* comes from a UK bank's FCA-mandated disclosure [3].
  - We assume a desk's weekday/seasonal shape is similar across the two markets.
  - Both are English-language retail banking with web/app complaint channels.
  - This is an assumption, stated on the slide.

## 2. Ticket volume

| Figure | Value | Source / derivation |
|---|---|---|
| Complaints received by the CFPB, 2024 | ~3,187,900 (2,829,400 sent to companies) | [1] CFPB Consumer Response Annual Report 2024, §2 "Complaint numbers" |
| Complaints for one large bank, H2 2024 | 70,569 | [3] Barclays UK complaints data, Jul–Dec 2024 |
| **Tickets per year for our client** | **141,138** | 2 × 70,569. **ESTIMATE E1:** H1 ≈ H2. Industry-wide H1→H2 2024 differed by 4.3 % (FCA, 1.86 m → 1.78 m) [4] |
| Tickets per week (mean) | 2,705 | ÷ 52.18 |
| Tickets per day (mean, 7-day) | 387 | ÷ 365 |
| **Mean arrival rate** | **16.1 /h = 0.00448 tickets/s** | ÷ 8,760 h |

## 3. Peak and non-peak

| Figure | Value | Source / derivation |
|---|---|---|
| Day-of-week pattern | Tue 17.8 %, Wed 17.6 %, Thu 17.3 %, Fri 16.5 %, Mon 15.4 %, Sat 9.4 %, Sun 6.0 % of weekly volume | [2] CFPB complaint API, Bank of America N.A., 2024, all 366 days (14,323 complaints) |
| Busiest-month factor | ×1.08 (max month 1,290 / mean 1,194) | [2] same series |
| **Peak day** | **520 tickets** | 2,705 × 17.8 % × 1.08 |
| Quiet day | 162 tickets (Sunday) | 2,705 × 6.0 % |
| Intraday pattern | 70 % of a day's tickets arrive 08:00–18:00 | **ESTIMATE E2.** Complaints are filed online 24/7 (98.6 % of CFPB 2024 complaints came via web [1]) but mostly in waking/working hours |
| Peak hour as a share of daily volume | 10.5 % (1.5 × the average business hour) | **ESTIMATE E3.** Bank contact-centre arrivals are bimodal over the day [5]. We take the busier mode at 1.5× the business-hour mean; clock times are not taken from the source |
| **Peak hour** | **55 tickets/h** | 520 × 0.70 ÷ 10 × 1.5 = 54.6 |
| Off-peak hour (quiet day, night) | 3.5 tickets/h | 162 × 0.30 ÷ 14 |
| Seasonal / event-driven spikes | ×2 surge allowance | **ESTIMATE E5.** An outage, fee change or fraud wave can double a peak hour. This sets the throughput headroom in R3 |
| **Peak multiplier over mean** | **×3.4** (peak-to-off-peak ×16) | 54.6 ÷ 16.1 |
| **Peak arrival rate** | **1.0 ticket/min = 0.0167 tickets/s** (design, rounded up from 0.91/min) | derived |
| Surge rate | 2.0 tickets/min = 0.0333 tickets/s | peak × E5 |

**Conclusion:** there is a clear peak, mid-week mid-morning, about 3.4× the mean and 16× a quiet hour. All latency and throughput requirements are set at the peak.

## 4. Agent-side search rate

| Figure | Value | Source / derivation |
|---|---|---|
| Agents on the desk | ≈ 23 | **ESTIMATE E6.** 141,138 tickets ÷ 250 working days ÷ 25 tickets per agent-day. No verified public productivity figure exists; Barclays closes 56 % of banking/card complaints within 3 days [3], which is consistent with same-week handling |
| Searches per ticket handled | 3 | **ESTIMATE E4.** Look up the customer's earlier tickets, look for similar open cases, check once more before closing |
| **Searches per minute (peak)** | **2.7 /min** (= 55 × 3 ÷ 60), about 7 per agent-hour | derived |
| **Ratio of searches to ticket posts** | **3 : 1** | → `SEARCH_RATIO=3` in `jmeter/run_matrix.sh` |

## 5. Ticket length distribution

Measured on all 1,000 rows of our slice (`data/team_slice.csv`) [6]. Percentiles use linear interpolation (`tools/workload_model.py`); `tools/prepare_jmeter_data.py` prints nearest-rank values (p50 779, p95 1,768). The two differ by under 1 %.

| Statistic | Chars | Approx. tokens (chars ÷ 3.6) |
|---|---|---|
| min | 202 | 56 |
| p50 | 778 | 216 |
| p95 | 1,759 | 489 |
| max | 1,998 | 555 |
| mean | 873 | 243 |

Tokens are approximate. The service logs the exact `prompt_eval_count` (narrative + about 105 prompt-template tokens) for every request, so the measured token distribution replaces this one after the first run.

**Course-extract note:** the extract caps narratives at 2,000 characters (max 1,998), and real complaints are longer.
- Prompt-evaluation time on CPU grows with prompt length, so our latencies are **optimistic** relative to production at p95 and above.
- p95 length is 2.3× p50, so p95 latency should sit clearly above p50 even with no queueing. Slide 9 separates that effect from queueing using the service log's `ollama_prompt_eval_ms`.

## 6. What this model implies for the requirements

- **Sustained throughput: 120 tickets/hour** (2/min). That is the surge rate: 2× the design peak, covering Poisson bursts inside the peak hour and incident surges. → R3
- **Peak arrival rate to survive without unbounded latency: 0.0167 tickets/s** (1/min), with searches at 3× that rate. → R1, R2
- **Latency budget for POST /tickets: p95 ≤ 15 s, p99 ≤ 30 s.**
  - No customer waits on this call, because intake is asynchronous for the customer, who gets an acknowledgement either way.
  - But POST is synchronous for the intake system, which holds a connection open. p99 must stay inside a typical 30 s gateway/client timeout.
  - A routing decision that takes 15 s is invisible in a process measured in days.
- **Cost of a misrouted ticket: about 5 agent-minutes plus at least one working day of delay** (**ESTIMATE E7**: the wrong team opens it, reads it, re-routes it, and the right team picks it up next day).
  - At 141,138 tickets/yr, every 1 % of misrouting costs about 1,411 re-triages, or 118 agent-hours/yr.
  - **15 % misrouting costs about 1,764 h/yr, about one full-time agent.** We set that as the most we will accept: worse than that, and the automation is paying for a person to clean up after it.
  - **Position: a misroute costs more than a slow triage.** So accuracy is the primary requirement (R4/R5), and latency and throughput are constraints. → R4, R5

## 7. Sources

1. Consumer Financial Protection Bureau (2025). *Consumer Response Annual Report, January 1 – December 31, 2024.* https://files.consumerfinance.gov/f/documents/cfpb_cr-annual-report_2025-05.pdf (accessed 6 Oct 2026).
2. Consumer Financial Protection Bureau. *Consumer Complaint Database* API, company = BANK OF AMERICA, NATIONAL ASSOCIATION, date_received 2024-01-01 to 2024-12-31, daily counts. https://www.consumerfinance.gov/data-research/consumer-complaints/ (queried 6 Oct 2026).
3. Barclays (2025). *UK complaints data — July to December 2024.* https://home.barclays/sustainability/esg-resource-hub/reporting-and-disclosures/uk-complaints-data/ (accessed 6 Oct 2026).
4. Financial Conduct Authority (2025). *Firm complaints data 2024 H2*, via data.gov.uk. https://ckan.publishing.service.gov.uk/dataset/a5e84f7c-33a4-4cd7-ae7b-dec2c09c7d88 (accessed 6 Oct 2026).
5. Brown, L., Gans, N., Mandelbaum, A., Sakov, A., Shen, H., Zeltyn, S., Zhao, L. (2005). Statistical Analysis of a Telephone Call Center: A Queueing-Science Perspective. *Journal of the American Statistical Association*, 100(469), 36–50.
6. Team P2-9 slice, rows 9000–9999 of the ICT3113 course extract of [2] (`data/team_slice.csv`).
