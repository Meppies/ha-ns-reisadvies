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
  snapped onto actual tracks via A* over the rail graph.
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

Each route (subentry) can be reconfigured (change from/to) or removed
from the integration tile. Sensor entity_ids stay stable thanks to
deterministic unique_ids.

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

- `ns_reisadvies.track_trip` — pin a trip by `ctx_recon`.
- `ns_reisadvies.untrack_trip` — unpin a trip by `ctx_recon`.

Both are entity-services; target a `sensor.ns_*` entity.

## Quality

This integration declares
[`quality_scale: platinum`](https://developers.home-assistant.io/docs/core/integration-quality-scale)
in the manifest. That covers, among other things, full async,
DataUpdateCoordinator-based polling, graceful degradation on transient
NS API outages, type-hinted Python, automated test coverage of the
config flow + sensor + migration, and entity-translation strings.

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
