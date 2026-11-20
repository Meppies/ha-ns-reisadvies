// NS Reisadvies — Lovelace card with auto-pin time slots and favourites.
// Comments and UI strings are in English (UK); user-facing text is
// localised via the small i18n helper below. Add a new language by
// adding a translation block to I18N.

const I18N = {
  en: {
    select_sensor: "Select a sensor.",
    loading: "Loading data...",
    no_trips: "No trips found...",
    platform: "Platform",
    direct: "Direct",
    stop_one: "1 stop",
    stop_other: "{n} stops",
    transfer: "Transfer",
    transfer_n: "{n} min transfer",
    cancelled: "ATTENTION: TRIP CANCELLED",
    total_travel: "Total travel time",
    unknown: "Unknown",
    show_stops: "Show stops",
    hide_stops: "Hide stops",
    stop_passing: "(does not stop)",
    checkout_checkin: "Check out {from}, check in {to}",
    stop_arrival_short: "A",
    stop_departure_short: "D",
    carriages_one: "1 carriage",
    carriages_other: "{n} carriages",
    minutes_short: "min",
    hour_short: "hr",
    hour_minutes: "{h} h {m} m",
    editor_title: "Title",
    editor_route_sensor: "Route sensor",
    editor_number_of_trips: "Number of trips",
    editor_scale: "Scale",
    editor_keep_favourites: "Keep favourites (hours)",
    editor_favourite_times: "Favourite times (pin 1 trip)",
    editor_time: "Time:",
    editor_name: "Name",
    editor_add_slot: "+ Add favourite time",
    editor_time_slot: "Time slot {n}",
    show_live_map: "Show live train position on a map",
    live_map_button: "Live map",
    live_map_title: "Live train position",
    live_map_loading: "Looking up the train…",
    live_map_no_data: "No live position available for this train.",
    live_map_speed: "{n} km/h",
    badge_tomorrow: "Trips for tomorrow",
    badge_in_n_days: "Trips in {n} days",
    badge_for_date: "Trips for {date}",
    weekdays: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"],
    search_from: "From",
    search_to: "To",
    search_via: "Via (optional)",
    search_swap: "Swap",
    search_go: "Search",
    search_searching: "Searching…",
    search_leave_now: "Leave now",
    search_leave_at: "Leave at",
    search_arrive_by: "Arrive by",
    search_recent: "Recent",
    search_clear_recent: "Clear",
    search_train_types: "Train types",
    search_any_train: "All trains",
    search_hint: "Fill in two stations and search.",
    search_pick_stations: "Pick a departure and an arrival station.",
    search_no_api_key: "No API key configured.",
    search_rejected: "NS refused the key.",
    search_unknown_station: "NS does not know one of these stations.",
    search_unavailable: "NS is not answering right now.",
    search_no_match: "No trips match those train types.",
    search_no_trips: "No trips found for this search.",
    disruptions_none: "No disruptions right now.",
    disruptions_unavailable: "Cannot reach NS for disruptions.",
    disruptions_kind_DISRUPTION: "Disruption",
    disruptions_kind_MAINTENANCE: "Engineering work",
    disruptions_kind_CALAMITY: "Announcement",
    disruptions_show_map: "Where",
    disruptions_advice: "Advice",
    disruptions_less: "Less",
    disruptions_at_ns: "At NS",
    disruptions_kinds: "Which kinds to show",
    disruptions_scope: "Where to look",
    disruptions_scope_all: "The whole country",
    disruptions_scope_routes: "Only my routes",
    disruptions_scope_stations: "Stations I pick",
    disruptions_stations_hint: "Station names, separated by commas.",
  },
  nl: {
    select_sensor: "Selecteer een sensor.",
    loading: "Gegevens laden...",
    no_trips: "Geen ritten gevonden...",
    platform: "Spoor",
    direct: "Direct",
    stop_one: "1 tussenstop",
    stop_other: "{n} tussenstops",
    transfer: "Overstappen",
    transfer_n: "{n} min overstappen",
    cancelled: "LET OP: REIS VERVALLEN",
    total_travel: "Totale reistijd",
    unknown: "Onbekend",
    show_stops: "Toon tussenstops",
    hide_stops: "Verberg tussenstops",
    stop_passing: "(stopt niet)",
    checkout_checkin: "Check-uit {from}, check-in {to}",
    stop_arrival_short: "A",
    stop_departure_short: "V",
    carriages_one: "1 bak",
    carriages_other: "{n} bakken",
    minutes_short: "min",
    hour_short: "uur",
    hour_minutes: "{h} u {m} m",
    editor_title: "Titel",
    editor_route_sensor: "Route sensor",
    editor_number_of_trips: "Aantal ritten",
    editor_scale: "Schaal",
    editor_keep_favourites: "Favorieten bewaren (uren)",
    editor_favourite_times: "Favoriete tijden (Pin 1 rit)",
    editor_time: "Tijd:",
    editor_name: "Naam",
    editor_add_slot: "+ Favoriete tijd toevoegen",
    editor_time_slot: "Tijdslot {n}",
    show_live_map: "Toon live trein-positie op de kaart",
    live_map_button: "Live kaart",
    live_map_title: "Live trein-positie",
    live_map_loading: "Trein wordt opgezocht…",
    live_map_no_data: "Geen live-positie beschikbaar voor deze trein.",
    live_map_speed: "{n} km/u",
    badge_tomorrow: "Reizen voor morgen",
    badge_in_n_days: "Reizen over {n} dagen",
    badge_for_date: "Reizen voor {date}",
    weekdays: ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"],
    search_from: "Van",
    search_to: "Naar",
    search_via: "Via (optioneel)",
    search_swap: "Omdraaien",
    search_go: "Zoeken",
    search_searching: "Bezig met zoeken…",
    search_leave_now: "Nu vertrekken",
    search_leave_at: "Vertrek om",
    search_arrive_by: "Aankomst om",
    search_recent: "Recent",
    search_clear_recent: "Wissen",
    search_train_types: "Treinsoorten",
    search_any_train: "Alle treinen",
    search_hint: "Vul twee stations in en zoek.",
    search_pick_stations: "Kies een vertrek- en een aankomststation.",
    search_no_api_key: "Geen API-sleutel ingesteld.",
    search_rejected: "NS weigert de sleutel.",
    search_unknown_station: "NS kent een van deze stations niet.",
    search_unavailable: "NS antwoordt op dit moment niet.",
    search_no_match: "Geen ritten met die treinsoorten.",
    search_no_trips: "Geen ritten gevonden voor deze zoekopdracht.",
    disruptions_none: "Op dit moment geen storingen.",
    disruptions_unavailable: "Kan de storingen niet bij NS ophalen.",
    disruptions_kind_DISRUPTION: "Storing",
    disruptions_kind_MAINTENANCE: "Werkzaamheden",
    disruptions_kind_CALAMITY: "Melding",
    disruptions_show_map: "Waar",
    disruptions_advice: "Advies",
    disruptions_less: "Minder",
    disruptions_at_ns: "Bij NS",
    disruptions_kinds: "Welke soorten tonen",
    disruptions_scope: "Waar kijken",
    disruptions_scope_all: "Heel Nederland",
    disruptions_scope_routes: "Alleen mijn routes",
    disruptions_scope_stations: "Stations die ik kies",
    disruptions_stations_hint: "Stationsnamen, gescheiden door komma's.",
  },
};

function _lang(hass) {
  const raw = (hass && (hass.locale?.language || hass.language)) || "en";
  return String(raw).slice(0, 2).toLowerCase();
}

// Resolve which IANA time zone to use for rendering departure / arrival
// times. The user's Lovelace setting `locale.time_zone` is either
// "local" (use browser zone) or "server" (use HA server zone).
// Prefer the explicit HA-server zone whenever available so trains
// rendered for a Dutch route do not shift when the browser is in
// another time zone (e.g. a Mac mini set to America/Los_Angeles).
function _tz(hass) {
  if (!hass) return undefined;
  const pref = hass.locale?.time_zone;
  const serverTz = hass.config?.time_zone;
  if (pref === "server" && serverTz) return serverTz;
  if (pref && pref !== "local") return pref;
  return serverTz || undefined;
}

function t(key, hass, vars) {
  const lang = _lang(hass);
  const dict = I18N[lang] || I18N.en;
  let str = dict[key];
  if (str === undefined) str = I18N.en[key];
  if (str === undefined) return key;
  if (vars && typeof str === "string") {
    Object.entries(vars).forEach(([k, v]) => {
      str = str.replace(new RegExp(`\\{${k}\\}`, "g"), v);
    });
  }
  return str;
}

// Home Assistant's own raster tiles (core >= 2026.10). `tok` is
// substituted by Leaflet from the layer options, so refreshing the
// token is a field assignment plus a redraw.
const NS_HA_TILE_URL = "/api/map_tiles/raster/{z}/{x}/{y}.png?token={tok}";
// Leaflet itself: same pin the HA frontend uses, so the browser has
// usually cached it already.
const NS_LEAFLET_CSS_URL = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
const NS_LEAFLET_CSS_SRI =
  "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=";

class NSReisadviesCard extends HTMLElement {
  setConfig(config) {
    // Wrap the whole body in a try/catch so an unexpected
    // localStorage failure or a transient null state during a HA
    // reload cannot bubble up as a "Configuration error" badge in
    // Lovelace. Anything that fails here falls back to a default and
    // the next hass setter call will recover.
    try {
      this._setConfigInner(config);
    } catch (err) {
      console.warn("ns-reisadvies-card setConfig failed, using defaults:", err);
      this._config = { title: "NS Reisadvies", max_rows: 5, scale: 100, fav_slots: 1, fav_hours: 6, ...config };
      this._pendingTrack = new Set();
      this._pendingUntrack = new Set();
      this._expandedLegs = new Set();
      this.favTimestamps = {};
      this._autoPinnedSlots = new Set();
      this._autoPinnedDay = null;
    }
  }

  _setConfigInner(config) {
    this._config = {
      title: "NS Reisadvies",
      max_rows: 5,
      scale: 100,
      fav_slots: 1,
      fav_hours: 6,
      ...config,
    };

    // Short-lived working memory for snappy reactions to user clicks.
    this._pendingTrack = new Set();
    this._pendingUntrack = new Set();

    // Track which leg expanders are open. Key: `${tripIdx}_${legIdx}`.
    // Lives in JS memory only — refreshing the page closes them.
    this._expandedLegs = new Set();

    const entityKey = this._config.entity || "default";

    // Local log to track the "age" of a heart. Acts as a fallback —
    // the integration itself enforces a server-side TTL.
    this.lsKey = `ns_fav_times_${entityKey}`;
    try {
      this.favTimestamps = JSON.parse(localStorage.getItem(this.lsKey)) || {};
    } catch (e) {
      this.favTimestamps = {};
    }

    // Track which AUTO-PIN SLOTS have already been used today, persisted
    // in localStorage so a browser refresh does not cause a second
    // auto-pin for the same slot. Per slot per day, never per ctxRecon —
    // the NS API rolls trips out of its window during the day, so the
    // "best match" for a slot can change while the slot is satisfied.
    this.lsKeyAutoPin = `ns_autopin_${entityKey}`;
    this._autoPinnedDay = this._dayKey();
    try {
      const raw = JSON.parse(localStorage.getItem(this.lsKeyAutoPin)) || {};
      if (raw.day === this._autoPinnedDay && Array.isArray(raw.slots)) {
        this._autoPinnedSlots = new Set(raw.slots);
      } else {
        this._autoPinnedSlots = new Set();
      }
    } catch (e) {
      this._autoPinnedSlots = new Set();
    }
  }

  _dayKey() {
    const d = new Date();
    return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
  }

  saveTimestamps() {
    try {
      localStorage.setItem(this.lsKey, JSON.stringify(this.favTimestamps));
    } catch (e) {
      // localStorage may be unavailable in sandboxed iframes.
    }
  }

  saveAutoPinned() {
    try {
      localStorage.setItem(this.lsKeyAutoPin, JSON.stringify({
        day: this._autoPinnedDay,
        slots: Array.from(this._autoPinnedSlots),
      }));
    } catch (e) {
      // ignore
    }
  }

  static getConfigElement() { return document.createElement("ns-reisadvies-editor"); }

  static getStubConfig() {
    return { entity: "", title: "NS Reisadvies", max_rows: 5, scale: 100, fav_slots: 1, fav_hours: 6 };
  }

  set hass(hass) {
    this._hass = hass;
    // Keep an open live map in step with the active theme.
    if (this._activeMap) this._syncMapTheme();
    if (!this.content) {
      const card = document.createElement("ha-card");
      this.content = document.createElement("div");
      this.content.style.padding = "0";
      card.appendChild(this.content);
      this.appendChild(card);
    }

    if (!this._config || !this._config.entity) return;

    // Skip the re-render if our own sensor's state object did not
    // change reference. HA emits a hass-update on every entity change
    // in the system, but our card only cares about its own sensor.
    // Without this gate the entire DOM is rewritten dozens of times
    // per minute, causing the timeline line to visibly flicker.
    const newState = hass.states[this._config.entity];

    if (this._lastStateObj === newState) {
      return;
    }
    this._lastStateObj = newState;
    this.updateContent();
  }

  // v2.24.0: where the trips come from, and whether pinning applies.
  // The search card renders with the same code but feeds it the
  // answer to a one-off lookup instead of a route's sensor, and has
  // nothing to pin them to.
  _sourceState() {
    if (!this._hass || !this._config || !this._config.entity) return null;
    return this._hass.states[this._config.entity];
  }

  _hasSource() {
    return !!(this._config && this._config.entity);
  }

  _favouritesAllowed() {
    return !!(this._config && this._config.entity);
  }

  // --- expiry / cleanup ----------------------------------------------------
  cleanOldFavorites(serverTracked) {
    if (!this._config.fav_hours) return;

    const limit = this._config.fav_hours * 60 * 60 * 1000;
    const now = Date.now();
    let changed = false;

    // Snapshot of keys so we can mutate this.favTimestamps inside the loop.
    const knownCtx = Object.keys(this.favTimestamps);

    // 1. Walk through the favourites that are currently active server-side.
    serverTracked.forEach(ctx => {
      if (!this.favTimestamps[ctx]) {
        // No local timestamp (other device, fresh browser, etc.).
        // IMPORTANT: do not reset to `now` — that would push the TTL out
        // every time a new device sees the favourite. Instead, mark it
        // as nearly expired so the next refresh prunes it server-side.
        this.favTimestamps[ctx] = now - limit + (5 * 60 * 1000); // expires in ~5 min
        changed = true;
      } else if (now - this.favTimestamps[ctx] > limit) {
        // Retention reached — server-side TTL will catch up too, but
        // call untrack_trip directly so the UI updates straight away.
        this._hass.callService("ns_reisadvies", "untrack_trip", {
          entity_id: this._config.entity,
          ctx_recon: ctx,
        }).catch(() => {});

        delete this.favTimestamps[ctx];
        changed = true;
      }
    });

    // 2. Drop entries from the local log that the server no longer tracks.
    knownCtx.forEach(ctx => {
      if (!serverTracked.includes(ctx) && !this._pendingTrack.has(ctx)) {
        delete this.favTimestamps[ctx];
        changed = true;
      }
    });

    if (changed) this.saveTimestamps();
  }

  toggleFavorite(ctxRecon, isCurrentlyTracked, event) {
    if (event) event.stopPropagation();
    if (!ctxRecon || !this._hass || !this._config.entity) return;

    if (isCurrentlyTracked) {
      this._pendingUntrack.add(ctxRecon);
      this._pendingTrack.delete(ctxRecon);
      delete this.favTimestamps[ctxRecon];

      this._hass.callService("ns_reisadvies", "untrack_trip", {
        entity_id: this._config.entity,
        ctx_recon: ctxRecon,
      });
    } else {
      this._pendingTrack.add(ctxRecon);
      this._pendingUntrack.delete(ctxRecon);
      this.favTimestamps[ctxRecon] = Date.now();

      this._hass.callService("ns_reisadvies", "track_trip", {
        entity_id: this._config.entity,
        ctx_recon: ctxRecon,
      });
    }

    this.saveTimestamps();
    this.updateContent();
  }

  processAutoFavs(stateObj) {
    const trackedTrips = stateObj.attributes.tracked_trips || [];
    const dag = new Date().getDay();

    // Reset the "already auto-pinned today" set at midnight so that the
    // next morning's slots can pin again.
    const todayKey = this._dayKey();
    if (this._autoPinnedDay !== todayKey) {
      this._autoPinnedDay = todayKey;
      this._autoPinnedSlots = new Set();
      this.saveAutoPinned();
    }

    const tripDuration = (trip) => {
      // Prefer actualDurationInMinutes, fall back to plannedDuration,
      // fall back to a computed difference between origin and final
      // destination plannedDateTime.
      if (typeof trip.actualDurationInMinutes === "number") return trip.actualDurationInMinutes;
      if (typeof trip.plannedDurationInMinutes === "number") return trip.plannedDurationInMinutes;
      try {
        const o = new Date(trip.legs[0].origin.plannedDateTime);
        const lastLeg = trip.legs[trip.legs.length - 1];
        const d = new Date(lastLeg.destination.plannedDateTime);
        return Math.round((d - o) / 60000);
      } catch (e) {
        return 9999;
      }
    };

    // Comparator returning the "better" trip per the user's tie-break
    // rules:
    //   1. Smallest |diff| (closest to favourite time).
    //   2. If equal: prefer the one BEFORE the favourite time
    //      (negative diff wins over positive).
    //   3. If both on the same side: shortest travel time wins.
    const isBetter = (cand, candDiff, current, currentDiff) => {
      if (current === null) return true;
      const aC = Math.abs(candDiff);
      const aB = Math.abs(currentDiff);
      if (aC !== aB) return aC < aB;
      // Same absolute distance: prefer "before" (negative diff).
      if (Math.sign(candDiff) !== Math.sign(currentDiff)) {
        return candDiff < currentDiff;
      }
      // Same side: shortest journey wins.
      return tripDuration(cand) < tripDuration(current);
    };

    for (let i = 1; i <= (this._config.fav_slots || 1); i++) {
      const slotKey = `slot_${i}`;
      // Already auto-pinned for this slot today → skip silently. The
      // pinned trip may have rolled out of the NS window by now, but
      // that is fine — the user only asked for one per slot per day.
      if (this._autoPinnedSlots.has(slotKey)) continue;

      const h = this._config[`auto_hour_${i}`];
      const m = this._config[`auto_min_${i}`];
      const daysStr = this._config[`auto_days_${i}`] || "";
      const activeDays = daysStr.split(",").filter(x => x !== "").map(Number);

      if (h === undefined || m === undefined) continue;
      if (!activeDays.includes(dag)) continue;

      const favMinutes = parseInt(h, 10) * 60 + parseInt(m, 10);
      let bestTrip = null;
      let bestDiff = 0;

      (stateObj.attributes.trips || []).forEach(trip => {
        if (!trip.legs || !trip.legs[0] || !trip.ctxRecon) return;
        const tDate = new Date(trip.legs[0].origin.plannedDateTime);
        if (isNaN(tDate.getTime())) return;
        const tripMinutes = tDate.getHours() * 60 + tDate.getMinutes();

        let diff = tripMinutes - favMinutes;
        if (diff < -720) diff += 1440;
        if (diff > 720) diff -= 1440;
        if (Math.abs(diff) > 60) return;  // only consider trips within ±1h

        if (isBetter(trip, diff, bestTrip, bestDiff)) {
          bestTrip = trip;
          bestDiff = diff;
        }
      });

      if (!bestTrip) continue;

      const ctx = bestTrip.ctxRecon;
      // Either pin it ourselves or, if the server already tracks it,
      // simply mark the slot as satisfied for the day.
      this._autoPinnedSlots.add(slotKey);
      this.saveAutoPinned();

      if (!trackedTrips.includes(ctx)) {
        this._pendingTrack.add(ctx);
        this.favTimestamps[ctx] = Date.now();
        this.saveTimestamps();
        this._hass.callService("ns_reisadvies", "track_trip", {
          entity_id: this._config.entity,
          ctx_recon: ctx,
        }).catch(() => {});
        setTimeout(() => this.updateContent(), 50);
      }
    }
  }

  formatDuration(minutes) {
    const lang = _lang(this._hass);
    const minShort = (I18N[lang] || I18N.en).minutes_short;
    if (minutes < 60) return `${minutes} ${minShort}`;
    const hours = Math.floor(minutes / 60);
    const rem = minutes % 60;
    if (rem === 0) {
      const hourShort = (I18N[lang] || I18N.en).hour_short;
      return `${hours} ${hourShort}`;
    }
    return t("hour_minutes", this._hass, { h: hours, m: rem });
  }

  formatTime(ts) {
    if (!ts || String(ts).includes("NaN")) return "--:--";
    const d = new Date(ts);
    if (isNaN(d.getTime())) return "--:--";
    const tz = _tz(this._hass);
    const opts = { hour: "2-digit", minute: "2-digit" };
    if (tz) opts.timeZone = tz;
    // v2.16.24: respect Home Assistant's user preferences (Settings →
    // Profile → Time format + Language) instead of silently using the
    // browser locale. Empty array as locale → toLocaleTimeString falls
    // back to navigator.language, which is wrong when the HA user has
    // chosen e.g. Dutch but their browser runs in en-US. We pass the
    // HA language as the BCP47 locale, and override hour12 only when
    // the user has explicitly picked 12-h or 24-h (the "language" /
    // "system" choices let the locale decide on its own).
    const hass = this._hass;
    const locale = (hass && hass.locale?.language) || hass?.language || undefined;
    const tf = hass?.locale?.time_format;
    if (tf === "24") {
      opts.hour12 = false;
    } else if (tf === "12") {
      opts.hour12 = true;
    }
    return d.toLocaleTimeString(locale ? [locale] : [], opts);
  }

  calculateDelay(p, a) {
    if (!p || !a) return "";
    const diff = Math.round((new Date(a) - new Date(p)) / 60000);
    return diff > 0 ? `<span class="tl-delay">+${diff}</span>` : "";
  }

  getIcon(p) {
    const n = (p && p.displayName) ? p.displayName.toUpperCase() : "";
    if (n.includes("METRO")) return "mdi:subway-variant";
    if (n.includes("BUS")) return "mdi:bus";
    if (n.includes("TRAM")) return "mdi:tram";
    return "mdi:train";
  }

