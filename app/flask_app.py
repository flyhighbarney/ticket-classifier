"""
Flask dashboard — dark theme matching design.html.
Routes: dashboard, triage table, live demo with agent trace.
"""

import csv
import json
import sys
import time
from pathlib import Path

from flask import Flask, render_template, request, jsonify

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.loop import process_ticket_agent
from agent.routing import route_ticket, get_routing_stats
from agent.chatbot import chat as chatbot_chat

app = Flask(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data"
CLASSIFIED_PATH = DATA_PATH / "classified_results.csv"


def _load_classified():
    if not CLASSIFIED_PATH.exists():
        return []
    with open(CLASSIFIED_PATH, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _compute_stats(rows):
    from collections import Counter
    total = len(rows)
    if total == 0:
        return {}

    tiers = Counter(r.get("tier", "") for r in rows)
    cats = Counter(r.get("category", "") for r in rows)
    confs = [float(r["confidence"]) for r in rows if r.get("confidence")]

    auto = tiers.get("auto_route", 0)
    escalate = tiers.get("escalate", 0)
    flagged = tiers.get("flagged", 0)

    return {
        "total": total,
        "auto_route_rate": round(100 * auto / total, 1),
        "escalation_rate": round(100 * escalate / total, 1),
        "flagged_rate": round(100 * flagged / total, 1),
        "avg_confidence": round(sum(confs) / len(confs) * 100, 1) if confs else 0,
        "categories": dict(cats.most_common()),
        "tiers": dict(tiers),
    }


@app.route("/")
def dashboard():
    rows = _load_classified()
    stats = _compute_stats(rows)
    return render_template("dashboard.html", stats=stats, rows=rows[:50])


@app.route("/demo")
def demo():
    return render_template("demo.html")


@app.route("/chat")
def chat_page():
    return render_template("chat.html")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    question = data.get("question", "")
    if not question.strip():
        return jsonify({"error": "No question provided"}), 400

    result = chatbot_chat(question)
    return jsonify(result)


@app.route("/chat")
def chat_page():
    return render_template("chat.html")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    question = data.get("question", "")
    if not question.strip():
        return jsonify({"error": "No question provided"}), 400

    result = chatbot_chat(question)
    return jsonify(result)


@app.route("/api/process", methods=["POST"])
def api_process():
    data = request.get_json()
    text = data.get("text", "")
    if not text.strip():
        return jsonify({"error": "No text provided"}), 400

    ticket_id = "DEMO-{:.0f}".format(time.time())
    result = process_ticket_agent(text)
    route_ticket(ticket_id, result, text)

    return jsonify({
        "ticket_id": ticket_id,
        **result,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
