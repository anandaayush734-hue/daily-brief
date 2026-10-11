#!/usr/bin/env python3
"""Step 2 of the daily pipeline: let an AI model edit the draft edition.

    python3 scripts/summarise.py                 # edits today's draft (IST)
    python3 scripts/summarise.py --publish       # ...and marks it published
    python3 scripts/summarise.py --date 2026-10-13

The model picks the most relevant stories, assigns sections and the five front-page
slots, and writes the summary, "Why it matters" and implications for each. It also writes
one Analyst's Corner piece and one Learn Something New explainer.

It only sees each story's headline and feed snippet, so it is told not to add facts.
Every story stays "unverified" and keeps its link to the original publisher.

Choose the AI with environment variables (set them as GitHub Secrets/Variables):
    AI_PROVIDER   anthropic | openai | gemini | xai        (default: anthropic)
    AI_MODEL      model ID for that provider               (default for anthropic: claude-haiku-5-5)
    ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY / XAI_API_KEY

Optional second opinion from a different AI:
    CHECKER_PROVIDER, CHECKER_MODEL   compares each summary with its headline and snippet
                                      and records any problems in the story's verification notes.
Standard library only.
"""
import argparse
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))
SITE = json.loads((ROOT / "data" / "site.json").read_text(encoding="utf-8"))
NEWS_SECTIONS = [s for s in SITE["sections"] if s["slug"] not in ("analysis", "learn")]

PROVIDERS = {
    "anthropic": {"key": "ANTHROPIC_API_KEY", "default_model": "claude-haiku-5-5"},
    "openai": {"key": "OPENAI_API_KEY", "base": "https://api.openai.com/v1"},
    "gemini": {"key": "GEMINI_API_KEY", "base": "https://generativelanguage.googleapis.com/v1beta/openai"},
    "xai": {"key": "XAI_API_KEY", "base": "https://api.x.ai/v1"},
}


# ------------------------------------------------------------------ AI call
def _post(url: str, headers: dict, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json", **headers})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            if e.code in (429, 500, 502, 503, 529) and attempt < 2:
                time.sleep(20 * (attempt + 1))
                continue
            raise SystemExit(f"AI request failed ({e.code}): {detail}")
    raise SystemExit("AI request failed after retries.")


def ask(provider: str, model: str, system: str, prompt: str) -> str:
    cfg = PROVIDERS.get(provider)
    if not cfg:
        raise SystemExit(f"Unknown AI provider '{provider}'. Use one of: {', '.join(PROVIDERS)}")
    key = os.environ.get(cfg["key"])
    if not key:
        raise SystemExit(f"Missing {cfg['key']}. Add it as a GitHub Secret (see SETUP_GUIDE.md).")
    model = model or cfg.get("default_model")
    if not model:
        raise SystemExit(f"Set AI_MODEL for provider '{provider}'.")
    if provider == "anthropic":
        data = _post("https://api.anthropic.com/v1/messages",
                     {"x-api-key": key, "anthropic-version": "2023-06-01"},
                     {"model": model, "max_tokens": 16000, "system": system,
                      "messages": [{"role": "user", "content": prompt}]})
        return "".join(b.get("text", "") for b in data.get("content", []))
    data = _post(f"{cfg['base']}/chat/completions", {"authorization": f"Bearer {key}"},
                 {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]})
    return data["choices"][0]["message"]["content"]


def ask_json(provider, model, system, prompt) -> dict:
    for attempt in range(2):
        text = ask(provider, model, system, prompt)
        m = re.search(r"\{.*\}", text, re.S)
        try:
            return json.loads(m.group(0) if m else text)
        except (json.JSONDecodeError, AttributeError):
            if attempt == 0:
                prompt += "\n\nYour last reply was not valid JSON. Reply with the JSON object only."
    raise SystemExit("The AI did not return valid JSON twice in a row.")


# ------------------------------------------------------------------ prompts
SYSTEM = """You are the night editor of The Daily Brief, a personal newspaper for a reader in India who follows
investment banking, M&A, IPOs, capital markets, the Indian economy (RBI, SEBI, rates, policy), global markets,
corporate earnings and strategy, trade and geopolitics, technology and AI, and climate finance.

Accuracy rules, which override everything else:
- Use ONLY facts stated in each item's headline and snippet. Never add numbers, names, dates, quotes or causes that are not there.
- If a snippet is thin, keep the summary short and say only what the headline supports.
- "Why it matters" and implications may explain general context and mechanisms, but must not state new facts about the event.
- Write in plain, neutral British English. No hype, no investment advice.
Reply with a single JSON object and nothing else."""


