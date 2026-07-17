# Customer Support Ticket Classifier & Auto-Router

## Executive summary

An autonomous, end-to-end ML pipeline that ingests messy customer support
text (scraped from real Amazon Q&A and reviews for Shark/Ninja products),
classifies it into one of four ticket categories, drafts a customer-facing
reply, and routes it to the appropriate support team — all powered by open
HuggingFace models running locally with no external API dependencies.

The system uses an agentic loop: a local instruct model reads each ticket,
selects an action (classify, draft, escalate, request clarification), and
can retry on low confidence. A deterministic fallback path catches agent
failures so the demo never hangs.

Final deliverable: a Streamlit dashboard matching the Review Intelligence
project's visual style.

---

## 1. Problem statement

SharkNinja handles high volumes of customer contacts across warranty claims,
troubleshooting, product questions, and return requests. Manual triage is
slow and inconsistent. Salesforce Agentforce was deployed in production —
this project builds a simplified, fully open-source prototype demonstrating
the same concept with measurable effort-reduction metrics.

---

## 2. Dataset

### 2.1 Source

Web-scraped Amazon data for 8–12 Shark/Ninja products across 3 categories:

| Category | Example products | Why |
|---|---|---|
| Vacuums | Shark Navigator, Shark Vertex | High volume of troubleshooting + warranty complaints in reviews |
| Blenders | Ninja Professional BL610, Ninja Foodi SS201 | Product questions dominate Q&A; return mentions appear in reviews |
| Air fryers | Ninja AF101, Ninja DZ201 | Mix of all four ticket types in reviews |

**Two data sources per product:**
- **Q&A section** — naturally messy, fragmented, shorthand text. Rich in
  product questions and troubleshooting. Thin on warranty/returns.