  renderComposition(leg) {
    const c = leg && leg.composition;
    if (!c) return "";
    const parts = c.parts || [];
    const num = c.numberOfParts;
    // Tooltip: type + carriage count (zichtbaar bij hover)
    const numLabel = num
      ? (num === 1 ? t("carriages_one", this._hass) : t("carriages_other", this._hass, { n: num }))
      : "";
    const typeLabel = c.trainType || "";
    const tooltip = [typeLabel, numLabel].filter(Boolean).join(" · ").replace(/"/g, "&quot;");
    const imgs = parts
      .filter(p => p.image)
      .map(p => `<img src="${p.image}" alt="${tooltip}" title="${tooltip}" loading="lazy">`)
      .join("");
    if (!imgs) return "";
    return `<div class="tl-train-composition"><span class="tcomp-images">${imgs}</span></div>`;
  }

  getCrowd(c) {
    const colors = { LOW: "#4CAF50", MEDIUM: "#FF9800", HIGH: "#F44336" };
    const color = colors[c] || "#888";
    const n = { LOW: 1, MEDIUM: 2, HIGH: 3 }[c] || 0;
    let h = "";
    for (let i = 1; i <= 3; i++) h += `<ha-icon icon="mdi:account" style="--mdc-icon-size:16px; width:16px; color:${i <= n ? color : "#888"}; opacity:${i <= n ? 1 : 0.3}; margin-right:-8px;"></ha-icon>`;
    return `<span style="display:inline-flex; align-items:center; margin-right:8px;">${h}</span>`;
  }

  updateContent() {
    if (!this._config || !this._hass) return;

    const card = this.querySelector("ha-card");
    if (card) card.header = this._config.title;

    if (!this._hasSource()) {
      this.content.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--primary-text-color);"><b>NS Reisadvies</b><br><br>${t("select_sensor", this._hass)}</div>`;
      return;
    }

    const stateObj = this._sourceState();
    if (!stateObj?.attributes?.trips) {
      this.content.innerHTML = `<div style="padding: 20px; text-align: center;">${t("loading", this._hass)}</div>`;
      return;
    }

    const serverTracked = stateObj.attributes.tracked_trips || [];
    this._liveMapEnabled = !!stateObj.attributes.live_train_map_enabled;

    // First time we have hass + config + the live map enabled, kick
    // off the rail-data load + per-leg route pre-computation. Both run
    // off the main thread (yields between trips) so the card render
    // stays snappy. Cached on the class so other card instances on
    // the same page reuse it.
    if (this._liveMapEnabled && !this._railWarmKicked) {
      this._railWarmKicked = true;
      this._warmRouteCache().catch(err => {
        console.warn("[ns-reisadvies] route pre-warm failed", err);
      });
    }
    // Configurable poll cadence while the modal is open. Clamp to the
    // same 5–60 s server-side range so a stale attribute can never
    // accidentally hammer the API.
    const refreshAttr = Number(stateObj.attributes.live_map_refresh_seconds);
    this._liveMapRefreshMs = (Number.isFinite(refreshAttr) ? Math.max(5, Math.min(60, refreshAttr)) : 10) * 1000;

    this.cleanOldFavorites(serverTracked);
    this.processAutoFavs(stateObj);

    const allTrips = stateObj.attributes.trips || [];

    serverTracked.forEach(ctx => this._pendingTrack.delete(ctx));
    Array.from(this._pendingUntrack).forEach(ctx => {
      if (!serverTracked.includes(ctx)) this._pendingUntrack.delete(ctx);
    });

    // v2.16.25: also drop trips whose departure is more than one
    // minute in the past on the card side. The coordinator already
    // applies the same filter at poll time, but between polls
    // (default 5 min) the cached sensor state still holds departed
    // trips. The 30-second card-side tick in connectedCallback
    // re-runs this filter so trains disappear in real-time. Pinned
    // favourites are exempt — they follow the Favourite retention
    // (hours) timer.
    const _nowMs = Date.now();
    const _STALE_AFTER_MS = 60 * 1000;
    const _isPinnedCtx = (ctx) =>
      !!ctx && (
        (serverTracked.includes(ctx) && !this._pendingUntrack.has(ctx))
        || this._pendingTrack.has(ctx)
      );
    const _hasDeparted = (trip) => {
      const leg0 = (trip.legs || [])[0];
      const origin = (leg0 && leg0.origin) || {};
      const iso = origin.actualDateTime || origin.plannedDateTime;
      if (!iso) return false;
      const ms = new Date(iso).getTime();
      if (isNaN(ms)) return false;
      return ms + _STALE_AFTER_MS < _nowMs;
    };
    const freshTrips = allTrips.filter(
      t => _isPinnedCtx(t.ctxRecon) || !_hasDeparted(t)
    );

    const tripsToShow = freshTrips.filter((trip, index) => {
      const ctx = trip.ctxRecon;
      let isFav = false;

      if (ctx) {
        if (serverTracked.includes(ctx) && !this._pendingUntrack.has(ctx)) isFav = true;
        if (this._pendingTrack.has(ctx)) isFav = true;
      }

      return index < this._config.max_rows || isFav;
    });

    if (tripsToShow.length === 0) {
      this.content.innerHTML = `<div style="padding: 20px; text-align: center;">${t("no_trips", this._hass)}</div>`;
      return;
    }

    let html = `
      <style>
        .ns-container { font-family: sans-serif; font-size: ${this._config.scale}%; line-height: 1.4; color: var(--primary-text-color); padding: 0 16px 16px 16px; }
        .trip-wrapper { position: relative; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--divider-color); }
        .trip-wrapper:last-child { border-bottom: none; margin-bottom: 0; }
        .trip-header-bar { display: flex; justify-content: flex-end; height: 30px; align-items: center; margin-bottom: 5px; }
        .fav-heart { cursor: pointer; z-index: 10; padding: 5px; }
        .heart-grey { color: var(--disabled-text-color); opacity: 0.3; }
        .heart-red { color: #ff5252; opacity: 1; }
        .tl-grid { display: grid; grid-template-columns: 75px 25px 1fr; gap: 0; }
        .tl-time { text-align: right; font-weight: bold; font-size: 1.1em; padding-right: 12px; color: var(--primary-text-color); white-space: nowrap; }
        .tl-delay { color: #ff5252; font-size: 0.9em; font-weight: bold; display: block; text-align: right; padding-right: 12px; margin-top: -2px; }
        .tl-duration-small { text-align: right; font-size: 0.8em; color: var(--secondary-text-color); padding-right: 12px; height: 100%; display: flex; align-items: center; justify-content: flex-end; }
        .tl-line-col { position: relative; display: flex; justify-content: center; }
        .tl-dot { width: 12px; height: 12px; border-radius: 50%; background: var(--card-background-color); border: 3px solid #3b82f6; z-index: 2; margin-top: 4px; }
        .tl-dot-fill { background: #3b82f6; }
        /* v2.22.0: a station the train has already left, in the same
           yellow the live map uses for the stretch behind the train. */
        .tl-dot-done { border-color: #FFC917; }
        .tl-dot-done.tl-dot-fill { background: #FFC917; }
        .tl-line { position: absolute; top: 10px; bottom: -10px; width: 3px; background: #3b82f6; z-index: 1; }
        .tl-info { padding-left: 12px; padding-bottom: 8px; }
        .tl-station-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
        .tl-station-name { font-weight: bold; font-size: 1.1em; flex-grow: 1; word-break: break-word; }
        .tl-platform { background: #003082; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em; white-space: nowrap; flex-shrink: 0; }
        .tl-platform-changed { background: #db4437; }
        .tl-travel-info { padding: 4px 0 12px 12px; font-size: 0.9em; min-width: 0; }
        .tl-direction-main { color: #FFC917; font-weight: bold; font-size: 1.05em; display: block; margin-bottom: 4px; }
        .tl-train-details { color: var(--secondary-text-color); display: flex; align-items: center; flex-wrap: wrap; }
        .detail-separator { margin: 0 6px; opacity: 0.5; font-size: 0.8em; }
        .tl-train-meta { font-size: 0.85em; color: var(--secondary-text-color); margin-top: 4px; opacity: 0.8; }
        .tl-train-composition { margin-top: 6px; max-width: 100%; overflow: hidden; }
        .tl-train-composition .tcomp-images {
          display: flex;
          align-items: center;
          gap: 2px;
          overflow-x: auto;
          overflow-y: hidden;
          scroll-behavior: smooth;
          -webkit-overflow-scrolling: touch;
          cursor: grab;
          padding-bottom: 4px;
        }
        .tl-train-composition .tcomp-images.dragging { cursor: grabbing; }
        .tl-train-composition .tcomp-images img {
          height: 38px;
          width: auto;
          object-fit: contain;
          display: block;
          flex-shrink: 0;
          user-select: none;
          -webkit-user-drag: none;
          pointer-events: none;
        }
        .tl-train-composition .tcomp-images::-webkit-scrollbar { height: 4px; }
        .tl-train-composition .tcomp-images::-webkit-scrollbar-track { background: transparent; }
        .tl-train-composition .tcomp-images::-webkit-scrollbar-thumb { background: var(--divider-color); border-radius: 2px; }
        .tl-train-composition .tcomp-images::-webkit-scrollbar-thumb:hover { background: var(--secondary-text-color); }
        .tl-wait-row { display: grid; grid-template-columns: 75px 25px 1fr; height: 30px; align-items: center; }
        .tl-wait-line-col { display: flex; justify-content: center; }
        .tl-wait-text { padding-left: 12px; color: var(--secondary-text-color); font-style: italic; font-size: 0.9em; display: flex; align-items: center; }
        .tl-checkout-row { display: grid; grid-template-columns: 75px 25px 1fr; min-height: 26px; align-items: center; padding: 2px 0; }
        .tl-checkout-line-col { display: flex; justify-content: center; }
        .tl-checkout-text { padding-left: 12px; color: #FF6B00; font-weight: 500; font-style: italic; font-size: 0.88em; display: flex; align-items: center; gap: 4px; }
        .tl-checkout-text ha-icon { --mdc-icon-size: 16px; color: #FF6B00; }
        .cancelled { text-decoration: line-through; text-decoration-color: #ff5252; opacity: 0.7; }
        .warning-msg { color: #ff5252; font-weight: bold; font-size: 0.9em; margin-left: 12px; text-transform: uppercase; margin-top: 8px; }
        .direct-text { color: #4CAF50; font-weight: bold; }
        .trip-footer { text-align: right; font-size: 0.85em; color: var(--secondary-text-color); margin-top: 4px; }
        .stops-toggle { display: inline-flex; align-items: center; cursor: pointer; margin-left: 4px; color: var(--primary-text-color); opacity: 0.7; transition: opacity 0.15s; }
        .stops-toggle:hover { opacity: 1; }
        .stops-toggle ha-icon { --mdc-icon-size: 18px; }
        .stops-toggle.open ha-icon { transform: rotate(180deg); transition: transform 0.2s; }
        .stop-row { display: grid; grid-template-columns: 75px 25px 1fr; align-items: center; min-height: 28px; padding: 2px 0; }
        .stop-row .stop-time-cell { text-align: right; padding-right: 12px; color: var(--primary-text-color); font-size: 0.95em; font-weight: 500; white-space: nowrap; font-variant-numeric: tabular-nums; display: flex; flex-direction: column; align-items: flex-end; gap: 1px; line-height: 1.2; }
        .stop-row .stop-time-cell .stop-time-line { display: inline-flex; align-items: baseline; gap: 4px; }
        .stop-row .stop-time-cell .stop-time-prefix { font-size: 0.75em; opacity: 0.65; font-weight: 700; text-transform: uppercase; }
        .stop-row .stop-time-cell .stop-delay { color: #ff5252; font-weight: bold; margin-left: 2px; }
        .stop-row .stop-line-col { position: relative; display: flex; justify-content: center; align-self: stretch; }
        /* v2.23.0: a small dot for an intermediate stop, so a station
           reads as a station rather than a gap in the dashes. */
        .stop-row .stop-dot { position: absolute; top: 50%; left: 50%; width: 7px; height: 7px;
          border-radius: 50%; background: var(--card-background-color);
          border: 2px solid var(--ns-stop-line, #3b82f6); transform: translate(-50%, -50%); z-index: 2; }
        .stop-row .stop-line-col::before { content: ""; width: 0; border-left: 2px dashed var(--ns-stop-line, #3b82f6); height: 100%; }
        .stop-row .stop-info { padding-left: 12px; display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 0.95em; color: var(--secondary-text-color); }
        .stop-row .stop-info .stop-name { flex: 1; word-break: break-word; }
        .tl-platform-small { background: #003082; color: white; padding: 1px 6px; border-radius: 3px; font-weight: bold; font-size: 0.78em; white-space: nowrap; flex-shrink: 0; }
        .tl-platform-small.tl-platform-changed { background: #db4437; }
        .stop-row.cancelled .stop-name, .stop-row.cancelled .stop-time-cell { text-decoration: line-through; text-decoration-color: #ff5252; opacity: 0.7; }
        .tl-map-icon-row { margin-top: 4px; display: flex; justify-content: flex-end; }
        .tl-map-icon-btn {
          display: inline-flex; align-items: center; gap: 4px;
          background: transparent; border: 1px solid var(--divider-color);
          color: var(--primary-text-color); border-radius: 14px;
          padding: 2px 8px 2px 6px; cursor: pointer;
          font-size: 0.78em; opacity: 0.8; transition: opacity .15s, background .15s;
          line-height: 1; white-space: nowrap;
        }
        .tl-map-icon-btn:hover { opacity: 1; background: rgba(255, 107, 0, 0.08); }
        .tl-map-icon-btn ha-icon { --mdc-icon-size: 16px; color: #FF6B00; }
        .ns-map-modal {
          position: fixed; inset: 0; z-index: 9999;
          background: rgba(0, 0, 0, 0.55);
          display: flex; align-items: center; justify-content: center;
          backdrop-filter: blur(2px);
        }
        .ns-map-modal .ns-map-card {
          background: var(--card-background-color, #1a1a1a); color: var(--primary-text-color);
          border-radius: 12px; box-shadow: 0 12px 40px rgba(0,0,0,0.5);
          width: min(720px, 92vw); height: min(640px, 86vh);
          display: flex; flex-direction: column; overflow: hidden;
        }
        .ns-map-modal .ns-map-header {
          display: flex; align-items: center; justify-content: space-between;
          padding: 10px 14px; border-bottom: 1px solid var(--divider-color);
        }
        .ns-map-modal .ns-map-header .ns-map-title {
          font-weight: 600; font-size: 1em; display: flex; align-items: center; gap: 8px;
        }
        .ns-map-modal .ns-map-header .ns-map-title .ns-map-train { color: #FF6B00; }
        .ns-map-modal .ns-map-header .ns-map-meta {
          font-size: 0.78em; opacity: 0.75; margin-left: 8px; font-weight: 400;
        }
        .ns-map-modal .ns-map-close {
          cursor: pointer; padding: 4px; border-radius: 50%; display: inline-flex;
        }
        .ns-map-modal .ns-map-close:hover { background: rgba(255,255,255,0.08); }
        .ns-map-modal .ns-map-body {
          flex: 1; min-height: 0; position: relative; background: var(--card-background-color);
        }
        .ns-map-modal ha-map {
          position: absolute; inset: 0; width: 100%; height: 100%;
        }
        .ns-map-modal .ns-map-loading {
          position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
          font-size: 0.9em; opacity: 0.7;
        }
        .ns-map-modal .ns-map-empty {
          position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
          padding: 20px; text-align: center; font-size: 0.95em; color: var(--secondary-text-color);
        }
        /* v2.15.0: per-route heading shown only when the route has a
           custom name. Two routes between the same stations with
           different filters can sit on the same dashboard with their
           own visible identities. */
        .route-heading { padding: 8px 0 12px 0; border-bottom: 1px solid var(--divider-color); margin-bottom: 16px; }
        .route-heading .route-name { font-size: 1.15em; font-weight: 700; color: var(--primary-text-color); line-height: 1.2; }
        .route-heading .route-stations { font-size: 0.85em; color: var(--secondary-text-color); margin-top: 2px; }
        /* v2.16.0: badge bovenaan dat de getoonde trips voor een
           latere dag zijn (filter-anker is gerold over middernacht). */
        .day-offset-badge { display: inline-block; padding: 4px 10px; border-radius: 12px; background: #FFC917; color: #003082; font-weight: 700; font-size: 0.85em; margin: 0 0 12px 0; }
        .day-offset-badge ha-icon { --mdc-icon-size: 16px; vertical-align: -3px; margin-right: 4px; }
      </style>
      <div class="ns-container">`;

    // v2.15.0: render an explicit per-route heading when the user gave
    // the route a custom name. For unnamed routes we skip this — the
    // default Home Assistant card title (the entity friendly name) is
    // already "<from> → <to>" and would otherwise duplicate.
    const routeName = stateObj.attributes.route_name;
    const fromStation = stateObj.attributes.from_station;
    const toStation = stateObj.attributes.to_station;
    if (routeName && fromStation && toStation) {
      html += `<div class="route-heading">`
            + `<div class="route-name">${routeName}</div>`
            + `<div class="route-stations">${fromStation} → ${toStation}</div>`
            + `</div>`;
    }

    // v2.16.1: yellow badge appears whenever the FIRST trip we are
    // about to render is on a future day — with or without a route
    // filter. Late-evening routes whose next train physically leaves
    // after midnight now also get "Reizen voor morgen". Three label
    // flavours, in order of specificity:
    //   * Specific-date filter set → "Reizen voor 24 december 2026" —
    //     literal date, regardless of offset.
    //   * Offset == 1 (and no day-of-week filter) → "Reizen voor
    //     morgen" — relative is the most natural for "tomorrow".
    //   * Otherwise (offset > 1, or weekday filter active) → spell
    //     out "Reizen voor maandag 11 mei 2026" so the user knows
    //     exactly which day they're looking at.
    const dayOffset = Number(stateObj.attributes.target_day_offset || 0);
    const targetDateIso = stateObj.attributes.target_date || null;
    if (dayOffset > 0 && targetDateIso) {
      const lang = _lang(this._hass);
      const targetDate = new Date(targetDateIso + "T00:00:00");
      const weekdayFmt = new Intl.DateTimeFormat(
        lang, { weekday: "long" },
      ).format(targetDate);
      const dateFmt = new Intl.DateTimeFormat(
        lang, { day: "numeric", month: "long", year: "numeric" },
      ).format(targetDate);
      const tplDate = t("badge_for_date", this._hass) || "Reizen voor {date}";
      const tplTomorrow = t("badge_tomorrow", this._hass) || "Reizen voor morgen";

      const specificDate = stateObj.attributes.filter_date;
      const filterDays = stateObj.attributes.filter_days;
      const hasWeekdayFilter = Array.isArray(filterDays) && filterDays.length > 0;
      let label;
      if (specificDate) {
        label = tplDate.replace("{date}", dateFmt);
      } else if (dayOffset === 1 && !hasWeekdayFilter) {
        label = tplTomorrow;
      } else {
        // Weekday filter, or just a far-future day → "<weekday> <date>".
        label = tplDate.replace("{date}", `${weekdayFmt} ${dateFmt}`);
      }
      const icon = dayOffset === 1 ? "mdi:calendar-tomorrow" : "mdi:calendar-clock";
      html += `<div class="day-offset-badge"><ha-icon icon="${icon}"></ha-icon>${label}</div>`;
    }

    const unknownLabel = t("unknown", this._hass);
    const platformLabel = t("platform", this._hass);

    tripsToShow.forEach((trip, tIdx) => {
      const ctx = trip.ctxRecon;
      let isFav = false;
      if (ctx) {
        if (serverTracked.includes(ctx) && !this._pendingUntrack.has(ctx)) isFav = true;
        if (this._pendingTrack.has(ctx)) isFav = true;
      }

      let dist = 0;
      const isCancelled = trip.status === "CANCELLED";
      const cCls = isCancelled ? "cancelled" : "";

      html += `<div class="trip-wrapper">
        <div class="trip-header-bar">
          <div class="fav-heart ${isFav ? "heart-red" : "heart-grey"}" data-idx="${tIdx}" data-ctx="${ctx || ""}" data-fav="${isFav}" style="${this._favouritesAllowed() ? "" : "display:none"}">
            <ha-icon icon="${isFav ? "mdi:heart" : "mdi:heart-outline"}"></ha-icon>
          </div>
        </div>`;

      trip.legs.forEach((leg, index) => {
        if (leg.distanceInMeters) dist += leg.distanceInMeters;
        const tDep = this.formatTime(leg.origin.plannedDateTime);
        const tArr = this.formatTime(leg.destination.plannedDateTime);
        const dDep = this.calculateDelay(leg.origin.plannedDateTime, leg.origin.actualDateTime);
        const dArr = this.calculateDelay(leg.destination.plannedDateTime, leg.destination.actualDateTime);

        let legDur = "";
        if (leg.origin.plannedDateTime && leg.destination.plannedDateTime) {
          const diff = Math.round((new Date(leg.destination.plannedDateTime) - new Date(leg.origin.plannedDateTime)) / 60000);
          const minLabel = t("minutes_short", this._hass);
          legDur = isNaN(diff) ? "" : `${diff} ${minLabel}`;
        }

        const pCls = (leg.origin.actualTrack !== leg.origin.plannedTrack && leg.origin.plannedTrack) ? "tl-platform tl-platform-changed" : "tl-platform";
        const pArrCls = (leg.destination.actualTrack !== leg.destination.plannedTrack && leg.destination.plannedTrack) ? "tl-platform tl-platform-changed" : "tl-platform";

        // Count "real" intermediate stops — exclude origin/destination
        // and stops where the train passes without stopping.
        const intermediates = (leg.stops || []).slice(1, -1).filter(s => !s.passing);
        const sCount = intermediates.length;
        const legKey = `${tIdx}_${index}`;
        const isExpanded = this._expandedLegs.has(legKey);

        const trainNum = (leg.product && leg.product.number) ? String(leg.product.number) : "";

        // v2.22.0: the vertical line is coloured along with the train.
        // Actual times where NS gives them, planned otherwise. The two
        // line pieces of this leg share one span: from leaving the
        // origin to reaching whichever station comes next in the
        // column — the first intermediate stop when the stops are
        // unfolded, the destination when they are not.
        const stamp = (...values) => {
          for (const value of values) {
            const ms = Date.parse(value || "");
            if (Number.isFinite(ms)) return ms;
          }
          return NaN;
        };
        const progStart = stamp(leg.origin.actualDateTime, leg.origin.plannedDateTime);
        const progArrival = stamp(
          leg.destination.actualDateTime, leg.destination.plannedDateTime,
        );
        const firstStop = isExpanded && sCount > 0 ? intermediates[0] : null;
        const progEnd = firstStop
          ? stamp(firstStop.actualArrivalDateTime, firstStop.plannedArrivalDateTime,
                  firstStop.actualDepartureDateTime, firstStop.plannedDepartureDateTime)
          : progArrival;
        // Where the clock says the train is, and — when the feed has
        // the train — where it actually is. The second wins; see
        // _paintProgress.
        const progKey = (station) => String(
          (station && (station.uicCode || station.stationCode)) || "",
        );
        const progName = (station) => String((station && station.name) || "");
        const endStation = firstStop || leg.destination;
        const progAttrs = Number.isFinite(progStart) && Number.isFinite(progEnd)
          ? ` data-prog-group="${tIdx}-${index}" data-prog-start="${progStart}" data-prog-end="${progEnd}"`
            + ` data-prog-train="${trainNum}" data-prog-from="${progKey(leg.origin)}"`
            + ` data-prog-to="${progKey(endStation)}" data-prog-from-name="${progName(leg.origin)}"`
            + ` data-prog-to-name="${progName(endStation)}"`
          : "";
        const dotAttrs = (station, moment) => (Number.isFinite(moment)
          ? ` data-prog-at="${moment}" data-prog-train="${trainNum}"`
            + ` data-prog-uic="${progKey(station)}" data-prog-name="${progName(station)}"`
          : "");
        const depDotAttr = dotAttrs(leg.origin, progStart);
        const arrDotAttr = dotAttrs(leg.destination, progArrival);
        const stopLabel = sCount === 1 ? t("stop_one", this._hass) : t("stop_other", this._hass, { n: sCount });
        const toggleLabel = isExpanded ? t("hide_stops", this._hass) : t("show_stops", this._hass);
        const sText = sCount <= 0
          ? `<span class="direct-text">${t("direct", this._hass)}</span>`
          : `<span>${stopLabel}</span><span class="stops-toggle ${isExpanded ? "open" : ""}" data-leg-key="${legKey}" title="${toggleLabel}" role="button"><ha-icon icon="mdi:chevron-down"></ha-icon></span>`;
        // Live positions come from ProRail's OBIS feed, which only
        // tracks Dutch operators. Foreign carriers (DB ICE, NMBS,
        // Eurostar) and most replacement bus services are missing —
        // suppress the icon for those so a user does not get an empty
        // marker. Whitelist beats blacklist: easier to extend.
        const opCode = String((leg.product && leg.product.operatorCode) || "").toUpperCase();
        const obisOperators = new Set([
          "NS", "ARR", "ARRIVA", "BLAUWNET", "KEOLIS",
          "KEOLIS-SYNTUS", "SYNTUS", "QBUZZ", "BRENG",
        ]);
        const showMapIcon = this._liveMapEnabled
          && trainNum
          && Array.isArray(leg.stops) && leg.stops.length > 1
          && obisOperators.has(opCode);
        // v2.17.2: `tIdx` indexes tripsToShow, which is allTrips minus
        // departed trips minus the max_rows cut. openLiveMap and the
        // poller read attributes.trips, so a positional index taken
        // from the rendered rows points at a different train as soon
        // as one has departed. Emit the index into the raw list, plus
        // the train number and planned departure of the row, so the
        // click can be resolved by identity if the list shifts again
        // between render and click.
        const rawTripIdx = allTrips.indexOf(trip);
        const legDepIso = (leg.origin && leg.origin.plannedDateTime) || "";
        const mapIconHtml = showMapIcon
          ? `<div class="tl-map-icon-row"><button class="tl-map-icon-btn" data-trip-idx="${rawTripIdx >= 0 ? rawTripIdx : tIdx}" data-leg-idx="${index}" data-train-num="${trainNum}" data-dep="${legDepIso}" title="${t("show_live_map", this._hass)}"><ha-icon icon="mdi:map-marker-radius-outline"></ha-icon><span>${t("live_map_button", this._hass)}</span></button></div>`
          : "";

        html += `
          <div class="tl-grid">
            <div><div class="tl-time ${cCls}">${tDep}</div>${dDep}</div>
            <div class="tl-line-col"><div class="tl-dot ${index === 0 ? "tl-dot-fill" : ""}"${depDotAttr}></div><div class="tl-line"${progAttrs}></div></div>
            <div class="tl-info"><div class="tl-station-header"><span class="tl-station-name ${cCls}">${leg.origin.name || unknownLabel}</span>
            <span class="${pCls} ${cCls}">${platformLabel} ${leg.origin.actualTrack || leg.origin.plannedTrack || "?"}</span></div>${mapIconHtml}</div>
          </div>
          <div class="tl-grid">
            <div class="tl-duration-small ${cCls}">${legDur}</div>
            <div class="tl-line-col"><div class="tl-line"${progAttrs}></div></div>
            <div class="tl-travel-info ${cCls}"><span class="tl-direction-main ${cCls}">${leg.direction || unknownLabel}</span>
              <div class="tl-train-details">${sText}<span class="detail-separator">•</span>
              <ha-icon icon="${this.getIcon(leg.product)}" style="--mdc-icon-size:16px; margin-right:4px;"></ha-icon>${(leg.product && leg.product.displayName) || unknownLabel}
              <span class="detail-separator">•</span>${this.getCrowd(leg.crowdForecast)}</div>
              <div class="tl-train-meta">${leg.name || unknownLabel}${leg.composition && leg.composition.trainType ? ' · ' + leg.composition.trainType : ''}</div>
              ${this.renderComposition(leg)}
            </div>
          </div>`;

        // Expanded intermediate stops — rendered BETWEEN origin/info
        // and destination so they sit visually inside the leg, not
        // beneath the next station.
        if (isExpanded && sCount > 0) {
          intermediates.forEach(stop => {
            const arrPlanned = stop.plannedArrivalDateTime || stop.plannedDepartureDateTime;
            const depPlanned = stop.plannedDepartureDateTime || stop.plannedArrivalDateTime;
            const tArrStop = this.formatTime(arrPlanned);
            const tDepStop = this.formatTime(depPlanned);
            const sameTime = (arrPlanned && depPlanned && arrPlanned === depPlanned) || (tArrStop === tDepStop);

            const arrDelay = stop.arrivalDelayInSeconds ? Math.round(stop.arrivalDelayInSeconds / 60) : 0;
            const depDelay = stop.departureDelayInSeconds ? Math.round(stop.departureDelayInSeconds / 60) : 0;
            const arrLabel = t("stop_arrival_short", this._hass);
            const depLabel = t("stop_departure_short", this._hass);

            let timeHtml;
            if (sameTime) {
              const delay = depDelay || arrDelay;
              const delayHtml = delay > 0 ? `<span class="stop-delay">+${delay}</span>` : "";
              timeHtml = `<span class="stop-time-line"><span>${tDepStop}</span>${delayHtml}</span>`;
            } else {
              const aDelay = arrDelay > 0 ? `<span class="stop-delay">+${arrDelay}</span>` : "";
              const dDelay = depDelay > 0 ? `<span class="stop-delay">+${depDelay}</span>` : "";
              timeHtml =
                `<span class="stop-time-line"><span class="stop-time-prefix">${arrLabel}</span><span>${tArrStop}</span>${aDelay}</span>` +
                `<span class="stop-time-line"><span class="stop-time-prefix">${depLabel}</span><span>${tDepStop}</span>${dDelay}</span>`;
            }

            const stopTrack = stop.actualDepartureTrack || stop.actualArrivalTrack
              || stop.plannedDepartureTrack || stop.plannedArrivalTrack || "";
            const plannedStopTrack = stop.plannedDepartureTrack || stop.plannedArrivalTrack;
            const actualStopTrack = stop.actualDepartureTrack || stop.actualArrivalTrack;
            const stopTrackChanged = !!(actualStopTrack && plannedStopTrack && actualStopTrack !== plannedStopTrack);
            const stopPlatformCls = stopTrackChanged ? "tl-platform-small tl-platform-changed" : "tl-platform-small";
            const platformHtml = stopTrack
              ? `<span class="${stopPlatformCls}">${platformLabel} ${stopTrack}</span>`
              : "";

            const stopMoment = stamp(
              stop.actualDepartureDateTime, stop.actualArrivalDateTime,
              stop.plannedDepartureDateTime, stop.plannedArrivalDateTime,
            );
            const stopProgAttr = Number.isFinite(stopMoment)
              ? ` data-prog-at="${stopMoment}" data-prog-train="${trainNum}"`
                + ` data-prog-uic="${stop.uicCode || stop.stationCode || ""}"`
                + ` data-prog-name="${stop.name || ""}"`
              : "";
            const rowCls = stop.cancelled ? "stop-row cancelled" : "stop-row";
            html += `<div class="${rowCls}">
              <div class="stop-time-cell">${timeHtml}</div>
              <div class="stop-line-col"${stopProgAttr}><span class="stop-dot"></span></div>
              <div class="stop-info"><span class="stop-name">${stop.name || unknownLabel}</span>${platformHtml}</div>
            </div>`;
          });
        }

        html += `
          <div class="tl-grid">
            <div><div class="tl-time ${cCls}">${tArr}</div>${dArr}</div>
            <div class="tl-line-col"><div class="tl-dot ${index === trip.legs.length - 1 ? "tl-dot-fill" : ""}"${arrDotAttr}></div></div>
            <div class="tl-info"><div class="tl-station-header"><span class="tl-station-name ${cCls}">${leg.destination.name || unknownLabel}</span>
            <span class="${pArrCls} ${cCls}">${platformLabel} ${leg.destination.actualTrack || leg.destination.plannedTrack || "?"}</span></div></div>
          </div>`;

        if (index < trip.legs.length - 1) {
          const nextLeg = trip.legs[index + 1];
          const wMin = Math.round((new Date(nextLeg.origin.actualDateTime) - new Date(leg.destination.actualDateTime)) / 60000);
          const transferText = isNaN(wMin)
            ? t("transfer", this._hass)
            : t("transfer_n", this._hass, { n: wMin });
          html += `<div class="tl-wait-row"><div></div><div class="tl-wait-line-col"><ha-icon icon="mdi:walk" style="--mdc-icon-size:16px; color:#888;"></ha-icon></div>
          <div class="tl-wait-text ${cCls}">${transferText}</div></div>`;

          // When the operator changes between legs (e.g. NS Sprinter
          // to Blauwnet) NS itself shows a check-out / check-in note
          // because the OV-chipkaart needs separate taps. Mirror that
          // in the card so travellers do not forget.
          const fromOp = (leg.product && (leg.product.operatorName || leg.product.operatorCode)) || "";
          const toOp = (nextLeg.product && (nextLeg.product.operatorName || nextLeg.product.operatorCode)) || "";
          if (fromOp && toOp && fromOp.toLowerCase() !== toOp.toLowerCase()) {
            const text = t("checkout_checkin", this._hass, { from: fromOp, to: toOp });
            html += `<div class="tl-checkout-row"><div></div><div class="tl-checkout-line-col"><ha-icon icon="mdi:contactless-payment-circle-outline"></ha-icon></div>
            <div class="tl-checkout-text ${cCls}">${text}</div></div>`;
          }
        }
      });
      if (isCancelled) {
        html += `<div class="warning-msg">${t("cancelled", this._hass)}</div>`;
      } else {
        html += `<div class="trip-footer">${t("total_travel", this._hass)}: ${this.formatDuration(trip.actualDurationInMinutes || 0)}${dist > 0 ? ` • ${Math.round(dist / 1000)} km` : ""}</div>`;
      }

      html += `</div>`;
    });
    this.content.innerHTML = html + `</div>`;
    this._paintProgress();

    const hearts = this.content.querySelectorAll(`.fav-heart`);
    hearts.forEach(btn => {
      const ctxRecon = btn.getAttribute("data-ctx");
      const isFav = btn.getAttribute("data-fav") === "true";
      btn.addEventListener("click", (e) => this.toggleFavorite(ctxRecon, isFav, e));
    });

    const toggles = this.content.querySelectorAll(`.stops-toggle`);
    toggles.forEach(btn => {
      const key = btn.getAttribute("data-leg-key");
      btn.addEventListener("click", (e) => this.toggleStops(key, e));
    });

    // Event delegation at the card root so the handler survives any
    // re-render and so the click can't be intercepted by an ancestor
    // before reaching us. Use capture phase to win against HA's own
    // click handlers on parent elements.
    if (!this._mapDelegated) {
      this._mapDelegated = true;
      const handler = (e) => {
        const t = e.target;
        if (!t || !t.closest) return;
        const btn = t.closest('.tl-map-icon-btn');
        if (!btn || !this.contains(btn)) return;
        e.preventDefault();
        e.stopPropagation();
        const tIdx = parseInt(btn.getAttribute("data-trip-idx"), 10);
        const lIdx = parseInt(btn.getAttribute("data-leg-idx"), 10);
        const expect = {
          num: btn.getAttribute("data-train-num") || "",
          dep: btn.getAttribute("data-dep") || "",
        };
        console.info("[ns-reisadvies] live map click", {tIdx, lIdx, ...expect});
        try {
          this.openLiveMap(tIdx, lIdx, expect);
        } catch (err) {
          console.error("[ns-reisadvies] openLiveMap threw:", err);
        }
      };
      this.addEventListener("click", handler, true);
    }

    // Drag-to-scroll for the carriage composition strip on desktop.
    // Touch devices scroll natively via swipe; mouse-wheel works too.
    const scrollers = this.content.querySelectorAll(`.tcomp-images`);
    scrollers.forEach(el => this._wireDragScroll(el));
  }

