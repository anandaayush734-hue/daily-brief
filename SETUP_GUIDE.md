# Setup guide: put The Daily Brief online with daily updates

No coding needed. Allow about 30–45 minutes. Everything happens in your web browser.

When you finish, your newspaper will live at `https://<your-username>.github.io/daily-brief/`
and will publish a new edition every morning at about **6:00 AM IST**.

---

## Step 1 — Create a GitHub account (5 min)

1. Go to **github.com** and click **Sign up**.
2. Pick a username. It becomes part of your website address.
3. Verify your email.

## Step 2 — Create a repository and upload the files (10 min)

A repository ("repo") is a folder on GitHub.

1. Click **+** (top right) → **New repository**.
2. Name: `daily-brief`. Choose **Public** (free GitHub Pages needs a public repo). Tick **Add a README file**. Click **Create repository**.
3. Unzip `daily-brief.zip` on your computer.
4. In your new repo, click **Add file → Upload files**.
5. Open the unzipped `daily-brief` folder and drag **everything inside it** (`index.html`, `assets`, `data`, `scripts`, `docs`, `README.md`, `SETUP_GUIDE.md`) into the browser window.
6. Click **Commit changes**.

## Step 3 — Add the daily automation file (5 min)

Folders starting with a dot are often hidden on your computer, so create this one directly on GitHub.

1. In the repo, click **Add file → Create new file**.
2. In the name box, type exactly: `.github/workflows/daily-edition.yml`
   (typing the `/` creates the folders).
3. Open `.github/workflows/daily-edition.yml` from the zip in a text editor (Notepad or TextEdit), copy everything, and paste it into GitHub.
   *If you can't see the `.github` folder, show hidden files: on Mac press `Cmd + Shift + .` in Finder; on Windows choose View → Show → Hidden items.*
4. Click **Commit changes**.

GitHub may immediately try to run it and show a red ✗ in the Actions tab. That is expected until you finish Steps 4–6.

## Step 4 — Turn on GitHub Pages (2 min)

1. In the repo, go to **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **GitHub Actions**.

## Step 5 — Get an AI API key (10 min)

Pick **one** AI to start. You need a developer API key. This is separate from a ChatGPT Plus or Claude Pro subscription and is billed by usage, so add a small amount of credit and set a monthly spending limit.

| AI | Where to get a key | Secret name | `AI_PROVIDER` value |
|---|---|---|---|
| Claude (Anthropic) | platform.claude.com → API keys | `ANTHROPIC_API_KEY` | `anthropic` |
| GPT (OpenAI) | platform.openai.com → API keys | `OPENAI_API_KEY` | `openai` |
| Gemini (Google) | aistudio.google.com → Get API key | `GEMINI_API_KEY` | `gemini` |
| Grok (xAI) | console.x.ai → API keys | `XAI_API_KEY` | `xai` |

**Keep the key private.** Never paste it into any file in the repo.

## Step 6 — Store the key safely in GitHub (3 min)

1. Repo **Settings → Secrets and variables → Actions**.
2. **Secrets** tab → **New repository secret**. Name: e.g. `ANTHROPIC_API_KEY`. Value: your key. Save.
3. **Variables** tab → **New repository variable**:
   - `AI_PROVIDER` = `anthropic` (or `openai`, `gemini`, `xai`)
   - `AI_MODEL` = the model ID to use. For Claude you can skip this (it defaults to `claude-haiku-5-5`, the low-cost model). For the others, copy a current model ID from that company's "models" documentation page.

## Step 7 — Run it once by hand (5 min)

1. Open the **Actions** tab. If asked, click **I understand my workflows, go ahead and enable them**.
2. Click **Daily edition** (left) → **Run workflow** → **Run workflow**.
3. Wait 1–3 minutes. A green tick means it worked. Click the run and then the link under **publish** to open your site.

From now on it runs by itself every morning. GitHub emails you if a run fails.

## Step 8 — Clean up the demo editions (optional)

Once your first real edition appears, delete the demo files in `data/editions/` (`2026-10-09.json`, `2026-10-10.json`, `2026-10-12.json`, and `2026-10-11.json` if it is still the demo). Open each file on GitHub → **⋯** menu → **Delete file** → **Commit changes**. The site redeploys automatically.

---

## Optional — Add a second AI as a checker

A second AI reads each summary next to the original headline and snippet and notes anything that looks added or wrong. Its comments appear in the **Source & verification** box on each article.

1. Add the second key as a secret (for example `GEMINI_API_KEY`).
2. Add variables `CHECKER_PROVIDER` = `gemini` and `CHECKER_MODEL` = a Gemini model ID.

Start with one AI for a week before adding this.

## Changing things later

| To change… | Edit this |
|---|---|
| Publish time | The `cron` line in `.github/workflows/daily-edition.yml` (it uses UTC; IST = UTC + 5:30) |
| News sources | `scripts/feeds.json` (each entry: name, RSS link, section) |
| Sections or their order | `data/site.json` |
| Number of stories | `--max-stories` in `scripts/summarise.py` (default 24) |

## What to expect

- **Stories are summaries, not full articles.** The AI only sees each headline and the short snippet in the feed, and every story links to the original publisher. Click through for the full story.
- **Stories are marked "Unverified".** Nobody has checked them against the full article. Treat them as a briefing, not as facts to act on.
- **Tomorrow's Watchlist will be empty** at first. A reliable events calendar is not in public RSS feeds, and the AI is not allowed to guess dates.
- **Feeds:** the included list uses RBI and SEBI press-release feeds and Google News searches. Google News feeds are meant for personal, non-commercial use. If a feed stops working, the run skips it and carries on.
- **Cost:** about 20–25 short summaries a day with a low-cost model is usually a small monthly amount, but check the provider's pricing page and set a spending limit.

## If something goes wrong

| What you see | What to do |
|---|---|
| Red ✗ with "Missing ANTHROPIC_API_KEY" | The secret name doesn't match. It must be spelled exactly as in the table above. |
| "Set AI_MODEL for provider…" | Add the `AI_MODEL` variable (Step 6). |
| "AI request failed (401)" | The key is wrong or expired. Create a new one and update the secret. |
| "AI request failed (402/429)" | Out of credit or rate-limited. Add credit or wait and re-run. |
| "No items collected" | All feeds failed. Check `scripts/feeds.json` links open in your browser. |
| Site shows the old edition | Check the Actions tab for a failed run. Then hard-refresh your browser. |
| Deploy step fails with a Pages error | Settings → Pages → Source must be **GitHub Actions** (Step 4). |