def edit_prompt(items: list[dict], max_stories: int) -> str:
    sections = "\n".join(f'- "{s["slug"]}": {s["name"]} ({s["description"]})' for s in NEWS_SECTIONS)
    listing = json.dumps([{"idx": i, "headline": a["headline"], "snippet": a["summary"][:450],
                           "source": a["source"]["name"], "feed_section": a["section"]} for i, a in enumerate(items)],
                         ensure_ascii=False)
    return f"""Here are today's candidate items:
{listing}

Tasks:
1. Choose up to {max_stories} items most relevant to the reader. Skip duplicates (same event from two sources: keep one),
   routine notices (minor enforcement orders, circulars of narrow interest) and anything off-topic.
2. For each chosen item give: section (one of the slugs below), a short category label (e.g. "M&A", "IPOs", "Monetary policy"),
   a 1-2 sentence summary, a 1-2 sentence why_it_matters, and 2 implications as {{"label": "For ...", "text": "..."}}.
3. Give exactly 5 chosen items a front_page_rank from 1 (lead) to 5, by importance to this reader; others get null.
4. Write one Analyst's Corner piece connecting 1-3 of today's chosen items (cite them by idx in based_on). It is commentary:
   explain mechanisms and what to watch, without new facts. 4-6 short paragraphs.
5. Write one Learn Something New explainer on a finance or business concept related to today's news.
   It must be standard, textbook-accurate material.

Sections:
{sections}

JSON shape:
{{"stories": [{{"idx": 0, "section": "deals", "category": "M&A", "front_page_rank": 1, "summary": "...",
   "why_it_matters": "...", "implications": [{{"label": "For acquirers", "text": "..."}}]}}],
 "analysis": {{"headline": "...", "dek": "...", "summary": "...", "body": ["paragraph", "..."], "why_it_matters": "...", "based_on": [0]}},
 "learn": {{"headline": "...", "dek": "...", "summary": "...", "body": ["paragraph", "..."],
   "key_takeaways": ["...", "..."], "why_it_matters": "..."}}}}"""


CHECK_SYSTEM = """You are a fact-checker. For each story, compare the summary, why_it_matters and implications with the
original headline and snippet. Flag any claim about the event that the headline/snippet does not support
(added numbers, names, causes, dates, or a wrong meaning). General context is fine. Reply with JSON only."""


