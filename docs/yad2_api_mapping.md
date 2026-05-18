# Yad2 API mapping

> **Status:** ⚠️ **Provisional / unverified.** The remote dev environment used to
> build the initial scaffolding blocks outbound traffic to `*.yad2.co.il`, so
> nothing here has been verified against a live response. The structure below
> is the public knowledge baseline we will iterate on once we can issue
> exploratory requests from an environment with network access (or from the
> user's laptop).
>
> When fields are confirmed / corrected, mark them with ✅ (verified DATE) or
> ❌ (rejected DATE) and add a short note. Keep the table append-only when in
> doubt.

## 1. Base endpoint

| Aspect | Value |
|---|---|
| Method | `GET` |
| URL | `https://gw.yad2.co.il/feed-search/lapi/feed/realestate` |
| Variant for sale | swap `realestate` segment or use `propertyGroup=apartments` + flags |
| Auth | none documented (anonymous browsing) |
| Encoding | URL query string |
| Pagination | `page=N` (1-based) |

### Required-ish headers (browser parity)

| Header | Example | Notes |
|---|---|---|
| `User-Agent` | desktop Chrome UA | rotate; mobile UAs also work |
| `Accept` | `application/json, text/plain, */*` | |
| `Accept-Language` | `he-IL,he;q=0.9,en;q=0.8` | |
| `Origin` | `https://www.yad2.co.il` | |
| `Referer` | `https://www.yad2.co.il/realestate/rent` | match the search type |
| `mainland-device-id` | UUID v4 | generated once per session; some endpoints reject without it |
| `Sec-Ch-Ua*` | client-hints set | optional but improves parity |

## 2. Query parameters

> All IDs (`topArea`, `area`, `city`, `neighborhood`) come from Yad2's internal
> taxonomy. Discover them via the website's URL bar after picking a location.

| Param | Type | Example | Notes |
|---|---|---|---|
| `topArea` | int | `2` | Region (e.g. Tel Aviv district) |
| `area` | int | `1` | Sub-region |
| `city` | int | `5000` | City id (Tel Aviv = 5000) |
| `neighborhood` | int / CSV | `1483` | One or many neighborhood ids |
| `propertyGroup` | enum | `apartments` | |
| `property` | CSV int | `1,3,6,7` | Specific property types |
| `price` | range | `5000-9000` | `min-max`, hyphen-separated |
| `rooms` | range | `2-3.5` | floats allowed |
| `squaremeter` | range | `40-90` | |
| `floor` | range | `0-10` | |
| `parking` | bool int | `1` | |
| `elevator` | bool int | `1` | |
| `balcony` | bool int | `1` | |
| `airConditioner` | bool int | `1` | |
| `forceLdLoad` | bool int | `true` | gives schema.org LD-JSON injection |
| `page` | int | `1` | pagination |

## 3. Response shape (expected)

```jsonc
{
  "data": {
    "feed": {
      "feed_items": [
        {
          "id": "string-or-int",
          "type": "ad",                  // "ad" vs "platinum" vs "kingdom" — see §4
          "price": 7800,
          "rooms": 3,
          "square_meters": 75,
          "floor": 2,
          "total_floors": 4,
          "city": "תל אביב",
          "neighborhood": "פלורנטין",
          "street": "וושינגטון",
          "address_number": "14",
          "coordinates": { "latitude": 32.05, "longitude": 34.77 },
          "images": ["https://...jpg", "..."],
          "title": "...",
          "row_1": "...",                // teaser strings shown on the card
          "row_2": "...",
          "row_3": "...",
          "merchant": false,
          "date_added": "2026-05-18T09:11:00Z",
          "link_token": "abc123",
          // Many more fields — capture everything in `raw_json` for later mining.
        }
      ],
      "total_items": 247
    }
  }
}
```

### Constructing the listing URL

`https://www.yad2.co.il/item/{link_token}` (older variant: `/s/c/{id}`). The
exact pattern needs verification.

## 4. Gotchas to handle

1. **Sponsored slots**: `type` of `platinum` / `kingdom` injects ads outside
   the area we asked for. Filter them out at scrape time, not by trusting the
   geo bounds alone.
2. **Aggregated cards** ("kingdom"): rolled-up developer projects. Skip unless
   we explicitly want them.
3. **Geo precision**: `coordinates` is sometimes the neighborhood centroid, not
   the actual building. Polygon filtering still works for "is in area"; do
   *not* trust it for distance-to-X-with-meter-precision.
4. **Bot detection**: heavy use leads to 403 / captcha. Backoff + UA rotation
   + low rps. If still blocked, fall back to Playwright with stealth.
5. **Schema drift**: Yad2 occasionally renames fields (`square_meters` ↔
   `square_meter`). Read defensively, log unknown shapes once, and update this
   doc.

## 5. Mapping to `db.models.Listing`

| `Listing` column | Yad2 source path | Transform |
|---|---|---|
| `source` | constant | `Source.YAD2` |
| `source_id` | `id` | `str(...)` |
| `url` | `link_token` | format with `https://www.yad2.co.il/item/{...}` |
| `title` | `title` or composed from `row_1` | |
| `price` | `price` | `int` |
| `rooms` | `rooms` | `float` |
| `sqm` | `square_meters` | `int` |
| `floor` | `floor` | |
| `total_floors` | `total_floors` | |
| `address` | `street + address_number` | concat |
| `city` | `city` | |
| `neighborhood` | `neighborhood` | |
| `lat` | `coordinates.latitude` | |
| `lng` | `coordinates.longitude` | |
| `parking` | derived from feature flags array | TBD |
| `elevator` | ditto | TBD |
| `balcony` | ditto | TBD |
| `furnished` | ditto | TBD |
| `pets_allowed` | unlikely surfaced; needs detail page | |
| `description` | from details endpoint | |
| `images_json` | `images` | already a list |
| `posted_at` | `date_added` | parse ISO |
| `raw_json` | entire item | for debugging |

## 6. Discovery checklist (when network is available)

1. Open https://www.yad2.co.il/realestate/rent in a real browser.
2. Open DevTools → Network → filter `XHR` and `Fetch`.
3. Apply filters: city + neighborhood + price range you'd actually search.
4. Locate the `feed-search/lapi/feed/realestate?...` request.
5. Copy as `cURL` (left sidebar → right-click → Copy → Copy as cURL).
6. Replay with `curl` from any allowlisted host and save the JSON to
   `tests/fixtures/yad2_feed_<area>.json` (anonymized).
7. Update this doc + write a VCR test against the fixture.

## 7. Implementation status

| Step | Status |
|---|---|
| Mapping document (this file) | ✅ provisional |
| `Yad2Scraper` HTTP client | 🚧 stub in `scrapers/yad2.py` |
| Live verification | ⏳ blocked on network access |
| VCR fixtures | ⏳ |
| Detail endpoint mapping | ⏳ |
