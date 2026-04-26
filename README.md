# NS Reisadvies — Home Assistant integration

Custom Home Assistant integration that pulls live travel advice from the NS
(Nederlandse Spoorwegen) public API for a configured station pair, plus a
matching Lovelace card with favourites and auto-pin time slots.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![GitHub release](https://img.shields.io/github/v/release/Meppies/ha-ns-reisadvies?display_name=tag)
[![Validate](https://github.com/Meppies/ha-ns-reisadvies/actions/workflows/validate.yml/badge.svg)](https://github.com/Meppies/ha-ns-reisadvies/actions/workflows/validate.yml)

## Features

- One sensor per from/to station pair, refreshed every N minutes (configurable).
- Trip data: planned/actual times, delays, platforms, transfers, occupancy,
  cancellations.
- Favourite trips ("hartjes") that survive a Home Assistant restart, with a
  configurable retention window — server-side TTL, no orphans.
- Auto-favourite time slots in the card editor: pick a time and the days it
  applies to, the closest matching trip is pinned automatically.
- Companion Lovelace card included; auto-loaded by the integration.

## Installation

### Via HACS (custom repository)

1. Open HACS in Home Assistant.
2. *Integrations → ⋮ → Custom repositories*.
3. Add `https://github.com/Meppies/ha-ns-reisadvies`, category *Integration*.
4. Find **NS Reisadvies** in the list, click *Download*.
5. Restart Home Assistant.
6. *Settings → Devices & services → Add integration → NS Reisadvies*.

### Manual

1. Copy `custom_components/ns_reisadvies/` into your
   `<config>/custom_components/` folder.
2. Restart Home Assistant.
3. Add the integration via *Settings → Devices & services*.

## Configuration

You'll need a free NS API key (subscription "NsApp"):
<https://apiportal.ns.nl/>.

When adding the integration:

| Field                  | Description                                    |
|------------------------|------------------------------------------------|
| API key                | Your NS API key (only needed once per HA).     |
| Vertrekstation         | The departure station.                         |
| Aankomststation        | The arrival station.                           |

Re-open *Configure* on an existing entry to tweak:

| Option                  | Default | Description                                |
|-------------------------|---------|--------------------------------------------|
| `api_key`               | —       | Replace if revoked.                        |
| `scan_interval_minuten` | 5       | How often to refresh (1–60 min).           |
| `fav_hours`             | 6       | TTL for pinned favourites (0 = no expiry). |

## Lovelace card

The card auto-registers under `/ns_reisadvies/ns-reisadvies-card.js`. Add it
to your dashboard with *Add card → Custom: NS Reisadvies*. Card config
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

## Development

- Issues / feature requests:
  <https://github.com/Meppies/ha-ns-reisadvies/issues>
- Brand assets live in
  [home-assistant/brands](https://github.com/home-assistant/brands).

## Licence

MIT — see [LICENSE](LICENSE).
