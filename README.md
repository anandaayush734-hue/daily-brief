# The Daily Brief

A personal digital newspaper for finance, markets, deals, policy, trade, technology and climate finance.

**All stories in the included editions are fictional demonstration content.** Each carries a `demo` verification status, a demo badge and a placeholder `example.com` source link.

## Stack

Plain HTML, CSS and JavaScript with JSON data files. No framework, no build step, no dependencies. It runs on any static host (GitHub Pages, Netlify, Cloudflare Pages, S3) and the pipeline only has to write JSON files.

```
index.html                 page shell
assets/css/style.css       all styling, incl. responsive and print rules
assets/js/components.js    reusable components: ArticleCard, Badge, Body, SourceBox, Watchlist…
assets/js/app.js           data loading, hash router and page views
data/site.json             sections, homepage order, timezone, verification labels
data/editions.json         manifest of editions (generated)
data/editions/*.json       one file per edition
scripts/validate.py        checks every edition against the schema
scripts/build_manifest.py  regenerates data/editions.json
scripts/ingest_rss.py      step 1: RSS/Atom feeds -> draft edition
scripts/summarise.py       step 2: AI picks, sections and summarises stories
scripts/feeds.json         news sources
.github/workflows/         daily schedule (06:00 IST)
SETUP_GUIDE.md             beginner setup guide
scripts/build_standalone.py  bundles site + data into one offline HTML file
docs/DATA_SCHEMA.md        field reference
```

## Run it locally

```bash
cd daily-brief
python3 -m http.server 8000
# open http://localhost:8000
```

Browsers block `fetch()` from `file://`, so serve the folder rather than double-clicking `index.html`. For an offline single file, run `python3 scripts/build_standalone.py` and open `dist/daily-brief.html`.

## Pages

| Route | Page |
|---|---|
| `#/` | Latest published edition |
| `#/edition/2026-10-10` | A previous edition |
| `#/edition/<date>/section/deals` | All stories in one section |
| `#/edition/<date>/article/<id>` | Article page (print-friendly) |
| `#/archive` | Previous editions |
| `#/search/<query>` | Search across all editions, with a section filter |

## Adding an edition

1. Write `data/editions/YYYY-MM-DD.json` (see `docs/DATA_SCHEMA.md`).
2. `python3 scripts/validate.py`
3. `python3 scripts/build_manifest.py`
4. Deploy the folder.

Sections and homepage order live in `data/site.json`, so you can add, rename or reorder sections without touching code.

## Daily automation (GitHub Actions)

**New to this? Follow `SETUP_GUIDE.md` step by step.**

```
06:00 IST  ingest_rss.py  ->  summarise.py (your AI)  ->  validate.py  ->  build_manifest.py  ->  commit  ->  GitHub Pages
           headlines from     picks stories, sections,     schema check     edition list          archive
           scripts/feeds.json front page, summaries
```

- `.github/workflows/daily-edition.yml` runs the steps every day at 06:00 IST, and on demand from the Actions tab.
- `scripts/summarise.py` works with Claude, GPT, Gemini or Grok (`AI_PROVIDER`), and can use a second AI as a checker (`CHECKER_PROVIDER`).
- The AI sees only headlines and feed snippets and is instructed not to add facts. Every story keeps its original link and stays marked **Unverified** until someone checks it.
- To review before publishing, remove `--publish` from the workflow: editions are then saved as drafts and you flip `status` to `published` yourself.

## Notes

- All content from JSON is HTML-escaped before rendering, and only `http(s)` source links are rendered as links.
- Search runs in the browser across all editions. Past a few hundred editions, generate a search index at build time instead.
- Times display in `Asia/Kolkata` (set in `site.json`).
