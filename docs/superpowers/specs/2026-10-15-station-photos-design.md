# Station photos and corrected pins — design

Date: 2026-10-15
Status: approved in conversation, awaiting review of this written spec

## Goal

When someone taps a station, show photos of that station, using Google's place
photos, and route 導航 to the station's exact Google listing. While doing so, fix
the 20 stations whose CPC coordinates are wrong, using coordinates the owner
looked up and entered personally.

Out of scope: showing or hiding stations that Google marks closed (6 found:
5 temporarily, 1 permanently). Can be a later change.

## Background (what the tests showed)

- Matching CPC stations to Google listings was tested on 10, then 100 random,
  then all 1,963 stations (2026-10-15).
- Name search first ("台灣中油 {name}站", circle bias 150 m around CPC's point,
  `includedType: gas_station`, strict), then "台灣中油 {CPC address}" with no
  location bias as a fallback. On 94 stations where both searches matched, both
  picked the same listing every time.
- Full run: 1,888 automatic matches, 13 found by address far from CPC's pin,
  21 review, 41 no match. After the owner's review: 1,962 stations have a place
  ID, 1 is not on Google (D4332 箔子寮漁船站), 20 have corrected coordinates.

## Google rules and prices this design relies on

Checked 2026-10-15 on developers.google.com.

- Place IDs are exempt from the caching restrictions and may be stored; refresh
  if older than 12 months, free with an ID-only Place Details request.
- Other Places content (names, addresses, locations, photo names) may not be
  stored. Photo names must come from a fresh request.
- Photo author attributions must be shown wherever the photo is shown.
- Text Search Pro: 5,000 free per month, then US$32 per 1,000.
- Place Details Essentials (IDs only), which includes the `photos` field:
  unlimited free.
- Place Details Photos (loading a photo image): 1,000 free per month, then
  US$7 per 1,000.
- Per-day quotas per method can be set under Google Maps Platform → Quotas →
  Places API (New); requests over the quota fail with 429. Daily quotas reset at
  midnight Pacific time.

## Design

### 1. Data and flow (approach A)

```
CPC feed ──► update_stations.py ──► site/data/stations.json  (published)
                    ▲                    + "pid" (Google place ID)
                    │                    + corrected lat/lng
          data/places.json  (in repo, not published)
                    ▲
          match_places.py  (weekly, only new/changed stations)
```

`data/places.json` holds one entry per station ID:

```json
{
  "D5139": {
    "pid": "ChIJ…",
    "src": "reviewed",
    "seen": "南寮漁船站|高雄市彌陀區南寮里漁港路73號",
    "fix": {"lat": 22.764367, "lng": 120.237296, "cpc": [24.84566, 120.92791]}
  },
  "D4332": {"pid": null, "src": "reviewed", "seen": "…"}
}
```

- `pid: null` means "not on Google": no photo, no lookups.
- `src`: `auto` (matched by the job) or `reviewed` (decided by the owner).
- `seen`: CPC name and address at match time, to detect CPC changes.
- `fix`: owner-entered coordinates, plus CPC's coordinates at the time of the
  fix (`cpc`), to detect CPC later moving the pin.
- Only place IDs and owner data are stored; no Google names, addresses or
  locations.
- Seeded once from the review: 1,962 place IDs, 1 null, 20 fixes. Entries the
  owner confirmed or corrected get `src: reviewed`; the 1,888 automatic matches
  get `src: auto`.

`update_stations.py` (standard library only, as now): download CPC data, apply
fixes, add `pid` to each station, write `stations.json`. A malformed
`places.json`, or a fix outside the Taiwan bounding box, stops the update so the
live site keeps its old data. `stations.json` grows about 60 KB.

### 2. Weekly job

New step after the CPC download, before deploy: `scripts/match_places.py`.

- Matches stations with no entry, and `auto` entries whose CPC name or address
  changed (`seen` differs). Never overwrites `reviewed` entries.
