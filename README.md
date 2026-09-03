# NS Reisadvies — Home Assistant integration

Custom Home Assistant integration that exposes NS travel advice as live
sensors plus a companion Lovelace card with favourites, auto-pin time
slots, train composition, and an opt-in live train map.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![GitHub release](https://img.shields.io/github/v/release/Meppies/ha-ns-reisadvies?display_name=tag)
[![Quality scale](https://img.shields.io/badge/quality--scale-platinum-e5e4e2.svg)](https://developers.home-assistant.io/docs/core/integration-quality-scale)
[![Validate](https://github.com/Meppies/ha-ns-reisadvies/actions/workflows/validate.yml/badge.svg)](https://github.com/Meppies/ha-ns-reisadvies/actions/workflows/validate.yml)

## What you get

- **One hub, many routes.** Add the integration once, then add as many
  routes (subentries) as you like — Hilversum → Duivendrecht,
  Duivendrecht → Hilversum, Aachen Hbf → Hilversum, etc. Each route is
  one sensor. Migrating from the old "one entry per route" layout is
  automatic and keeps your existing entity_ids stable.
- **689 stations** across NL, B, D, F and GB. Type-to-filter combo
  picker.
- **Trip data** per sensor: planned/actual times, delays, platforms,
  transfers, occupancy, cancellations, intermediate stops, walking
  legs.
- **Favourite trips** ("hartjes") — pin a specific train so it stays
  visible on the card across HA restarts. Configurable retention window
  with server-side TTL (no orphan favourites left behind).
- **Auto-pin time slots** in the card editor: pick a time + days,
  the closest matching trip is pinned automatically every day.
- **Train composition** (opt-in): adds carriage count + rolling-stock
  type + carriage images per leg. Pulled from NS' Journey API; turn it
  off to save quota.
- **Check-out / check-in hint** rendered between legs whenever an
  operator change forces a new check.
- **Live train map** (opt-in): tap a small icon under the departure
  platform to open a modal with real GPS positions from ProRail's
  OBIS feed (the same source [treinposities.nl][trnp] uses), the
  full train route, the stops, and a yellow / blue split that
  follows the train's progress. The whole NL rail network is cached
  weekly and rendered as a dim base layer; the route polyline is
  snapped onto actual tracks via A* over the rail graph. The base map
  is Home Assistant's own `ha-map`, so it uses whatever map HA ships
  and follows the light or dark theme.
- **Companion Lovelace card** auto-registers as a Lovelace resource —
  no manual `resources:` editing.

[trnp]: https://treinposities.nl/

## Installation

### Via HACS (custom repository)

1. Open HACS in Home Assistant.
2. *Integrations → ⋮ → Custom repositories*.
3. Add `https://github.com/Meppies/ha-ns-reisadvies`, category
   *Integration*.
4. Find **NS Reisadvies** in the list, click *Download*.
5. Restart Home Assistant.
6. *Settings → Devices & services → Add integration → NS Reisadvies*.

### Manual

1. Copy `custom_components/ns_reisadvies/` into your
   `<config>/custom_components/` folder.
2. Restart Home Assistant.
3. Add the integration via *Settings → Devices & services*.

## Uninstalling

1. *Settings → Devices & services → NS Reisadvies → ⋮ → Delete*. This
   removes the hub entry, every route subentry, every sensor created
   by the integration and the per-route favourite-trip storage files.
2. *HACS → Integrations → NS Reisadvies → ⋮ → Remove* to delete
   `custom_components/ns_reisadvies/` from disk.
3. Optional clean-up: open *Settings → Dashboards → Resources* and
   remove the `/ns_reisadvies/ns-reisadvies-card.js` resource if it
   still appears (newer HA versions clean it up automatically when
   the integration is removed).
4. Restart Home Assistant.

The persistent storage files
(`.storage/ns_reisadvies_tracked_trips_*` and the cached
`rail.geojson` inside the integration's `www/` folder) are removed
when steps 1 and 2 complete — no manual file deletion is needed.

## Configuration

You'll need a free NS API key (subscription **Ns-App**):
<https://apiportal.ns.nl/>. The same key drives every route, so you
only enter it once.

When adding the integration:

| Field            | Description                              |
|------------------|------------------------------------------|
| API key          | Your NS API key.                         |
| Vertrekstation   | First route's departure station.         |
| Aankomststation  | First route's arrival station.           |

Add more routes later via the integration tile (*Add route*).

### Hub-wide options

Re-open *Configure* on the integration tile to tweak:

| Option                       | Default | Description                                                                                  |
|------------------------------|---------|----------------------------------------------------------------------------------------------|
| `api_key`                    | —       | Replace if revoked.                                                                          |
| `scan_interval_minuten`      | 5       | How often the integration polls NS for trip data (1–60 min).                                 |
| `fav_hours`                  | 6       | TTL for pinned favourites (0 = no expiry).                                                   |
| `fetch_composition`          | off     | Adds an extra NS API call per unique train per refresh to fetch carriages + rolling stock.   |
| `live_train_map`             | off     | Shows the live-map icon under each leg in the card.                                          |
| `live_map_refresh_seconds`   | 10      | Polling cadence while the live map modal is open (5–60 s).                                   |

### Per-route configuration

Each route (subentry) can be reconfigured (change from/to, name, or
filters) or removed from the integration tile. Sensor entity_ids stay
stable thanks to deterministic unique_ids.

#### Optional route name (v2.15.0)

A route can carry an optional **name**. When set:

- the sensor's friendly name becomes that name (e.g. *Werk*) instead of
  *Hilversum → Duivendrecht*;
- the entity_id slug is derived from the name (`sensor.ns_werk` instead
  of `sensor.ns_hilversum_duivendrecht`);
- you may have **multiple routes between the same stations** as long
  as their names differ — useful for combining one route per filter
  (for example: a *Werk* route filtered to Mon–Fri 08:00 ±60 min, plus
  a *Weekend* route on the same stations with no filter).

Leave the field blank to keep the v2.13.x / v2.14.x default behaviour
(name = `<from> → <to>`, entity_id = `sensor.ns_<from>_<to>`).

#### Optional per-route trip filters (v2.14.0)

Each route can be pinned to specific weekdays, a time of day with a
margin window (0–360 min in 15-min steps), or a single date. Filters
are combinable; leaving them blank keeps the default *next trip from
now* behaviour. Filters are exposed inside the route form under a
collapsible **Optional filters** section.

## Lovelace card

The card auto-registers via Lovelace resources. Add it to your
dashboard with *Add card → Custom: NS Reisadvies*. Card config
options (set via the visual editor or YAML):

| Key                       | Description                                          |
|---------------------------|------------------------------------------------------|
| `entity`                  | Required. The `sensor.ns_*` entity to display.       |
| `title`                   | Card title.                                          |
| `max_rows`                | Number of trips to show (1–15).                      |
| `scale`                   | Font scale percentage (50–150).                      |
| `fav_hours`               | Local TTL hint (mirrors the integration option).     |
| `fav_slots`               | Number of auto-favourite time slots.                 |
| `auto_hour_<i>`           | "HH" for slot `i`.                                   |
| `auto_min_<i>`            | "MM" for slot `i`.                                   |
| `auto_days_<i>`           | Comma-separated weekdays, Sun=0..Sat=6.              |
| `auto_name_<i>`           | Display name for slot `i`.                           |

## Services

The integration exposes three services. The first two are entity-services
(target a specific `sensor.ns_*` entity); the third operates on the
integration globally.

### `ns_reisadvies.track_trip`

Pin a trip on the targeted route's sensor so it stays visible across
refreshes even after NS drops it from the regular `/v3/trips` window.
Pinned trips survive a Home Assistant restart and expire automatically
after `Favourite retention (hours)` (default 6h after the trip's planned
departure).

| Field        | Required | Description                                                                                                  |
|--------------|----------|--------------------------------------------------------------------------------------------------------------|
| `ctx_recon`  | yes      | The `ctxRecon` string from the trip you want to pin. Lovelace card surfaces this via its "pin" action.       |

Service-call example (Developer Tools → Services):

```yaml
service: ns_reisadvies.track_trip
target:
  entity_id: sensor.ns_amsterdam_centraal_to_utrecht_centraal
data:
  ctx_recon: "TgIIBg9TVw=="
```

### `ns_reisadvies.untrack_trip`

Remove a previously pinned trip from the route's favourites list. Idempotent —
calling with an unknown `ctx_recon` is a no-op.

| Field        | Required | Description                                                            |
|--------------|----------|------------------------------------------------------------------------|
| `ctx_recon`  | yes      | The `ctxRecon` of the trip to unpin. Must match the value used to pin. |

```yaml
service: ns_reisadvies.untrack_trip
target:
  entity_id: sensor.ns_amsterdam_centraal_to_utrecht_centraal
data:
  ctx_recon: "TgIIBg9TVw=="
```

### `ns_reisadvies.refresh_rail_cache`

Force a fresh download of the ProRail rail-network GeoJSON used by the
live train map. Use this if the live map renders straight-line routes
between stations — that typically means the cache file is missing or
stale because a previous scheduled refresh failed. The integration
normally rebuilds the cache once a week.

No fields. No target — operates on the hub.

```yaml
service: ns_reisadvies.refresh_rail_cache
```

## Supported functions

Each route (subentry) under the hub creates exactly one entity:

- **`sensor.ns_<slug>`** — primary entity. The slug is `<from>_<to>`
  for unnamed routes, or `<route_name>` when a custom name is set.
  State is the planned departure of the next upcoming trip;
  `extra_state_attributes` carries the full trips list (for the card),
  the list of pinned favourites, the route components (`route_name`,
  `from_station`, `to_station`), and the hub-wide
  `live_train_map_enabled` / `live_map_refresh_seconds` flags.

The integration also exposes:

- **`ns_reisadvies.track_trip`** and **`ns_reisadvies.untrack_trip`**
  service actions to pin / unpin a trip by `ctx_recon`. Used by the
  Lovelace card's heart icon — you usually do not call these
  directly.
- **WebSocket commands** `ns_reisadvies/track_train_{start,poll,stop}`
  used by the live train map modal to fetch the GPS position of a
  specific train on demand (only while the modal is open).

## Use cases

- **Multiple variants of the same route** — give each one a name and
  its own filter. *Werk* (Hilversum → Duivendrecht, Mon–Fri 08:00 ±60
  min) and *Weekend* (same stations, no filter) sit side by side on
  the dashboard with their own headings.
- **Daily commute display** — pin one or two routes on a wall-mounted
  HA dashboard so you see the next trains plus their delays at a
  glance, without opening the NS app.
- **"Time to leave" automation** — trigger a TTS notification a few
  minutes before your usual train departs, scaling the warning by the
  current delay value (so you get extra heads-up when the train is
  late).
- **Live train map for kids** — pair the live-map icon with a tablet
  in the hallway so children can see the train approaching on a real
  rail map before you head out the door.
- **Travel-cost reporting** — combine the `Total travel time` and
  `total km` attributes with HA statistics to track how much time
  you actually spend on rails per week or per month.

## Known limitations

- **Live-map GPS is OBIS-only.** The live train map uses ProRail's
  public `NS_treinlocaties` feed (the same source `treinposities.nl`
  uses). Trains operated by DB ICE, NMBS or Eurostar across foreign
  routes are not on this feed; the live-map icon is hidden for those
  legs.
- **Composition data has gaps.** Some trains do not appear in the
  `/v2/journey` endpoint (typically older NS rolling-stock or trains
  outside the active timetable window). The integration logs one
  warning the first time and falls back gracefully — the trip itself
  still renders without the carriage breakdown.
- **Trips list is not persisted by Recorder.** Per-trip details are
  exposed via `extra_state_attributes` for the Lovelace card, but
  the JSON blob exceeds Recorder's 16 384-byte limit and Recorder
  drops it. State history (`sensor.ns_*` itself) is recorded
  normally; only the rich attribute history is dropped.
- **NS API quota.** The free `Ns-App` subscription limits requests
  per minute. Default poll cadence (5 min) is well within the limit
  for a reasonable number of routes; very aggressive intervals
  combined with many routes plus `fetch_composition: true` can hit
  the cap.

## Troubleshooting

- **"Configuration error" on the card after a Home Assistant
  update** — usually means the Lovelace resource path was lost. Try
  *Settings → Devices & services → NS Reisadvies → ⋮ → Reload*. If
  that doesn't help, manually re-register the resource:
  *Settings → Dashboards → Resources → Add resource*, URL
  `/ns_reisadvies/ns-reisadvies-card.js?v=2.11.0`, type "JavaScript
  Module".
- **Sensor goes unavailable repeatedly** — check
  *Settings → System → Logs* for `ns_reisadvies` warnings. The
  coordinator logs the first failure and the recovery only (Silver
  rule), so a long sequence of `unavailable` log lines means NS is
  actually returning errors. Verify your API key on
  <https://apiportal.ns.nl/> and try the reauth flow if the key was
  rotated.
- **Reauth dialog appears unexpectedly** — Home Assistant opens it
  whenever NS returns HTTP 401/403. Paste a fresh key from
  apiportal.ns.nl into the dialog; it is verified with a real probe
  before being saved.
- **Live-map icon is missing on some legs** — the operator runs on a
  network that's not in ProRail's OBIS feed (DB ICE, NMBS, Eurostar).
  Expected behaviour, not a bug.
- **Train composition images do not load** — the most likely cause
  is that the NS API key does not have the `Reisinformatie API
  v2/v3` subscription beyond the standard `Ns-App` tier. Either
  enable the relevant subscription on `apiportal.ns.nl` or turn off
  *Fetch train composition* in the integration options.

For everything else, attach the integration's *Diagnostics* dump to
your bug report (*Settings → Devices & services → NS Reisadvies →
⋮ → Download diagnostics*). The dump redacts the API key and the
opaque `ctxRecon` identifiers.

## Examples

A "leaving in 5 minutes" notification driven by the next departure:

```yaml
automation:
  - alias: "Warn me 5 min before my morning train"
    trigger:
      - platform: template
        value_template: >-
          {% set next = state_attr('sensor.ns_hilversum_duivendrecht', 'trips')[0] %}
          {% set planned = next.legs[0].origin.plannedDateTime %}
          {{ as_timestamp(planned) - as_timestamp(now()) | int < 300 }}
    condition:
      - condition: time
        weekday: [mon, tue, wed, thu, fri]
        after: '06:30:00'
        before: '09:30:00'
    action:
      - service: notify.mobile_app_phone
        data:
          title: "Train leaves in 5 min"
          message: >-
            {% set t = state_attr('sensor.ns_hilversum_duivendrecht', 'trips')[0] %}
            Platform {{ t.legs[0].origin.actualTrack or t.legs[0].origin.plannedTrack }},
            delay {{ t.legs[0].origin.actualDateTime != t.legs[0].origin.plannedDateTime }}
```

Pin a trip from a script (the same call the heart icon makes):

```yaml
script:
  pin_my_morning_trip:
    sequence:
      - service: ns_reisadvies.track_trip
        target:
          entity_id: sensor.ns_hilversum_duivendrecht
        data:
          ctx_recon: "VXJpY2..."
```

## How data is updated

- A `DataUpdateCoordinator` per route polls the NS travel-advice API
  every `scan_interval_minuten` minutes (default 5, range 1 – 60).
  Each coordinator fetches `/v3/trips`, then per-pinned-favourite
  `/v3/trips/trip` calls in parallel, optionally followed by
  `/v2/journey` for carriage composition.
- The stations geo cache (`/v2/stations`) is fetched at most once per
  Home Assistant boot, on demand from the live train map.
- The full NL rail network (`ProRail Spoorbaanhartlijn`) is cached
  weekly to disk under `custom_components/ns_reisadvies/www/rail.geojson`
  and served via the integration's static path so the Lovelace card
  can render it as a base layer without re-downloading.
- Live train GPS is polled only while the live-map modal is open, at
  `live_map_refresh_seconds` cadence (default 10 s, range 5 – 60).
- On transient NS API failures the coordinator logs **once** when it
  flips to unavailable and **once** when it recovers. Sensors flip to
  `unavailable` while the coordinator is failing, then flip back.

## Quality

This integration declares
[`quality_scale: platinum`](https://developers.home-assistant.io/docs/core/integration-quality-scale)
in the manifest. The actual rule-by-rule status lives in
[`quality_scale.yaml`](custom_components/ns_reisadvies/quality_scale.yaml)
in the integration root and is kept honest as work progresses
(`done` / `todo` / `exempt` with reasons).

## Data sources

| Endpoint                                                            | Used for                                              |
|---------------------------------------------------------------------|-------------------------------------------------------|
| `gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips`           | Trip planning per route.                              |
| `gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips/trip`      | Per-trip detail for pinned favourites.                |
| `gateway.apiportal.ns.nl/reisinformatie-api/api/v2/journey`         | Train composition (opt-in).                           |
| `gateway.apiportal.ns.nl/reisinformatie-api/api/v2/stations`        | Station coordinates for the live map.                 |
| `utility.arcgis.com/.../NS_treinlocaties/FeatureServer/0/query`     | Live train GPS positions (ProRail OBIS).              |
| `maps.prorail.nl/.../ProRail_basiskaart/FeatureServer/6/query`      | Full NL rail network (weekly cache).                  |

## Development

- Issues / feature requests:
  <https://github.com/Meppies/ha-ns-reisadvies/issues>
- Brand assets live in
  [home-assistant/brands](https://github.com/home-assistant/brands).
- Tests run with `pytest tests/` from the repo root (requires
  `homeassistant`, `pytest`, `pytest-asyncio`, `pytest-homeassistant-custom-component`).

## Licence

MIT — see [LICENSE](LICENSE).
