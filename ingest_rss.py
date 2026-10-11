#!/usr/bin/env python3
"""Step 1 of the daily pipeline: collect fresh headlines from RSS/Atom feeds.

    python3 scripts/ingest_rss.py --feeds scripts/feeds.json
    python3 scripts/ingest_rss.py --feeds scripts/feeds.json --date 2026-10-13 --max-age-hours 36

Writes data/editions/<date>.json as a DRAFT with every item marked "unverified".
Step 2 (scripts/summarise.py) turns that draft into the finished edition.
Standard library only. Only use feeds you are allowed to use, and keep the original links.
"""
import argparse
import hashlib
import html
import json
import pathlib
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
EDITIONS = ROOT / "data" / "editions"
IST = timezone(timedelta(hours=5, minutes=30))
ATOM = "{http://www.w3.org/2005/Atom}"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DailyBrief personal reader)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()


def parse_date(value):
    """Return an aware datetime in IST, or None. Feeds often omit the timezone; assume IST then."""
    if not value:
        return None
    value = value.strip()
    dt = None
    try:
        dt = parsedate_to_datetime(value)  # RFC 822, e.g. "Sat, 10 Oct 2026 01:25:00 GMT"
    except (TypeError, ValueError, IndexError):
        pass
    if dt is None:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))  # ISO 8601 (Atom)
        except ValueError:
            m = re.match(r"(\d{1,2}) (\w{3}),? (\d{4})(?: ([+-]\d{4}))?", value)  # e.g. "09 Oct, 2026 +0530"
            if not m:
                return None
            try:
                dt = datetime.strptime(f"{m[1]} {m[2]} {m[3]} {m[4] or '+0530'}", "%d %b %Y %z")
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def fix_link(link: str) -> str:
    link = (link or "").strip()
    m = re.match(r"^(https?://[^/]+)/(https?://.*)$", link)  # e.g. a feed that repeats its own domain
    return m.group(2) if m else link


def parse_items(xml: bytes):
    root = ET.fromstring(xml)
    for item in root.iter("item"):  # RSS 2.0
        src = item.find("source")
        yield {
            "title": clean(item.findtext("title")),
            "link": fix_link(item.findtext("link")),
            "summary": clean(item.findtext("description")),
            "published": item.findtext("pubDate"),
            "source_name": clean(src.text) if src is not None and src.text else None,
        }
    for entry in root.iter(f"{ATOM}entry"):  # Atom
        link = entry.find(f"{ATOM}link")
        yield {
            "title": clean(entry.findtext(f"{ATOM}title")),
            "link": fix_link(link.get("href", "") if link is not None else ""),
            "summary": clean(entry.findtext(f"{ATOM}summary") or entry.findtext(f"{ATOM}content")),
            "published": entry.findtext(f"{ATOM}updated") or entry.findtext(f"{ATOM}published"),
            "source_name": None,
        }


def next_edition_number(date: str) -> int:
    best = 0
    for p in EDITIONS.glob("*.json"):
        if p.stem == date:
            continue
        try:
            best = max(best, int(json.loads(p.read_text(encoding="utf-8")).get("edition_number", 0)))
        except (ValueError, json.JSONDecodeError):
            pass
    return best + 1


def main() -> None:
    now = datetime.now(IST)
    ap = argparse.ArgumentParser()
    ap.add_argument("--feeds", required=True, help="JSON list of {id, name, url, section, category, max_items}")
    ap.add_argument("--date", default=now.strftime("%Y-%m-%d"), help="Edition date (default: today in IST)")
    ap.add_argument("--edition-number", type=int, default=None, help="Default: highest existing + 1")
    ap.add_argument("--max-age-hours", type=int, default=36, help="Skip items older than this")
    ap.add_argument("--publish-time", default="06:00", help="HH:MM IST")
    args = ap.parse_args()

    feeds = json.loads(pathlib.Path(args.feeds).read_text(encoding="utf-8"))
    cutoff = now - timedelta(hours=args.max_age_hours)
    seen_links, seen_titles, articles = set(), set(), []
    for feed in feeds:
        try:
            items = list(parse_items(fetch(feed["url"])))
        except Exception as exc:  # one broken feed must not stop the edition
            print(f"  skip {feed['id']}: {exc}")
            continue
        kept = 0
        for it in items:
            if kept >= feed.get("max_items", 8):
                break
            title_key = re.sub(r"\W+", " ", it["title"].lower()).strip()[:90]
            if not it["link"].startswith("http") or not it["title"] or it["link"] in seen_links or title_key in seen_titles:
                continue
            published = parse_date(it["published"])
            if published and published < cutoff:
                continue
            published = published or now
            seen_links.add(it["link"])
            seen_titles.add(title_key)
            kept += 1
            uid = hashlib.sha1(it["link"].encode()).hexdigest()[:10]
            ts = published.isoformat(timespec="seconds")
            articles.append({
                "id": f"{args.date}-{feed['section']}-{uid}",
                "section": feed["section"],
                "category": feed.get("category", feed["section"]),
                "front_page_rank": None,
                "headline": it["title"],
                "dek": "",
                "summary": it["summary"][:700] or it["title"],
                "body": [],
                "why_it_matters": "",
                "implications": [],
                "author": None,
                "published_at": ts,
                "updated_at": None,
                "source": {"name": it["source_name"] or feed["name"], "url": it["link"], "published_at": ts, "type": "rss"},
                "verification": {"status": "unverified", "checked_by": None, "checked_at": None,
                                 "notes": "Collected automatically from the publisher's feed. Not checked."},
                "tags": [],
                "is_demo": False,
                "pipeline": {"feed_id": feed["id"], "ingested_at": now.isoformat(timespec="seconds"),
                             "summarised_by": None, "summary_model": None},
            })
        print(f"  {feed['id']}: {kept} items")

    edition = {
        "schema_version": "1.0",
        "edition_number": args.edition_number or next_edition_number(args.date),
        "date": args.date,
        "published_at": f"{args.date}T{args.publish_time}:00+05:30",
        "status": "draft",
        "is_demo": False,
        "editor_note": "",
        "articles": articles,
        "watchlist": [],
    }
    EDITIONS.mkdir(parents=True, exist_ok=True)
    out = EDITIONS / f"{args.date}.json"
    out.write_text(json.dumps(edition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote draft {out.relative_to(ROOT)} with {len(articles)} items.")
    if not articles:
        raise SystemExit("No items collected. Check the feed URLs in your feeds file.")


if __name__ == "__main__":
    main()