  _wireDragScroll(el) {
    let isDown = false;
    let startX = 0;
    let scrollLeft = 0;
    el.addEventListener("mousedown", (e) => {
      // Only respond to primary button
      if (e.button !== 0) return;
      isDown = true;
      el.classList.add("dragging");
      startX = e.pageX - el.offsetLeft;
      scrollLeft = el.scrollLeft;
    });
    const stop = () => {
      if (!isDown) return;
      isDown = false;
      el.classList.remove("dragging");
    };
    el.addEventListener("mouseleave", stop);
    el.addEventListener("mouseup", stop);
    el.addEventListener("mousemove", (e) => {
      if (!isDown) return;
      e.preventDefault();
      const x = e.pageX - el.offsetLeft;
      const walk = (x - startX) * 1.4;
      el.scrollLeft = scrollLeft - walk;
    });
  }

  toggleStops(legKey, event) {
    if (event) event.stopPropagation();
    if (!legKey) return;
    if (this._expandedLegs.has(legKey)) {
      this._expandedLegs.delete(legKey);
    } else {
      this._expandedLegs.add(legKey);
    }
    this.updateContent();
  }

  // ----- Live train map ---------------------------------------------------
  //
  // Opens an overlay with HA's <ha-map> showing the train's live position,
  // the route polyline, and a marker per stop. Position is fetched only
  // while the dialog is open (start/poll/stop WebSocket commands), so this
  // imposes zero ongoing API cost when the map is closed.

  _mapHostRoot() {
    // Anchor the modal in <home-assistant>'s shadow root when we can.
    // <ha-map> reads its websocket connection, config and theme from Lit
    // contexts that are provided by that element, and a modal parked on
    // document.body sits outside that tree. Falls back to the body.
    const ha = document.querySelector("home-assistant");
    return (ha && ha.shadowRoot) || document.body;
  }

  _injectStyles(root, id, css) {
    // Node.DOCUMENT_FRAGMENT_NODE (11) covers both shadow roots we use;
    // anything else means the modal sits in the light DOM, where the
    // document head is the right place.
    const target = (root && root.nodeType === 11) ? root : document.head;
    if (target.querySelector("style#" + id)) return;
    const style = document.createElement("style");
    style.id = id;
    style.textContent = css;
    target.appendChild(style);
  }

  _ensureModalStyles(root) {
    // The modal lives outside the card's own shadow root, so the in-card
    // <style> block does NOT apply to it. Inject once per root.
    this._injectStyles(root, "ns-reisadvies-modal-styles", this._modalCss());
    this._injectStyles(root, "ns-reisadvies-map-styles", this._mapCss());
  }

  _modalCss() {
    return `
      .ns-map-modal {
        position: fixed; inset: 0; z-index: 9999;
        background: rgba(0, 0, 0, 0.55);
        display: flex; align-items: center; justify-content: center;
        backdrop-filter: blur(2px);
      }
      .ns-map-modal .ns-map-card {
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color, #212121);
        border-radius: 12px;
        box-shadow: 0 12px 40px rgba(0,0,0,0.5);
        width: min(720px, 92vw); height: min(640px, 86vh);
        display: flex; flex-direction: column; overflow: hidden;
      }
      .ns-map-modal .ns-map-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 10px 14px; border-bottom: 1px solid var(--divider-color, #e0e0e0);
      }
      .ns-map-modal .ns-map-title {
        font-weight: 600; font-size: 1em; display: flex; align-items: center; gap: 8px;
      }
      .ns-map-modal .ns-map-title .ns-map-train { color: #FF6B00; }
      .ns-map-modal .ns-map-meta { font-size: 0.78em; opacity: 0.75; margin-left: 8px; font-weight: 400; }
      .ns-map-modal .ns-map-close {
        cursor: pointer; padding: 4px; border-radius: 50%; display: inline-flex;
      }
      .ns-map-modal .ns-map-close:hover {
        background: var(--secondary-background-color, rgba(127,127,127,0.15));
      }
      .ns-map-modal .ns-map-body {
        flex: 1; min-height: 0; position: relative;
        background: var(--card-background-color, #fff);
      }
      .ns-map-modal .ns-map-loading {
        position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
        font-size: 0.9em; opacity: 0.7;
      }
      .ns-map-modal .ns-map-empty {
        position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
        padding: 20px; text-align: center; font-size: 0.95em;
        color: var(--secondary-text-color, #727272);
      }
    `;
  }

  _mapCss() {
    // Injected twice: into the root that holds the modal (for the map
    // container itself) and into <ha-map>'s shadow root, because the
    // stop and train markers are rendered inside that shadow root where
    // a document-level stylesheet does not reach.
    return `
      .ns-leaflet {
        position: absolute; inset: 0; width: 100%; height: 100%;
        display: block;
        background: var(--card-background-color, #fff);
      }
      .leaflet-container {
        background: var(--card-background-color, #fff); font-family: inherit;
      }
      /* Fallback raster tiles only: tint them for a dark theme. */
      .ns-map-dark .leaflet-tile-pane {
        filter: invert(1) hue-rotate(180deg) brightness(0.95) contrast(0.9);
      }
      /* Side-view train tile, mirrored to match the train's heading. */
      .ns-leaflet-train {
        width: 44px; height: 22px;
        position: relative;
        transition: transform 0.5s ease-out;
        filter: drop-shadow(0 2px 3px rgba(0,0,0,0.55));
      }
      .ns-leaflet-train svg { display: block; width: 100%; height: 100%; }
      .ns-leaflet-train .ns-cat {
        position: absolute; left: 50%; top: 50%;
        transform: translate(-50%, -50%);
        font: 700 8px/1 "Helvetica Neue", Helvetica, Arial, sans-serif;
        color: #003082; letter-spacing: 0.3px;
        text-shadow: 0 1px 0 rgba(255,255,255,0.7);
        pointer-events: none;
      }
      .ns-leaflet-stop {
        width: 14px; height: 14px; border-radius: 50%;
        background: var(--card-background-color, #fff);
        border: 3px solid #FFC917;
        box-shadow: 0 1px 3px rgba(0,0,0,0.4);
      }
      .ns-leaflet-stop.endpoint { width: 18px; height: 18px; border-width: 4px; }
    `;
  }

  // v2.17.2: resolve a leg by identity, not by position.
  //
  // The rendered rows come from `tripsToShow` — allTrips with departed
  // trips dropped and max_rows applied — while this lookup reads
  // `attributes.trips`. The two lists drift apart the moment a train
  // departs, and the sensor is repolled underneath an open map, so an
  // index captured at render time can address a different train by the
  // time it is used. That is how a row for IC 1825 to Hilversum could
  // open the map on Sprinter 7416 to Amsterdam.
  //
  // `expect` carries the train number and planned departure that were
  // on screen. The index is treated as a hint: if it still points at
  // that train, it is used as-is; otherwise the leg is found again by
  // identity and the corrected indices are returned.
  _resolveLeg(tripIdx, legIdx, expect) {
    if (!this._hass || !this._config) return null;
    const stateObj = this._sourceState();
    const trips = (stateObj && stateObj.attributes && stateObj.attributes.trips) || [];
    const wanted = expect || {};
    const matches = (leg) => {
      if (!leg || !leg.product) return false;
      if (wanted.num && String(leg.product.number) !== String(wanted.num)) return false;
      if (wanted.dep && leg.origin && leg.origin.plannedDateTime
          && leg.origin.plannedDateTime !== wanted.dep) return false;
      return true;
    };
    const hinted = trips[tripIdx] && trips[tripIdx].legs && trips[tripIdx].legs[legIdx];
    if (hinted && matches(hinted)) {
      return { trip: trips[tripIdx], leg: hinted, tripIdx, legIdx };
    }
    if (!wanted.num && !wanted.dep) {
      return hinted ? { trip: trips[tripIdx], leg: hinted, tripIdx, legIdx } : null;
    }
    for (let i = 0; i < trips.length; i++) {
      const legs = (trips[i] && trips[i].legs) || [];
      for (let j = 0; j < legs.length; j++) {
        if (!matches(legs[j])) continue;
        if (i !== tripIdx || j !== legIdx) {
          console.warn(
            `[ns-reisadvies] live map index drift: ${tripIdx}/${legIdx} → ${i}/${j} `
            + `for train ${wanted.num || "?"} (${wanted.dep || "no departure"})`
          );
        }
        return { trip: trips[i], leg: legs[j], tripIdx: i, legIdx: j };
      }
    }
    console.warn(
      `[ns-reisadvies] live map: train ${wanted.num || "?"} `
      + `(${wanted.dep || "no departure"}) is no longer in the sensor state`
    );
    return null;
  }

