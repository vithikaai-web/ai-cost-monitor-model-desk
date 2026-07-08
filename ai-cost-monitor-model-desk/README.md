# Model Desk — live AI pricing & capability dashboard

A weekly-refreshing dashboard tracking list pricing and context windows across
Anthropic, OpenAI, Google, DeepSeek, xAI, Meta, and Mistral.

## How it works (the four building blocks)

| Block | Implementation |
|---|---|
| **Source** | `scripts/fetch_pricing.py` pulls the public OpenRouter model catalog (no API key needed) |
| **Schedule** | `.github/workflows/refresh.yml` — a GitHub Action, cron `0 6 * * 1` (every Monday 06:00 UTC) |
| **Store** | `data/models.json` — committed back to the repo by the Action every run |
| **Serve** | `index.html` fetches `data/models.json` at page-load time; hosted via GitHub Pages |

The sync script only auto-updates **facts** (price, context window). Anything
it can't confidently match against your existing list gets added with
`"tier": "unreviewed"` and `"reviewed": false` — those need a human look before
they mean anything on the Capability tab. Check `data/last_run_diff.md` after
each run to see exactly what changed.

## Hosting: GitHub Pages vs. Vercel

Either works — both are free and both auto-deploy from this same repo. Pick one.

### Option A: GitHub Pages
See "One-time setup" below.

### Option B: Vercel (recommended if you want a nicer dashboard, preview URLs per branch, and faster global CDN)

1. Push this repo to GitHub (steps below) first — Vercel deploys *from* GitHub, it doesn't replace it.
2. Go to vercel.com → sign in with your GitHub account (one click, no separate password).
3. Click **Add New → Project**, and pick this repo from the list.
4. On the import screen: Framework Preset = **Other** (there's no build step — this is plain HTML/JS). Leave Build Command and Output Directory blank/default. Click **Deploy**.
5. ~10 seconds later you get a live URL like `model-desk-<random>.vercel.app`.
6. **The important part**: you don't have to do anything else. Vercel auto-deploys on every push to `main` by default — and our GitHub Action already pushes to `main` every Monday. So the weekly bot commit *is* the weekly redeploy trigger. No Vercel-side cron needed.
7. `vercel.json` in this repo sets `Cache-Control: must-revalidate` on `data/models.json` specifically — without it, Vercel's CDN could serve a cached copy of last week's data for a while after a redeploy. This makes sure this week's numbers show up immediately.
8. To verify the whole loop end-to-end: Actions tab → run the workflow manually → within a minute, check the Vercel dashboard's Deployments list → you should see a new deployment appear on its own, with no Vercel-specific action from you.

## One-time setup (GitHub — required for both hosting options)



1. **Create a GitHub repo** (github.com → New repository → e.g. `model-desk`, public is fine and free).
2. **Push these files** to it:
   ```bash
   cd model-desk
   git init
   git add .
   git commit -m "Initial dashboard"
   git branch -M main
   git remote add origin https://github.com/<your-username>/model-desk.git
   git push -u origin main
   ```
3. **Turn on GitHub Pages**: repo → Settings → Pages → under "Build and deployment", Source = "Deploy from a branch" → Branch = `main`, folder = `/ (root)` → Save.
   Your live URL will be `https://<your-username>.github.io/model-desk/` (takes ~1 minute to go live after saving).
4. **Test the Action without waiting for Monday**: repo → Actions tab → "Weekly pricing refresh" → "Run workflow" button → Run. Watch it go green. Check that it committed (repo → commits) and that `data/last_run_diff.md` shows something sensible.
5. Done. It now runs itself every Monday.

## Updating something by hand

You don't need to wait for the bot for anything judgment-based:

- **Change a tier or use-case pick**: edit `data/models.json` (or the `USE_CASES` array inside `index.html` for the Capability tab), commit, push. Live in ~30 seconds.
- **Add a lab the bot doesn't cover**: add the provider to `PROVIDER_MAP` in `fetch_pricing.py` *and* to `PROV_COLOR` in `index.html`.
- **Review the bot's new additions**: filter `data/models.json` for `"reviewed": false`, decide on a real tier, flip it to `true`.

## Troubleshooting

- **Blank page / dashboard stuck on "loading…"** — you're probably viewing `index.html` by double-clicking it. `fetch()` needs a real server; GitHub Pages provides one, but locally you need to run `python3 -m http.server` in this folder and open `http://localhost:8000` — opening the file directly (`file://...`) will always fail this fetch, that's a browser security rule, not a bug in this code.
- **Action fails at the push step** — check that repo → Settings → Actions → General → Workflow permissions is set to "Read and write permissions." (`contents: write` in the workflow file only works if the repo-level setting allows it.)
- **Action stopped running on its own** — GitHub automatically disables *scheduled* workflows after 60 days with no repo activity. A `git push` of any kind (even editing this README) resets that clock. If it's been quiet for a while, go to the Actions tab and re-enable it.
- **A price looks wrong** — check `orId` in that model's entry in `data/models.json`; that's the exact OpenRouter slug it was matched against, useful for spotting a bad match versus a real provider price change.
