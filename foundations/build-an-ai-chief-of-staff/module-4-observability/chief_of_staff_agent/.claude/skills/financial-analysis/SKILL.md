---
name: financial-analysis
description: Standard operating procedure for board-ready financial analysis at TechStart Inc. Use whenever the user asks about runway, burn rate, cash position, financial forecasts, the cost or impact of hiring, or wants a financial summary for the board or leadership.
---

# Financial Analysis SOP

This skill defines **how we run a financial analysis** at TechStart Inc, so the answer is
consistent, grounded in real data, and board-ready every time. Follow these steps in order.

## Step 1 — Ground in the data first (do NOT guess)

Before any calculation, read the relevant source data in `financial_data/`:

- `financial_data/burn_rate.csv` — monthly burn, headcount, revenue, net burn (historical)
- `financial_data/revenue_forecast.json` — current ARR, monthly growth rate, forward projections
- `financial_data/hiring_costs.csv` — loaded monthly cost per role/level

Use the company facts in `CLAUDE.md` (burn ~$500K/mo, 20 months runway, $10M cash, $2.4M ARR)
as context, but prefer the numbers in `financial_data/` when they conflict — that is the source of truth.

## Step 2 — Run the right script (don't hand-calculate)

Compute with the project scripts via **Bash** rather than estimating in your head. Pick by question type:

| Question is about… | Run | Example |
|---|---|---|
| Runway / burn from a cash balance | `scripts/simple_calculation.py <total_cash> <monthly_burn>` | `python scripts/simple_calculation.py 10000000 500000` |
| ARR / revenue projection over time | `scripts/financial_forecast.py --arr <arr> --growth <rate> --months <n> --burn <burn> --format json` | `python scripts/financial_forecast.py --arr 2400000 --growth 0.15 --months 12 --format json` |
| Cost/impact of hiring N engineers | `scripts/hiring_impact.py <num_engineers> [salary]` | `python scripts/hiring_impact.py 10 200000` |

Each script prints JSON — parse it and use the exact numbers it returns.

For an open-ended strategic trade-off (e.g. "should we hire or extend runway?"), you may delegate to the
**financial-analyst** subagent via the Task tool for deeper modeling. Use this skill for the standard
runway/burn/forecast/hiring questions; delegate only when the analysis is genuinely open-ended.

## Step 3 — Present in the standard structure

Always report results in this fixed order:

1. **Headline metric** — the single number that answers the question (e.g. "Runway: 20 months").
2. **Key drivers** — the 2–4 inputs that drive it (burn rate, growth, headcount cost), with values.
3. **Recommendation** — one clear, actionable next step tied to the current Q2 priorities in `CLAUDE.md`.

Keep it tight and decision-oriented — this is for the CEO and the board, not a spreadsheet dump.
Cite which data file and script produced the numbers so the analysis is auditable.
