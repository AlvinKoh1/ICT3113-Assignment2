# Workload Model — ICT3113 Group P2-9

Slide 3. Every figure needs a citation or a stated estimation method. Figures
you cannot source are fine — figures you cannot *account for* are not.

> **Structure each figure as:** value → source or derivation → what it implies
> for the requirements. A number with no consequence for §5 does not belong here.

---

## 1. Client profile (state your assumptions)

The brief says "a financial services company" and nothing more. You must pick a
scale and defend it — every downstream number depends on it.

- **Institution size assumed:** <e.g. a mid-size retail bank with ~2M retail customers>
- **Basis:** <why this scale? cite a comparable institution or a regulator's published banding>
- **Geography / regulator:** <the CFPB data is US; say whether you model a US desk or map it onto a local equivalent, and how>

## 2. Ticket volume

| Figure | Value | Source / derivation |
|---|---|---|
| Complaints received by the industry per year | | CFPB Consumer Response Annual Report — cite year and page |
| Share attributable to an institution of our assumed size | | <derivation: e.g. complaints per million customers> |
| **Tickets per year for our client** | | derived |
| **Tickets per business day** | | ÷ ~250 business days |
| **Mean arrival rate (tickets/sec)** | | this is your baseline JMeter rate |

**Suggested primary source:** CFPB *Consumer Response Annual Report* (published
each March) gives total complaint volume and a breakdown by product — the same
seven-ish product families as this dataset. Complaint volume per named company
is also available in the public database.

## 3. Peak and non-peak

The requirements must cater for the peak, so this section has to produce a
**peak multiplier**, not just prose.

| Figure | Value | Source / derivation |
|---|---|---|
| Intraday pattern | | <e.g. business-hours concentration; cite or state the assumption> |
| Peak hour as a share of daily volume | | |
| Day-of-week pattern | | <Monday spike after weekend accumulation is a common, citable pattern> |
| Seasonal / event-driven spikes | | <e.g. a breach, a fee change, a regulatory deadline> |
| **Peak multiplier over mean** | **×___** | derived |
| **Peak arrival rate (tickets/sec)** | | mean × multiplier |

> If you conclude there is no meaningful peak, say so explicitly and justify it.
> "We found no peak" is a position; silence is not.

## 4. Agent-side search rate

| Figure | Value | Source / derivation |
|---|---|---|
| Agents on the desk | | <derive from ticket volume and handling time> |
| Searches per agent per hour | | <estimate; state the reasoning> |
| **Searches per second (mean / peak)** | | |
| Ratio of searches to ticket posts | | → sets `SEARCH_RATIO` in `run_matrix.sh` |

Searches are cheap and tickets are expensive, but searches run **concurrently**
with classification on the same box. The point of the mixed load is to show
whether a slow `POST /tickets` degrades `GET /search` for the human agents.

## 5. Ticket length distribution

Measured directly from your own slice — `tools/prepare_jmeter_data.py` prints
these. This is the one section where you have hard data rather than estimates.

| Statistic | Chars | Approx. tokens (chars ÷ 3.6) |
|---|---|---|
| min | | |
| p50 | | |
| p95 | | |
| max | | |
| mean | | |

**Course-extract note:** narratives in the extract are capped at 2000 characters.
Real complaints are not. Say what that does to your latency estimates — a real
deployment would see longer prompts and therefore longer prompt-eval times, so
your measurements are **optimistic** relative to production. Quantify the gap if
you can (CFPB narratives run to several thousand characters).

Latency on CPU scales with prompt length, so the length distribution maps onto a
*latency* distribution. If p95 length is ~2.3× p50 length, expect p95 latency to
be materially above p50 for reasons that have nothing to do with queueing —
separate the two effects when you interpret Slide 9.

## 6. What this model implies for the requirements

Close the loop. Three or four sentences, each ending in a number that reappears
on Slide 4:

- Sustained throughput the service must support: ____ tickets/hour
- Peak arrival rate it must survive without unbounded latency: ____ tickets/sec
- Latency budget for `POST /tickets`: ____ (and the reasoning — is a slow
  classification actually visible to anyone, given intake is asynchronous from
  the customer's point of view?)
- Cost of a misrouted ticket: ____ (in agent-minutes or dollars) — this is what
  lets you trade accuracy against speed in Step 6.

> The last one is the hard one and the one that decides your recommendation.
> The brief says explicitly that neither it nor the client tells you whether a
> misrouted ticket or a slow triage costs more. **You must take a position.**
> Estimate the handling cost of a misroute (re-reading, re-routing, delay to the
> customer, SLA exposure) and state it as a number you can defend.

## 7. Sources

<Numbered list, matching Slide 12. Include access dates.>
