# Changelog

All notable changes to this integration will be documented in this file. The
format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.9.0] — 2026-05-08

### Changed
- **ConfigEntry layout (v2 → v3 migration).** Hub-wide configurable
  options (`scan_interval_minuten`, `fav_hours`, `fetch_composition`,
  `live_train_map`, `live_map_refresh_seconds`) move from
  `entry.data` to `entry.options`. Only the API key remains in
  `entry.data`. Migration is automatic and idempotent. Satisfies the
  Bronze quality-scale rule on `data` vs `options` separation.
- **Runtime data on the entry.** Coordinators, the live-train-map
  session map, and the per-HA stations geo cache now live on
  `entry.runtime_data` (typed via `NSRuntimeData`) instead of
  `hass.data[DOMAIN][entry_id]`. Bronze rule `runtime-data`.
- **Sensor uses `has_entity_name = True`.** Each route now creates a
  proper `DeviceInfo` (name = "Hilversum → Duivendrecht") and the
  sensor takes its friendly name from the device. Entity IDs stay
  unchanged. Bronze rule `has-entity-name` plus the related Gold
  `devices` rule.

### Added
- **`test-before-configure`.** The config flow now probes
  `/v2/stations` with the entered API key and surfaces
  `invalid_auth` / `cannot_connect` errors in the form before the
  entry is created. The same probe runs in the options flow when the
  key is rotated. Bronze rule `test-before-configure`.
- **`PARALLEL_UPDATES = 0`** on the sensor platform (each route has
  its own coordinator that does the actual fetching). Silver rule
  `parallel-updates`.
- **`quality_scale.yaml`** in the integration root tracks every rule
  in the official quality-scale checklist as `done` / `todo` /
  `exempt` with reasons. Honest by design — the manifest still
  declares `platinum` as the target tier.
- **README "Uninstalling" section** with step-by-step removal
  instructions. Bronze rule `docs-removal-instructions`.

### Notes
- This release fixes architectural Bronze gaps that existed since
  v1.4.0. There are no behavioural changes for end users; existing
  sensor entity_ids and the Lovelace card both keep working
  identically. The next release in this stream (v2.10.0) tackles
  the Silver gaps (entity-unavailable, log-when-unavailable, reauth
  flow, > 95 % test coverage).

## [2.8.0] — 2026-05-08

### Added
- Quality scale declared as `platinum` in the manifest, plus a `loggers`
  field so the integration appears under Settings → System → Logs.
- `single_config_entry: true` — HA now blocks adding a second hub via
  the UI (you should add routes as subentries instead).
- Full type hints across `coordinator.py`, `__init__.py`, `sensor.py`,
  `config_flow.py`. mypy strict-mode clean.
- Pytest test suite (`tests/`) covering the config flow, sensor state,
  and migration path.
- `CHANGELOG.md` (this file) plus updated `README.md` / `info.md`.

### Changed
- README and info.md rewritten to reflect every feature shipped since
  v1.4.0 (foreign stations, train composition, hub+subentries, live
  train map, configurable poll cadence, full-NL rail base layer).

## [2.7.3] — 2026-05-08

### Fixed
- HA 2026.5.0 runs Lovelace resource modules inside a View Transition
  and aborts it shortly after, silently rolling back our
  `customElements.define` while the rest of the script continued. The
  dashboard then showed "Configuration error". Registration is now
  retried synchronously, on `readystatechange`, on `load`, and on a
  short timer so it always sticks.

## [2.7.2] — 2026-05-08

### Changed
- Replaced the array-based priority queue in the rail-snapping A* with
  a real binary min-heap. Long cross-country routes (Amersfoort →
  Zwolle and similar) now finish in tens of milliseconds.
- Snap radius bumped from 2 km to 5 km, top-5 candidate nodes per
  stop. Reduces straight-line fallbacks on stations slightly off-track.

### Added
- Per-segment console diagnostics: each routed segment logs its
  point-count and snap distances; each fallback logs the stop pair
  and how many candidates were tried.

## [2.7.1] — 2026-05-08

### Changed
- Rail GeoJSON + the routing graph are now loaded once per page and
  shared across modal opens. Routes are pre-warmed for every visible
  leg with a live-map icon, so opening the modal is instant — only the
  GPS-fetch happens on click.

## [2.7.0] — 2026-05-07

