#!/usr/bin/env bash
# Preview the site at http://localhost:8000
# Usage: GOOGLE_MAPS_API_KEY=... [GOOGLE_MAP_ID=...] scripts/serve_local.sh
# Without a key the map loads in Google's "development purposes only" mode.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf scratch/_site
mkdir -p scratch
cp -R site scratch/_site
sed -i.bak \
  -e "s|__GOOGLE_MAPS_API_KEY__|${GOOGLE_MAPS_API_KEY:-}|" \
  -e "s|__GOOGLE_MAP_ID__|${GOOGLE_MAP_ID:-DEMO_MAP_ID}|" \
  scratch/_site/index.html
rm scratch/_site/index.html.bak
sed -i.bak "s|__BUILD__|dev$(date +%s)|g" scratch/_site/index.html scratch/_site/app.js
rm scratch/_site/*.bak
exec python3 -m http.server 8000 --directory scratch/_site
