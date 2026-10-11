#!/usr/bin/env python3
"""Rebuild data/editions.json from every file in data/editions/.

Run this after the pipeline writes or edits an edition:
    python3 scripts/build_manifest.py
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
EDITIONS = ROOT / "data" / "editions"
MANIFEST = ROOT / "data" / "editions.json"


def main() -> None:
    entries = []
    for path in sorted(EDITIONS.glob("*.json")):
        ed = json.loads(path.read_text(encoding="utf-8"))
        articles = ed.get("articles", [])
        lead = min((a for a in articles if a.get("front_page_rank")),
                   key=lambda a: a["front_page_rank"], default=articles[0] if articles else None)
        statuses = {}
        for a in articles:
            s = a.get("verification", {}).get("status", "unverified")
            statuses[s] = statuses.get(s, 0) + 1
        entries.append({
            "date": ed["date"],
            "edition_number": ed["edition_number"],
            "published_at": ed["published_at"],
            "status": ed.get("status", "draft"),
            "is_demo": ed.get("is_demo", False),
            "lead_headline": lead["headline"] if lead else None,
            "article_count": len(articles),
            "verification_counts": statuses,
            "path": f"editions/{path.name}",
        })
    entries.sort(key=lambda e: e["date"], reverse=True)
    manifest = {"schema_version": "1.0", "editions": entries}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {MANIFEST.relative_to(ROOT)} with {len(entries)} editions.")


if __name__ == "__main__":
    main()
