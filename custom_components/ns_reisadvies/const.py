"""Constants for the NS Reisadvies integration."""

DOMAIN = "ns_reisadvies"
NAME = "NS Reisadvies"

# Config entry schema version.
#
#   v1: legacy "one config entry per route" layout (pre-v2.0.0).
#   v2: hub + subentries layout (v2.0.0). Hub-wide settings still on
#       ConfigEntry.data, route data on subentries.
#   v3: Platinum-cleanup (v2.9.0). Hub-wide configurable options moved
#       from ConfigEntry.data to ConfigEntry.options. ConfigEntry.data
#       only carries credentials (api_key) and other immutable setup
#       fields.
CONFIG_ENTRY_VERSION = 3

# Subentry type used for individual routes under the hub.
SUBENTRY_TYPE_ROUTE = "route"

# Config keys — these are part of the data contract for existing config
# entries. Do NOT rename without a migration path: the keys are baked
# into ConfigEntry.data and ConfigEntry.options of every installed
# instance.
CONF_API_KEY = "api_key"
CONF_FROM_STATION = "act_station"
CONF_TO_STATION = "arr_station"

# Optional human-readable name for the route subentry (v2.15.0).
# When set, the sensor's friendly name and entity_id are derived from
# this rather than from the station pair, allowing multiple routes
# between the same stations (e.g. "Werk" + "Weekend" both Hilversum →
# Duivendrecht with different filters).
CONF_ROUTE_NAME = "route_name"
CONF_SCAN_INTERVAL = "scan_interval_minuten"
CONF_FAV_HOURS = "fav_hours"
CONF_FETCH_COMPOSITION = "fetch_composition"
CONF_LIVE_TRAIN_MAP = "live_train_map"
CONF_LIVE_MAP_REFRESH_SECONDS = "live_map_refresh_seconds"

# Hub-wide opt-in (v2.18.0): publish a GPS device_tracker entity for
# every pinned favourite, so the train shows up on Home Assistant's map
# and can drive zone triggers. Off by default: it is the only thing in
# this integration that polls an external feed in the background.
CONF_TRACK_FAVOURITES = "track_favourites_on_map"
# Live automation sensors (v2.28.0): speed, next station, progress and
# the rest, for the trip a route is focused on.
CONF_LIVE_SENSORS = "live_sensors"
# Per route (v2.28.0): minutes it takes to get to the departure station
# — on foot, by bike, bus or car — for the "leave at" sensor and the
# "time to leave" binary sensor.
CONF_MINUTES_TO_STATION = "minutes_to_station"
CONF_DISRUPTIONS = "disruptions"
# Dienstkaartje (v2.27.0): off until the user asks for it, and then
# only for the people they name.
#
# And, for now, not even then: dienstkaartje.nl is somebody's hobby
# server with no published terms, and we have asked its author whether
# this use is welcome before sending any traffic their way. Until that
# answer arrives the switch is not offered in the options at all and
# the option is ignored if it is already set — the code is here, it
# just does not run. One flag to flip when the answer comes.
DIENSTKAARTJE_AVAILABLE = False
CONF_DIENSTKAARTJE = "dienstkaartje"
CONF_DIENSTKAARTJE_USERS = "dienstkaartje_users"
CONF_FAV_TRACK_SECONDS = "favourite_track_seconds"

# Hub-wide UI preference (v2.15.2): which weekday should appear first
# in the route subentry's "Days of the week" dropdown. Stored as a
# single-character string ("0" = Monday … "6" = Sunday) for parity with
# Python's weekday() convention. Display-only — does not change the
# semantics of filter_days values.
CONF_FIRST_WEEKDAY = "first_weekday"