  async openLiveMap(tripIdx, legIdx, expect) {
    if (!this._hass || !this._config) return;
    const hostRoot = this._mapHostRoot();
    this._ensureModalStyles(hostRoot);
    const resolved = this._resolveLeg(tripIdx, legIdx, expect);
    if (!resolved) return;
    const leg = resolved.leg;
    tripIdx = resolved.tripIdx;
    legIdx = resolved.legIdx;
    const trainNum = (leg.product && leg.product.number) ? String(leg.product.number) : "";
    if (!trainNum) return;

    // Build the modal scaffolding once per click.
    this.closeLiveMap();  // safety: clear any stale session
    const modal = document.createElement("div");
    modal.className = "ns-map-modal";
    const titleLabel = t("live_map_title", this._hass);
    const trainLabel = (leg.product.displayName || leg.product.shortCategoryName || "")
      + " " + trainNum;
    modal.innerHTML = `
      <div class="ns-map-card">
        <div class="ns-map-header">
          <div class="ns-map-title">
            <ha-icon icon="mdi:train"></ha-icon>
            <span>${titleLabel}</span>
            <span class="ns-map-meta"><span class="ns-map-train">${trainLabel.trim()}</span> <span class="ns-map-pos"></span></span>
          </div>
          <span class="ns-map-close" role="button" title="Close"><ha-icon icon="mdi:close"></ha-icon></span>
        </div>
        <div class="ns-map-body">
          <div class="ns-map-loading">${t("live_map_loading", this._hass)}</div>
        </div>
      </div>`;
    hostRoot.appendChild(modal);
    this._activeMap = {
      modalEl: modal, sessionId: null, pollHandle: null,
      tripIdx, legIdx, expect,
    };

    const closeFn = () => this.closeLiveMap();
    modal.querySelector(".ns-map-close").addEventListener("click", closeFn);
    // Click outside the inner card closes the modal.
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeFn();
    });
    this._activeMap.escHandler = (e) => { if (e.key === "Escape") closeFn(); };
    document.addEventListener("keydown", this._activeMap.escHandler);

    // Build the stops payload — pass through the full leg.stops shape
    // so the backend has lat/lng + actualDepartureDateTime per stop and
    // does not need a secondary /v2/journey or /v2/stations lookup.
    const rawStops = (Array.isArray(leg.stops) && leg.stops.length > 1)
      ? leg.stops
      : [leg.origin, leg.destination].filter(Boolean);
    const stopsForBackend = rawStops
      .filter(s => !s.passing)
      .map(s => ({
        name: s.name || "",
        uicCode: s.uicCode || s.stationCode || "",
        lat: s.lat,
        lng: s.lng,
        actualDepartureDateTime: s.actualDepartureDateTime || null,
        plannedDepartureDateTime: s.plannedDepartureDateTime || null,
      }));

    // Anchor: the planned departure of THIS specific train run, used by
    // the backend to pass `dateTime` to /v1/trein/{nr} so NS picks the
    // right physical rotation. NS uses different field names depending
    // on the response shape: leg.origin uses plannedDateTime/actualDateTime;
    // leg.stops uses plannedDepartureDateTime/actualDepartureDateTime.
    const anchor = leg.origin?.plannedDateTime
      || leg.origin?.actualDateTime
      || leg.origin?.plannedDepartureDateTime
      || leg.origin?.actualDepartureDateTime
      || null;

    // Kick off the backend session.
    let resp;
    try {
      resp = await this._hass.callWS({
        type: "ns_reisadvies/track_train_start",
        train_number: trainNum,
        stops: stopsForBackend,
        anchor,
      });
    } catch (err) {
      this._renderMapEmpty(modal, String((err && err.message) || err));
      return;
    }
    if (!this._activeMap || this._activeMap.modalEl !== modal) return;  // closed during await
    this._activeMap.sessionId = resp.session_id;

    this._renderMapInto(modal, resp, leg);

    // Poll cadence is configurable in the hub options (default 10 s,
    // 5–60 s allowed). Stored in hass.data and re-exposed via the
    // sensor's live_map_refresh_seconds attribute. Server-side cleanup
    // timer (10 min) still fires if the page closes without notifying.
    const intervalMs = this._liveMapRefreshMs || 10000;
    this._activeMap.pollHandle = setInterval(() => this._pollLiveMap(), intervalMs);
  }

  _renderMapEmpty(modal, hint) {
    const body = modal.querySelector(".ns-map-body");
    if (!body) return;
    body.innerHTML = `<div class="ns-map-empty">${t("live_map_no_data", this._hass)}${hint ? `<br><small style="opacity:.6">${hint}</small>` : ""}</div>`;
  }

  _isDarkMode() {
    return !!(this._hass && this._hass.themes && this._hass.themes.darkMode);
  }

  _syncMapTheme() {
    // Called from `set hass`, so switching the HA theme while the live
    // map is open repaints the base layer instead of leaving a dark map
    // on a light dashboard.
    const ctx = this._activeMap;
    if (!ctx) return;
    const dark = this._isDarkMode();
    if (ctx.haMapEl) {
      const mode = dark ? "dark" : "light";
      if (ctx.haMapEl.themeMode !== mode) ctx.haMapEl.themeMode = mode;
      return;
    }
    if (ctx.mapDiv) ctx.mapDiv.classList.toggle("ns-map-dark", dark);
  }

  // ---- base layer -------------------------------------------------
  //
  // Up to HA 2026.9 this ran on <ha-map> and borrowed its Leaflet
  // instance. HA 2026.10 rewrote ha-map onto a vector engine and
  // removed the public `leafletMap` handle, so that path cannot work
  // any more: the wait for it timed out and every map fell back to
  // OpenStreetMap's own servers, which answer embedded apps with a
  // "403 Access blocked" tile. The card now keeps its own Leaflet --
  // the rail layer, route lines and markers are all Leaflet overlays
  // -- and takes only the base layer from Home Assistant.

  _ensureLeafletCss(root) {
    // Leaflet positions tiles, panes and markers from its own
    // stylesheet. `_ensureLeafletLoaded` links it into document.head,
    // which does not reach the modal: that is anchored in
    // <home-assistant>'s shadow root, and document styles stop at a
    // shadow boundary. Without this the map fetches every tile and
    // builds every overlay, then paints them unpositioned on white.
    const target = (root && root.nodeType === 11) ? root : document.head;
    if (target.querySelector("link#ns-reisadvies-leaflet-css-scoped")) return;
    const link = document.createElement("link");
    link.id = "ns-reisadvies-leaflet-css-scoped";
    link.rel = "stylesheet";
    link.href = NS_LEAFLET_CSS_URL;
    link.integrity = NS_LEAFLET_CSS_SRI;
    link.crossOrigin = "";
    target.appendChild(link);
  }

  async _fetchTileToken() {
    // HA 2026.10+ serves map tiles behind a rotating token: two are
    // valid at a time and they turn over every 30 minutes. Older
    // cores do not know the command, which is the signal to fall back.
    const conn = this._hass && this._hass.connection;
    if (!conn) return null;
    try {
      const res = await conn.sendMessagePromise({ type: "map_tiles/access_token" });
      return (res && (res.token || res.access_token)) || null;
    } catch (err) {
      return null;
    }
  }

  _startTileTokenRefresh(ctx) {
    // Well inside the 30-minute rotation, so a map left open does not
    // start 403-ing halfway through a journey.
    this._stopTileTokenRefresh(ctx);
    if (!ctx || !ctx.haTiles) return;
    ctx.tokenHandle = setInterval(async () => {
      const token = await this._fetchTileToken();
      if (!token || !ctx.baseLayer || this._activeMap !== ctx) return;
      ctx.baseLayer.options.tok = token;
      ctx.baseLayer.redraw();
    }, 20 * 60 * 1000);
  }

  _stopTileTokenRefresh(ctx) {
    if (ctx && ctx.tokenHandle) {
      clearInterval(ctx.tokenHandle);
      ctx.tokenHandle = null;
    }
  }

  async _buildMapSurface(body) {
    if (!await this._ensureLeafletLoaded()) return null;
    this._ensureLeafletCss(body.getRootNode());
    const L = window.L;
    const mapDiv = document.createElement("div");
    mapDiv.className = "ns-leaflet";
    mapDiv.classList.toggle("ns-map-dark", this._isDarkMode());
    body.appendChild(mapDiv);
    const map = L.map(mapDiv, { zoomControl: true, attributionControl: true });

    const token = await this._fetchTileToken();
    const attribution =
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
    let baseLayer;
    if (token) {
      // Same cartography the rest of Home Assistant draws, proxied by
      // core, so the card needs no tile provider of its own.
      baseLayer = L.tileLayer(NS_HA_TILE_URL, {
        tok: token,
        maxZoom: 19,
        attribution,
      });
    } else {
      // HA < 2026.10 has no tile proxy. OpenStreetMap's servers refuse
      // embedded apps, so this is a genuine last resort.
      baseLayer = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution,
      });
    }
    baseLayer.addTo(map);
    return { map, leaflet: L, haMapEl: null, mapDiv, baseLayer, haTiles: !!token };
  }

  async _ensureLeafletLoaded() {
    // Fallback loader only. The map normally runs on <ha-map>, which
    // brings its own Leaflet; this pulls a copy from unpkg for hosts
    // where ha-map is missing, or where it loaded without exposing its
    // Leaflet module. Same pin HA frontend uses, so the browser often
    // has it cached already.
    if (window.L && window.L.map) return true;
    if (this._leafletLoading) {
      try { await this._leafletLoading; } catch {}
      return !!(window.L && window.L.map);
    }
    this._leafletLoading = (async () => {
      // CSS first.
      if (!document.getElementById("ns-reisadvies-leaflet-css")) {
        const link = document.createElement("link");
        link.id = "ns-reisadvies-leaflet-css";
        link.rel = "stylesheet";
        link.href = NS_LEAFLET_CSS_URL;
        link.integrity = NS_LEAFLET_CSS_SRI;
        link.crossOrigin = "";
        document.head.appendChild(link);
      }
      // JS.
      await new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
        s.integrity = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=";
        s.crossOrigin = "";
        s.onload = resolve;
        s.onerror = () => reject(new Error("leaflet.js failed to load"));
        document.head.appendChild(s);
      });
    })();
    try {
      await this._leafletLoading;
      return true;
    } catch (err) {
      console.error("[ns-reisadvies] Leaflet load failed:", err);
      return false;
    }
  }

  async _renderMapInto(modal, resp, leg) {
    const body = modal.querySelector(".ns-map-body");
    if (!body) return;
    // Prefer the full train journey (origin → destination of the train)
    // over the user's leg subset, so the map shows the WHOLE rit.
    const sourceStops = (resp.journey_stops && resp.journey_stops.length)
      ? resp.journey_stops
      : (resp.stops || []);
    const stopsWithCoord = sourceStops.filter(s => s.lat != null && s.lng != null);
    // Always store the rich leg.stops with timing on the active map so
    // we can interpolate the train's position client-side in step with
    // the wall clock — far more reliable than NS'  /v1/trein lookup,
    // which keys on a non-unique ritnummer.
    this._activeMap.legStopsRaw = (Array.isArray(leg.stops) ? leg.stops : [])
      .filter(s => !s.passing);
    // v2.21.0: the train's WHOLE run, with the times NS reports at each
    // stop. The estimate walks over this rather than over the leg, so
    // the train is somewhere sensible while it is still on its way to
    // the departure station and after it has left the arrival station
    // behind.
    this._activeMap.journeyStopsRaw = Array.isArray(resp.journey_stops)
      ? resp.journey_stops
      : [];
    // v2.15.4: store leg.product on the active-map context so
    // _applyMapData (called repeatedly from polling + interpolation)
    // can read shortCategoryName without needing leg in scope. The
    // earlier parentNode crash hid this latent ReferenceError.
    this._activeMap.legProduct = leg.product || null;
    // Prefer the real GPS fix the backend returns; fall back to a
    // wall-clock estimate over the train's run when no feed has a
    // recent fix for this train (briefly during station dwells, or for
    // trains that report no position at all).
    const trainPos = resp.train_position || this._interpolateTrainPos();
    if (!trainPos && stopsWithCoord.length === 0) {
      this._renderMapEmpty(modal);
      return;
    }

    body.innerHTML = "";
    const built = await this._buildMapSurface(body);
    if (!this._activeMap || this._activeMap.modalEl !== modal) {
      // Modal closed while the map was still coming up.
      if (built && built.haMapEl && built.haMapEl.parentNode) {
        built.haMapEl.parentNode.removeChild(built.haMapEl);
      } else if (built && built.map) {
        try { built.map.remove(); } catch (err) { /* already gone */ }
      }
      return;
    }
    if (!built) {
      this._renderMapEmpty(modal, "map failed to load");
      return;
    }

    const L = built.leaflet;
    const map = built.map;

    this._activeMap.haMapEl = built.haMapEl;
    this._activeMap.mapDiv = built.mapDiv;
    this._activeMap.baseLayer = built.baseLayer;
    this._activeMap.haTiles = built.haTiles;
    this._startTileTokenRefresh(this._activeMap);
    this._activeMap.leaflet = L;
    this._activeMap.lmap = map;
    this._activeMap.stopMarkers = [];
    this._activeMap.passedLine = null;
    this._activeMap.futureLine = null;
    this._activeMap.trainMarker = null;
    this._activeMap.stopsWithCoord = stopsWithCoord;

    // Render the rail base layer + apply the cached route. The data
    // and routing graph are already loaded via _ensureRailReady()
    // which was kicked off during the card's first render — so this
    // is just a synchronous Leaflet add (or a quick await on the
    // already-resolved promise on the very first modal open after
    // page load).
    const railResult = NSReisadviesCard._railResult || await this._ensureRailReady();
    if (this._activeMap && this._activeMap.modalEl === modal) {
      if (railResult) this._activeMap.railLayer = this._renderRailLayerInto(map);
      // Look up the pre-computed route geometry, or compute it now
      // if the warm-up missed this leg (rare).
      const cache = NSReisadviesCard._routeCache = NSReisadviesCard._routeCache || new Map();
      const key = stopsWithCoord
        .map(s => s.uicCode || s.stationCode || `${s.lat},${s.lng}`)
        .join("|");
      let segs = cache.get(key);
      if (!segs && railResult) {
        segs = this._railSnapStopsWith(stopsWithCoord, railResult.graph);
        cache.set(key, segs);
      }
      this._activeMap.snappedSegments = segs || null;
    }

    this._applyMapData(trainPos);
    this._updatePosLabel(trainPos, leg);
  }

  // Lazily load the ProRail rail GeoJSON + build the routing graph.
  // Class-level so all card instances on the same page share it; the
  // graph is built ONCE for the whole NL network, not per-modal. Once
  // ready, opening the live map is just a state-machine update and a
  // GPS fetch — no fetching/parsing/graph-building inside the click.
  _ensureRailReady() {
    if (NSReisadviesCard._railReady) return NSReisadviesCard._railReady;
    NSReisadviesCard._railReady = (async () => {
      let data = null;
      try {
        const resp = await fetch("/ns_reisadvies/rail.geojson");
        if (resp.ok) data = await resp.json();
      } catch (err) {
        console.warn("[ns-reisadvies] cached rail load failed", err);
      }
      if (!data) return null;

      const features = data.features || [];
      const railPolylines = [];
      const lineStrings = [];
      for (const f of features) {
        const g = f.geometry;
        if (!g) continue;
        if (g.type === "LineString") {
          const ll = g.coordinates.map(c => [c[1], c[0]]);
          railPolylines.push(ll);
          lineStrings.push(ll);
        } else if (g.type === "MultiLineString") {
          for (const seg of g.coordinates) {
            const ll = seg.map(c => [c[1], c[0]]);
            railPolylines.push(ll);
            lineStrings.push(ll);
          }
        }
      }

      // Build full-NL graph once.
      //
      // v2.15.8: back to 4-decimal precision (~11 m) for junction
      // welding. v2.15.6's 3-decimal (~110 m) was over-aggressive: at
      // Utrecht Centraal (and other big stations) it merged separate
      // parallel/crossing tracks into a single tangled blob, which
      // made the A* search loop through the rangeer-emplacement and
      // produce 60 km+ paths for the 3 km Utrecht Overvecht → Utrecht
      // CS hop.
      //
      // To still bridge the small (12–15 m) gaps between adjacent
      // ProRail features that 4-decimal misses, a second pass adds
      // **proximity edges** between any two nodes within 25 m. That
      // welds disjoint clusters without polluting station areas with
      // false cross-line shortcuts.
      const haversine = (a, b) => {
        const R = 6371000.0;
        const r = Math.PI / 180;
        const la1 = a[0] * r, la2 = b[0] * r;
        const dla = (b[0] - a[0]) * r;
        const dlo = (b[1] - a[1]) * r;
        const h = Math.sin(dla / 2) ** 2
          + Math.cos(la1) * Math.cos(la2) * Math.sin(dlo / 2) ** 2;
        return 2 * R * Math.asin(Math.sqrt(h));
      };
      const graph = new Map();
      const nodeCoords = new Map();
      const k = c => `${c[0].toFixed(4)},${c[1].toFixed(4)}`;
      for (const ls of lineStrings) {
        for (let i = 0; i < ls.length - 1; i++) {
          const a = ls[i], b = ls[i + 1];
          const ka = k(a), kb = k(b);
          if (ka === kb) continue;
          if (!nodeCoords.has(ka)) nodeCoords.set(ka, a);
          if (!nodeCoords.has(kb)) nodeCoords.set(kb, b);
          const w = haversine(a, b);
          if (!graph.has(ka)) graph.set(ka, []);
          if (!graph.has(kb)) graph.set(kb, []);
          graph.get(ka).push({ to: kb, w });
          graph.get(kb).push({ to: ka, w });
        }
      }
      // Second pass: bridge nodes that sit close to each other but
      // ended up in different graph components because 4-decimal
      // rounding put them on different sides of a junction.
      //
      // v2.15.9: radius bumped 25 m → 60 m so the gaps between
      // Hilversum Sportpark, Hollandsche Rading, and Utrecht
      // Overvecht (and similar areas) actually get welded — 25 m
      // turned out to be too tight in practice. Crucially we ONLY
      // bridge "endpoint-ish" nodes (≤ 2 existing neighbours): a
      // dense station-junction has 3+ neighbours, so its parallel
      // tracks are protected from being cross-wired into one blob.
      // Spatial-grid bucketed so we stay well below O(n²); each cell
      // is 0.001° (~110 m) so all candidates within 60 m sit in the
      // same or 8 neighbouring cells.
      const PROX_METERS = 60;
      const CELL = 0.001;
      const buckets = new Map();
      const cellKey = (lat, lng) =>
        `${Math.floor(lat / CELL)},${Math.floor(lng / CELL)}`;
      for (const [key, c] of nodeCoords) {
        const ck = cellKey(c[0], c[1]);
        if (!buckets.has(ck)) buckets.set(ck, []);
        buckets.get(ck).push({ key, c });
      }
      let bridgesAdded = 0;
      let bridgesSkippedDense = 0;
      for (const [ck, nodes] of buckets) {
        const [cy, cx] = ck.split(",").map(Number);
        const neigh = [];
        for (let dy = -1; dy <= 1; dy++) {
          for (let dx = -1; dx <= 1; dx++) {
            const arr = buckets.get(`${cy + dy},${cx + dx}`);
            if (arr) neigh.push(...arr);
          }
        }
        for (const n1 of nodes) {
          for (const n2 of neigh) {
            if (n1.key === n2.key) continue;
            if (n1.key > n2.key) continue;  // dedupe undirected pairs
            const d = haversine(n1.c, n2.c);
            if (d > PROX_METERS) continue;
            const adj1 = graph.get(n1.key);
            const adj2 = graph.get(n2.key);
            if (adj1 && adj1.some(e => e.to === n2.key)) continue;
            // Endpoint-only filter: skip the bridge when BOTH ends
            // already sit on a busy junction (≥3 neighbours). That
            // protects parallel/crossing tracks at big stations from
            // being cross-wired.
            if ((adj1 ? adj1.length : 0) >= 3 && (adj2 ? adj2.length : 0) >= 3) {
              bridgesSkippedDense++;
              continue;
            }
            graph.get(n1.key).push({ to: n2.key, w: d });
            if (!graph.has(n2.key)) graph.set(n2.key, []);
            graph.get(n2.key).push({ to: n1.key, w: d });
            bridgesAdded++;
          }
        }
      }
      // v2.16.13: degree-1 stub bridging. The 60 m proximity pass above
      // misses gaps a little bigger than that — e.g. the Utrecht CS →
      // Utrecht Lunetten / Houten line splits into two sub-graphs that
      // are ~74 m apart at the closest point (lat 52.0702, lng 5.140).
      // Both halves are in the main connected component (so the
      // components-bridging pass below won't help — they're already in
      // the same "global" component, just via a 100+ km detour through
      // Arnhem), and the 60 m proximity pass doesn't reach across the
      // 74 m gap.
      //
      // A degree-1 node is a dead-end vertex in the rail polyline: an
      // endpoint of one ProRail feature with no continuation. In the
      // wild these are almost always intended-to-connect endpoints
      // where two GeoJSON features should meet but their endpoint
      // coordinates differ by a few dozen metres. Stitch each degree-1
      // stub to its nearest other node within 200 m (any degree) — that
      // closes the Utrecht→Lunetten gap and similar gaps elsewhere
      // (Houten Castellum, Culemborg, Zaltbommel) without touching
      // dense junctions. Empirically: 184 / 208 stubs bridge; Utrecht→
      // Den Bosch drops from 126.9 km to 48.0 km (direct 46.1 km), and
      // unrelated routes are unaffected within ±0 km.
      const STUB_BRIDGE_M = 200;
      const STUB_CELL = 0.002; // ~220 m at NL latitudes
      const stubBuckets = new Map();
      const stubCellKey = (lat, lng) =>
        `${Math.floor(lat / STUB_CELL)},${Math.floor(lng / STUB_CELL)}`;
      for (const [key, c] of nodeCoords) {
        const ck = stubCellKey(c[0], c[1]);
        if (!stubBuckets.has(ck)) stubBuckets.set(ck, []);
        stubBuckets.get(ck).push({ key, c });
      }
      let stubBridgesAdded = 0;
      for (const [k1, neigh1] of graph) {
        if (neigh1.length !== 1) continue;
        const c1 = nodeCoords.get(k1);
        const cy = Math.floor(c1[0] / STUB_CELL);
        const cx = Math.floor(c1[1] / STUB_CELL);
        let bestKey = null;
        let bestD = Infinity;
        for (let dy = -1; dy <= 1; dy++) {
          for (let dx = -1; dx <= 1; dx++) {
            const arr = stubBuckets.get(`${cy + dy},${cx + dx}`);
            if (!arr) continue;
            for (const cand of arr) {
              if (cand.key === k1) continue;
              if (neigh1.some(e => e.to === cand.key)) continue;
              const d = haversine(c1, cand.c);
              if (d > STUB_BRIDGE_M) continue;
              if (d < bestD) { bestD = d; bestKey = cand.key; }
            }
          }
        }
        if (bestKey) {
          graph.get(k1).push({ to: bestKey, w: bestD });
          if (!graph.has(bestKey)) graph.set(bestKey, []);
          graph.get(bestKey).push({ to: k1, w: bestD });
          stubBridgesAdded++;
        }
      }
      // v2.17.1: continuation-gap welding. The two passes above still
      // miss the most common defect in the ProRail export: a line cut
      // mid-run, both ends ordinary degree-2 vertices, slightly
      // further apart than the 60 m proximity pass reaches and not
      // degree-1 so the stub pass ignores them too. Measured at
      // 's-Hertogenbosch: a 65 m gap with 93 km of graph around it,
      // which is what pushed that route's snap 1.2 km off the
      // platform. Amsterdam Muiderpoort → Amstel had the same shape.
      //
      // Raising PROX_METERS globally would cross-wire parallel tracks
      // and flyovers, so this pass welds only where all three hold:
      //   * the gap is at most GAP_M;
      //   * neither node already has an edge running that way (within
      //     GAP_TOL_DEG), so both really are open line ends facing
      //     each other — parallel tracks and crossings fail this,
      //     since their own neighbours sit across the gap direction;
      //   * the graph cannot get from one to the other within
      //     GAP_DETOUR_M anyway, so a working switch is never
      //     duplicated and a viaduct is never welded to the line
      //     underneath it.
      const GAP_M = 150;
      const GAP_TOL_DEG = 40;
      const GAP_DETOUR_M = 1500;
      const GAP_CELL = 0.002;
      const gapBuckets = new Map();
      for (const [key, c] of nodeCoords) {
        const ck = `${Math.floor(c[0] / GAP_CELL)},${Math.floor(c[1] / GAP_CELL)}`;
        if (!gapBuckets.has(ck)) gapBuckets.set(ck, []);
        gapBuckets.get(ck).push({ key, c });
      }
      // Planar direction vector, longitude scaled so both axes are
      // comparable at NL latitudes.
      const dirVec = (from, to) => {
        const lat0 = from[0] * Math.PI / 180;
        return [(to[1] - from[1]) * Math.cos(lat0), to[0] - from[0]];
      };
      const angleDeg = (u, v) => {
        const lu = Math.hypot(u[0], u[1]);
        const lv = Math.hypot(v[0], v[1]);
        if (!lu || !lv) return 180;
        const c = Math.max(-1, Math.min(1, (u[0] * v[0] + u[1] * v[1]) / (lu * lv)));
        return Math.acos(c) * 180 / Math.PI;
      };
      // True when the node has no edge already running towards the
      // target: an open end rather than a passing vertex.
      const facesGap = (key, c, target) => {
        const v = dirVec(c, target);
        for (const e of (graph.get(key) || [])) {
          const c2 = nodeCoords.get(e.to);
          if (c2 && angleDeg(dirVec(c, c2), v) < GAP_TOL_DEG) return false;
        }
        return true;
      };
      const heapPush = (h, item) => {
        h.push(item);
        let i = h.length - 1;
        while (i > 0) {
          const p = (i - 1) >> 1;
          if (h[p][0] <= h[i][0]) break;
          const t = h[p]; h[p] = h[i]; h[i] = t;
          i = p;
        }
      };
      const heapPop = (h) => {
        const top = h[0];
        const last = h.pop();
        if (h.length) {
          h[0] = last;
          let i = 0;
          for (;;) {
            const l = 2 * i + 1;
            const r = l + 1;
            let m = i;
            if (l < h.length && h[l][0] < h[m][0]) m = l;
            if (r < h.length && h[r][0] < h[m][0]) m = r;
            if (m === i) break;
            const t = h[m]; h[m] = h[i]; h[i] = t;
            i = m;
          }
        }
        return top;
      };
      // Bounded Dijkstra, only ever used to prove that no short way
      // round exists. Capped on distance and on visited nodes so a
      // dense yard cannot make this pass expensive.
      const reachableWithin = (from, to, cutoff) => {
        const dist = new Map([[from, 0]]);
        const heap = [[0, from]];
        const seen = new Set();
        let pops = 0;
        while (heap.length && pops < 6000) {
          const [d, key] = heapPop(heap);
          if (seen.has(key)) continue;
          seen.add(key);
          pops++;
          if (key === to) return true;
          if (d > cutoff) return false;
          for (const e of (graph.get(key) || [])) {
            const nd = d + e.w;
            if (nd <= cutoff && nd < (dist.get(e.to) ?? Infinity)) {
              dist.set(e.to, nd);
              heapPush(heap, [nd, e.to]);
            }
          }
        }
        return false;
      };
      let gapBridgesAdded = 0;
      for (const [ck, nodes] of gapBuckets) {
        const [cy, cx] = ck.split(",").map(Number);
        const neigh = [];
        for (let dy = -1; dy <= 1; dy++) {
          for (let dx = -1; dx <= 1; dx++) {
            const arr = gapBuckets.get(`${cy + dy},${cx + dx}`);
            if (arr) neigh.push(...arr);
          }
        }
        for (const n1 of nodes) {
          for (const n2 of neigh) {
            if (n1.key >= n2.key) continue;
            const d = haversine(n1.c, n2.c);
            if (d < 1 || d > GAP_M) continue;
            const adj1 = graph.get(n1.key);
            if (adj1 && adj1.some(e => e.to === n2.key)) continue;
            if (!facesGap(n1.key, n1.c, n2.c)) continue;
            if (!facesGap(n2.key, n2.c, n1.c)) continue;
            if (reachableWithin(n1.key, n2.key, GAP_DETOUR_M)) continue;
            graph.get(n1.key).push({ to: n2.key, w: d });
            if (!graph.has(n2.key)) graph.set(n2.key, []);
            graph.get(n2.key).push({ to: n1.key, w: d });
            gapBridgesAdded++;
          }
        }
      }
      // v2.16.0: connected-components bridging. After the proximity
      // pass there are still small isolated sub-graphs (typically the
      // ProRail GeoJSON has feature-level discontinuities of 100–500 m
      // at some junctions, freight branches that don't quite touch
      // the passenger network, etc). Find every component via BFS;
      // for each non-largest component, drop a single bridge to the
      // nearest node in the main component (capped at 5 km). That
      // guarantees A* between any two station snaps will find a path
      // — no more case-by-case tuning per route.
      const visited = new Set();
      const components = [];
      for (const startKey of graph.keys()) {
        if (visited.has(startKey)) continue;
        const comp = [];
        const queue = [startKey];
        visited.add(startKey);
        while (queue.length) {
          const cur = queue.shift();
          comp.push(cur);
          for (const e of graph.get(cur) || []) {
            if (!visited.has(e.to)) {
              visited.add(e.to);
              queue.push(e.to);
            }
          }
        }
        components.push(comp);
      }
      components.sort((a, b) => b.length - a.length);
      // v2.16.10: keep the set of main-component node keys so that
      // _railSnapCandidatesWith can filter out tiny disconnected
      // sub-graphs (rangeer-spoor, freight-only branches, etc.) when
      // picking snap candidates. Snapping to an island = guaranteed
      // straight-line fallback or 100+ km A* detour.
      //
      // v2.16.11: declare BEFORE the bridging loop so the loop can
      // promote successfully-bridged sub-components into the Set.
      // (The previous post-loop declaration triggered a temporal
      // dead-zone ReferenceError during pre-warm.)
      const mainComponent = new Set(components[0] || []);
      // Bucket the main component nodes for fast nearest-node lookup
      // when bridging. 1.1 km cells → search 7×7 cells = ~7 km box,
      // plenty for the 5 km cap below.
      const MAIN_CELL = 0.01;
      const mainBuckets = new Map();
      if (components.length) {
        for (const k of components[0]) {
          const c = nodeCoords.get(k);
          const ck = `${Math.floor(c[0] / MAIN_CELL)},${Math.floor(c[1] / MAIN_CELL)}`;
          if (!mainBuckets.has(ck)) mainBuckets.set(ck, []);
          mainBuckets.get(ck).push({ key: k, c });
        }
      }
      let componentsBridged = 0;
      const MAX_BRIDGE_M = 5000;
      for (let i = 1; i < components.length; i++) {
        const small = components[i];
        let bestDist = Infinity;
        let bestFrom = null;
        let bestTo = null;
        for (const sk of small) {
          const sc = nodeCoords.get(sk);
          const cy = Math.floor(sc[0] / MAIN_CELL);
          const cx = Math.floor(sc[1] / MAIN_CELL);
          for (let dy = -3; dy <= 3; dy++) {
            for (let dx = -3; dx <= 3; dx++) {
              const arr = mainBuckets.get(`${cy + dy},${cx + dx}`);
              if (!arr) continue;
              for (const m of arr) {
                const d = haversine(sc, m.c);
                if (d < bestDist) {
                  bestDist = d;
                  bestFrom = sk;
                  bestTo = m.key;
                }
              }
            }
          }
        }
        if (bestFrom && bestDist <= MAX_BRIDGE_M) {
          graph.get(bestFrom).push({ to: bestTo, w: bestDist });
          graph.get(bestTo).push({ to: bestFrom, w: bestDist });
          componentsBridged++;
          // Promote the small component into mainBuckets so subsequent
          // bridges can attach to it too, AND into mainComponent so the
          // snap helper trusts these nodes (v2.16.11 bug fix).
          for (const k of small) {
            const c = nodeCoords.get(k);
            const ck = `${Math.floor(c[0] / MAIN_CELL)},${Math.floor(c[1] / MAIN_CELL)}`;
            if (!mainBuckets.has(ck)) mainBuckets.set(ck, []);
            mainBuckets.get(ck).push({ key: k, c });
            mainComponent.add(k);
          }
        }
      }
      console.info(
        `[ns-reisadvies] rail graph: ${nodeCoords.size} nodes, `
        + `${bridgesAdded} proximity bridges (≤${PROX_METERS} m), `
        + `${bridgesSkippedDense} skipped at junctions, `
        + `${stubBridgesAdded} degree-1 stubs bridged (≤${STUB_BRIDGE_M} m), `
        + `${gapBridgesAdded} continuation gaps welded (≤${GAP_M} m), `
        + `${components.length} components → ${componentsBridged} bridged `
        + `(largest: ${components[0]?.length || 0} nodes)`
      );

      const result = {
        railPolylines,
        graph: { graph, nodeCoords, haversine, mainComponent },
      };
      NSReisadviesCard._railResult = result;
      return result;
    })();
    return NSReisadviesCard._railReady;
  }

  // Render the cached rail GeoJSON onto an open Leaflet map.
  _renderRailLayerInto(map) {
    const r = NSReisadviesCard._railResult;
    if (!r || !r.railPolylines || !r.railPolylines.length) return null;
    // v2.15.3: render the grey rail base into its own dedicated pane.
    // Earlier versions called layer.addTo(map).bringToBack() in one
    // tick, which crashes in Leaflet 1.9.x with
    // "Cannot read properties of undefined (reading 'parentNode')"
    // when the SVG renderer hasn't attached the parent yet. Using a
    // pane with a z-index below overlayPane (400) keeps the rail layer
    // visually under the colored route without needing bringToBack().
    const PANE_NAME = "ns_rail_base";
    if (!map.getPane(PANE_NAME)) {
      map.createPane(PANE_NAME);
      const pane = map.getPane(PANE_NAME);
      if (pane) pane.style.zIndex = 250;
    }
    const L = (this._activeMap && this._activeMap.leaflet) || window.L;
    const layer = L.polyline(r.railPolylines, {
      color: "#5a6a7a",
      weight: 1.6,
      opacity: 0.55,
      interactive: false,
      pane: PANE_NAME,
    });
    layer.addTo(map);
    return layer;
  }

  // Pre-warm the routing cache for every visible leg with a live-map
  // icon. Each unique stops-uic sequence is routed at most once and
  // the result is stored on the class. Yields between trips so the
  // UI stays responsive even with many trips on screen.
  async _warmRouteCache() {
    if (!this._hass || !this._config) return;
    const r = await this._ensureRailReady();
    if (!r) return;
    const stateObj = this._sourceState();
    const trips = (stateObj && stateObj.attributes && stateObj.attributes.trips) || [];
    const cache = NSReisadviesCard._routeCache = NSReisadviesCard._routeCache || new Map();
    for (const t of trips) {
      for (const leg of (t.legs || [])) {
        if (!leg.product || !leg.product.number) continue;
        const stops = (leg.stops || []).filter(s => !s.passing && s.lat != null && s.lng != null);
        if (stops.length < 2) continue;
        const key = stops.map(s => s.uicCode || s.stationCode || `${s.lat},${s.lng}`).join("|");
        if (cache.has(key)) continue;
        // Yield to the event loop so we don't lock the UI on big trip lists.
        await new Promise(rr => setTimeout(rr, 0));
        const segs = this._railSnapStopsWith(stops, r.graph);
        cache.set(key, segs);
      }
    }
  }

  // Snap a [lat,lng] to the K nearest rail-graph nodes.
  //
  // v2.16.2: enforce a minimum geographic spread between picks so the
  // K snaps don't all cluster on one side of a big station yard
  // (the Utrecht Centraal Maarssen-detour bug).
  //
  // v2.16.10: also filter out "untrustworthy" candidates BEFORE the
  // distance ranking:
  //   * Nodes outside the largest connected component — tiny isolated
  //     sub-graphs that the components-bridging pass couldn't reach
  //     within 5 km. Snapping there forces A* through the synthetic
  //     bridge edge, which usually produces a long detour.
  //   * Degree-1 dead-end stubs — typically freight branches or
  //     maintenance spurs. The main passenger line always has degree
  //     ≥ 2 (forward + back). Skipping stubs avoids snaps that lock
  //     A* onto a yard that only connects to the network via one edge.
  // K bumped 20 → 40 with minSpread 150 m → 100 m so we sample even
  // denser station yards (e.g. Amsterdam Centraal has parallel tracks
  // 50–80 m apart and the v2.16.2 K=20 was missing a couple of them).
  _railSnapCandidatesWith(g, point, k = 40, maxDist = 2000, minSpread = 100) {
    if (!g) return [];
    const main = g.mainComponent;
    const ranked = [];
    for (const [key, c] of g.nodeCoords) {
      // v2.16.10: skip sub-component noise
      if (main && main.size > 0 && !main.has(key)) continue;
      // v2.16.10: skip degree-1 stubs (freight branches, dead-ends)
      const neigh = g.graph.get(key);
      if (!neigh || neigh.length < 2) continue;
      const d = g.haversine(point, c);
      if (d > maxDist) continue;
      ranked.push({ key, c, dist: d });
    }
    ranked.sort((a, b) => a.dist - b.dist);
    // Greedy diversity pass: keep the closest, then each next pick
    // must be ≥ minSpread metres from every already-picked node.
    // Always keep the closest 3 unconditionally so we don't lose
    // resolution at small tightly-clustered stations.
    const picked = [];
    for (const cand of ranked) {
      if (picked.length < 3) {
        picked.push(cand);
      } else {
        let tooClose = false;
        for (const p of picked) {
          if (g.haversine(cand.c, p.c) < minSpread) {
            tooClose = true;
            break;
          }
        }
        if (!tooClose) picked.push(cand);
      }
      if (picked.length >= k) break;
    }
    return picked.map(p => ({ key: p.key, dist: p.dist }));
  }

  // A* shortest path on the rail graph using haversine as the
  // admissible heuristic. Uses a binary min-heap as the priority
  // queue so 75 km cross-country routes finish in under a second
  // even with thousands of nodes. Returns the path as [lat,lng]
  // pairs, or null if unreachable.
  _railPathWith(g, fromKey, toKey) {
    if (!g) return null;
    const { graph, nodeCoords, haversine } = g;
    if (fromKey === toKey) {
      const c = nodeCoords.get(fromKey);
      return c ? [c] : null;
    }
    const goal = nodeCoords.get(toKey);
    if (!goal) return null;

    const cameFrom = new Map();
    const gScore = new Map();
    gScore.set(fromKey, 0);
    const closed = new Set();

    // Binary min-heap keyed by f-score.
    const heap = [];
    const heapPush = (n) => {
      heap.push(n);
      let i = heap.length - 1;
      while (i > 0) {
        const p = (i - 1) >> 1;
        if (heap[p].f <= heap[i].f) break;
        [heap[p], heap[i]] = [heap[i], heap[p]];
        i = p;
      }
    };
    const heapPop = () => {
      if (!heap.length) return null;
      const top = heap[0];
      const last = heap.pop();
      if (heap.length) {
        heap[0] = last;
        let i = 0;
        const n = heap.length;
        while (true) {
          const l = i * 2 + 1, r = i * 2 + 2;
          let best = i;
          if (l < n && heap[l].f < heap[best].f) best = l;
          if (r < n && heap[r].f < heap[best].f) best = r;
          if (best === i) break;
          [heap[best], heap[i]] = [heap[i], heap[best]];
          i = best;
        }
      }
      return top;
    };

    heapPush({ key: fromKey, f: haversine(nodeCoords.get(fromKey), goal) });
    while (heap.length) {
      const cur = heapPop();
      if (closed.has(cur.key)) continue;
      if (cur.key === toKey) {
        const path = [nodeCoords.get(toKey)];
        let n = toKey;
        while (cameFrom.has(n)) {
          n = cameFrom.get(n);
          path.unshift(nodeCoords.get(n));
        }
        return path;
      }
      closed.add(cur.key);
      const curG = gScore.get(cur.key);
      const neigh = graph.get(cur.key) || [];
      for (const e of neigh) {
        if (closed.has(e.to)) continue;
        const tent = curG + e.w;
        if (tent >= (gScore.get(e.to) ?? Infinity)) continue;
        gScore.set(e.to, tent);
        cameFrom.set(e.to, cur.key);
        const f = tent + haversine(nodeCoords.get(e.to), goal);
        heapPush({ key: e.to, f });
      }
    }
    return null;
  }

  // Build a snapped polyline for the WHOLE route by routing through
  // the rail graph between consecutive stops. Tries the top few snap
  // candidates per stop so a single bad snap (onto an isolated
  // sub-graph) doesn't fall back to a straight chord.
  _railSnapStopsWith(stops, g) {
    if (!stops || stops.length < 2 || !g) return null;
    const segments = [];
    for (let i = 0; i < stops.length - 1; i++) {
      const a = stops[i], b = stops[i + 1];
      // v2.16.10: K bumped 20 → 40 with 100 m spread (down from
      // 150 m). The defaults inside _railSnapCandidatesWith already
      // express this — pass undefined for k+maxDist+minSpread so the
      // helper's defaults can evolve without re-tuning the call site.
      const candA = this._railSnapCandidatesWith(g, [a.lat, a.lng]);
      const candB = this._railSnapCandidatesWith(g, [b.lat, b.lng]);
      // v2.15.7: try ALL 25 snap-pair combinations and keep the
      // shortest path (haversine sum). The previous code stopped at
      // the first working path, which on dense networks (Utrecht ↔
      // Hilversum, Hilversum ↔ Almere) sometimes returned a long
      // detour via the wrong line because the closest-by-distance
      // snap candidate had landed on a track in the wrong direction.
      // Computing path length per candidate adds <50ms even on the
      // 80km IC routes and gives the geographically correct answer.
      //
      // v2.17.1: score the pair, do not just measure the rail path.
      // Ranking on `len` alone is degenerate: the drawn polyline is
      // [stop A] → path → [stop B], so the two snap legs are straight
      // cheats across open country, and a pair that snaps 2 km toward
      // each other always yields a shorter "path" than the pair that
      // sits on the platforms. Measured on the Gooilijn before this
      // fix: Weesp → Naarden-Bussum returned a 4.9 km path with
      // snapA=1997 m and snapB=1894 m, against 8.5 km direct — two
      // long straight chords with a stub of track in between.
      //
      // Counting the snap legs once (len + snapA + snapB) does not fix
      // it either, because a straight line between two stations is
      // always shorter than the track between them, so cheating still
      // wins by a few dozen metres. The snap legs therefore cost
      // SNAP_PENALTY times their length: cheating only pays when the
      // geometry genuinely demands it. At weight 3 the same leg snaps
      // to 4 m / 44 m and returns 9.0 km of real track.
      const SNAP_PENALTY = 3;
      let bestPath = null;
      let bestLen = Infinity;
      let bestScore = Infinity;
      let bestPathSnaps = null;
      let triedCount = 0;
      let foundCount = 0;
      for (const sa of candA) {
        for (const sb of candB) {
          triedCount++;
          const path = this._railPathWith(g, sa.key, sb.key);
          if (!path || path.length < 2) continue;
          foundCount++;
          let len = 0;
          for (let p = 0; p < path.length - 1; p++) {
            len += g.haversine(path[p], path[p + 1]);
          }
          const score = len + SNAP_PENALTY * (sa.dist + sb.dist);
          if (score < bestScore) {
            bestPath = path;
            bestLen = len;
            bestScore = score;
            bestPathSnaps = { sa, sb };
          }
        }
      }
      if (!bestPath) {
        const closestA = candA[0]?.dist?.toFixed(0) ?? "n/a";
        const closestB = candB[0]?.dist?.toFixed(0) ?? "n/a";
        console.warn(
          `[ns-reisadvies] NO RAIL PATH ${a.name} → ${b.name} | `
          + `straight-line fallback | snaps tried: ${triedCount} | `
          + `closest A: ${closestA}m, B: ${closestB}m`
        );
        segments.push([[a.lat, a.lng], [b.lat, b.lng]]);
        continue;
      }
      // v2.16.10: tiered outlier filter. The flat 2×+2 km cap from
      // v2.16.2 was too tight at short stations (sometimes the only
      // way out of a yard is a 3× loop) and too loose for long IC
      // legs (2×+2 km would still let a 60 km detour through). New
      // policy by direct distance:
      //   * <  5 km direct → cap = 5× + 2 km (station-yard slack)
      //   * <  30 km        → cap = 3× + 2 km (covers Hilversum →
      //                          Utrecht's via-Maarssen 3.4× and the
      //                          Naarden-Bussum → Almere via-Weesp
      //                          2.04× legitimate hop)
      //   * >= 30 km        → cap = 2× + 5 km (long IC legs hardly
      //                          ever exceed 1.3× direct; a 2× hit
      //                          means the snap is wrong)
      const directKm = g.haversine([a.lat, a.lng], [b.lat, b.lng]) / 1000;
      const pathKm = bestLen / 1000;
      // v2.17.1: measure what is actually drawn — the two snap legs
      // included — so a pair that only looks short because it cheats
      // across 2 km of polder is caught here as well.
      const snapKm = (bestPathSnaps.sa.dist + bestPathSnaps.sb.dist) / 1000;
      const drawnKm = pathKm + snapKm;
      let cap;
      if (directKm < 5)        cap = directKm * 5 + 2;
      else if (directKm < 30)  cap = directKm * 3 + 2;
      else                     cap = directKm * 2 + 5;
      if (drawnKm > cap) {
        console.warn(
          `[ns-reisadvies] PATH TOO LONG ${a.name} → ${b.name}: `
          + `${drawnKm.toFixed(1)} km drawn (${pathKm.toFixed(1)} km track `
          + `+ ${snapKm.toFixed(1)} km snap) vs direct ${directKm.toFixed(1)} km — `
          + `straight-line fallback`
        );
        segments.push([[a.lat, a.lng], [b.lat, b.lng]]);
        continue;
      }
      console.info(
        `[ns-reisadvies] rail-snap ${a.name} → ${b.name}: `
        + `${bestPath.length} pts, ${pathKm.toFixed(1)} km `
        + `(direct ${directKm.toFixed(1)} km), `
        + `${foundCount}/${triedCount} candidates ok, `
        + `snap A=${bestPathSnaps.sa.dist.toFixed(0)}m B=${bestPathSnaps.sb.dist.toFixed(0)}m`
      );
      segments.push([[a.lat, a.lng], ...bestPath, [b.lat, b.lng]]);
    }
    return segments;
  }

  _applyMapData(trainPos, freshStops) {
    const ctx = this._activeMap;
    if (!ctx || !ctx.lmap) return;
    const L = ctx.leaflet;
    const map = ctx.lmap;

    // Refresh passed flags from poll responses if provided.
    if (freshStops && freshStops.length) {
      const byKey = new Map();
      freshStops.forEach(s => {
        const k = (s.uicCode || s.code || s.name || "").toString();
        if (k) byKey.set(k, s);
      });
      ctx.stopsWithCoord = (ctx.stopsWithCoord || []).map(s => {
        const k = (s.uicCode || s.code || s.name || "").toString();
        const fresh = k && byKey.get(k);
        return fresh ? { ...s, passed: !!fresh.passed } : s;
      });
    }
    const stops = ctx.stopsWithCoord || [];

    // Build the colored polyline. Prefer rail-snapped geometry when
    // the rail graph is available, fall back to straight chords.
    if (stops.length >= 2) {
      const yellowSeg = [];
      const blueSeg = [];
      const tp = trainPos && trainPos.lat != null && trainPos.lng != null
        ? [trainPos.lat, trainPos.lng]
        : null;

      // Use the snapped geometry that was pre-computed (or just-now
      // computed) when the modal opened. Fall back to straight
      // chords if for some reason it isn't available.
      const snapped = ctx.snappedSegments || stops.slice(0, -1).map((a, i) => {
        const b = stops[i + 1];
        return [[a.lat, a.lng], [b.lat, b.lng]];
      });

      // Find the boundary index: last stop with passed=true.
      let lastPassedIdx = -1;
      for (let i = 0; i < stops.length; i++) {
        if (stops[i].passed) lastPassedIdx = i;
      }

      // Helper: split a polyline at the closest point to `tp`. Returns
      // [before, after] each as [[lat,lng], ...]. Falls back to a
      // simple endpoint cut if `tp` is missing.
      const splitAtTrain = (poly, tpLL) => {
        if (!tpLL || poly.length < 2) return [poly, poly];
        let bestI = 0, bestD = Infinity;
        const dist2 = (a, b) =>
          (a[0] - b[0]) * (a[0] - b[0]) + (a[1] - b[1]) * (a[1] - b[1]);
        for (let i = 0; i < poly.length; i++) {
          const d = dist2(poly[i], tpLL);
          if (d < bestD) { bestD = d; bestI = i; }
        }
        const before = poly.slice(0, bestI + 1).concat([tpLL]);
        const after = [tpLL].concat(poly.slice(bestI + 1));
        return [before, after];
      };

      for (let i = 0; i < snapped.length; i++) {
        const a = stops[i], b = stops[i + 1];
        const seg = snapped[i];
        if (a.passed && b.passed) {
          yellowSeg.push(seg);
        } else if (i === lastPassedIdx && tp) {
          const [before, after] = splitAtTrain(seg, tp);
          if (before.length >= 2) yellowSeg.push(before);
          if (after.length >= 2) blueSeg.push(after);
        } else {
          blueSeg.push(seg);
        }
      }
      const refresh = (existing, segments, color) => {
        if (existing) existing.remove();
        if (!segments.length) return null;
        return L.polyline(segments, {
          color,
          weight: 4,
          opacity: 0.9,
        }).addTo(map);
      };
      ctx.passedLine = refresh(ctx.passedLine, yellowSeg, "#FFC917");
      ctx.futureLine = refresh(ctx.futureLine, blueSeg, "#3b82f6");
    }

    // Stop markers (build once).
    if (!ctx.stopMarkers.length && stops.length) {
      stops.forEach((s, i) => {
        const isEndpoint = i === 0 || i === stops.length - 1;
        // v2.23.0: a station the train races through is not a stop.
        // It stays in the list — the line is drawn through it and the
        // estimate uses it to know how far along the train is — but
        // marking it would promise a halt that is not on offer. An
        // intercity would otherwise appear to call at every village
        // between Amsterdam and Utrecht.
        if (!isEndpoint && String(s.status || "").toUpperCase() === "PASSING") {
          return;
        }
        const icon = L.divIcon({
          className: "ns-leaflet-stop-wrap",
          html: `<div class="ns-leaflet-stop${isEndpoint ? " endpoint" : ""}"></div>`,
          iconSize: isEndpoint ? [18, 18] : [14, 14],
          iconAnchor: isEndpoint ? [9, 9] : [7, 7],
        });
        const m = L.marker([s.lat, s.lng], { icon, title: s.name }).addTo(map);
        m.bindTooltip(s.name, { direction: "top", offset: [0, -8] });
        ctx.stopMarkers.push(m);
      });
    }

    // Train marker — side-view train tile, treinposities.nl-style.
    // Yellow NS body with blue stripe, four windows, dark blue cab and
    // a red light at the front. The tile is rotated to match the GPS
    // heading so the front faces the direction of travel.
    if (trainPos && trainPos.lat != null && trainPos.lng != null) {
      const ll = [trainPos.lat, trainPos.lng];
      if (!ctx.trainMarker) {
        // viewBox 88x44, drawn pointing RIGHT (heading 90 = east).
        // Rotation in CSS later converts heading → marker angle.
        const tile = `
          <svg viewBox="0 0 88 44" xmlns="http://www.w3.org/2000/svg">
            <!-- yellow body with rounded corners -->
            <path d="M4 14 Q4 8 12 8 L72 8 Q80 8 84 14 L86 22 L86 32 Q86 36 82 36 L8 36 Q4 36 4 32 Z" fill="#FFC917" stroke="#003082" stroke-width="1.2"/>
            <!-- blue stripe along the bottom (NS livery) -->
            <rect x="6" y="30" width="80" height="4" fill="#003082"/>
            <!-- cab window (front, pointing right) -->
            <path d="M68 14 Q72 12 78 14 L82 20 L78 22 L70 22 Z" fill="#cfe6ff" stroke="#003082" stroke-width="0.8"/>
            <!-- passenger windows -->
            <rect x="14" y="15" width="10" height="9" rx="1.5" fill="#cfe6ff" stroke="#003082" stroke-width="0.6"/>
            <rect x="28" y="15" width="10" height="9" rx="1.5" fill="#cfe6ff" stroke="#003082" stroke-width="0.6"/>
            <rect x="42" y="15" width="10" height="9" rx="1.5" fill="#cfe6ff" stroke="#003082" stroke-width="0.6"/>
            <rect x="56" y="15" width="10" height="9" rx="1.5" fill="#cfe6ff" stroke="#003082" stroke-width="0.6"/>
            <!-- front headlight -->
            <circle cx="83" cy="26" r="1.6" fill="#fffae0"/>
            <!-- wheels -->
            <circle cx="18" cy="36" r="3.5" fill="#1c1c1c"/>
            <circle cx="32" cy="36" r="3.5" fill="#1c1c1c"/>
            <circle cx="56" cy="36" r="3.5" fill="#1c1c1c"/>
            <circle cx="70" cy="36" r="3.5" fill="#1c1c1c"/>
          </svg>`;
        const cat = (trainPos.train_type || ctx.legProduct?.shortCategoryName || "").toString().slice(0, 4);
        const icon = L.divIcon({
          className: "ns-leaflet-train-wrap",
          html: `<div class="ns-leaflet-train">${tile}<span class="ns-cat">${cat}</span></div>`,
          iconSize: [44, 22],
          iconAnchor: [22, 11],
        });
        ctx.trainMarker = L.marker(ll, {
          icon,
          zIndexOffset: 1000,
          title: "Trein",
          rotationAngle: 0,
        }).addTo(map);
      } else {
        ctx.trainMarker.setLatLng(ll);
      }
      // Keep the marker visually stable: the train tile stays
      // horizontal (no rotation), only its X-axis is mirrored when the
      // train is heading west. That removes the jarring flip the
      // user saw at the south/north heading boundary and is the same
      // approach treinposities.nl uses. We accept that N/S motion is
      // not visually distinguished — it never looked good there
      // anyway because trains are very wide and don't read well at a
      // 90° tilt.
      // Skip mirror updates while the train is essentially parked
      // (speed ≈ 0); heading values are noisy at standstill.
      const speedNum = Number(trainPos.speed);
      if (Number.isFinite(speedNum) && speedNum > 1 && trainPos.heading != null) {
        const h = ((Number(trainPos.heading) % 360) + 360) % 360;
        const scaleX = (h > 180 && h < 360) ? -1 : 1;
        const el = ctx.trainMarker.getElement();
        const tileEl = el && el.querySelector(".ns-leaflet-train");
        if (tileEl) {
          tileEl.style.transform = `scaleX(${scaleX})`;
          // Counter-flip the category label (SPR/IC) so the text
          // stays readable when the tile is mirrored.
          const cat = tileEl.querySelector(".ns-cat");
          if (cat) {
            cat.style.transform = scaleX === -1
              ? "translate(-50%, -50%) scaleX(-1)"
              : "translate(-50%, -50%)";
          }
        }
      }
    }

    // First-time fit. The drawn line is the train's whole run, which
    // can stretch across the country, so the view is framed on the
    // traveller's own leg plus wherever the train is — both the bit
    // that matters and the train itself stay in sight.
    if (!ctx.fitDone) {
      const focus = (ctx.legStopsRaw || [])
        .filter(s => s.lat != null && s.lng != null);
      const allLatLngs = (focus.length >= 2 ? focus : stops)
        .map(s => [s.lat, s.lng]);
      if (trainPos && trainPos.lat != null) allLatLngs.push([trainPos.lat, trainPos.lng]);
      if (allLatLngs.length) {
        map.fitBounds(allLatLngs, { padding: [40, 40], maxZoom: 13 });
      }
      ctx.fitDone = true;
      // Leaflet sometimes mis-sizes when its container animates in.
      // Force a recompute after layout settles.
      setTimeout(() => map.invalidateSize(), 200);
    }
  }

  // v2.22.0: colour the timeline's vertical line along with the train.
  // The stretch already travelled turns the same yellow the live map
  // uses, the rest stays blue, and the boundary sits where the train is
  // — part-way between two stations when it is between them, on the
  // station when it is standing there.
  //
  // The line of one leg is drawn as several elements of different
  // heights (and, with the stops unfolded, one dashed piece per stop),
  // so the division is worked out here, after render, when the browser
  // knows how tall each piece turned out. Times come from NS: actual
  // where it reports them, planned where it does not.
  _paintProgress(retry = true) {
    if (!this.content) return;
    const DONE = "#FFC917";
    const TODO = "#3b82f6";
    const now = Date.now();

    // Straight after innerHTML the browser may not have laid the card
    // out yet, and every piece of line measures zero. Come back once
    // it has rather than leaving the line unpainted.
    const firstLine = this.content.querySelector(".tl-line[data-prog-group]");
    if (retry && firstLine && firstLine.offsetHeight === 0) {
      requestAnimationFrame(() => this._paintProgress(false));
      return;
    }

    const groups = new Map();
    this.content.querySelectorAll(".tl-line[data-prog-group]").forEach(el => {
      const key = el.getAttribute("data-prog-group");
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(el);
    });

    groups.forEach(elements => {
      const first = elements[0];
      const start = Number(first.getAttribute("data-prog-start"));
      const end = Number(first.getAttribute("data-prog-end"));
      if (!Number.isFinite(start) || !Number.isFinite(end)) return;
      let frac = end > start
        ? Math.max(0, Math.min(1, (now - start) / (end - start)))
        : (now >= end ? 1 : 0);

      // While the train is on its way, ask where it really is. The
      // timetable only says where it is due, and NS gives a time for
      // stations it has not reached yet, so a train running behind
      // would otherwise colour a station it is still approaching.
      const train = first.getAttribute("data-prog-train");
      if (now >= start && now <= end) this._ensureProgress(train);
      const live = this._progressIndex(
        train,
        first.getAttribute("data-prog-from"), first.getAttribute("data-prog-from-name"),
        first.getAttribute("data-prog-to"), first.getAttribute("data-prog-to-name"),
      );
      if (live != null) frac = live;
      const total = elements.reduce((sum, el) => sum + el.offsetHeight, 0);
      if (total <= 0) return;
      const filled = frac * total;
      let walked = 0;
      elements.forEach(el => {
        const height = el.offsetHeight;
        const top = walked;
        walked += height;
        if (filled >= walked) {
          el.style.background = DONE;
        } else if (filled <= top || height <= 0) {
          el.style.background = TODO;
        } else {
          const pct = ((filled - top) / height) * 100;
          el.style.background =
            `linear-gradient(to bottom, ${DONE} ${pct}%, ${TODO} ${pct}%)`;
        }
      });
    });

    // An unfolded stop: its dashed piece and the station dots are
    // either behind the train or still ahead of it.
    const behindTheTrain = (el) => {
      const passed = this._progressPassed(
        el.getAttribute("data-prog-train"),
        el.getAttribute("data-prog-uic"),
        el.getAttribute("data-prog-name"),
      );
      if (passed != null) return passed;
      const at = Number(el.getAttribute("data-prog-at"));
      return Number.isFinite(at) && now >= at;
    };
    this.content.querySelectorAll(".stop-line-col[data-prog-at]").forEach(el => {
      el.style.setProperty("--ns-stop-line", behindTheTrain(el) ? DONE : TODO);
    });
    this.content.querySelectorAll(".tl-dot[data-prog-at]").forEach(el => {
      el.classList.toggle("tl-dot-done", behindTheTrain(el));
    });
  }

  // Ask the backend where a train is along its run, at most once every
  // 20 seconds per train. The answer is cached on the card and the
  // line is repainted when it lands; both the run and the national
  // vehicle feed are cached in the integration, so several cards
  // asking at once cost one request between them.
  _ensureProgress(train) {
    if (!train || !this._hass) return;
    this._progress = this._progress || new Map();
    const held = this._progress.get(train);
    const now = Date.now();
    if (held && now - held.at < 20000) return;
    if (held && held.pending) return;
    this._progress.set(train, { at: now, pending: true, data: held && held.data });
    this._hass.callWS({
      type: "ns_reisadvies/train_progress",
      train_number: train,
    }).then(data => {
      this._progress.set(train, { at: Date.now(), pending: false, data });
      this._paintProgress(false);
    }).catch(() => {
      // No position, an older Home Assistant, or the command is not
      // registered: the clock-based colouring stands.
      this._progress.set(train, { at: Date.now(), pending: false, data: null });
    });
  }

  // The train's place in the run, as an index with a fraction, and the
  // helpers that turn it into "how far along this leg" and "has this
  // station been passed".
  _progressFor(train) {
    const held = train && this._progress && this._progress.get(train);
    const data = held && held.data;
    if (!data || typeof data.position_index !== "number") return null;
    if (!Array.isArray(data.stops) || !data.stops.length) return null;
    return data;
  }

  _stopIndex(data, uic, name) {
    const wanted = String(uic || "");
    const wantedName = String(name || "").toLowerCase();
    for (let i = 0; i < data.stops.length; i++) {
      const stop = data.stops[i];
      if (wanted && String(stop.uicCode || "") === wanted) return i;
      if (wantedName && String(stop.name || "").toLowerCase() === wantedName) return i;
    }
    return -1;
  }

  _progressIndex(train, fromUic, fromName, toUic, toName) {
    const data = this._progressFor(train);
    if (!data) return null;
    const from = this._stopIndex(data, fromUic, fromName);
    const to = this._stopIndex(data, toUic, toName);
    if (from < 0 || to < 0 || to <= from) return null;
    return Math.max(0, Math.min(1, (data.position_index - from) / (to - from)));
  }

  // "Behind the train" includes the station it is standing in: the
  // backend answers with that station's exact index while the train is
  // at the platform, so a train waiting at Naarden-Bussum colours
  // Naarden-Bussum rather than leaving it for when it pulls out.
  _progressPassed(train, uic, name) {
    const data = this._progressFor(train);
    if (!data) return null;
    const index = this._stopIndex(data, uic, name);
    if (index < 0) return null;
    return data.position_index >= index;
  }

  _updatePosLabel(pos, leg) {
    if (!this._activeMap || !this._activeMap.modalEl) return;
    const el = this._activeMap.modalEl.querySelector(".ns-map-pos");
    if (!el) return;
    if (!pos) {
      el.textContent = "";
      return;
    }
    const speed = pos.speed != null ? Math.round(pos.speed) : null;
    const parts = [];
    if (speed != null) parts.push(t("live_map_speed", this._hass, { n: speed }));
    if (pos.station_name) parts.push(pos.station_name);
    el.textContent = parts.length ? "· " + parts.join(" · ") : "";
  }

  async _pollLiveMap() {
    const ctx = this._activeMap;
    if (!ctx || !ctx.sessionId) return;

    // Refresh leg.stops from the live sensor state so newly confirmed
    // actualDepartureDateTime values flow into the interpolation. The
    // sensor is repolled by the coordinator on its own scan-interval,
    // so we just have to re-read.
    if (this._hass && this._config?.entity && ctx.tripIdx != null && ctx.legIdx != null) {
      // v2.17.2: re-resolve by identity. The trips list shifts under an
      // open map every time a train departs, so re-reading by index
      // would quietly swap in another train's stops mid-session.
      const resolved = this._resolveLeg(ctx.tripIdx, ctx.legIdx, ctx.expect);
      if (resolved) {
        ctx.tripIdx = resolved.tripIdx;
        ctx.legIdx = resolved.legIdx;
        if (Array.isArray(resolved.leg.stops)) {
          ctx.legStopsRaw = resolved.leg.stops.filter(s => !s.passing);
        }
      }
    }

    try {
      const resp = await this._hass.callWS({
        type: "ns_reisadvies/track_train_poll",
        session_id: ctx.sessionId,
      });
      // v2.21.0: the poll brings the run's times along, so an estimate
      // made between fixes uses departures NS confirmed since the map
      // was opened instead of the picture it had at the start.
      if (resp && Array.isArray(resp.journey_stops) && resp.journey_stops.length) {
        ctx.journeyStopsRaw = resp.journey_stops;
      }
      const real = resp && resp.train_position;
      const pos = real || this._interpolateTrainPos();
      this._applyMapData(pos, resp && resp.journey_stops);
      this._updatePosLabel(pos);
    } catch (err) {
      console.warn("ns_reisadvies live map poll failed", err);
      const interp = this._interpolateTrainPos();
      if (interp) {
        this._applyMapData(interp);
        this._updatePosLabel(interp);
      }
    }
  }

  // Estimate where the train is from the timetable of its WHOLE run.
  //
  // The full journey is preferred over the traveller's own leg. A train
  // is normally already under way towards the departure station, and it
  // carries on after the traveller gets out, so an estimate that only
  // knows the leg parks the marker on the departure station until the
  // moment of departure and pins it to the arrival station afterwards —
  // which is exactly what users saw once the GPS feeds went quiet.
  //
  // Only an ACTUAL time counts as proof of where the train has been.
  // Everything beyond the last confirmed stop is projected from the
  // schedule, shifted by the delay measured at that stop, so a late
  // train is never teleported ahead of itself.
  _interpolateTrainPos() {
    const ctx = this._activeMap;
    if (!ctx) return null;
    const hasCoord = s => s && s.lat != null && s.lng != null;
    const journey = (ctx.journeyStopsRaw || []).filter(hasCoord);
    const stops = journey.length >= 2
      ? journey
      : (ctx.legStopsRaw || []).filter(hasCoord);
    if (stops.length < 2) return null;

    const now = Date.now();
    const stamp = (s, k) => {
      const v = s && s[k];
      if (!v) return null;
      const d = Date.parse(v);
      return Number.isFinite(d) ? d : null;
    };

    // Delay at the last stop that reported an actual time.
    let delay = 0;
    for (const s of stops) {
      const actual = stamp(s, "actualDepartureDateTime")
        ?? stamp(s, "actualArrivalDateTime");
      if (actual == null || actual > now) continue;
      const planned = stamp(s, "plannedDepartureDateTime")
        ?? stamp(s, "plannedArrivalDateTime");
      if (planned != null) delay = actual - planned;
    }
    const shift = v => (v == null ? null : v + delay);
    const leaveAt = s => stamp(s, "actualDepartureDateTime")
      ?? shift(stamp(s, "plannedDepartureDateTime"));
    const reachAt = s => stamp(s, "actualArrivalDateTime")
      ?? shift(stamp(s, "plannedArrivalDateTime"));

    const first = stops[0];
    const last = stops[stops.length - 1];
    const start = leaveAt(first) ?? reachAt(first);
    if (start != null && now < start) {
      return {
        lat: first.lat, lng: first.lng, station_name: first.name,
        source: "at-origin", estimated: true,
      };
    }
    const finish = reachAt(last) ?? leaveAt(last);
    if (finish != null && now >= finish) {
      return {
        lat: last.lat, lng: last.lng, station_name: last.name,
        source: "arrived", estimated: true,
      };
    }

    for (let i = 0; i < stops.length - 1; i++) {
      const a = stops[i];
      const b = stops[i + 1];
      const left = leaveAt(a) ?? reachAt(a);
      const arrives = reachAt(b) ?? leaveAt(b);
      if (left == null || arrives == null) continue;
      if (now >= arrives) continue;
      if (now < left) {
        // Reached `a`, not away yet: standing at the platform.
        return {
          lat: a.lat, lng: a.lng, station_name: a.name,
          source: "at-stop", estimated: true,
        };
      }
      const span = arrives - left;
      if (span <= 0) continue;
      const frac = Math.max(0, Math.min(1, (now - left) / span));
      return {
        lat: a.lat + (b.lat - a.lat) * frac,
        lng: a.lng + (b.lng - a.lng) * frac,
        station_name: `${a.name} \u2192 ${b.name}`,
        source: "interpolated",
        estimated: true,
        frac,
      };
    }

    // No pair fitted: stay on the stop we are surest about.
    return {
      lat: last.lat, lng: last.lng, station_name: last.name,
      source: "arrived", estimated: true,
    };
  }

  closeLiveMap() {
    const ctx = this._activeMap;
    if (!ctx) return;
    this._activeMap = null;
    if (ctx.pollHandle) clearInterval(ctx.pollHandle);
    this._stopTileTokenRefresh(ctx);
    if (ctx.escHandler) document.removeEventListener("keydown", ctx.escHandler);
    if (ctx.sessionId && this._hass) {
      this._hass.callWS({
        type: "ns_reisadvies/track_train_stop",
        session_id: ctx.sessionId,
      }).catch(() => {});
    }
    // Tear down the map so its DOM listeners and tile downloads do not
    // linger.
    if (ctx.lmap) {
      try { ctx.lmap.remove(); } catch {}
    }
    if (ctx.modalEl && ctx.modalEl.parentNode) {
      ctx.modalEl.parentNode.removeChild(ctx.modalEl);
    }
  }

  connectedCallback() {
    if (super.connectedCallback) super.connectedCallback();
    // v2.16.25: re-render every 30 seconds so departed trips drop
    // from the timeline within ≤ 1 min, regardless of when the
    // coordinator next polls NS. The render path is gated by
    // `set hass` (no DOM rewrite unless state changes) but
    // ``updateContent`` is called directly here so it always reruns
    // the stale filter against a fresh ``Date.now()``.
    if (this._staleTickHandle == null) {
      this._staleTickHandle = setInterval(() => {
        if (this._lastStateObj && this._config) {
          this.updateContent();
        }
      }, 30 * 1000);
    }
  }

  disconnectedCallback() {
    this.closeLiveMap();
    if (this._staleTickHandle != null) {
      clearInterval(this._staleTickHandle);
      this._staleTickHandle = null;
    }
    if (super.disconnectedCallback) super.disconnectedCallback();
  }
}

