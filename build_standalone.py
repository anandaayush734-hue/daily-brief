#!/usr/bin/env python3
"""Bundle the site and all published data into one self-contained HTML file.

    python3 scripts/build_standalone.py            -> dist/daily-brief.html
    python3 scripts/build_standalone.py --fragment -> dist/daily-brief-fragment.html
                                                     (no <html>/<head> wrapper, for hosts that add their own)

Useful for emailing an edition, opening offline, or hosting where fetch() is not available.
"""
import argparse
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fragment", action="store_true")
    args = ap.parse_args()

    bundle = {"site.json": json.loads((DATA / "site.json").read_text(encoding="utf-8")),
              "editions.json": json.loads((DATA / "editions.json").read_text(encoding="utf-8"))}
    for e in bundle["editions.json"]["editions"]:
        if e["status"] != "draft":
            bundle[e["path"]] = json.loads((DATA / e["path"]).read_text(encoding="utf-8"))

    css = (ROOT / "assets/css/style.css").read_text(encoding="utf-8")
    js = "\n".join((ROOT / f"assets/js/{n}.js").read_text(encoding="utf-8") for n in ("components", "app"))
    data_js = "window.DAILY_BRIEF_BUNDLE = " + json.dumps(bundle, ensure_ascii=False).replace("</", "<\\/") + ";"

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="assets/css/style.css">', f"<style>\n{css}\n</style>")
    html = re.sub(r'\s*<link rel="alternate"[^>]*>', "", html)
    html = re.sub(r'<script src="assets/js/components.js"></script>\s*<script src="assets/js/app.js"></script>',
                  lambda _: f"<script>\n{data_js}\n</script>\n<script>\n{js}\n</script>", html)

    if args.fragment:
        head = re.search(r"<head>(.*?)</head>", html, re.S).group(1)
        head = re.sub(r"<meta[^>]*>\s*", "", head)
        body = re.search(r"<body>(.*?)</body>", html, re.S).group(1)
        html = head.strip() + "\n" + body.strip() + "\n"
        out = ROOT / "dist" / "daily-brief-fragment.html"
    else:
        out = ROOT / "dist" / "daily-brief.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