# Per-route filter (v2.14.0). All optional, all combinable.
# - filter_days: list[int] of weekday numbers (0=Mon … 6=Sun). Empty/None = every day.
# - filter_time: ISO time string "HH:MM" or None.
# - filter_window_minutes: int 0-360 (steps of 15). Window applies on
#   both sides of the target moment when filtering returned trips.
# - filter_date: ISO date "YYYY-MM-DD" or None. Pinning to a single
#   date overrides the rolling-day behaviour for that route.
CONF_FILTER_DAYS = "filter_days"
CONF_FILTER_TIME = "filter_time"
CONF_FILTER_WINDOW_MINUTES = "filter_window_minutes"
CONF_FILTER_DATE = "filter_date"
# - filter_train_types: list of NS category codes ("IC", "SPR", ...).
#   Empty means every type. A trip survives only when every leg you
#   board is one of the chosen types.
CONF_FILTER_TRAIN_TYPES = "filter_train_types"

# Codes offered in the route form, in the order they are shown. The
# picker also accepts typed values, because the regional operators use
# codes that vary and NS adds new ones without notice; the sensor's
# ``available_train_types`` attribute reports what a route really sees.
TRAIN_TYPE_CODES: tuple[str, ...] = (
    "IC", "ICD", "SPR", "ST", "ICE", "EST", "NJ",
)

# A strict filter thins out a page of NS results, so the search is
# repeated from just after the last trip until enough survive. Two
# extra calls at most, and only while the filter is on.
FILTER_MIN_RESULTS = 5
FILTER_EXTRA_SEARCHES = 2

# Defaults
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_FAV_HOURS = 6  # 0 disables expiry
DEFAULT_FETCH_COMPOSITION = False  # extra API calls — opt in
DEFAULT_LIVE_TRAIN_MAP = False  # on-demand only, but icon is opt-in
DEFAULT_LIVE_MAP_REFRESH_SECONDS = 10  # poll cadence while modal is open

# Favourite tracking (v2.18.0).
DEFAULT_TRACK_FAVOURITES = False  # background polling — opt in
DEFAULT_LIVE_SENSORS = True
# One extra request per refresh, shared by every route, in exchange for
# knowing when the line you travel is in trouble: on by default.
DEFAULT_DISRUPTIONS = True
DEFAULT_DIENSTKAARTJE = False
DEFAULT_DIENSTKAARTJE_USERS = ""
DEFAULT_FAV_TRACK_SECONDS = 30  # a 120 km/h train covers ~1 km in 30 s
FAV_TRACK_SECONDS_MIN = 15
FAV_TRACK_SECONDS_MAX = 120
# How long before the planned departure the tracker starts reporting a
# position, and how long after arrival it keeps the last fix. Short on
# both sides: before departure the train is usually still finishing its
# previous run, and after arrival the number is reused elsewhere.
FAV_TRACK_LEAD_MINUTES = 5
# The focus trip's sensors (v2.28.0) are recomputed once a minute, so
# "minutes to departure" counts down and the clock-based events fire
# on time. NS is only asked for a position inside a window around the
# traveller's own train — from this long before it leaves until a few
# minutes after it arrives — and only while a live entity is enabled.
FOCUS_TICK_SECONDS = 60
# A connection with less than this many minutes left counts as at risk.
TRANSFER_RISK_MINUTES = 2
# The last train of the day is looked up with one planner request from
# this time on, at most once an hour. NS's service day runs past
# midnight, so "today" ends at the rollover hour the next morning.
LAST_TRAIN_SEARCH_FROM = "23:00"
LAST_TRAIN_REFRESH_MINUTES = 60
SERVICE_DAY_ROLLOVER_HOUR = 4
LIVE_LEAD_MINUTES = 30
LIVE_GRACE_MINUTES = 5
FAV_TRACK_GRACE_MINUTES = 2

