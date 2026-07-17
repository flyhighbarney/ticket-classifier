# SharkNinja AI Ticket Classifier

An end-to-end system that scrapes real Amazon reviews, classifies them into support categories using HuggingFace models, and routes them to the right team. No OpenAI, no Claude, no paid APIs anywhere in the pipeline.

Built it to answer a question I kept running into: can you build a useful AI triage system using only open-source models that run on a laptop?

The short answer is yes, with caveats. The system works. It classifies tickets, generates draft replies, and routes them. But zero-shot classification on messy review text hits a confidence ceiling that fine-tuning would blow past. More on that below.

## What it actually does

1. **Scrapes Amazon reviews** for Shark and Ninja products using Selenium (500 reviews across coffee makers, vacuums, and blenders)
2. **Classifies each review** into support categories (warranty, troubleshooting, product question, return request) using zero-shot classification
3. **An agent loop** decides what to do with each ticket: classify it, draft a reply, escalate it, or ask for clarification
4. **Routes tickets** to team buckets (Warranty Ops, Tech Support, Sales, Returns) based on category and confidence
5. **A Flask dashboard** shows system performance, a live demo with agent trace visualization, and a chatbot for asking questions about the data

## The data: before and after

The raw dataset is messy on purpose. These are real Amazon reviews, not synthetic data. Here's what the pipeline takes in vs. what comes out:

### Raw input (straight from Amazon)

| Text | Stars |
|------|-------|
| `Perfect !!! - i have a K15 and was concerned it wouldnt fit  but it was PERFECT !!!` | 5 |
| `WORST Reusable Coffee Filter EVER! - It lets the coffee flow out the top of it and into your cup!..Also the holes are TOO big` | 1 |
| `horrid - thin and chinsy i could even bother returning it i threw them out` | 1 |
| `just ok - These are ok... I am always looking for ways to make my Keurig more cost efficient` | 3 |

No labels, no categories, no structure. Typos, slang, multiple exclamation marks, run-on sentences. This is what real customer text looks like.

### After classification

| Text (truncated) | Category | Confidence | Tier | Team |
|---|---|---|---|---|
| `WORST Reusable Coffee Filter EVER!...` | warranty_claim | 56.2% | flagged | Warranty Ops |
| `horrid - thin and chinsy...` | return_request | 46.7% | escalate | Returns |
| `One Star - Did not fit either one of my Keurig Machines so sent it back for a refund` | return_request | 65.7% | auto_route | Returns |
| `single cup reusable - I was a little disappointed that it doesn't quite fit...` | troubleshooting | 78.8% | auto_route | Tech Support |

Each ticket now has a category, a confidence score, a routing tier (auto_route/flagged/escalate), and a team assignment. The system also generates draft replies for tickets it's confident about.

### Overall numbers

- **500 tickets** classified
- **35.2%** product questions, **22.2%** returns, **21.6%** troubleshooting, **21.0%** warranty claims
- **7.4%** auto-routed (confidence >= 65%)
- **17.8%** flagged for review (50-64%)
- **74.8%** escalated (< 50%)
- **43.6%** average confidence

That escalation rate is high. It's the honest tradeoff of zero-shot classification on noisy data, and I left it visible on purpose. A hiring manager looking at this should see that I measured the gap, not that I hid it.

## Why HuggingFace (and why these specific models)

I used two models, both running locally:

**facebook/bart-large-mnli** for classification. It's a zero-shot classifier, meaning it can categorize text into labels it has never been trained on. You give it a review and candidate labels like "warranty claim or defective product" and it scores each one. I picked it because:
- No labeled training data needed. I scraped 500 reviews with no labels and classified them immediately.
- It runs on CPU in under a second per ticket.
- The alternative was fine-tuning a model, which requires labeled data I didn't have.

**google/flan-t5-base** for text generation (draft replies, agent reasoning). It's small (250M parameters) and limited, but it can extract product names and summarize issues well enough for template-based replies. I paired it with structured templates because flan-t5 alone writes repetitive responses.

