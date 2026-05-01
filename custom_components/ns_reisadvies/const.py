"""Constants for the NS Reisadvies integration."""

DOMAIN = "ns_reisadvies"
NAME = "NS Reisadvies"

# Config entry schema version. Used by async_migrate_entry to lift
# legacy multi-entry installs (v1.x) into a single hub with route
# subentries (v2.0.0).
CONFIG_ENTRY_VERSION = 2

# Subentry type used for individual routes under the hub.
SUBENTRY_TYPE_ROUTE = "route"

# Config keys — these are part of the data contract for existing config
# entries. Do NOT rename without a migration path: the keys are baked
# into ConfigEntry.data and ConfigEntry.options of every installed
# instance.
CONF_API_KEY = "api_key"
CONF_FROM_STATION = "act_station"
CONF_TO_STATION = "arr_station"
CONF_SCAN_INTERVAL = "scan_interval_minuten"
CONF_FAV_HOURS = "fav_hours"
CONF_FETCH_COMPOSITION = "fetch_composition"
CONF_LIVE_TRAIN_MAP = "live_train_map"

# Defaults
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_FAV_HOURS = 6  # 0 disables expiry
DEFAULT_FETCH_COMPOSITION = False  # extra API calls — opt in
DEFAULT_LIVE_TRAIN_MAP = False  # on-demand only, but icon is opt-in

# API URLs
API_URL = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips"
TRIP_API_URL = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips/trip"
JOURNEY_API_URL = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v2/journey"
STATIONS_API_URL = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v2/stations"
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

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = "ns_reisadvies_tracked_trips"