# Live positions (v2.21.0). A favourite is followed for as long as its
# train is running, not just while the traveller is on board, so the
# train is visible while it is still on its way to the departure
# station and while it carries on past the arrival station.
#
# NS's vehicle feed is national: one request holds every train that
# reports a position, so it is fetched once and shared by every route
# and every open map. Keeping it for a few seconds is enough to collapse
# a tick's worth of lookups into that single request without the marker
# ever lagging behind by a noticeable distance.
VEHICLE_CACHE_SECONDS = 10
# A train's own run barely changes, so its journey is re-read sparingly;
# it is only needed to know when the run starts and ends and which
# stations it passes.
JOURNEY_CACHE_SECONDS = 60
# ProRail's ArcGIS feed has been answering every request with an error
# since well before v2.21.0. It is kept as a second source in case it
# returns, but after this many consecutive failures it is left alone for
# a while instead of costing a request per train per tick.
ARCGIS_FAILURES_BEFORE_BACKOFF = 3
ARCGIS_BACKOFF_MINUTES = 30
# Outside this many hours around a pinned trip nothing is fetched at
# all: a favourite pinned for tomorrow morning must not keep the feed
# busy overnight.
FAV_RUN_LOOKAROUND_HOURS = 4

# Disruptions (v2.25.0). One national request covers every route, so
# it is fetched once per refresh and shared, like the vehicle feed.
# Two minutes is well inside the five-minute default scan interval and
# keeps several routes on one request.
DISRUPTIONS_CACHE_SECONDS = 120

# Dienstkaartje (v2.27.0). Someone else's hobby server, so: one answer
# per person is reused for two minutes, the on-demand sweep of everyone
# on a shift is reused for five, and a 429 buys the whole site a rest
# rather than a retry.
DIENSTKAARTJE_CACHE_SECONDS = 120
DIENSTKAARTJE_SWEEP_CACHE_SECONDS = 300
DIENSTKAARTJE_BACKOFF_MINUTES = 15
# A sweep walks pages of ten and stops, however many people are on a
# shift: the point is the train the user is on, not a census.
DIENSTKAARTJE_SWEEP_MAX_PAGES = 6
DIENSTKAARTJE_SWEEP_MAX_PEOPLE = 60
# How many people may be followed at once. Each one costs a request
# per refresh, so the limit is about being a good guest.
DIENSTKAARTJE_MAX_FOLLOWED = 10
DEFAULT_FILTER_WINDOW_MINUTES = 0  # default: no fuzz around the target
DEFAULT_FIRST_WEEKDAY = "0"  # Monday — NL/EU default; users in US locales can override

# API URLs
API_URL = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips"
TRIP_API_URL = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips/trip"
JOURNEY_API_URL = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v2/journey"
DISRUPTIONS_API_URL = (
    "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/disruptions"
)
STATIONS_API_URL = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v2/stations"
# Dienstkaartje (v2.27.0) — not an NS endpoint: a hobby project where
# railway staff publish the shift they are working themselves.
DIENSTKAARTJE_API_URL = "https://data.dienstkaartje.nl/api/v1/dienstkaartje"
# Per-train info (composition + current station, no GPS):
VIRTUAL_TRAIN_API_URL = "https://gateway.apiportal.ns.nl/virtual-train-api/api/v1/trein"
# Live GPS feed used by the NS app's map view. Filterable by `route`
# (= ritnummer). Returns lat/lng/snelheid/richting per vehicle.
VIRTUAL_TRAIN_VEHICLE_URL = "https://gateway.apiportal.ns.nl/virtual-train-api/vehicle"
VIRTUAL_TRAIN_VEHICLE_FALLBACK_URL = "https://gateway.apiportal.ns.nl/virtual-train-api/api/vehicle"

# ProRail's public ArcGIS feature service exposing OBIS train positions —
# the same feed treinposities.nl/treinenradar.nl use. No API key needed,
# no station-level rounding: returns real GPS lat/lng + speed + heading
# per train. We query by `treinNummer` for a single train.
ARCGIS_TREINEN_URL = (
    "https://utility.arcgis.com/usrsvcs/servers/"
    "9e11bc6bace24952bf2b7cd1df1a5311/rest/services/"
    "NS_treinlocaties/FeatureServer/0/query"
)

# ProRail Spoorbaanhartlijn — full NL rail network, used as the grey
# base layer in the live train map. Static enough to cache for a week.
PRORAIL_RAIL_URL = (
    "https://maps.prorail.nl/arcgis/rest/services/"
    "ProRail_basiskaart/FeatureServer/6/query"
)

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = "ns_reisadvies_tracked_trips"
