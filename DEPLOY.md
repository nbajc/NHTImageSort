# Deploy Nexus Hestia Image Sort — Step by Step

Live demo: `demo.nexushestia.com` (after step 6)

---

## What you're deploying

- **Backend** → Railway (Flask + SQLite, OpenAI for AI)
- **Frontend** → Vercel (React/Vite)
- **Cost** → Railway ~$5/mo after free tier, Vercel free

---

## Step 1 — Copy these files into your repo

From this `cloud-deploy/` folder, copy to the root of `NHTImageSort/`:

```
app.py          ← replaces your existing app.py
agents.py       ← replaces your existing agents.py
seed_demo.py    ← new file
requirements.txt ← replaces existing
Procfile        ← new file
railway.json    ← new file
.env.example    ← new file
.gitignore      ← replaces existing
frontend/vercel.json ← add to your frontend/ folder
```

```bash
# From this directory:
cp app.py agents.py seed_demo.py requirements.txt Procfile railway.json .env.example .gitignore ../
cp frontend/vercel.json ../frontend/
```

---

## Step 2 — Get an OpenAI API key

1. Go to https://platform.openai.com/api-keys
2. Create a new key
3. Keep it — you'll need it in Step 4

Cost: GPT-4o-mini vision is ~$0.001 per image. 100 demo images = ~$0.10.

---

## Step 3 — Push to GitHub

```bash
cd /path/to/NHTImageSort

# Make sure .gitignore is correct first
git add .
git status   # confirm no images, no .env, no node_modules

git commit -m "cloud deploy: OpenAI fallback, Railway + Vercel config"
git push origin main
```

---

## Step 4 — Deploy backend to Railway

1. Go to https://railway.app → **New Project**
2. Choose **Deploy from GitHub repo** → select `NHTImageSort`
3. Railway auto-detects Python and runs `Procfile`
4. Go to your service → **Variables** tab → add:

   | Variable | Value |
   |---|---|
   | `USE_CLOUD` | `true` |
   | `OPENAI_API_KEY` | `sk-...your key...` |

5. Click **Deploy** (or it deploys automatically)
6. Wait ~2 minutes. Check **Logs** tab — you should see:
   ```
   Seeding 8 demo images...
   ✓ Seeding complete.
   [INFO] Booting worker with pid: ...
   ```
7. Copy your Railway URL — looks like `https://nhtimagesort-production.up.railway.app`

**Test it:**
```bash
curl https://YOUR-RAILWAY-URL.up.railway.app/api/info
# Should return: {"cloud_mode": true, "status": "ok", ...}

curl https://YOUR-RAILWAY-URL.up.railway.app/api/search
# Should return 8 demo images
```

---

## Step 5 — Deploy frontend to Vercel

1. Edit `frontend/vercel.json` — replace `YOUR-RAILWAY-APP` with your actual Railway URL:
   ```json
   "destination": "https://nhtimagesort-production.up.railway.app/api/:path*"
   ```

2. Commit and push:
   ```bash
   git add frontend/vercel.json
   git commit -m "set Railway backend URL"
   git push
   ```

3. Go to https://vercel.com → **New Project** → Import `NHTImageSort`
4. Vercel detects Vite automatically
5. Set **Root Directory** to `frontend`
6. Click **Deploy**
7. You get a URL like `https://nhtimagesort.vercel.app`

---

## Step 6 — Point demo.nexushestia.com to Vercel

1. In Vercel: **Settings** → **Domains** → Add `demo.nexushestia.com`
2. In your DNS (wherever nexushestia.com is managed):
   - Add CNAME: `demo` → `cname.vercel-dns.com`
   - Or follow Vercel's exact instructions for your DNS provider
3. Wait 5-15 min for DNS propagation
4. Visit `https://demo.nexushestia.com` ✓

---

## What the demo shows

- **8 pre-seeded architecture images** across categories (Exterior, Interior, Construction, Residential, Commercial, Hospitality, Detail, Cultural)
- **Search** — type anything in the search bar, finds by description, category, or tag
- **Upload + process** — drag in any image, GPT-4o-mini describes and categorizes it in real time
- **HITL editor** — click any image to edit the description, add #hashtags
- **Delete / Remove doubles** — works fully

---

## Cloud mode banner

The frontend will show a small banner (via `/api/info`) noting:
*"Cloud demo — AI powered by OpenAI. Client deployments run 100% on-premise with Ollama."*

This is your on-premise pitch, not a disclaimer. It's a feature.

---

## Costs

| Service | Cost |
|---|---|
| Railway Hobby plan | $5/mo |
| OpenAI GPT-4o-mini | ~$0.001/image |
| Vercel | Free |
| **Total** | **~$5/mo** |

---

## Going back to local mode

Nothing changes locally. Your `USE_CLOUD` env var only applies to Railway.

```bash
# Local — still works exactly as before
python app.py      # Flask on port 5000
cd frontend && npm run dev  # Vite on port 5173
```

---

## Troubleshooting

**Railway shows build error:**
- Check that `Procfile` is in the repo root (not in a subfolder)
- Check `requirements.txt` has `gunicorn`

**Images not showing:**
- Railway has an ephemeral filesystem — seeded images reload on each deploy
- This is expected for the demo. Client deployments use persistent local storage

**Search returns empty:**
- Check Railway logs for the seed step
- Hit `GET /api/search` directly to confirm DB has data

**CORS errors in frontend:**
- `flask-cors` is installed and `CORS(app)` is set — should be fine
- If still blocked, add your Vercel domain to the CORS origins explicitly