class NSReisadviesEditor extends HTMLElement {
  setConfig(config) { if (config) this._config = config; }

  set hass(hass) {
    this._hass = hass;
    if (!this._rendered && this._config) {
      this.render();
      this._rendered = true;
    }
  }

  render() {
    if (!this._hass || !this._config) return;
    // Prefer entity registry (hass.entities) so we only show OUR sensors and
    // exclude unrelated integrations (e.g. nederlandse_spoorwegen) that also
    // register sensor.ns_* entities. Fall back to the prefix-match if the
    // registry data isn't available for some reason.
    const reg = this._hass.entities;
    let entities;
    if (reg && typeof reg === "object") {
      entities = Object.keys(reg)
        .filter(eid => eid.startsWith("sensor.") && reg[eid] && reg[eid].platform === "ns_reisadvies")
        .sort();
    } else {
      entities = Object.keys(this._hass.states).filter(e => e.startsWith("sensor.ns_")).sort();
    }
    // If the configured entity isn't in the list (e.g. user has a stale
    // config or has a sensor from outside the registry), keep it visible
    // so the dropdown still reflects current state.
    if (this._config.entity && !entities.includes(this._config.entity)) {
      entities = entities.concat([this._config.entity]).sort();
    }
    const lang = _lang(this._hass);
    const dict = I18N[lang] || I18N.en;
    const labels = dict.weekdays;
    const weekDays = [
      { label: labels[0], val: 1 },
      { label: labels[1], val: 2 },
      { label: labels[2], val: 3 },
      { label: labels[3], val: 4 },
      { label: labels[4], val: 5 },
      { label: labels[5], val: 6 },
      { label: labels[6], val: 0 },
    ];
    const slots = this._config.fav_slots || 1;
    const curRows = this._config.max_rows || 5;
    const curScale = this._config.scale || 100;
    const curFavH = this._config.fav_hours !== undefined ? this._config.fav_hours : 6;
    const curTitle = this._config.title || "NS Reisadvies";

    let html = `
      <style>
        .box { background: rgba(128,128,128,0.1); padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #FFC917; position: relative; }
        .time-row { display: flex; gap: 10px; margin: 15px 0; align-items: center; }
        .select-styled { background: #2a2a2a !important; color: white !important; padding: 6px 8px !important; height: 38px !important; border-radius: 6px !important; border: 1px solid #444 !important; font-size: 1.1em !important; font-weight: 500 !important; cursor: pointer !important; min-width: 70px !important; text-align: center !important; }
        .day-grid { display: flex; justify-content: space-between; margin-top: 15px; }
        .day-unit { font-size: 0.85em; display: flex; flex-direction: column; align-items: center; gap: 5px; }
        .chk { width: 17px; height: 17px; cursor: pointer; }
        .slider-row { margin-bottom: 15px; }
        .slider-label { display: block; margin-bottom: 5px; font-weight: 500; }
        .val-span { font-weight: bold; float: right; color: #3b82f6; }
      </style>
      <div style="padding: 10px;">
        <ha-textfield label="${t("editor_title", this._hass)}" id="title" style="width:100%; margin-bottom:20px;"></ha-textfield>
        <label style="margin-bottom: 5px; display: block; font-size: 0.9em; opacity: 0.8;">${t("editor_route_sensor", this._hass)}</label>
        <select id="entity" style="width:100%; padding:10px; background:var(--card-background-color); color:inherit; margin-bottom:20px; border:1px solid var(--divider-color); border-radius: 6px;">
          ${entities.map(e => `<option value="${e}" ${e === this._config.entity ? "selected" : ""}>${e}</option>`).join("")}
        </select>
        <div class="slider-row"><label class="slider-label">${t("editor_number_of_trips", this._hass)} <span class="val-span" id="val-rows">${curRows}</span></label><input type="range" id="max_rows" min="1" max="15" value="${curRows}" style="width:100%;"></div>
        <div class="slider-row"><label class="slider-label">${t("editor_scale", this._hass)} <span class="val-span" id="val-scale">${curScale}%</span></label><input type="range" id="scale" min="50" max="150" value="${curScale}" style="width:100%;"></div>

        <div class="slider-row" style="margin-bottom: 25px;">
           <label class="slider-label">${t("editor_keep_favourites", this._hass)} <span class="val-span" id="val-fav">${curFavH}</span></label>
           <input type="range" id="fav_hours" min="0" max="48" value="${curFavH}" style="width:100%;">
        </div>

        <h3 style="margin-bottom: 12px; font-size: 1.1em;">${t("editor_favourite_times", this._hass)}</h3>`;

    for (let i = 1; i <= slots; i++) {
      const activeDays = (this._config[`auto_days_${i}`] || "").split(",").filter(x => x !== "");
      const curHour = this._config[`auto_hour_${i}`] !== undefined
        ? String(this._config[`auto_hour_${i}`]).padStart(2, "0")
        : "08";
      const curMin = this._config[`auto_min_${i}`] !== undefined
        ? String(this._config[`auto_min_${i}`]).padStart(2, "0")
        : "00";
      html += `
        <div class="box">
          <ha-icon icon="mdi:delete" class="delete-slot" data-index="${i}" style="position: absolute; right: 10px; top: 10px; color: #ff5252; cursor: pointer; opacity: 0.7;"></ha-icon>
          <ha-textfield label="${t("editor_name", this._hass)}" id="auto_name_${i}" style="width: calc(100% - 30px); margin-bottom: 5px;"></ha-textfield>
          <div class="time-row">
            <span>${t("editor_time", this._hass)}</span>
            <select class="select-styled" id="auto_hour_${i}">${Array.from({ length: 24 }, (_, n) => `<option value="${n.toString().padStart(2, "0")}" ${curHour === n.toString().padStart(2, "0") ? "selected" : ""}>${n.toString().padStart(2, "0")}</option>`).join("")}</select>
            <span>:</span>
            <select class="select-styled" id="auto_min_${i}">${Array.from({ length: 60 }, (_, n) => `<option value="${n.toString().padStart(2, "0")}" ${curMin === n.toString().padStart(2, "0") ? "selected" : ""}>${n.toString().padStart(2, "0")}</option>`).join("")}</select>
          </div>
          <div class="day-grid">
            ${weekDays.map(day => `<label class="day-unit"><span>${day.label}</span><input type="checkbox" class="chk" data-index="${i}" data-day="${day.val}" ${activeDays.includes(day.val.toString()) ? "checked" : ""}></label>`).join("")}
          </div>
        </div>`;
    }

    html += `<button id="add-slot" style="width:100%; padding: 12px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; margin-top: 5px;">${t("editor_add_slot", this._hass)}</button></div>`;

    this.innerHTML = html;

    // Custom-element properties must be set after innerHTML.
    const titleField = this.querySelector("#title");
    if (titleField) {
      titleField.value = curTitle;
      titleField.addEventListener("change", (ev) => this._fire({ title: ev.target.value }));
    }

    for (let i = 1; i <= slots; i++) {
      const nameField = this.querySelector(`#auto_name_${i}`);
      if (nameField) {
        const fallback = t("editor_time_slot", this._hass, { n: i });
        nameField.value = this._config[`auto_name_${i}`] || fallback;
      }
    }

    this.querySelector("#add-slot").addEventListener("click", () => {
      const newIdx = slots + 1;
      // Important: persist the defaults straight away. Otherwise
      // processAutoFavs would skip this slot because auto_hour/auto_min
      // would be undefined.
      this._fire({
        fav_slots: newIdx,
        [`auto_hour_${newIdx}`]: "08",
        [`auto_min_${newIdx}`]: "00",
        [`auto_days_${newIdx}`]: "",
        [`auto_name_${newIdx}`]: t("editor_time_slot", this._hass, { n: newIdx }),
      });
      this.render();
    });
    this.querySelector("#max_rows").addEventListener("input", (e) => {
      this.querySelector("#val-rows").innerText = e.target.value;
      this._fire({ max_rows: parseInt(e.target.value, 10) });
    });
    this.querySelector("#scale").addEventListener("input", (e) => {
      this.querySelector("#val-scale").innerText = e.target.value + "%";
      this._fire({ scale: parseInt(e.target.value, 10) });
    });

    this.querySelector("#fav_hours").addEventListener("input", (e) => {
      this.querySelector("#val-fav").innerText = e.target.value;
      this._fire({ fav_hours: parseInt(e.target.value, 10) });
    });

    this.querySelectorAll(".delete-slot").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.dataset.index, 10);
        let newConfig = { ...this._config };
        for (let j = idx; j < slots; j++) {
          newConfig[`auto_name_${j}`] = newConfig[`auto_name_${j + 1}`];
          newConfig[`auto_hour_${j}`] = newConfig[`auto_hour_${j + 1}`];
          newConfig[`auto_min_${j}`] = newConfig[`auto_min_${j + 1}`];
          newConfig[`auto_days_${j}`] = newConfig[`auto_days_${j + 1}`];
        }
        delete newConfig[`auto_name_${slots}`];
        delete newConfig[`auto_hour_${slots}`];
        delete newConfig[`auto_min_${slots}`];
        delete newConfig[`auto_days_${slots}`];
        newConfig.fav_slots = slots - 1;
        this._config = newConfig;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: newConfig } }));
        this.render();
      });
    });

    this.querySelectorAll(".chk").forEach(chk => {
      chk.addEventListener("change", () => {
        const idx = chk.dataset.index;
        const checks = this.querySelectorAll(`.chk[data-index="${idx}"]:checked`);
        const val = Array.from(checks).map(c => c.dataset.day).join(",");
        this._fire({ [`auto_days_${idx}`]: val });
      });
    });

    this.querySelectorAll("select, ha-textfield:not(#title)").forEach(el => {
      el.addEventListener("change", (ev) => this._fire({ [ev.target.id]: ev.target.value }));
    });
  }

  _fire(obj) {
    const newConfig = { ...this._config, ...obj };
    this._config = newConfig;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: newConfig } }));
  }
}

