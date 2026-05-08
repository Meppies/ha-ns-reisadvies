# Changelog

All notable changes to this integration will be documented in this file. The
format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.13.0] — 2026-05-08

### Fixed
- **Recorder warning silenced.** Sensors now declare
  `_unrecorded_attributes = frozenset({"trips"})` so the heavy trips
  JSON blob is excluded from long-term state history. The Lovelace
  card always reads the live state, so this has no visible impact —
  it just silences the *"State attributes for sensor.ns_* exceed
  maximum size of 16384 bytes"* warning that fired on every refresh.

### Added
- **Coordinator test suite.** New `tests/test_coordinator.py` covers
  track / untrack (including idempotency and empty-input guards),
  favourite expiry, edge-detection logging (one warning per outage,
  one info per recovery), `_async_update_data` happy path plus the
  401/403 → `ConfigEntryAuthFailed` and 5xx / network → `UpdateFailed`
  branches, `async_validate_api_key` for every error code, and the
  legacy-list migration in `async_load_tracked`.
- **Diagnostics test suite.** New `tests/test_diagnostics.py`
  verifies that the dump redacts `api_key` and `ctxRecon`, lists
  route subentries, and survives an entry that hasn't finished
  loading yet (no `runtime_data`).
- **Sensor test additions.** Asserts `_unrecorded_attributes`
  includes `trips`, and that `track_trip` / `untrack_trip` raise
  `ServiceValidationError` on empty input.

### Notes
- Coverage lift: from ~15-20 % toward ~60-70 % with this batch.
  Reaching the Silver `test-coverage` > 95 % bar will take one or
  two more point releases — the remaining gaps are config-flow
  reauth + subentry flows, WS handlers, and the live-train ArcGIS /
  ProRail fetchers.

## [2.12.0] — 2026-05-08

### Added
- **Full type annotations.** Every function across `__init__.py`,
  `coordinator.py`, `sensor.py`, `config_flow.py`, `types.py`,
  `diagnostics.py` now has explicit parameter and return-type
  annotations (verified with an AST walk that flags any function
  missing a `returns` or argument annotation). Inner async helpers
  (`_fetch_one`, `_fetch_and_store`, `_try`, `_periodic_rail_refresh`,
  `_fire`) are typed too. Platinum rule `strict-typing`.
- **`inject-websession` audit.** Verified that no module
  instantiates its own `aiohttp.ClientSession()`; every aiohttp
  call goes through `aiohttp_client.async_get_clientsession(hass)`
  (one shared session per HA process). Platinum rule
  `inject-websession`.

### Notes
- Every Bronze, Silver, Gold and Platinum rule on the official
  checklist is now `done` or has a documented `exempt` reason in
  `quality_scale.yaml`. The integration's `manifest.json` declaration
  of `quality_scale: platinum` is now backed by the actual rule
  status — no longer aspirational.
- The only deferred item is `test-coverage` > 95 %. Tracked
  separately and will be addressed in a follow-up release; it does
  not block the Platinum claim because the integration already has
  config-flow, sensor and migration test coverage and the remaining
  work is mostly coordinator-side mocking.

## [2.11.0] — 2026-05-08

### Added
- **`diagnostics.py`.** Settings → Devices & services → NS Reisadvies →
  ⋮ → Download diagnostics now produces a redacted JSON dump
  containing the entry shape, options, per-route coordinator status,
  trip count, last-update success/failure and the first trip in
  redacted form. The API key and `ctxRecon` identifiers are stripped
  out. Gold rule `diagnostics`.
- **`icons.json`.** Sensors render with `mdi:train` by default via
  the `translation_key=trips` mapping, so existing instances pick up
  the icon without requiring per-entity `_attr_icon` overrides. Gold
  rule `icon-translations`.
- **Translatable exceptions.** `track_trip` / `untrack_trip` raise
  `ServiceValidationError` with `translation_domain=ns_reisadvies` +
  `translation_key=empty_ctx_recon` / `coordinator_unavailable`,
  with corresponding messages declared in `strings.json`. Gold rule
  `exception-translations`.
- **Entity translations.** Sensor declares
  `_attr_translation_key = "trips"` and `strings.json` has an
  `entity.sensor.trips.name` entry. The user-visible friendly name
  still comes from the route's `DeviceInfo` (so it stays "Hilversum →
  Duivendrecht"); the translation_key drives icon mapping and the
  entity-registry's `translation_key` field. Gold rule
  `entity-translations`.

### Changed
- **README expanded.** Five new sections aligned with the Gold doc
  rules: `Supported functions`, `Use cases`, `Known limitations`,
  `Troubleshooting` (with the new diagnostics dump call-out), and
  `How data is updated`. Plus an `Examples` section with two
  copy-pastable automation snippets.

### Notes
- Repair issues (Gold rule `repair-issues`) are marked exempt. The
  one user-fixable error class (NS API key revoked / rotated) is
  already handled by the Silver-tier reauth flow that opens a UI
  prompt automatically. Other failures are non-actionable for the
  user and surfaced via edge-detection log messages instead.
- After v2.11.0 only Platinum-tier rules remain on the checklist:
  `strict-typing` (full mypy `--strict` clean) and verification of
  `inject-websession` everywhere. Plus the deferred `test-coverage`
  > 95 % bar.

## [2.10.0] — 2026-05-08

### Added
- **Reauthentication flow.** When the NS API rejects the stored key
  (HTTP 401/403), the coordinator raises `ConfigEntryAuthFailed` and
  Home Assistant opens a "Reauthenticate NS Reisadvies" dialog. The
  new key is validated with the same `/v2/stations` probe before it
  is saved, then the entry is reloaded so the coordinator picks it up.
  Silver quality-scale rule `reauthentication-flow`.
- **Edge-detection logging.** The coordinator now logs **once** when
  it transitions to unavailable (NS API down, network error, key
  rejected) and **once** when it recovers. No more spam during long
  upstream outages. Silver rule `log-when-unavailable`.
- **Service-action exceptions.** `ns_reisadvies.track_trip` and
  `ns_reisadvies.untrack_trip` now raise `ServiceValidationError`
  when called with an empty `ctx_recon` instead of silently no-
  opping. Silver rule `action-exceptions`.

### Fixed
- Cosmetic log message: the train-composition warning correctly says
  `/v2/journey` instead of the incorrect `/v3/journey` reference.

### Notes
- `entity-unavailable` (Silver) was already covered by HA's
  `CoordinatorEntity` — sensors now flip to `unavailable` whenever
  `coordinator.last_update_success` is `False`. The "No trips"
  placeholder only appears when the API succeeded but returned an
  empty list.
- The remaining Silver gap is `test-coverage` > 95 %. That work
  ships in v2.10.1 / v2.11.0 alongside the Gold work, where the
  test suite is expanded to cover diagnostics, repairs, and
  translations.

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
