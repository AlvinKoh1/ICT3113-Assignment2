# Labelling Protocol — ICT3113 Group P2-9

**Version:** v1.1. The v1.0 rules below were used for labelling; the v1.1 additions from adjudication are in the revision history at the bottom.
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

### v1.0 — 7 Oct 2026
Initial protocol, written before any ticket was read. Authors: Gabriel (M3, protocol lead) and Alvin (M2, Annotator B).

### v1.1 — 7 Oct 2026
Added after adjudication of the 36 disagreements between Annotator A (Gabriel) and Annotator B (Alvin). Each rule below closes a gap that a disagreement exposed. The prompting rows are marked `protocol_updated: yes` in `golden/disagreements.csv`. Disagreements where v1.0 already gave the answer and one annotator simply misapplied it (e.g. 9005 scam wire, 9782 prepaid card, 9894 debit-card fraud) did not change the protocol and stay `protocol_updated: no`.

No label was changed by these rules after adjudication. They record the reasoning the adjudication already used, so a third annotator would reach the same labels.

Drafted by Irfan (M1) from the recorded resolution notes. AWAITING CONFIRMATION by Gabriel (M3, protocol lead) and Alvin (M2).

**Rule 1.1: Wrong information furnished by the lender is Credit reporting.**
When the *main* grievance (for several grievances, the first substantive one, per §5) is an entry on the credit report (a balance on a settled loan, a late payment that did not happen), label Credit reporting. This holds even though the furnisher is the consumer's own lender and the loan is named. If the report is only a consequence or a piece of evidence in a complaint about the loan itself, label the product. For example, 9733 (repossession and fees first, re-aging on the report last) stays Consumer loan. The same goes for a card or loan event whose only link to credit is a side effect on the score (see 1.4). When the furnisher is a debt collector, Rule 1.2 applies instead.
*Prompted by:* 9412 and 9459, where A labelled Credit reporting and B labelled Consumer loan. *Resolution:* Credit reporting; the harm is to the record.

**Rule 1.2: For collection debts, the target of the complaint decides between Debt collection and Credit reporting.**
§4 puts Debt collection above Credit reporting, but that applies only to genuine ties. If the consumer is disputing a collection *entry* with the bureaus, the complaint is about the record → Credit reporting. If the consumer is complaining about what the collector *did* (validation, contact, pursuing a debt not owed) → Debt collection. A request to validate a debt is collection conduct whatever the underlying product. A collector that keeps collecting on, and keeps reporting, a debt the consumer has shown is fraudulent is also collection conduct → Debt collection (e.g. 9362), even though the consumer wants the entry removed.
*Prompted by:* 9732 and 9941, where A labelled Debt collection / Credit reporting and B the other. *Resolution:* Credit reporting; the dispute is about the report entry. Also 9717, where A labelled Mortgage and B labelled Debt collection. *Resolution:* Debt collection; a validation demand to the debt holder.

**Rule 1.3: Money transfer or service vs Bank account or service.**
Accounts inside P2P and payment apps (Cash App and similar) are Money transfer or service, including the app closing an account with funds in it and disputes over app payments. They are not deposit accounts, and they are not credit cards. A bank's own handling of a deposit account (freezes, holds, stop-payment orders) is Bank account or service, even when a payment to someone else is involved. This includes unauthorised app transactions debited from a bank account when the complaint is that the bank will not stop or reverse them (e.g. 9894). A platform that fits none of the seven (e.g. brokerage or payment-platform access) goes to Money transfer or service as nearest fit, flagged POOR FIT.
*Prompted by:* 9124, where A labelled Bank account or service and B labelled Money transfer or service. *Resolution:* Money transfer or service. Also 9661 (Money transfer vs Credit card; *resolution:* Money transfer or service) and 9953 (Money transfer vs Bank account; *resolution:* Bank account or service, a stop-payment on a bank account).

**Rule 1.4: Credit card covers the whole card-account life cycle.**
Applications and approval, balance-transfer offers, transfer of the account to another issuer or servicer, and closure are Credit card. This holds even when the consumer mentions the effect on their credit score. When the narrative names an issuer that also offers deposit accounts (e.g. Capital One) but describes only a card relationship, label Credit card. Bank account or service needs a deposit account in the story.
*Prompted by:* 9771 (A: Bank account or service, B: Credit card), 9779 (A: Debt collection, B: Credit card), 9951 (A: Credit reporting, B: Credit card) and 9411 (A: Bank account or service, B: Credit card). *Resolution:* Credit card in all four.

**Rule 1.5: Point-of-sale instalment financing, and first-party collection.**
Buy-now-pay-later and point-of-sale instalment financing (e.g. Affirm) is Consumer loan. When the *creditor's own* collections department pursuing the consumer is the grievance, label Debt collection, exactly as for a third-party collector. When the grievance is the loan itself and collection is only a consequence, label the loan's category.
*Prompted by:* 9012, where A labelled Money transfer or service and B labelled Consumer loan. *Resolution:* Consumer loan. Also 9526, where A labelled Consumer loan and B labelled Debt collection. *Resolution:* Debt collection; the collections department's conduct was the grievance.

**Rule 1.6: Servicing terms are not a Mortgage signal on their own.**
Forbearance, modification and repayment-plan language appears in both mortgage and non-mortgage servicing. Label Mortgage only when the loan is secured by real property: the home, a mortgage servicer, escrow or foreclosure appears in the story (e.g. 9918, a modification during foreclosure). Otherwise label Consumer loan.
*Prompted by:* 9981, where A labelled Mortgage and B labelled Consumer loan. *Resolution:* Consumer loan; student-loan style forbearance with no property involved.