// v2.24.0: a card for looking something up on the spot.
//
// Everything below the form is the ordinary card: the same timeline,
// the same stops, the same live-map button. Only the source differs —
// instead of a route's sensor it renders the answer to a one-off
// search, which is why it extends the card rather than copying it.
//
// Nothing is stored on the server: no route, no favourite, no sensor.
// The recent searches live in this browser alone.
class NSReisadviesSearchCard extends NSReisadviesCard {
  static getConfigElement() {
    return document.createElement("ns-reisadvies-search-editor");
  }

  static getStubConfig() {
    return { title: "Reisadvies zoeken", max_rows: 6 };
  }

  setConfig(config) {
    const given = config || {};
    super.setConfig({
      title: "NS Reisadvies",
      max_rows: 6,
      scale: 100,
      fav_slots: 0,
      fav_hours: 0,
      ...given,
      // A search has no route behind it, so there is no entity and
      // nothing to pin a favourite to.
      entity: "",
    });
    this._query = {
      from: given.from || "",
      to: given.to || "",
      via: given.via || "",
      when: "",
      mode: "now",
      types: Array.isArray(given.train_types) ? given.train_types.slice() : [],
    };
    this._result = null;
    this._problem = null;
    this._busy = false;
    this._stations = [];
  }

  getCardSize() { return 6; }

