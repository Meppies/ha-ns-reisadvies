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

# Defaults
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_FAV_HOURS = 6  # 0 disables expiry
DEFAULT_FETCH_COMPOSITION = False  # extra API calls — opt in

# API URLs
API_URL = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips"
TRIP_API_URL = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips/trip"
JOURNEY_API_URL = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/journey"

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = "ns_reisadvies_tracked_trips"