**Ollama + Llama** (optional) for the chatbot and improved agent reasoning. When Ollama is running locally with a Llama model, the agent loop uses it for better action selection and the chatbot uses it to answer questions about the data. Falls back to flan-t5 when Ollama isn't available.

The paid API route (Claude, GPT-4) would obviously produce better classifications and replies. But the point was to see what's possible without spending per-token, which matters if you're deploying to production at scale.

## How the agent loop works

This is not a scripted pipeline. The agent receives each ticket and decides what to do:

```
Customer text arrives
    |
    v
Agent model reads text, picks action:
    classify / draft / escalate / clarify
    |
    +-- classify --> BART zero-shot --> confidence score
    |                   |
    |                   +-- conf < 50%? --> retry with hint text
    |                   +-- conf >= 65%? --> auto-route
    |                   +-- 50-64%? --> flag for review
    |
    +-- draft --> classify first, then flan-t5 extracts
    |             product + issue, template builds reply
    |
    +-- escalate --> straight to manual review
    |
    +-- clarify --> flan-t5 generates clarifying question
    |
    v
Route to team bucket (JSON file in output/<team>/)
```

If the agent's output doesn't parse as valid JSON (which happens with small models), it falls back to a deterministic scripted pipeline. Every decision is logged to an agent trace, which the dashboard visualizes step by step.

## Project structure

```
ticket-classifier/
    scraper/
        config.py          # Product ASINs, request settings
        browser.py         # Selenium Edge with persistent login
        scrape_reviews_sel.py  # Review scraper with anti-bot handling
        scrape_qa_sel.py   # Q&A scraper (limited by JS rendering)
        scrape_live.py     # CLI entry point
    agent/
        schema.py          # Categories, thresholds, routing map
        models.py          # BART + flan-t5 loading (lazy, GPU-aware)
        actions.py         # classify() and draft_reply()
        loop.py            # Agent loop with retry + fallback
        fallback.py        # Deterministic scripted pipeline
        routing.py         # Route to team output buckets
        chatbot.py         # Data-aware chatbot (Llama/flan-t5)
    app/
        flask_app.py       # Flask routes (dashboard, demo, chat, API)
        templates/
            dashboard.html # Performance metrics + triage table
            demo.html      # Live demo with agent trace visualization
            chat.html      # Chatbot for asking about the data
    data/
        raw_scraped.csv    # 500 raw Amazon reviews (messy, real)
        classified_results.csv  # Same 500 with classifications
    docs/
        design.html        # UI mockup reference
    test_agent.py          # Agent loop integration test
    test_classifier.py     # Classification accuracy test
```

## Setup

```bash
git clone https://github.com/flyhighbarney/ticket-classifier.git
cd ticket-classifier
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### Run the dashboard

```bash
python -m app.flask_app
# Open http://localhost:5000
```

### Run the agent test

```bash
python test_agent.py
```

### Optional: better agent + chatbot with Ollama

```bash
# Install Ollama from https://ollama.com
ollama pull llama3.2
# The system auto-detects Ollama and uses Llama for agent reasoning + chatbot
```

## What I'd improve with more time

- **Fine-tune BART on labeled data.** The 74.8% escalation rate comes from zero-shot confidence being low on informal text. Even 200 labeled examples would push auto-route rates past 50%.
- **Streaming agent trace.** Right now the demo page waits for the full result. Server-sent events would show each step as it happens.
- **Better draft replies.** flan-t5-base is too small for nuanced customer communication. A fine-tuned T5-large or Llama-based generator would produce replies worth sending.
- **Q&A scraping.** Amazon's Q&A section is heavily JS-rendered. A headless browser with better wait strategies could capture it.
- **Evaluation framework.** I'd build a human-labeled eval set of 100 tickets and measure precision/recall per category, not just confidence scores.

## Tools used

- Python 3.11
- HuggingFace Transformers (BART, flan-t5)
- Selenium + Edge WebDriver
- Flask
- Tailwind CSS (CDN)
- Ollama (optional, for Llama)

---

Built by Geffrey A. as a portfolio project for the SharkNinja Controls Engineering Co-op.

Co-Authored-By: Claude <noreply@anthropic.com>
