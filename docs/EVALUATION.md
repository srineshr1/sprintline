# Evaluation Methodology

Aligned with **PROJECT.md §8** and implemented in `backend/app/services/evaluation.py`, exposed at:

`GET /api/projects/{id}/ai/evaluate`

## Why evaluate?

A GenAI Agile tool can look impressive in screenshots while producing unusable stories. This project treats **measurement** as a first-class feature: metrics are computed from **persisted project state**, not from chat logs.

## Metrics

### 1. Acceptance criteria (AC) coverage

| Field | Meaning |
|-------|---------|
| `total_stories` | Count of stories in the project |
| `with_ac` | Stories with ≥1 non-empty acceptance criterion |
| `without_ac` | Complement |
| `coverage_pct` | `100 * with_ac / total_stories` |

**Interpretation:** Higher coverage ⇒ more testable backlog (INVEST: Testable). Critic also flags `missing_ac` as **error** severity.

### 2. INVEST-style rubric (automated checklist)

Each story is scored 0/1 on six dimensions; **story score** = mean of dimensions; **project score** = mean of story scores.

| Dimension | Pass heuristic (simplified) |
|-----------|-----------------------------|
| Independent | Title present; no “blocked by / depends on story” wording |
| Negotiable | Has description, rationale, or reasonably long title |
| Valuable | User-story form (*As a… I want… so that…*) or value keywords |
| Estimable | Points in 1–13 |
| Small | Points in 1–8 |
| Testable | ≥2 AC, or ≥1 AC with sufficient length |

**Output:** `average_score` (0–1), `average_pct`, `dimension_pass_rates`, optional `per_story` breakdown.

**Caveat:** This is a **research rubric for automated measurement**, not a formal Scrum audit. It is reproducible and code-reviewed, which is suitable for viva comparison (before/after user edits, with/without critic).

### 3. Sprint planned vs completed vs remaining

For each sprint with assigned items:

| Field | Meaning |
|-------|---------|
| `capacity_points` | Team capacity |
| `planned_points` | Sum of points of assigned stories |
| `completed_points` | Points with `status=done` |
| `remaining_points` | Points not done (todo + in progress) |
| `utilization_pct` | planned / capacity |
| `completion_pct` | completed / planned |

**Interpretation:** Supports “sprint realism” discussion: did the AI plan overload capacity? Did the team complete the plan over a mock sprint?

### 4. Board summary

Status counts (todo / in_progress / done) and overall points completion.

## Critic agent (quality pass)

Implemented in `backend/app/services/critic.py`.

| Check | Severity | Example code |
|-------|----------|--------------|
| Empty title | error | `empty_title` |
| Missing AC | error | `missing_ac` |
| Thin AC (only one) | warning | `thin_ac` |
| Vague / short title | warning | `vague_title`, `title_too_short` |
| Large story (>13 pts) | warning | `large_story` |
| Capacity overload | error | `capacity_overload` |

Critic findings are **advisory**. Endpoints that critique do **not** rewrite story fields. User PATCH remains authoritative (tested in API suite).

## Suggested viva experiments

1. **Time saved (manual observation):** minutes to first full backlog with AI vs manual writing for the same brief.  
2. **AC coverage:** run evaluate immediately after generate; re-run after user fixes critic errors; report delta.  
3. **INVEST average:** same before/after edit.  
4. **Edit rate (optional manual):** fraction of AI titles/AC the user changes.  
5. **Sprint realism:** planned points vs capacity; after mock status updates, completion %.  
6. **Ablation idea:** compare backlog quality with critic warnings visible vs ignoring critic (qualitative user study, n=3–5 classmates).

## How to reproduce metrics on a project

```bash
# after generate-backlog and optional edits
curl -s http://127.0.0.1:8000/api/projects/1/ai/evaluate | python3 -m json.tool
```

Or UI → **Quality & metrics** → **Refresh metrics**.

## Relation to report chapters

| Report section | Evidence from system |
|----------------|----------------------|
| Design of multi-agent pipeline | Architecture + pipeline steps in API responses |
| Quality control | Critic codes + screenshots of Quality tab |
| Quantitative results | AC %, INVEST %, sprint planned/done tables |
| Limitations | Stub agents, heuristic INVEST, no multi-user auth |
