# Labelling Protocol — ICT3113 Group P2-9

**Version:** v1.0 (DRAFT — must be reviewed by the team before labelling begins)
**Status:** written **before** any ticket was read and before any model was run.

> This is a starting draft. The brief requires the protocol to be revised when a
> disagreement reveals a gap in it, and requires those revisions to be visible.
> Keep every version: append a new version section at the bottom, never
> overwrite. The revision history is part of the mark.

---

## 1. Task

Assign each complaint narrative **exactly one** of seven categories. The
consumer-selected labels in the source data are noisy and must not be consulted;
`golden/candidates.csv` deliberately omits them.

## 2. The decision rule

Classify by **the financial product or service the complaint is about**, not by
the customer's emotional register, not by which company is named, and not by
what the customer asks for as a remedy.

When two products appear, apply this test in order:

1. **What is the grievance?** Label the product the *complained-of conduct*
   attaches to, not the product that merely appears in the story.
2. **Whose action is being complained about?** If a customer complains that a
   debt collector reported a credit-card debt to a bureau, the conduct is
   collection or reporting, not the card.
3. If steps 1 and 2 leave a genuine tie, apply the precedence order in §4.

## 3. Category definitions

### Credit reporting
Complaints about **credit files, credit reports, credit scores, and the bureaus
or furnishers that maintain them**. Inaccurate or unrecognised tradelines,
disputes that were not investigated, items that should have aged off, hard
inquiries the consumer did not authorise, identity theft appearing on a report,
freezes and fraud alerts.
*Signal:* the harm is to the consumer's **record**, not to an account balance.

### Debt collection
Complaints about the **conduct of collecting an alleged debt**. Calls at
prohibited hours, threats, contacting third parties, refusing to validate a
debt, collecting a debt already paid or not owed, collecting a time-barred debt,
a debt sold between collectors.
*Signal:* someone is **pursuing** the consumer for money. The underlying product
is often a card or loan; that does not matter — the conduct is collection.

### Mortgage
Complaints about **loans secured by real property**: origination, underwriting,
closing costs, escrow, servicing transfers, payment application, modification,
forbearance, foreclosure, PMI, HELOCs and home equity loans.

### Credit card
Complaints about **revolving credit card accounts**: APR and fee changes,
billing disputes and chargebacks, rewards, credit limit changes, unauthorised
charges on a card, card account closure. Includes store cards.

### Bank account or service
Complaints about **deposit accounts and everyday banking**: checking and
savings, overdraft and NSF fees, holds on deposits, account closure by the bank,
debit card transactions, ATMs, cashier's cheques, CDs.

### Consumer loan
Complaints about **closed-end instalment credit that is not a mortgage**: auto
loans and leases, personal and instalment loans, student loans, title and
payday-style instalment products.

### Money transfer or service
Complaints about **moving money and money-service products**: domestic and
international wires, remittance providers, P2P payment apps, prepaid and gift
cards, virtual currency, money orders, and scams executed through a transfer.

## 4. Precedence for genuine ties

Only after §2 fails. Higher wins:

1. **Debt collection** — collection conduct dominates whatever the debt is for.
2. **Credit reporting** — reporting conduct dominates the underlying product.
3. **Mortgage** — the secured nature dominates a generic servicing complaint.
4. The specific product category (Credit card / Consumer loan / Bank account or
   service / Money transfer or service).

*Rationale:* 1 and 2 sit on top because they describe conduct by a party that is
often not the product issuer, and because that is the team the ticket routes to.

> **Note for the report:** this precedence order is a judgement call, not a fact.
> It shapes your golden labels and therefore every accuracy number you report.
> State it on Slide 6 and be ready to defend it.

## 5. Edge cases

| Situation | Rule |
|---|---|
| Fits two categories about equally | Apply §2, then §4. Record it in `notes`. |
| Fits none of the seven | Choose the nearest by §2 and flag `notes: POOR FIT`. Every ticket must get one of the seven — the service has no "other" class. |
| Narrative too redacted to tell | Label on whatever signal survives; flag `confidence: low`. If genuinely undecidable, flag `notes: UNDECIDABLE` and raise it at adjudication — the team may replace the ticket, but only **before** the freeze and only with the replacement recorded here. |
| Identity theft / fraud | Label by what was attacked: a fraudulent tradeline on a report → Credit reporting; fraudulent charges on a card → Credit card; a scam wire → Money transfer or service. |
| Complaint is about a credit bureau's own customer service | Credit reporting. |
| Student loan | Consumer loan. Not its own category in this scheme. |
| Overdraft fee charged on a checking account | Bank account or service, even when a collector later pursues the balance — unless the *grievance* is the collection conduct (§2.2). |
| Wire fraud where the bank refuses to help recover | Money transfer or service. The grievance attaches to the transfer. |
| Multiple distinct complaints in one narrative | Label the **first substantive** grievance. Record the others in `notes`. |

## 6. Procedure

1. Each annotator works **alone** and does not discuss tickets with the other
   annotator until every ticket is labelled.
2. Fill `label` for every row. Use `confidence` (`high` / `low`) and `notes`
   freely — notes are what make the adjudication meeting fast.
3. Copy category names **exactly**; `tools/agreement.py` rejects anything else.
4. Commit your own sheet (`golden/labels_<initials>.csv`) as a **separate
   commit** from the other annotator's. Two independent commits are the evidence
   that the labelling was independent.
5. Then run `tools/agreement.py`, adjudicate `golden/disagreements.csv` as a
   team, and record a `resolution_note` for **every** disagreement.
6. Where a disagreement exposed a gap in this protocol, add a rule below in a
   new version section and set `protocol_updated: yes` on that row.

## 7. Do not

- Do not look at `golden/candidates_sourcelabels.csv` before labelling.
- Do not run any model against these tickets before the golden set is committed.
- Do not "fix" your labels after seeing model output. That is the specific
  failure this whole procedure exists to prevent.

---

## Revision history

### v1.0 — <DATE>
Initial protocol, written before any ticket was read. Authors: <names>.

### v1.1 — <DATE>
<!-- Template. One entry per rule change, each traceable to a disagreement.
Rule added: ...
Prompted by: rows ..., where <A> labelled X and <B> labelled Y.
Resolution: ...
-->
