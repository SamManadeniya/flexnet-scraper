# Flexnet Japan Vehicle Scraper & Web Service

High-performance web service and scraper for [Flexnet Japan](https://www.flexnet.co.jp/search) (~6,600+ vehicles). It allows users to search vehicles by criteria or direct URL via an interactive Web Form, scrapes comprehensive specs, downloads 30+ pristine high-resolution photos per vehicle, and automatically synchronizes them into **Supabase** with **Google Sheets webhook** notifications.

Configured and ready to deploy directly to **Netlify** (via Netlify Serverless Functions) or run locally.

---

## ✨ Features

- **Interactive Web Form Dashboard**:
  - Filter by Model / Keyword (e.g. *Hiace*, *Land Cruiser 80*, *Prado*, *Hilux*, *Renoca*, *Campervan*).
  - Filter by Min / Max Model Year.
  - Choose how many cars to scrape (5, 10, 15, or 20).
  - Single Car URL Mode: Paste any Flexnet URL and import it in ~1 second.
  - Interactive car cards with full specs, price in JPY, and photo gallery modal.
- **Ready for Netlify Hosting**:
  - `netlify.toml` pre-configured for Netlify Global CDN + Netlify Serverless Python Functions (`mangum` ASGI adapter).
  - Fast, serverless responses within Netlify timeout limits.
- **Dual Supabase Table Support**:
  - Works out-of-the-box with your existing **`matched_vehicles`** table (`JdmCarHunter`).
  - Supports the dedicated **`flexnet_vehicles`** table via `schema.sql`.
- **Google Sheets Webhook**:
  - Real-time notifications sent to your Google Apps Script webhook with run summaries and new car batches.

---

## 📁 Project Structure

```
flexnet scraper/
├── public/
│   └── index.html           # Modern glassmorphic Web UI dashboard & form
├── netlify/
│   └── functions/
│       └── api.py           # Netlify Serverless Function entrypoint (Mangum)
├── netlify.toml             # Netlify deployment & routing configuration
├── .env                     # Supabase & Webhook credentials
├── requirements.txt         # Dependencies (includes mangum for serverless)
├── config.py                # Environment configuration loader
├── database.py              # Supabase client & dual-mode upserts
├── notifier.py              # Google Sheets webhook integration
├── schema.sql               # Optional dedicated Supabase SQL schema & RLS policies
├── scraper/
│   ├── client.py            # Async HTTP client with rate-limiting & retries
│   ├── parser.py            # Search listing & detail page parser
│   └── engine.py            # Orchestrator with state & progress tracking
├── run_cli.py               # CLI entrypoint (Application Service)
├── api.py                   # FastAPI REST API (Local Web Service)
├── start_api.sh             # Shortcut to launch Web Service locally
└── start_cli.sh             # Shortcut to run CLI scraper locally
```

---

## 🚀 Running Locally

### 1. Launch the Web Service
```bash
./start_api.sh
```
Or manually:
```bash
source .venv/bin/activate
python api.py
```

### 2. Open in Your Browser
Open: **[http://localhost:8000](http://localhost:8000)**

You will see the interactive **FLEXNET HUNTER** dashboard:
1. Select a preset (e.g. *Toyota Hiace*, *Land Cruiser 80*, *Renoca*).
2. Set year range and limit.
3. Click **"Scrape & Sync to Supabase"**.
4. The vehicles appear instantly with photos, specs, and price, already saved into your Supabase database!

---

## 🌐 Deploying to Netlify

This project is fully structured for Netlify deployment:

### Option A: Deploy via GitHub (Recommended)
1. Push this folder to a GitHub repository.
2. In your [Netlify Dashboard](https://app.netlify.com/):
   - Click **"Add new site"** -> **"Import an existing project"**.
   - Select your GitHub repository.
3. Netlify will automatically detect:
   - **Publish directory**: `public`
   - **Functions directory**: `netlify/functions`
4. Add your Environment Variables in Netlify under **Site Configuration -> Environment variables**:
   - `SUPABASE_URL`: `https://rxbjexoxyfownnwxzbjn.supabase.co`
   - `SUPABASE_KEY`: `your_supabase_anon_or_service_role_key`
   - `GOOGLE_SHEETS_WEBHOOK_URL`: `your_webhook_url`
5. Click **Deploy Site**!

### Option B: Deploy via Netlify CLI
```bash
# 1. Install Netlify CLI if not already installed
npm install -g netlify-cli

# 2. Login & Deploy
netlify login
netlify deploy --prod
```

---

## 🔌 API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Web UI Form & Dashboard |
| `GET` | `/health` | Service health & Supabase connection check |
| `GET` | `/api/stats` | Count of vehicles stored in Supabase |
| `POST` | `/api/scrape/search` | Search & scrape vehicles by query / filters (returns JSON array) |
| `POST` | `/api/scrape/single` | Scrape a single vehicle URL on-demand |
| `POST` | `/api/scrape/start` | Start full background crawl (bulk) |
| `GET` | `/api/scrape/status` | Live status & progress percentage of bulk crawl |
| `POST` | `/api/scrape/stop` | Gracefully cancel running scrape job |
| `GET` | `/docs` | Interactive Swagger API documentation |
