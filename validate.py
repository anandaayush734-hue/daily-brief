#!/usr/bin/env python3
"""Check every edition file against the rules the front end relies on.

    python3 scripts/validate.py          # exits 1 if any errors

Uses only the standard library so it can run in any CI or cron job.
See docs/DATA_SCHEMA.md for the field reference.
"""
import json
import pathlib
import re
import sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = json.loads((ROOT / "data" / "site.json").read_text(encoding="utf-8"))
SECTIONS = {s["slug"] for s in SITE["sections"]}
STATUSES = set(SITE["verification_statuses"])
EDITION_STATUSES = {"draft", "scheduled", "published"}
REQUIRED_ARTICLE = ["id", "section", "category", "headline", "summary", "why_it_matters",
                    "published_at", "source", "verification"]


def iso(value: str) -> bool:
    try:
        dt = datetime.fromisoformat(value)
        return dt.tzinfo is not None
    except (TypeError, ValueError):
        return False


def check_edition(path: pathlib.Path) -> list[str]:
    errs: list[str] = []
    ed = json.loads(path.read_text(encoding="utf-8"))
    p = path.name
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ed.get("date", "")):
        errs.append(f"{p}: 'date' must be YYYY-MM-DD")
    if path.stem != ed.get("date"):
        errs.append(f"{p}: filename must match the edition date")
    if not isinstance(ed.get("edition_number"), int):
        errs.append(f"{p}: 'edition_number' must be an integer")
    if not iso(ed.get("published_at")):
        errs.append(f"{p}: 'published_at' must be ISO 8601 with a timezone offset")
    if ed.get("status") not in EDITION_STATUSES:
        errs.append(f"{p}: 'status' must be one of {sorted(EDITION_STATUSES)}")

    ids, ranks = set(), []
    for i, a in enumerate(ed.get("articles", [])):
        where = f"{p} article[{i}] ({a.get('id', '?')})"
        for f in REQUIRED_ARTICLE:
            if not a.get(f):
                errs.append(f"{where}: missing '{f}'")
        if a.get("id") in ids:
            errs.append(f"{where}: duplicate id")
        ids.add(a.get("id"))
        if a.get("section") not in SECTIONS:
            errs.append(f"{where}: unknown section '{a.get('section')}'")
        if a.get("published_at") and not iso(a["published_at"]):
            errs.append(f"{where}: 'published_at' needs a timezone offset")
        src = a.get("source") or {}
        needs_link = src.get("type") != "ai"  # AI-written explainers/analysis may have no external link
        if needs_link and not str(src.get("url", "")).startswith(("http://", "https://")):
            errs.append(f"{where}: source.url must be an http(s) link")
        status = (a.get("verification") or {}).get("status")
        if status not in STATUSES:
            errs.append(f"{where}: verification.status '{status}' is not in site.json")
        if status == "demo" and not a.get("is_demo"):
            errs.append(f"{where}: demo stories must set is_demo: true")
        if not ed.get("is_demo") and a.get("is_demo"):
            errs.append(f"{where}: demo story inside a non-demo edition")
        if a.get("front_page_rank"):
            ranks.append(a["front_page_rank"])
        for block in a.get("body", []):
            if isinstance(block, dict) and block.get("type") not in {"p", "h2", "quote", "list"}:
                errs.append(f"{where}: unsupported body block type '{block.get('type')}'")
    if len(ranks) != len(set(ranks)):
        errs.append(f"{p}: front_page_rank values must be unique")
    for w in ed.get("watchlist", []):
        if not w.get("title") or not w.get("date"):
            errs.append(f"{p} watchlist {w.get('id', '?')}: needs title and date")
    return errs


def main() -> int:
    errors = []
    files = sorted((ROOT / "data" / "editions").glob("*.json"))
    for f in files:
        errors += check_edition(f)
    for e in errors:
        print("ERROR", e)
    print(f"Checked {len(files)} editions: {len(errors)} errors.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