### Changed
- Routing graph nodes are merged at 4-decimal precision (~11 m) so
  neighbouring rail features auto-connect at junctions instead of
  staying isolated.
- Replaced Dijkstra with A* using haversine as the admissible
  heuristic. Cross-country routing is now usable.
- Top-3 snap candidates per stop with first-success-wins so a single
  bad snap (rangeer-spoor, freight branch) does not fall back to a
  straight chord.
- Train tile category label is counter-rotated when the marker is
  mirrored so SPR/IC stays readable.

## [2.6.2] — 2026-05-07

### Changed
- Train marker is now always horizontal — only mirrored for west-bound
  headings instead of rotated. No more "upside down going west" or
  apparent backward motion at the south/north heading boundary.

## [2.6.1] — 2026-05-07

### Fixed
- Train marker is right-side up for west-bound trains (mirror via
  `scaleX(-1)` rather than rotate 180°).
- Live-map icon is hidden for non-OBIS-tracked operators (DB ICE,
  NMBS, Eurostar) since their positions are not on the public feed.

## [2.6.0] — 2026-05-07

### Added
- Full Dutch rail network is now downloaded once at startup and
  refreshed weekly. Stored as `rail.geojson` in the integration's
  www folder and served via the existing static path. Card loads it
  in one go so zooming out shows the whole NL rail map.

## [2.5.1] — 2026-05-06

### Added
- Coloured route polyline is snapped onto the actual rail tracks
  using Dijkstra over the loaded ProRail Spoorbaanhartlijn graph.

## [2.5.0] — 2026-05-06

### Added
- Real ProRail rail tracks rendered as a dim grey base layer in the
  live-map modal. Train marker (real GPS) now visibly sits on a
  track.

## [2.4.2] — 2026-05-06

### Added
- Configurable live-map refresh interval (5–60 s) in the hub options.
  Default 10 s.

## [2.4.1] — 2026-05-06

### Changed
- Live-map train marker is a side-view tile (NS yellow body, blue
  stripe, windows, wheels, headlight) like the markers
  treinposities.nl uses. Type label (SPR/IC/ICD) sits on top of the
  body.

## [2.4.0] — 2026-05-06

### Added
- **Live train GPS** via ProRail's public ArcGIS NS_treinlocaties feed
  (the same OBIS data treinposities.nl uses). Real lat/lng + speed +
  heading per train, no NS API key required for this endpoint.

### Removed
- The NS Virtual Train v1 endpoint is no longer used for position —
  it shared `ritnummer` between unrelated runs and produced
  misleading markers.

## [2.3.2] — 2026-05-04

### Fixed
- A transient HTTP 5xx from the NS travel-advice API on first refresh
  no longer puts the whole hub in `setup_retry`. The sensors stay
  registered with empty state and the next refresh heals on its own;
  Lovelace cards keep rendering instead of showing "Configuration
  error".

## [2.3.1] — 2026-05-04

### Added
- Live-map polyline now shows the **full train run** (origin →
  destination of the train, not just the user's leg) and is split
  into yellow (already passed) and blue (still ahead) at the train's
  current position. Updates with each 10-second poll.

## [2.2.0] — 2026-05-03

### Added
- Live train map per leg (opt-in). A small map icon under the
  departure platform of each leg opens a modal with the train's
  position, the route, and the stops. Position is fetched only while
  the modal is open.

## [2.1.0] — 2026-04-29

### Added
- Foreign stations (Belgium, Germany, France, UK) — 689 stations
  total. Useful for routes via Aachen, Brussel, Düsseldorf, etc.

## [2.0.0] — 2026-04-29

### Changed
- Refactor to **Hub + subentries**: one config entry holds the
  integration-wide options (API key, scan interval, favourite
  retention, fetch composition); each route is now a subentry under
  that hub. Replaces the previous "one entry per route" layout.
- Migration preserves existing sensor entity_ids by rewriting the
  entity registry — your dashboards keep working.

## [1.6.0] — 2026-04-28

### Added
- Optional train composition (carriage count, rolling-stock type,
  carriage images) via NS' Journey API. Off by default to save quota.

## [1.5.0] — 2026-04-27

### Added
- Intermediate stops are now expandable per leg. Click the chevron to
  reveal each stop, its arrival/departure time, and platform.

## [1.4.0] — 2026-04-26

### Added
- Initial public release on HACS as a custom integration.
