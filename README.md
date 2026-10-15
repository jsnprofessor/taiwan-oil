# 中油加油站地圖

A mobile-friendly map of CPC (台灣中油) gas stations, hosted on GitHub Pages with Google Maps.

- Data: [台灣中油公司加油站服務資訊](https://data.gov.tw/dataset/6065) (government open data)
- A GitHub Action downloads fresh data every Monday, commits it, and redeploys the site.
  If the download fails or looks wrong, the live site keeps its old data and GitHub emails you.

## Files

- `site/` – the website (`index.html`, `app.js`, `style.css`, `data/stations.json`)
- `site/filters.js` – filter rules; tested by `node --test tests/`
- `scripts/update_stations.py` – downloads the feed and writes `site/data/stations.json`
- `scripts/serve_local.sh` – local preview at http://localhost:8000
- `.github/workflows/deploy.yml` – weekly update + deploy

## One-time setup

### 1. Google Maps (Google Cloud Console)

1. Create a project and attach a billing account (Google requires one, even within the free tier).
2. Enable **Maps JavaScript API**.
3. Create an **API key**. Under restrictions:
   - Application restriction: **Websites**. Add `https://<your-username>.github.io/*`
     (and `http://localhost:8000/*` for local testing).
   - API restriction: **Maps JavaScript API** only.
4. Create a **Map ID** (Map Management → Create, type JavaScript). Markers need it.
5. Recommended: set a daily quota cap on map loads and a budget alert, so a traffic spike
   can't cause a surprise bill.

The key is visible in the page source. That's normal for Maps JavaScript keys; the
website restriction is what protects it.

Cost (checked 2026-10-15 on Google's pricing page): 10,000 map loads per month are free,
then $7 per 1,000. Directions links open Google Maps directly and don't use the key.

### 2. GitHub

1. Create a repo and push this folder to the `main` branch.
2. Settings → Secrets and variables → Actions → **Variables** tab. Add:
   - `GOOGLE_MAPS_API_KEY`
   - `GOOGLE_MAP_ID`
3. Settings → Pages → Source: **GitHub Actions**.
4. Actions → "Update data and deploy" → **Run workflow**.

## Local preview

```bash
GOOGLE_MAPS_API_KEY=your-key GOOGLE_MAP_ID=your-map-id scripts/serve_local.sh
```

Refresh the data by hand with `python3 scripts/update_stations.py`.