  // The ordinary card reads a sensor; this one reads its own answer.
  _sourceState() { return this._result; }
  _hasSource() { return !!this._result; }
  _favouritesAllowed() { return false; }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (this._activeMap) this._syncMapTheme();
    this._buildShell();
    if (first) {
      this._loadStations();
      this._restoreRecent();
      if (this._query.from && this._query.to && this._config.auto_search) {
        this._runSearch();
      }
    }
  }

  _buildShell() {
    // Built once. Home Assistant sets `hass` on every state change in
    // the whole system — several times a second on a busy install —
    // and rebuilding the form there would throw away the field the
    // user is typing in, focus and all. The form is redrawn only when
    // something it shows actually changes.
    if (this.content) return;
    const card = document.createElement("ha-card");
    card.header = this._config.title;
    this.form = document.createElement("div");
    this.form.className = "ns-search";
    this.content = document.createElement("div");
    this.content.style.padding = "0";
    card.appendChild(this.form);
    card.appendChild(this.content);
    this.appendChild(card);
    this._renderForm();
    this.content.innerHTML =
      `<div class="ns-search-hint">${t("search_hint", this._hass)}</div>`;
  }

  async _loadStations() {
    // The list ships with the integration, so this is one small call
    // and then instant typing.
    try {
      const answer = await this._hass.callWS({ type: "ns_reisadvies/stations" });
      this._stations = (answer && answer.stations) || [];
    } catch (err) {
      console.warn("[ns-reisadvies] station list unavailable", err);
    }
  }

  _recentKey() { return "ns_reisadvies_recent_searches"; }

  _restoreRecent() {
    try {
      const raw = window.localStorage.getItem(this._recentKey());
      this._recent = raw ? JSON.parse(raw) : [];
    } catch (err) {
      this._recent = [];
    }
    if (!Array.isArray(this._recent)) this._recent = [];
    this._renderForm();
  }

  _rememberRecent(query) {
    const entry = {
      from: query.from, to: query.to, via: query.via || "",
      types: (query.types || []).slice(),
    };
    const same = (a, b) => a.from === b.from && a.to === b.to && a.via === b.via;
    this._recent = [entry].concat(
      (this._recent || []).filter(other => !same(other, entry)),
    ).slice(0, 5);
    try {
      window.localStorage.setItem(this._recentKey(), JSON.stringify(this._recent));
    } catch (err) {
      // A browser that refuses storage still searches fine.
    }
  }

  _clearRecent() {
    this._recent = [];
    try {
      window.localStorage.removeItem(this._recentKey());
    } catch (err) { /* nothing to clean up */ }
    this._renderForm();
  }

  _renderForm() {
    if (!this.form || !this._hass) return;
    const q = this._query;
    const esc = (value) => String(value || "")
      .replace(/&/g, "&amp;").replace(/"/g, "&quot;")
      .replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const recent = (this._recent || []).map((entry, index) => `
      <button class="ns-chip" data-recent="${index}" type="button">
        ${esc(entry.from)} → ${esc(entry.to)}${entry.via ? " ·" : ""}
      </button>`).join("");
    const typeChip = (code, label) => `
      <button class="ns-chip ${q.types.includes(code) ? "on" : ""}"
              data-type="${code}" type="button">${label}</button>`;

    // A redraw replaces the fields, so remember where the cursor was.
    const focused = this.form.querySelector("input:focus");
    const focusedField = focused ? focused.getAttribute("data-field") : null;
    const caret = focused ? focused.selectionStart : null;

    this.form.innerHTML = `
      <style>
        .ns-search { padding: 12px 16px 4px 16px; display: flex; flex-direction: column; gap: 8px; }
        .ns-search .row { display: flex; gap: 8px; align-items: center; }
        .ns-search input[type="text"], .ns-search input[type="datetime-local"] {
          flex: 1; min-width: 0; box-sizing: border-box; padding: 10px 12px; font-size: 1em; font-family: inherit;
          color: var(--primary-text-color); background: var(--card-background-color);
          border: 1px solid var(--divider-color); border-radius: 10px; }
        .ns-search input:focus { outline: 2px solid var(--primary-color); outline-offset: -1px; }
        /* v2.25.0: the browser's own datalist popup opened and shut
           again while typing, which made a station impossible to pick.
           This is a list the card draws itself: it narrows as you
           type, and the chevron opens it without typing at all. */
        .ns-search .ns-station { position: relative; flex: 1; min-width: 0; display: flex; }
        .ns-search .ns-station input { flex: 1; min-width: 0; padding-right: 34px; }
        .ns-search .ns-caret { position: absolute; right: 2px; top: 2px; bottom: 2px;
          width: 30px; border: none; background: none; cursor: pointer;
          color: var(--secondary-text-color); display: flex; align-items: center;
          justify-content: center; }
        .ns-search .ns-caret ha-icon { --mdc-icon-size: 20px; }
        .ns-search .ns-suggest { position: absolute; z-index: 9; top: calc(100% + 4px);
          left: 0; right: 0; margin: 0; padding: 4px 0; list-style: none;
          max-height: 232px; overflow-y: auto; border-radius: 10px;
          border: 1px solid var(--divider-color);
          background: var(--card-background-color);
          box-shadow: 0 6px 18px rgba(0,0,0,0.25); display: none; }
        .ns-search .ns-suggest.open { display: block; }
        .ns-search .ns-suggest li { padding: 9px 12px; cursor: pointer;
          color: var(--primary-text-color); font-size: 0.95em; }
        .ns-search .ns-suggest li.on, .ns-search .ns-suggest li:hover {
          background: rgba(255, 201, 23, 0.25); }
        .ns-search .ns-suggest li b { color: #003082; }
        .ns-search .ns-swap { flex: 0 0 auto; width: 40px; height: 40px; border-radius: 50%;
          border: 1px solid var(--divider-color); background: var(--card-background-color);
          color: var(--primary-text-color); cursor: pointer; display: flex;
          align-items: center; justify-content: center; }
        .ns-search .ns-chip { padding: 6px 10px; font-size: 0.85em; font-family: inherit;
          border-radius: 999px; border: 1px solid var(--divider-color);
          background: var(--card-background-color); color: var(--secondary-text-color);
          cursor: pointer; white-space: nowrap; }
        .ns-search .ns-chip.on { background: #FFC917; color: #003082; border-color: #FFC917;
          font-weight: 700; }
        .ns-search .chips { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
        .ns-search .chips .label { font-size: 0.8em; color: var(--secondary-text-color);
          text-transform: uppercase; letter-spacing: 0.04em; margin-right: 2px; }
        .ns-search .ns-go { flex: 1; padding: 11px 16px; font-size: 1em; font-weight: 700;
          font-family: inherit; border: none; border-radius: 10px; cursor: pointer;
          background: #003082; color: #fff; }
        .ns-search .ns-go[disabled] { opacity: 0.6; cursor: default; }
        .ns-search .ns-problem { color: #ff5252; font-size: 0.9em; min-height: 1.2em; }
        .ns-search-hint { padding: 18px 16px 22px 16px; text-align: center;
          color: var(--secondary-text-color); }
      </style>
      ${recent ? `<div class="chips"><span class="label">${t("search_recent", this._hass)}</span>${recent}
        <button class="ns-chip" data-clear="1" type="button">${t("search_clear_recent", this._hass)}</button></div>` : ""}
      <div class="row">
        ${this._stationField("from", t("search_from", this._hass), q.from)}
        <button class="ns-swap" data-swap="1" type="button" title="${t("search_swap", this._hass)}">
          <ha-icon icon="mdi:swap-vertical"></ha-icon></button>
        ${this._stationField("to", t("search_to", this._hass), q.to)}
      </div>
      <div class="row">
        ${this._stationField("via", t("search_via", this._hass), q.via)}
      </div>
      <div class="chips">
        <button class="ns-chip ${q.mode === "now" ? "on" : ""}" data-mode="now" type="button">${t("search_leave_now", this._hass)}</button>
        <button class="ns-chip ${q.mode === "leave" ? "on" : ""}" data-mode="leave" type="button">${t("search_leave_at", this._hass)}</button>
        <button class="ns-chip ${q.mode === "arrive" ? "on" : ""}" data-mode="arrive" type="button">${t("search_arrive_by", this._hass)}</button>
      </div>
      ${q.mode === "now" ? "" : `<div class="row">
        <input type="datetime-local" data-field="when" value="${esc(q.when || this._defaultWhen())}">
      </div>`}
      <div class="chips">
        <span class="label">${t("search_train_types", this._hass)}</span>
        ${typeChip("IC", "Intercity")}
        ${typeChip("ICD", "IC direct")}
        ${typeChip("SPR", "Sprinter")}
        ${typeChip("ST", "Stoptrein")}
        ${q.types.length ? `<button class="ns-chip" data-type="" type="button">${t("search_any_train", this._hass)}</button>` : ""}
      </div>
      <div class="row">
        <button class="ns-go" data-go="1" type="button" ${this._busy ? "disabled" : ""}>
          ${this._busy ? t("search_searching", this._hass) : t("search_go", this._hass)}
        </button>
      </div>
      <div class="ns-problem">${this._problem ? t(this._problem, this._hass) : ""}</div>
    `;
    this._wireForm();

    if (focusedField) {
      const again = this.form.querySelector(`input[data-field="${focusedField}"]`);
      if (again) {
        again.focus();
        if (caret != null) {
          try { again.setSelectionRange(caret, caret); } catch (err) { /* not a text field */ }
        }
      }
    }
  }

  _stationField(field, label, value) {
    const esc = (text) => String(text == null ? "" : text)
      .replace(/&/g, "&amp;").replace(/"/g, "&quot;")
      .replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return `
      <div class="ns-station">
        <input type="text" data-field="${field}" placeholder="${esc(label)}"
               value="${esc(value)}" autocomplete="off" autocapitalize="words"
               spellcheck="false" enterkeyhint="search">
        <button class="ns-caret" data-caret="${field}" type="button"
                tabindex="-1" aria-label="${esc(label)}">
          <ha-icon icon="mdi:menu-down"></ha-icon></button>
        <ul class="ns-suggest" data-list="${field}"></ul>
      </div>`;
  }

  // The stations whose name starts with what has been typed come
  // first, then the ones that merely contain it, so "ams" offers
  // Amsterdam before Bussum-Zuid-Amstel-and-so-on.
  _matchStations(typed) {
    const all = this._stations || [];
    const needle = String(typed || "").trim().toLowerCase();
    if (!needle) return all.slice(0, 60);
    const starts = [];
    const holds = [];
    for (const name of all) {
      const low = name.toLowerCase();
      if (low.startsWith(needle)) starts.push(name);
      else if (low.includes(needle)) holds.push(name);
      if (starts.length >= 40) break;
    }
    return starts.concat(holds).slice(0, 40);
  }

  _closeSuggestions(except) {
    if (!this.form) return;
    this.form.querySelectorAll(".ns-suggest").forEach(list => {
      if (list !== except) list.classList.remove("open");
    });
  }

  _showSuggestions(field, typed) {
    const list = this.form.querySelector(`.ns-suggest[data-list="${field}"]`);
    if (!list) return;
    const matches = this._matchStations(typed);
    if (!matches.length) {
      list.classList.remove("open");
      list.innerHTML = "";
      return;
    }
    const needle = String(typed || "").trim().toLowerCase();
    list.innerHTML = matches.map((name, index) => {
      const at = needle ? name.toLowerCase().indexOf(needle) : -1;
      const shown = at < 0 ? name : (
        name.slice(0, at) + "<b>" + name.slice(at, at + needle.length) + "</b>"
        + name.slice(at + needle.length)
      );
      return `<li data-name="${name.replace(/"/g, "&quot;")}" data-index="${index}">${shown}</li>`;
    }).join("");
    list.classList.remove("hidden");
    list.classList.add("open");
    this._closeSuggestions(list);
    list.querySelectorAll("li").forEach(item => {
      // mousedown, not click: blur would close the list first.
      item.addEventListener("mousedown", (event) => {
        event.preventDefault();
        this._pickStation(field, item.getAttribute("data-name"));
      });
    });
  }

  _pickStation(field, name) {
    this._query[field] = name;
    const input = this.form.querySelector(`input[data-field="${field}"]`);
    if (input) input.value = name;
    this._closeSuggestions();
    const list = this.form.querySelector(`.ns-suggest[data-list="${field}"]`);
    if (list) list.classList.remove("open");
  }

  _highlight(list, delta) {
    const items = [...list.querySelectorAll("li")];
    if (!items.length) return null;
    let index = items.findIndex(item => item.classList.contains("on"));
    index = index < 0 ? (delta > 0 ? 0 : items.length - 1) : index + delta;
    if (index < 0) index = items.length - 1;
    if (index >= items.length) index = 0;
    items.forEach(item => item.classList.remove("on"));
    items[index].classList.add("on");
    items[index].scrollIntoView({ block: "nearest" });
    return items[index];
  }

  _uid() {
    if (!this._uidValue) {
      this._uidValue = Math.random().toString(36).slice(2, 8);
    }
    return this._uidValue;
  }

  _defaultWhen() {
    // The datetime input wants local wall-clock without a zone.
    const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);
    return now.toISOString().slice(0, 16);
  }

  _wireForm() {
    this.form.querySelectorAll("input[data-field]").forEach(input => {
      const field = input.getAttribute("data-field");
      const stationField = ["from", "to", "via"].includes(field);
      input.addEventListener("change", () => { this._query[field] = input.value.trim(); });
      input.addEventListener("input", () => {
        this._query[field] = input.value.trim();
        if (stationField) this._showSuggestions(field, input.value);
      });
      if (stationField) {
        input.addEventListener("focus", () => {
          if (input.value.trim()) this._showSuggestions(field, input.value);
        });
        input.addEventListener("blur", () => {
          // A tap on the list fires mousedown first, so by the time
          // blur lands the choice has already been made. Only this
          // field's own list is closed: leaving one field to open
          // another's list must not shut the one just opened.
          setTimeout(() => {
            const own = this.form
              && this.form.querySelector(`.ns-suggest[data-list="${field}"]`);
            if (own) own.classList.remove("open");
          }, 120);
        });
      }
      input.addEventListener("keydown", (event) => {
        const list = stationField
          ? this.form.querySelector(`.ns-suggest[data-list="${field}"]`)
          : null;
        const open = list && list.classList.contains("open");
        if (open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
          event.preventDefault();
          this._highlight(list, event.key === "ArrowDown" ? 1 : -1);
          return;
        }
        if (open && event.key === "Escape") {
          event.preventDefault();
          this._closeSuggestions();
          return;
        }
        if (event.key !== "Enter") return;
        const chosen = open ? list.querySelector("li.on") : null;
        if (chosen) {
          // Enter on a highlighted station fills it in; the next
          // Enter searches.
          event.preventDefault();
          this._pickStation(field, chosen.getAttribute("data-name"));
          return;
        }
        this._query[field] = input.value.trim();
        this._closeSuggestions();
        this._runSearch();
      });
    });
    this.form.querySelectorAll("[data-caret]").forEach(button => {
      button.addEventListener("mousedown", (event) => {
        event.preventDefault();
        const field = button.getAttribute("data-caret");
        const list = this.form.querySelector(`.ns-suggest[data-list="${field}"]`);
        const input = this.form.querySelector(`input[data-field="${field}"]`);
        if (list && list.classList.contains("open")) {
          this._closeSuggestions();
          return;
        }
        this._showSuggestions(field, input ? input.value : "");
        if (input) input.focus();
      });
    });
    const click = (selector, handler) => {
      this.form.querySelectorAll(selector).forEach(el => {
        el.addEventListener("click", (event) => { event.preventDefault(); handler(el); });
      });
    };
    click("[data-swap]", () => {
      this._readInputs();
      const from = this._query.from;
      this._query.from = this._query.to;
      this._query.to = from;
      this._renderForm();
    });
    click("[data-mode]", (el) => {
      this._readInputs();
      this._query.mode = el.getAttribute("data-mode");
      this._renderForm();
    });
    click("[data-type]", (el) => {
      this._readInputs();
      const code = el.getAttribute("data-type");
      if (!code) {
        this._query.types = [];
      } else if (this._query.types.includes(code)) {
        this._query.types = this._query.types.filter(other => other !== code);
      } else {
        this._query.types = this._query.types.concat([code]);
      }
      this._renderForm();
    });
    click("[data-recent]", (el) => {
      const entry = (this._recent || [])[Number(el.getAttribute("data-recent"))];
      if (!entry) return;
      this._query.from = entry.from;
      this._query.to = entry.to;
      this._query.via = entry.via || "";
      this._query.types = (entry.types || []).slice();
      this._renderForm();
      this._runSearch();
    });
    click("[data-clear]", () => this._clearRecent());
    click("[data-go]", () => { this._readInputs(); this._runSearch(); });
  }

  _readInputs() {
    this.form.querySelectorAll("input[data-field]").forEach(input => {
      this._query[input.getAttribute("data-field")] = input.value.trim();
    });
  }

  async _runSearch() {
    if (this._busy || !this._hass) return;
    const q = this._query;
    if (!q.from || !q.to) {
      this._problem = "search_pick_stations";
      this._renderForm();
      return;
    }
    this._busy = true;
    this._problem = null;
    this._renderForm();
    this.content.innerHTML =
      `<div class="ns-search-hint">${t("search_searching", this._hass)}</div>`;

    let answer = null;
    try {
      answer = await this._hass.callWS({
        type: "ns_reisadvies/search",
        from_station: q.from,
        to_station: q.to,
        via: q.via || null,
        when: q.mode === "now" ? null : this._isoWhen(q.when),
        arrival: q.mode === "arrive",
        train_types: q.types,
      });
    } catch (err) {
      console.warn("[ns-reisadvies] search failed", err);
      this._problem = "search_unavailable";
    }
    this._busy = false;

    const trips = (answer && answer.trips) || [];
    if (answer && answer.problem) this._problem = `search_${answer.problem}`;
    if (!this._problem && !trips.length) this._problem = "search_no_trips";

    if (trips.length) {
      this._rememberRecent(q);
      this._result = {
        state: "search",
        attributes: {
          trips,
          tracked_trips: [],
          live_train_map_enabled: true,
          live_map_refresh_seconds: 10,
          from_station: q.from,
          to_station: q.to,
          target_day_offset: 0,
          target_date: null,
          filter_days: [],
          filter_date: null,
        },
      };
      this._lastStateObj = this._result;
      this.updateContent();
    } else {
      this._result = null;
      this.content.innerHTML =
        `<div class="ns-search-hint">${t(this._problem, this._hass)}</div>`;
    }
    this._renderForm();
  }

  _isoWhen(value) {
    if (!value) return null;
    const parsed = new Date(value);
    return Number.isFinite(parsed.getTime()) ? parsed.toISOString() : null;
  }
}