# ------------------------------------------------------------------ main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(IST).strftime("%Y-%m-%d"))
    ap.add_argument("--max-stories", type=int, default=24)
    ap.add_argument("--publish", action="store_true", help="Mark the edition as published")
    args = ap.parse_args()

    path = ROOT / "data" / "editions" / f"{args.date}.json"
    ed = json.loads(path.read_text(encoding="utf-8"))
    items = ed["articles"]
    if not items:
        raise SystemExit("The draft has no items. Run ingest_rss.py first.")

    provider = (os.environ.get("AI_PROVIDER") or "anthropic").strip().lower()
    model = os.environ.get("AI_MODEL", "").strip() or PROVIDERS.get(provider, {}).get("default_model")
    print(f"Editing {len(items)} items with {provider}/{model} ...")
    out = ask_json(provider, model, SYSTEM, edit_prompt(items, args.max_stories))

    slugs = {s["slug"] for s in NEWS_SECTIONS}
    now = datetime.now(IST).isoformat(timespec="seconds")
    chosen, used_ranks = [], set()
    for s in out.get("stories", []):
        i = s.get("idx")
        if not isinstance(i, int) or not 0 <= i < len(items):
            continue
        a = dict(items[i])
        a["section"] = s.get("section") if s.get("section") in slugs else a["section"]
        a["category"] = (s.get("category") or a["category"])[:40]
        rank = s.get("front_page_rank")
        a["front_page_rank"] = rank if isinstance(rank, int) and 1 <= rank <= 5 and rank not in used_ranks else None
        if a["front_page_rank"]:
            used_ranks.add(rank)
        a["summary"] = s.get("summary") or a["summary"]
        a["why_it_matters"] = s.get("why_it_matters") or "See the original source for details."
        a["implications"] = [x for x in s.get("implications", []) if isinstance(x, dict) and x.get("text")][:3]
        a["verification"] = {"status": "unverified", "checked_by": None, "checked_at": None,
                             "notes": "AI summary of the publisher's headline and snippet. Not checked against the full article."}
        a["pipeline"] = {**a.get("pipeline", {}), "summarised_by": provider, "summary_model": model}
        chosen.append(a)
    if not chosen:
        raise SystemExit("The AI selected no stories.")

    def written(kind: str, section: str, data: dict, status: str, notes: str, src: dict) -> dict:
        return {
            "id": f"{args.date}-{section}-01", "section": section, "category": "Analysis" if section == "analysis" else "Concept",
            "front_page_rank": None, "headline": data.get("headline", ""), "dek": data.get("dek", ""),
            "summary": data.get("summary", ""), "body": [p for p in data.get("body", []) if isinstance(p, str)],
            "why_it_matters": data.get("why_it_matters", ""), "implications": [],
            "key_takeaways": data.get("key_takeaways", []) or None,
            "author": kind, "published_at": now, "updated_at": None, "source": src,
            "verification": {"status": status, "checked_by": None, "checked_at": None, "notes": notes},
            "tags": [], "is_demo": False,
            "pipeline": {"feed_id": None, "ingested_at": None, "summarised_by": provider, "summary_model": model},
        }

    an = out.get("analysis") or {}
    if an.get("headline"):
        refs = [items[i] for i in an.get("based_on", []) if isinstance(i, int) and 0 <= i < len(items)]
        src = refs[0]["source"] if refs else {"name": "The Daily Brief", "url": "", "type": "ai"}
        names = "; ".join(f'{r["headline"]} ({r["source"]["name"]})' for r in refs)
        chosen.append(written("The Analyst's Corner (AI-written)", "analysis", an, "unverified",
                              f"AI-written commentary based on: {names or 'today’s stories'}. Opinion, not reporting.", dict(src)))
    ln = out.get("learn") or {}
    if ln.get("headline"):
        chosen.append(written("Learn Something New (AI-written)", "learn", ln, "evergreen",
                              "AI-written explainer of a standard concept. Does not report news.",
                              {"name": "The Daily Brief explainer", "url": "", "type": "ai"}))

    # Optional second AI cross-check
    cprov = os.environ.get("CHECKER_PROVIDER", "").strip().lower()
    if cprov:
        cmodel = os.environ.get("CHECKER_MODEL", "").strip() or PROVIDERS.get(cprov, {}).get("default_model")
        originals = {a["id"]: a for a in items}
        payload = [{"id": a["id"], "headline": originals[a["id"]]["headline"], "snippet": originals[a["id"]]["summary"][:450],
                    "summary": a["summary"], "why_it_matters": a["why_it_matters"], "implications": a["implications"]}
                   for a in chosen if a["id"] in originals]
        print(f"Cross-checking {len(payload)} stories with {cprov}/{cmodel} ...")
        res = ask_json(cprov, cmodel, CHECK_SYSTEM,
                       json.dumps(payload, ensure_ascii=False) +
                       '\n\nReply as {"problems": [{"id": "...", "issue": "..."}]} with an empty list if all are fine.')
        problems = {p.get("id"): p.get("issue", "") for p in res.get("problems", [])}
        for a in chosen:
            if a["id"] in problems:
                a["verification"]["notes"] += f" A second AI ({cprov}) flagged: {problems[a['id']]}"
            elif a["id"] in originals:
                a["verification"]["notes"] += f" Cross-checked by a second AI ({cprov}) against the headline and snippet; no problems found."

    ed["articles"] = chosen
    if args.publish:
        ed["status"] = "published"
        ed["published_at"] = min(ed["published_at"], now)
    path.write_text(json.dumps(ed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path.relative_to(ROOT)}: {len(chosen)} stories, front page ranks {sorted(used_ranks)}, status {ed['status']}.")


if __name__ == "__main__":
    sys.exit(main())