- Search and rules as tested:
  - MATCH: within 150 m and name or address agrees; or within 1 km, address
    agrees, and name or CPC brand agrees.
  - Found by address with address + (name or brand) agreeing but over 1 km away:
    save the place ID, report "pin may be wrong".
  - Ties: more signals, then CPC-branded listing, then distance.
  - REVIEW (within 1 km, name or address agrees) and no match: not saved,
    retried next week, reported.
- At most 50 stations per run; the rest continue next week.
- Failure (no key, quota, Google error) logs a warning and the job continues;
  matching never blocks the data update or deploy.
- Commits `stations.json` and `data/places.json` together.
- Review notice: one GitHub issue, 「需要檢查的加油站」, created or updated when
  there is something to check, closed when the list is empty. It lists doubtful
  and unfound stations with map links, "pin may be wrong" stations, and CPC
  changes to `reviewed` or fixed stations. Needs `issues: write` permission.
- Key: GitHub Actions secret `PLACES_API_KEY`, restricted to Places API (New),
  no application restriction (GitHub runner addresses change). Separate from the
  website map key.

### 3. Photos in the station card

- On opening a card with a `pid`: `new Place({id}).fetchFields({fields: ['photos']})`
  (free tier). Keep the photo list in memory only while the page is open.
- Swipeable strip with scroll snap and a counter (「2 / 10」). Each image is
  requested only when it becomes the visible slide; no preloading of the next.
  Requested at about 800 px wide.
- Under each photo: 「相片：{author}」, linked to the author's profile when given.
  Plus a 「Google 地圖」 credit and a 「在 Google 地圖查看更多相片」 link to the
  listing. Exact attribution rules to be checked against Google's policy before
  building.
- Layout: for stations with a `pid`, reserve a 16:9 area when the card opens,
  with a grey placeholder while loading. No photos, or an error (including the
  daily cap): pump icon with 「暫無相片」 / 「相片暫時無法顯示」. Stations with
  `pid: null`: no photo area.
- 導航 link adds `destination_place_id={pid}` when available.
- The website key needs Places API (New) added to its allowed APIs (website
  restriction unchanged).

### 4. Corrected pins

- Applied every week by `update_stations.py` from `fix`.
- If CPC's own coordinates for a fixed station move more than 100 m from
  `fix.cpc`, the fix stays and the station is listed on the review issue.
- The coordinates were looked up by the owner; no third-party credit needed.

## Cost controls

- GetPhotoMedia: 33 per day (stays within 1,000 free per month). Evenings may
  show 「相片暫時無法顯示」 after the cap; resets 3–4 p.m. Taiwan time.
- SearchText: 150 per day. Weekly use is usually 0–10 searches.
- Unused Places methods (Autocomplete, Nearby Search, …): 1 per day.
- Billing alert at US$1.

## Testing

- Python unit tests (standard library `unittest`) for the matcher, using
  recorded-shape responses, no live calls. Cases from real data: 馬公漁船 (far,
  name and address agree), 石榴 (CPC brand beats franchise office), 中森 (CPC
  listing beats inspection shop), 東湖 in 汐止 (rejected), 將軍漁船 (nearby CPC
  listing at another address, rejected), 好市多 `之`/`-`, 山隆銅鑼 (character
  pairs), Penghu's garbled address.
- Python tests for `update_stations.py`: fixes applied, `pid` added, malformed
  `places.json` stops the update.
- Workflow runs Python and existing JavaScript tests before deploying.
- Browser check locally with the real key: photos load, a swipe loads exactly
  one more image, no photo area for the null station, placeholder when photo
  requests are blocked, no layout shift, 導航 link includes the place ID.
- After deploy: live check, then the owner checks on iPhone.

## Owner setup

1. Places key as GitHub secret `PLACES_API_KEY` (Places API (New) only, no IP
   restriction), set from the key file with `gh secret set`.
2. Website key: add Places API (New) to allowed APIs.
3. Quotas: GetPhotoMedia 33/day, SearchText 150/day, unused methods 1/day.
4. Billing alert at US$1.

## Cleanup

After `data/places.json` is seeded: delete `scratch/review/`, `scratch/match-test/`
(including `results.jsonl`), and `scratch/places_key.txt` once the secret is set.