// The ordinary card's editor asks for a route sensor and favourite
// times. Neither means anything here: a search has no route to pin a
// favourite to and no sensor to read. Nor does this one offer
// stations to fill in up front — the card is a search box, and that
// is where you type. What is left is how the card looks. A dashboard
// that does want a journey filled in beforehand can still set
// `from`, `to`, `via`, `train_types` and `auto_search` in YAML.
class NSReisadviesSearchEditor extends HTMLElement {
  setConfig(config) { if (config) this._config = config; }

  set hass(hass) {
    this._hass = hass;
    if (!this._rendered && this._config) {
      this._rendered = true;
      this.render();
    }
  }

  render() {
    if (!this._hass || !this._config) return;
    const cfg = this._config;
    const rows = cfg.max_rows || 6;
    const scale = cfg.scale || 100;
    this.innerHTML = `
      <style>
        .ns-ed { padding: 10px; }
        .ns-ed .slider-row { margin-bottom: 15px; }
        .ns-ed .slider-label { display: block; margin-bottom: 5px; font-weight: 500; }
        .ns-ed .val-span { font-weight: bold; float: right; color: #3b82f6; }
        .ns-ed h3 { margin: 18px 0 10px 0; font-size: 1.05em; }
      </style>
      <div class="ns-ed">
        <ha-textfield label="${t("editor_title", this._hass)}" id="title"
                      style="width:100%; margin-bottom:20px;"></ha-textfield>
        <div class="slider-row">
          <label class="slider-label">${t("editor_number_of_trips", this._hass)}
            <span class="val-span" id="val-rows">${rows}</span></label>
          <input type="range" id="max_rows" min="1" max="15" value="${rows}" style="width:100%;">
        </div>
        <div class="slider-row">
          <label class="slider-label">${t("editor_scale", this._hass)}
            <span class="val-span" id="val-scale">${scale}%</span></label>
          <input type="range" id="scale" min="50" max="150" value="${scale}" style="width:100%;">
        </div>
      </div>`;

    const titleField = this.querySelector("#title");
    if (titleField) {
      titleField.value = cfg.title || "NS Reisadvies";
      titleField.addEventListener("change", (ev) => this._fire({ title: ev.target.value }));
    }
    this.querySelector("#max_rows").addEventListener("input", (ev) => {
      this.querySelector("#val-rows").innerText = ev.target.value;
      this._fire({ max_rows: parseInt(ev.target.value, 10) });
    });
    this.querySelector("#scale").addEventListener("input", (ev) => {
      this.querySelector("#val-scale").innerText = ev.target.value + "%";
      this._fire({ scale: parseInt(ev.target.value, 10) });
    });
  }

  _fire(obj) {
    const newConfig = { ...this._config, ...obj };
    this._config = newConfig;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: newConfig } }));
  }
}

// v2.25.0: what NS says is wrong with the railway.
//
// Three kinds come out of one feed: an unplanned DISRUPTION, planned
// MAINTENANCE, and a CALAMITY — an announcement rather than a stretch
// of line, which is why it has no map button. Which kinds a card shows
// is chosen when the card is added.
//
// It extends the ordinary card for one reason: the map. Drawing the
// affected stretch needs the tile token, the Leaflet loading and the
// modal that the live train map already brings.
class NSReisadviesDisruptionsCard extends NSReisadviesCard {
  static getConfigElement() {
    return document.createElement("ns-reisadvies-disruptions-editor");
  }

  static getStubConfig() {
    return { title: "Storingen", types: ["DISRUPTION", "CALAMITY"], scope: "all" };
  }

  setConfig(config) {
    const given = config || {};
    super.setConfig({
      title: "NS Storingen",
      max_rows: 10,
      scale: 100,
      fav_slots: 0,
      fav_hours: 0,
      ...given,
      entity: "",
    });
    this._types = Array.isArray(given.types) && given.types.length
      ? given.types.slice()
      : ["DISRUPTION", "CALAMITY"];
    this._scope = given.scope || "all";
    this._stationFilter = Array.isArray(given.stations) ? given.stations.slice() : [];
    this._items = null;
    this._open = new Set();
    this._failed = false;
  }

  getCardSize() { return 4; }
  _favouritesAllowed() { return false; }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (this._activeMap) this._syncMapTheme();
    if (!this.content) {
      const card = document.createElement("ha-card");
      card.header = this._config.title;
      this.content = document.createElement("div");
      this.content.style.padding = "0";
      card.appendChild(this.content);
      this.appendChild(card);
      this.content.innerHTML =
        `<div class="ns-dis-empty">${t("loading", this._hass)}</div>`;
    }
    if (first) {
      this._load();
      // A disruption lasts hours; checking every two minutes is plenty
      // and the answer is cached in the integration anyway.
      this._disTick = setInterval(() => this._load(), 120 * 1000);
    }
  }

  disconnectedCallback() {
    if (super.disconnectedCallback) super.disconnectedCallback();
    if (this._disTick) clearInterval(this._disTick);
    this._disTick = null;
  }

  async _load() {
    if (!this._hass) return;
    try {
      const answer = await this._hass.callWS({
        type: "ns_reisadvies/disruptions",
        types: this._types,
        scope: this._scope,
        stations: this._stationFilter,
      });
      this._items = (answer && answer.disruptions) || [];
      this._failed = false;
    } catch (err) {
      console.warn("[ns-reisadvies] disruptions unavailable", err);
      this._failed = true;
    }
    this._render();
  }

  _render() {
    if (!this.content || !this._hass) return;
    const esc = (value) => String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/"/g, "&quot;")
      .replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const style = `
      <style>
        .ns-dis { padding: 4px 16px 16px 16px; }
        .ns-dis-empty { padding: 20px 16px; text-align: center;
          color: var(--secondary-text-color); }
        .ns-dis-item { border-bottom: 1px solid var(--divider-color); padding: 12px 0; }
        .ns-dis-item:last-child { border-bottom: none; }
        .ns-dis-head { display: flex; gap: 8px; align-items: flex-start; }
        .ns-dis-kind { flex: 0 0 auto; font-size: 0.7em; font-weight: 700;
          text-transform: uppercase; letter-spacing: 0.04em; padding: 3px 8px;
          border-radius: 999px; color: #fff; white-space: nowrap; margin-top: 2px; }
        .ns-dis-kind.DISRUPTION { background: #d32f2f; }
        .ns-dis-kind.MAINTENANCE { background: #FFC917; color: #003082; }
        .ns-dis-kind.CALAMITY { background: #003082; }
        .ns-dis-title { font-weight: 700; color: var(--primary-text-color); flex: 1; }
        .ns-dis-summary { color: var(--primary-text-color); margin-top: 6px;
          font-size: 0.95em; }
        .ns-dis-meta { color: var(--secondary-text-color); font-size: 0.85em;
          margin-top: 4px; }
        .ns-dis-actions { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
        .ns-dis-btn { font-family: inherit; font-size: 0.85em; padding: 5px 10px;
          border-radius: 999px; border: 1px solid var(--divider-color);
          background: var(--card-background-color); color: var(--secondary-text-color);
          cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }
        .ns-dis-btn ha-icon { --mdc-icon-size: 16px; color: #FF6B00; }
        .ns-dis-advice { margin: 8px 0 0 0; padding-left: 18px;
          color: var(--primary-text-color); font-size: 0.9em; }
        .ns-dis-advice li { margin-bottom: 3px; }
      </style>`;

    if (this._failed) {
      this.content.innerHTML =
        `${style}<div class="ns-dis-empty">${t("disruptions_unavailable", this._hass)}</div>`;
      return;
    }
    if (this._items === null) {
      this.content.innerHTML =
        `${style}<div class="ns-dis-empty">${t("loading", this._hass)}</div>`;
      return;
    }
    if (!this._items.length) {
      this.content.innerHTML =
        `${style}<div class="ns-dis-empty">${t("disruptions_none", this._hass)}</div>`;
      return;
    }

    const rows = this._items.slice(0, this._config.max_rows || 10).map((item, index) => {
      const open = this._open.has(item.id);
      const mappable = (item.stations || []).some(s => s.lat != null && s.lng != null);
      const meta = [item.period, item.expected_until, item.extra_travel_time]
        .filter(Boolean).map(esc).join(" · ");
      const advice = open && (item.advices || []).length
        ? `<ul class="ns-dis-advice">${item.advices.map(a => `<li>${esc(a)}</li>`).join("")}</ul>`
        : "";
      return `
        <div class="ns-dis-item">
          <div class="ns-dis-head">
            <span class="ns-dis-kind ${esc(item.type)}">${t(`disruptions_kind_${item.type}`, this._hass)}</span>
            <span class="ns-dis-title">${esc(item.title)}</span>
          </div>
          <div class="ns-dis-summary">${esc(item.summary)}</div>
          ${meta ? `<div class="ns-dis-meta">${meta}</div>` : ""}
          ${advice}
          <div class="ns-dis-actions">
            ${mappable ? `<button class="ns-dis-btn" data-map="${index}" type="button">
              <ha-icon icon="mdi:map-marker-path"></ha-icon>${t("disruptions_show_map", this._hass)}</button>` : ""}
            ${(item.advices || []).length ? `<button class="ns-dis-btn" data-open="${esc(item.id)}" type="button">
              ${open ? t("disruptions_less", this._hass) : t("disruptions_advice", this._hass)}</button>` : ""}
            ${item.url ? `<a class="ns-dis-btn" href="${esc(item.url)}" target="_blank" rel="noopener">
              ${t("disruptions_at_ns", this._hass)}</a>` : ""}
          </div>
        </div>`;
    }).join("");

    this.content.innerHTML = `${style}<div class="ns-dis">${rows}</div>`;
    this.content.querySelectorAll("[data-open]").forEach(button => {
      button.addEventListener("click", () => {
        const id = button.getAttribute("data-open");
        if (this._open.has(id)) this._open.delete(id); else this._open.add(id);
        this._render();
      });
    });
    this.content.querySelectorAll("[data-map]").forEach(button => {
      button.addEventListener("click", () => {
        const item = this._items[Number(button.getAttribute("data-map"))];
        if (item) this.openDisruptionMap(item);
      });
    });
  }

  // The affected stretch on a map, following the track.
  //
  // Two things make it look right. A disruption that hits two lines —
  // "Zwolle - Emmen; Almelo - Hardenberg" — arrives as two sections,
  // and they are drawn as two stretches rather than one line that
  // jumps across country between them. And each stretch is snapped
  // onto the rail graph the live train map already builds, so it
  // follows the rails instead of cutting straight through the fields.
  async openDisruptionMap(item) {
    const runs = (Array.isArray(item.sections) && item.sections.length
      ? item.sections
      : [item.stations || []])
      .map(run => (run || []).filter(s => s.lat != null && s.lng != null))
      .filter(run => run.length);
    const stops = runs.flat();
    if (!stops.length) return;
    this.closeLiveMap();

    const modal = document.createElement("div");
    modal.className = "ns-map-modal";
    modal.innerHTML = `
      <div class="ns-map-card">
        <div class="ns-map-header">
          <div class="ns-map-title">
            <ha-icon icon="mdi:alert-octagon-outline"></ha-icon>
            <span>${item.title}</span>
          </div>
          <span class="ns-map-close" role="button" title="Close"><ha-icon icon="mdi:close"></ha-icon></span>
        </div>
        <div class="ns-map-body">
          <div class="ns-map-loading">${t("live_map_loading", this._hass)}</div>
        </div>
      </div>`;
    const hostRoot = this._mapHostRoot();
    this._ensureModalStyles(hostRoot);
    hostRoot.appendChild(modal);
    this._activeMap = { modalEl: modal };

    const closeFn = () => this.closeLiveMap();
    modal.querySelector(".ns-map-close").addEventListener("click", closeFn);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeFn();
    });
    this._activeMap.escHandler = (event) => {
      if (event.key === "Escape") closeFn();
    };
    document.addEventListener("keydown", this._activeMap.escHandler);

    const body = modal.querySelector(".ns-map-body");
    const built = await this._buildMapSurface(body);
    if (!built || !this._activeMap || this._activeMap.modalEl !== modal) return;
    const L = built.leaflet;
    const map = built.map;
    this._activeMap.lmap = map;
    this._activeMap.haTiles = built.haTiles;
    this._activeMap.baseLayer = built.baseLayer;
    this._startTileTokenRefresh(this._activeMap);

    // Snap each stretch onto the rails when the network is available;
    // without it (the live map switched off, so no cached rail data)
    // fall back to a straight line between the stations.
    const railResult = NSReisadviesCard._railResult || await this._ensureRailReady();
    if (!this._activeMap || this._activeMap.modalEl !== modal) return;
    const drawn = [];
    runs.forEach(run => {
      const chords = run.map(s => [s.lat, s.lng]);
      let segments = null;
      if (railResult && run.length > 1) {
        try {
          segments = this._railSnapStopsWith(run, railResult.graph);
        } catch (err) {
          console.warn("[ns-reisadvies] disruption snap failed", err);
        }
      }
      (segments && segments.length ? segments : [chords]).forEach(seg => {
        if (seg.length > 1) drawn.push(seg);
      });
    });
    if (drawn.length) {
      L.polyline(drawn, { color: "#d32f2f", weight: 5, opacity: 0.9 }).addTo(map);
    }
    // The ends of each stretch get the bigger dot, not just the ends
    // of the list: with two stretches, both have two ends. And a
    // station both stretches name gets one marker, not two on top of
    // each other.
    const key = (stop) => `${stop.lat},${stop.lng}`;
    const ends = new Set();
    runs.forEach(run => {
      ends.add(key(run[0]));
      ends.add(key(run[run.length - 1]));
    });
    const seen = new Set();
    const marked = stops.filter(stop => {
      if (seen.has(key(stop))) return false;
      seen.add(key(stop));
      return true;
    });
    const points = marked.map(s => [s.lat, s.lng]);
    marked.forEach((stop) => {
      const endpoint = ends.has(key(stop));
      const marker = L.marker([stop.lat, stop.lng], {
        icon: L.divIcon({
          className: "ns-leaflet-stop-wrap",
          html: `<div class="ns-leaflet-stop${endpoint ? " endpoint" : ""}"></div>`,
          iconSize: endpoint ? [18, 18] : [14, 14],
          iconAnchor: endpoint ? [9, 9] : [7, 7],
        }),
        title: stop.name,
      }).addTo(map);
      marker.bindTooltip(stop.name, { direction: "top", offset: [0, -8] });
    });
    map.fitBounds(points, { padding: [40, 40], maxZoom: 13 });
    setTimeout(() => map.invalidateSize(), 200);
  }
}


// Only what a disruptions card has to decide: which kinds to show and
// how much of the country counts.
class NSReisadviesDisruptionsEditor extends HTMLElement {
  setConfig(config) { if (config) this._config = config; }

  set hass(hass) {
    this._hass = hass;
    if (!this._rendered && this._config) {
      this._rendered = true;
      this.render();
    }
  }

  render() {
    if (!this._hass || !this._config) return;
    const cfg = this._config;
    const types = Array.isArray(cfg.types) && cfg.types.length
      ? cfg.types
      : ["DISRUPTION", "CALAMITY"];
    const scope = cfg.scope || "all";
    const chip = (code) => `
      <button class="chip ${types.includes(code) ? "on" : ""}" data-type="${code}"
              type="button">${t(`disruptions_kind_${code}`, this._hass)}</button>`;
    const scopeChip = (value, label) => `
      <button class="chip ${scope === value ? "on" : ""}" data-scope="${value}"
              type="button">${label}</button>`;

    this.innerHTML = `
      <style>
        .ns-ed { padding: 10px; }
        .ns-ed h3 { margin: 18px 0 8px 0; font-size: 1.05em; }
        .ns-ed .chips { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }
        .ns-ed .chip { padding: 6px 10px; font-size: 0.85em; font-family: inherit;
          border-radius: 999px; border: 1px solid var(--divider-color);
          background: var(--card-background-color); color: var(--secondary-text-color);
          cursor: pointer; }
        .ns-ed .chip.on { background: #FFC917; color: #003082; border-color: #FFC917;
          font-weight: 700; }
        .ns-ed .hint { color: var(--secondary-text-color); font-size: 0.85em;
          margin-bottom: 10px; }
        .ns-ed .field { width: 100%; box-sizing: border-box; padding: 10px;
          background: var(--card-background-color); color: inherit;
          border: 1px solid var(--divider-color); border-radius: 6px; }
      </style>
      <div class="ns-ed">
        <ha-textfield label="${t("editor_title", this._hass)}" id="title"
                      style="width:100%; margin-bottom:16px;"></ha-textfield>
        <h3>${t("disruptions_kinds", this._hass)}</h3>
        <div class="chips">
          ${chip("DISRUPTION")}${chip("MAINTENANCE")}${chip("CALAMITY")}
        </div>
        <h3>${t("disruptions_scope", this._hass)}</h3>
        <div class="chips">
          ${scopeChip("all", t("disruptions_scope_all", this._hass))}
          ${scopeChip("routes", t("disruptions_scope_routes", this._hass))}
          ${scopeChip("stations", t("disruptions_scope_stations", this._hass))}
        </div>
        ${scope === "stations" ? `
          <div class="hint">${t("disruptions_stations_hint", this._hass)}</div>
          <input class="field" type="text" id="stations"
                 value="${(cfg.stations || []).join(", ")}">` : ""}
      </div>`;

    const titleField = this.querySelector("#title");
    if (titleField) {
      titleField.value = cfg.title || "NS Storingen";
      titleField.addEventListener("change", (ev) => this._fire({ title: ev.target.value }));
    }
    this.querySelectorAll(".chip[data-type]").forEach(button => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        const code = button.getAttribute("data-type");
        const next = types.includes(code)
          ? types.filter(other => other !== code)
          : types.concat([code]);
        // Showing nothing at all is never what anyone meant.
        this._fire({ types: next.length ? next : [code] });
        this.render();
      });
    });
    this.querySelectorAll(".chip[data-scope]").forEach(button => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        this._fire({ scope: button.getAttribute("data-scope") });
        this.render();
      });
    });
    const stations = this.querySelector("#stations");
    if (stations) {
      stations.addEventListener("change", (ev) => {
        this._fire({
          stations: ev.target.value.split(",").map(s => s.trim()).filter(Boolean),
        });
      });
    }
  }

  _fire(obj) {
    const newConfig = { ...this._config, ...obj };
    this._config = newConfig;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: newConfig } }));
  }
}

// Registration — HA 2026.5.0+ runs Lovelace resource modules during a
// View Transition. Calling customElements.define inside a transition
// can silently no-op (the registry change is rolled back when the
// transition aborts, and HA's frontend sometimes aborts these). To
// survive that, we attempt registration multiple times: synchronously
// here, then on document-ready, then as a microtask, plus a few
// retries on a timer. Each attempt is guarded so a successful prior
// define is never re-thrown into a real error.
const _NSRegister = () => {
  if (!customElements.get("ns-reisadvies-editor")) {
    try { customElements.define("ns-reisadvies-editor", NSReisadviesEditor); } catch (e) {
      if (!(e instanceof DOMException)) console.error("ns-reisadvies-editor define failed:", e);
    }
  }
  if (!customElements.get("ns-reisadvies-card")) {
    try { customElements.define("ns-reisadvies-card", NSReisadviesCard); } catch (e) {
      if (!(e instanceof DOMException)) console.error("ns-reisadvies-card define failed:", e);
    }
  }
  if (!customElements.get("ns-reisadvies-search-editor")) {
    try { customElements.define("ns-reisadvies-search-editor", NSReisadviesSearchEditor); } catch (e) {
      if (!(e instanceof DOMException)) console.error("ns-reisadvies-search-editor define failed:", e);
    }
  }
  if (!customElements.get("ns-reisadvies-disruptions-editor")) {
    try { customElements.define("ns-reisadvies-disruptions-editor", NSReisadviesDisruptionsEditor); } catch (e) {
      if (!(e instanceof DOMException)) console.error("ns-reisadvies-disruptions-editor define failed:", e);
    }
  }
  if (!customElements.get("ns-reisadvies-disruptions-card")) {
    try { customElements.define("ns-reisadvies-disruptions-card", NSReisadviesDisruptionsCard); } catch (e) {
      if (!(e instanceof DOMException)) console.error("ns-reisadvies-disruptions-card define failed:", e);
    }
  }
  if (!customElements.get("ns-reisadvies-search-card")) {
    try { customElements.define("ns-reisadvies-search-card", NSReisadviesSearchCard); } catch (e) {
      if (!(e instanceof DOMException)) console.error("ns-reisadvies-search-card define failed:", e);
    }
  }
};
_NSRegister();
if (typeof queueMicrotask === "function") queueMicrotask(_NSRegister);
if (document.readyState !== "complete") {
  document.addEventListener("readystatechange", _NSRegister);
  window.addEventListener("load", _NSRegister, { once: true });
}
// HA's frontend aborts View Transitions after a brief delay — retry
// shortly after to make sure registration actually sticks.
setTimeout(_NSRegister, 50);
setTimeout(_NSRegister, 250);
setTimeout(_NSRegister, 1000);
setTimeout(_NSRegister, 3000);

// Register the card with Home Assistant so it shows up in the
// "Add card" picker. Without this entry the JS file still loads,
// but the picker has no idea the card exists.
window.customCards = window.customCards || [];
window.customCards.push({
  type: "ns-reisadvies-card",
  name: "NS Reisadvies",
  description: "NS travel advice with favourites and automatic time slots",
  preview: false,
  documentationURL: "https://github.com/Meppies/ha-ns-reisadvies",
});

window.customCards.push({
  type: "ns-reisadvies-disruptions-card",
  name: "NS Reisadvies — disruptions",
  description: "NS disruptions, engineering works and calamities, with the affected stretch on a map",
  preview: false,
  documentationURL: "https://github.com/Meppies/ha-ns-reisadvies",
});

window.customCards.push({
  type: "ns-reisadvies-search-card",
  name: "NS Reisadvies — search",
  description: "Look up a journey on the spot, without configuring a route",
  preview: false,
  documentationURL: "https://github.com/Meppies/ha-ns-reisadvies",
});

console.info(
  "%c NS-REISADVIES-CARD %c v2.25.1 ",
  "color: white; background: #003082; font-weight: 700;",
  "color: #003082; background: #FFC917; font-weight: 700;"
);