- **Product reviews** — longer-form, covers warranty claims ("got a
  replacement under warranty"), return requests ("had to send it back"),
  and troubleshooting ("stopped working after 3 months"). Fills the gaps
  Q&A leaves.

### 2.2 Scrape strategy

One-time scrape → saved as a static CSV/JSON. No live scraping at runtime.
The scraper is a standalone script, not part of the production pipeline.

**Scraper constraints:**
- Respect `robots.txt` and rate-limit (2–3 second delay between requests)
- Use `requests` + `BeautifulSoup` (no Selenium unless JS-rendered content
  requires it — Amazon Q&A may need it)
- Save raw HTML alongside parsed output for reproducibility
- Target: 500–1000 raw text entries across all products

### 2.3 Raw schema — `raw_scraped.csv`

| field | type | source | notes |
|---|---|---|---|
| id | string | generated | UUID |
| product_asin | string | URL | e.g. B07GH4Z9Q7 |
| product_name | string | listing title | |
| brand | string | parsed | Shark or Ninja |
| category | enum | assigned | vacuum / blender / air_fryer |
| source_type | enum | assigned | `qa` or `review` |
| text | text | scraped | raw question, answer, or review body |
| star_rating | int 1–5 / null | review only | null for Q&A entries |
| date | date / null | if available | |
| verified_purchase | bool / null | review only | |

### 2.4 "Messy" characteristics (natural, not injected)

- Typos, abbreviations, slang ("doesnt work", "pos", "smh")
- Missing punctuation, run-on sentences
- Mixed product references ("my ninja blender thing", "the shark one")
- Ambiguous intent (a review that is both a complaint and a question)
- Variable length (3 words to 3 paragraphs)
- HTML artifacts, unicode issues from scrape

### 2.5 Labeling

No manual labeling for training — zero-shot classification handles this.
A small manually-labeled evaluation set (50–100 entries, stratified across
all 4 categories) is created post-scrape for measuring classifier accuracy.

---

## 3. Ticket categories

| Category | Route to | Example signal phrases |
|---|---|---|
| `warranty_claim` | Warranty Ops | "under warranty", "replacement", "defective", "broke after X months" |
| `troubleshooting` | Tech Support | "how do I fix", "not working", "error", "won't turn on", "overheating" |
| `product_question` | Sales | "does it come with", "is it compatible", "what size", "can I use it for" |
| `return_request` | Returns | "return", "refund", "send it back", "money back", "disappointed" |

Ambiguous tickets (e.g. a troubleshooting complaint that also mentions
wanting a return) get classified by the agent; low-confidence cases are
escalated to human review.

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Streamlit Dashboard                 │
│  ┌───────────┐ ┌──────────┐ ┌────────────────────┐  │
│  │ Ticket    │ │ Agent    │ │ Effort-Reduction   │  │
│  │ Table     │ │ Trace    │ │ Metrics Panel      │  │
│  └───────────┘ └──────────┘ └────────────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │
           ┌───────────▼───────────┐
           │    Agent Loop (core)  │
           │  local instruct model │
           │  decides next action  │
           └───┬───┬───┬───┬──────┘
               │   │   │   │
    ┌──────────▼┐ ┌▼──────┐ ┌▼─────────┐ ┌▼──────────┐
    │ CLASSIFY  │ │ DRAFT │ │ ESCALATE │ │ CLARIFY   │
    │ (HF zero- │ │ (HF   │ │ (flag for│ │ (generate │
    │  shot)    │ │ gen)  │ │  human)  │ │  question)│
    └───────────┘ └───────┘ └──────────┘ └───────────┘
               │       │
    ┌──────────▼───────▼──────────┐
    │         ROUTE               │
    │  category → team mapping    │
    │  output to team bucket      │
    └─────────────────────────────┘
```

### 4.1 Agent loop — detailed flow

```
INPUT: raw ticket text
  │
  ▼
AGENT (local instruct model) reads ticket + system prompt
  │
  ├─→ action: CLASSIFY
  │     └─→ HF zero-shot classifier → {category, confidence}
  │           ├─ confidence ≥ 0.65 → continue to DRAFT
  │           └─ confidence < 0.65 → AGENT re-reads with classification hint
  │                 ├─ retry confidence ≥ 0.50 → continue to DRAFT (flagged)
  │                 └─ still < 0.50 → ESCALATE
  │
  ├─→ action: DRAFT
  │     └─→ HF generative model → draft reply text
  │           └─→ continue to ROUTE
  │
  ├─→ action: ESCALATE
  │     └─→ mark ticket as needs_human_review, skip DRAFT/ROUTE
  │
  ├─→ action: CLARIFY
  │     └─→ HF generative model → clarifying question
  │           └─→ in demo: simulated, ticket stays in queue
  │
  └─→ FALLBACK (agent output doesn't parse)
        └─→ scripted pipeline: classify → draft → route (no agent reasoning)
            logged as fallback_triggered=true

OUTPUT: {category, confidence, team, draft_reply, agent_trace[], fallback_used}
```

### 4.2 Confidence thresholds

| Threshold | Meaning | Action |
|---|---|---|
| ≥ 0.65 | High confidence | Auto-route, no flag |
| 0.50 – 0.64 | Medium confidence | Auto-route, flagged for spot-check |
| < 0.50 | Low confidence | Escalate to human review |

These are starting values. Tune on the eval set after initial runs.

---

## 5. Models

All models run locally via HuggingFace `transformers`. No external APIs.

| Role | Model | Why |
|---|---|---|
| **Zero-shot classifier** | `facebook/bart-large-mnli` | Proven zero-shot NLI model, no labeled data needed, fast inference on CPU |
| **Response drafter** | `google/flan-t5-base` (or `-large` if hardware allows) | Instruction-following text generation, small enough to run locally, decent at short customer replies |
| **Agent decision-maker** | `google/flan-t5-large` or `mistralai/Mistral-7B-Instruct-v0.3` via Ollama | Needs to parse a ticket and output a structured action choice. Larger model = more reliable action selection. Ollama path simplifies loading 7B models. |

### 5.1 Agent action schema

The agent receives a constrained system prompt and must output one of:

```json
{
  "action": "classify" | "draft" | "escalate" | "clarify",
  "reasoning": "short explanation"
}
```

If the model output doesn't parse as valid JSON with a valid action, the
fallback scripted pipeline runs instead. This is the key reliability
mechanism — the agent is the aspirational path; the scripted pipeline is
the guaranteed path.

### 5.2 Model fallback chain

```
Preferred:  Mistral-7B-Instruct (via Ollama) — best action selection
Fallback 1: flan-t5-large (via transformers) — lighter, less reliable
Fallback 2: scripted pipeline (no agent) — deterministic, always works
```

The system auto-detects which models are available at startup and selects
the best available option.

---

## 6. Routing

Simulated — no real ticketing system. Category maps to team:

| Category | Routed team | Output |
|---|---|---|
| `warranty_claim` | Warranty Ops | Written to `output/warranty_ops/` |
| `troubleshooting` | Tech Support | Written to `output/tech_support/` |
| `product_question` | Sales | Written to `output/sales/` |
| `return_request` | Returns | Written to `output/returns/` |

Each routed ticket is a JSON file containing the full processing trace.

---

## 7. Effort-reduction metrics

| Metric | How measured |
|---|---|
| **Auto-route rate** | % of tickets classified with confidence ≥ 0.65 (no human needed) |
| **Escalation rate** | % of tickets where confidence < 0.50 (human required) |
| **Agent success rate** | % of tickets where the agent loop completed without fallback |
| **Classification accuracy** | Measured against the manually-labeled eval set (50–100 tickets) |
| **Estimated time saved** | (auto-routed tickets × avg manual triage time of 2 min) vs. (escalated tickets × 2 min) |
| **Category distribution** | Breakdown of ticket volume by category — shows routing balance |

---

## 8. Streamlit dashboard

### 8.1 Pages / views

**Page 1 — Ticket Triage (main view)**
- Upload a CSV or use the pre-loaded scraped dataset
- Table of all tickets with columns: text preview, category, confidence,
  team, status (auto-routed / flagged / escalated)
- Click a row to expand: full text, drafted reply, agent trace (each
  action the agent took), fallback status
- Filter by category, confidence band, status

**Page 2 — Metrics Dashboard**
- Auto-route rate gauge
- Classification accuracy (if eval set loaded)
- Category distribution bar chart
- Confidence distribution histogram
- Estimated time saved calculation
- Agent success rate vs. fallback rate

**Page 3 — Live Demo**
- Text input: paste or type a customer message
- "Process" button runs the full agent loop in real-time
- Shows step-by-step agent trace as it runs
- Displays: classified category + confidence, drafted reply, routed team

### 8.2 Visual style

Match Review Intelligence project: clean layout, minimal color palette,
data-dense tables, metric cards at the top of dashboards.

---

## 9. Project structure

```
ticket-classifier/
├── docs/
│   └── PROJECT_SPEC.md          ← this file
├── scraper/
│   ├── scrape_amazon.py         ← one-time scraper script
│   ├── config.py                ← product ASINs, categories, delays
│   └── raw_html/                ← archived raw HTML (gitignored)
├── data/
│   ├── raw_scraped.csv          ← output of scraper
│   ├── eval_set.csv             ← manually labeled subset for accuracy
│   └── processed/               ← any intermediate cleaned data
├── agent/
│   ├── loop.py                  ← agent loop: read ticket → choose action → execute
│   ├── actions.py               ← classify, draft, escalate, clarify implementations
│   ├── fallback.py              ← scripted pipeline (no agent reasoning)
│   ├── models.py                ← model loading, auto-detection, fallback chain
│   └── schema.py                ← action schema, confidence thresholds, team mapping
├── app/
│   ├── streamlit_app.py         ← main Streamlit entry point
│   ├── pages/
│   │   ├── triage.py            ← ticket table + detail view
│   │   ├── metrics.py           ← effort-reduction dashboard
│   │   └── demo.py              ← live single-ticket demo
│   └── components/              ← shared UI components
├── tests/
│   ├── test_classifier.py       ← zero-shot classification unit tests
│   ├── test_agent_loop.py       ← agent action parsing, fallback triggering
│   └── test_routing.py          ← category → team mapping
├── output/                      ← routed ticket outputs (gitignored)
│   ├── warranty_ops/
│   ├── tech_support/
│   ├── sales/
│   └── returns/
├── requirements.txt
├── README.md
└── .gitignore
```

---

## 10. Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| ML framework | HuggingFace `transformers`, `torch` |
| Zero-shot | `facebook/bart-large-mnli` via `pipeline("zero-shot-classification")` |
| Text generation | `google/flan-t5-base` or `-large` via `pipeline("text2text-generation")` |
| Agent model | `flan-t5-large` or Mistral-7B-Instruct via Ollama |
| Scraping | `requests`, `beautifulsoup4`, optionally `selenium` for JS-rendered Q&A |
| Dashboard | `streamlit` |
| Data handling | `pandas` |
| Testing | `pytest` |

---

## 11. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Amazon blocks scraper | No data | Rate-limit, rotate user-agent, save raw HTML on first success. If blocked, use cached data. |
| Q&A requires JS rendering | Scraper returns empty | Fall back to Selenium or headless browser for Q&A pages only |
| Agent model outputs garbage | Pipeline hangs | Hard fallback to scripted pipeline after 1 failed parse attempt. Log fallback_triggered. |
| Warranty/return categories still thin after review scrape | Imbalanced eval | Report the imbalance honestly. Demonstrate classifier works on available data. Note as a known limitation. |
| 7B model too large for local machine | Agent loop unavailable | Auto-detect available models. Fall back to flan-t5-large → flan-t5-base → scripted pipeline. |
| Zero-shot accuracy is poor on messy text | Bad classifications | Preprocess: strip HTML artifacts, normalize unicode. If still poor, try `MoritzLaurer/deberta-v3-large-zeroshot-v2.0` as an alternative classifier. |

---

## 12. Explicitly out of scope

- Real Salesforce / ticketing system integration
- Fine-tuning any model (zero-shot and pre-trained instruct only)
- Multi-language support (English only)
- Real-time / streaming inference
- Any use of Claude, OpenAI, or other paid API
- Sentiment analysis as a standalone feature (classification subsumes it)
- Customer identity resolution or PII handling

---

## 13. Build order

| Phase | What | Depends on |
|---|---|---|
| **1. Scraper** | Build and run the Amazon scraper, produce `raw_scraped.csv` | Nothing |
| **2. Classifier** | Wire up zero-shot classification, test on scraped data | Phase 1 |
| **3. Drafter** | Wire up flan-t5 response generation | Phase 2 |
| **4. Agent loop** | Build the agentic decision layer + fallback | Phases 2, 3 |
| **5. Routing** | Category → team mapping, output to team buckets | Phase 4 |
| **6. Eval set** | Manually label 50–100 entries, measure accuracy | Phase 2 |
| **7. Dashboard** | Streamlit app: triage table, metrics, live demo | Phases 4, 5, 6 |
| **8. Polish** | README, cleanup, final metrics, screenshots | Phase 7 |
