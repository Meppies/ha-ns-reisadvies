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
    weekdays: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"],
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
    weekdays: ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"],
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
    return d.toLocaleTimeString([], opts);
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

    if (!this._config.entity) {
      this.content.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--primary-text-color);"><b>NS Reisadvies</b><br><br>${t("select_sensor", this._hass)}</div>`;
      return;
    }

    const stateObj = this._hass.states[this._config.entity];
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

    const tripsToShow = allTrips.filter((trip, index) => {
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
        .stop-row .stop-line-col { display: flex; justify-content: center; align-self: stretch; }
        .stop-row .stop-line-col::before { content: ""; width: 0; border-left: 2px dashed #3b82f6; height: 100%; }
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
          <div class="fav-heart ${isFav ? "heart-red" : "heart-grey"}" data-idx="${tIdx}" data-ctx="${ctx || ""}" data-fav="${isFav}">
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
        const stopLabel = sCount === 1 ? t("stop_one", this._hass) : t("stop_other", this._hass, { n: sCount });
        const toggleLabel = isExpanded ? t("hide_stops", this._hass) : t("show_stops", this._hass);
        const sText = sCount <= 0
          ? `<span class="direct-text">${t("direct", this._hass)}</span>`
          : `<span>${stopLabel}</span><span class="stops-toggle ${isExpanded ? "open" : ""}" data-leg-key="${legKey}" title="${toggleLabel}" role="button"><ha-icon icon="mdi:chevron-down"></ha-icon></span>`;

        const trainNum = (leg.product && leg.product.number) ? String(leg.product.number) : "";
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
        const mapIconHtml = showMapIcon
          ? `<div class="tl-map-icon-row"><button class="tl-map-icon-btn" data-trip-idx="${tIdx}" data-leg-idx="${index}" title="${t("show_live_map", this._hass)}"><ha-icon icon="mdi:map-marker-radius-outline"></ha-icon><span>${t("live_map_button", this._hass)}</span></button></div>`
          : "";

        html += `
          <div class="tl-grid">
            <div><div class="tl-time ${cCls}">${tDep}</div>${dDep}</div>
            <div class="tl-line-col"><div class="tl-dot ${index === 0 ? "tl-dot-fill" : ""}"></div><div class="tl-line"></div></div>
            <div class="tl-info"><div class="tl-station-header"><span class="tl-station-name ${cCls}">${leg.origin.name || unknownLabel}</span>
            <span class="${pCls} ${cCls}">${platformLabel} ${leg.origin.actualTrack || leg.origin.plannedTrack || "?"}</span></div>${mapIconHtml}</div>
          </div>
          <div class="tl-grid">
            <div class="tl-duration-small ${cCls}">${legDur}</div>
            <div class="tl-line-col"><div class="tl-line"></div></div>
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

            const rowCls = stop.cancelled ? "stop-row cancelled" : "stop-row";
            html += `<div class="${rowCls}">
              <div class="stop-time-cell">${timeHtml}</div>
              <div class="stop-line-col"></div>
              <div class="stop-info"><span class="stop-name">${stop.name || unknownLabel}</span>${platformHtml}</div>
            </div>`;
          });
        }

        html += `
          <div class="tl-grid">
            <div><div class="tl-time ${cCls}">${tArr}</div>${dArr}</div>
            <div class="tl-line-col"><div class="tl-dot ${index === trip.legs.length - 1 ? "tl-dot-fill" : ""}"></div></div>
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
        console.info("[ns-reisadvies] live map click", {tIdx, lIdx});
        try {
          this.openLiveMap(tIdx, lIdx);
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

  _ensureModalStyles() {
    // The modal lives at document.body — outside any card shadow root —
    // so the in-card <style> block does NOT apply to it. Inject once.
    if (document.getElementById("ns-reisadvies-modal-styles")) return;
    const style = document.createElement("style");
    style.id = "ns-reisadvies-modal-styles";
    style.textContent = `
      .ns-map-modal {
        position: fixed; inset: 0; z-index: 9999;
        background: rgba(0, 0, 0, 0.55);
        display: flex; align-items: center; justify-content: center;
        backdrop-filter: blur(2px);
      }
      .ns-map-modal .ns-map-card {
        background: var(--card-background-color, #1a1a1a);
        color: var(--primary-text-color, white);
        border-radius: 12px;
        box-shadow: 0 12px 40px rgba(0,0,0,0.5);
        width: min(720px, 92vw); height: min(640px, 86vh);
        display: flex; flex-direction: column; overflow: hidden;
      }
      .ns-map-modal .ns-map-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 10px 14px; border-bottom: 1px solid var(--divider-color, #444);
      }
      .ns-map-modal .ns-map-title {
        font-weight: 600; font-size: 1em; display: flex; align-items: center; gap: 8px;
      }
      .ns-map-modal .ns-map-title .ns-map-train { color: #FF6B00; }
      .ns-map-modal .ns-map-meta { font-size: 0.78em; opacity: 0.75; margin-left: 8px; font-weight: 400; }
      .ns-map-modal .ns-map-close {
        cursor: pointer; padding: 4px; border-radius: 50%; display: inline-flex;
      }
      .ns-map-modal .ns-map-close:hover { background: rgba(255,255,255,0.08); }
      .ns-map-modal .ns-map-body {
        flex: 1; min-height: 0; position: relative; background: var(--card-background-color, #1a1a1a);
      }
      .ns-map-modal .ns-leaflet {
        position: absolute; inset: 0; width: 100%; height: 100%;
        background: #1a1a1a;
      }
      .ns-map-modal .leaflet-container {
        background: #1a1a1a; font-family: inherit;
      }
      /* Side-view train tile, rotated to match the train's heading. */
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
        background: #1a1a1a; border: 3px solid #FFC917;
        box-shadow: 0 1px 3px rgba(0,0,0,0.4);
      }
      .ns-leaflet-stop.endpoint { width: 18px; height: 18px; border-width: 4px; }
      .ns-map-modal .ns-map-loading {
        position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
        font-size: 0.9em; opacity: 0.7;
      }
      .ns-map-modal .ns-map-empty {
        position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
        padding: 20px; text-align: center; font-size: 0.95em;
        color: var(--secondary-text-color, #aaa);
      }
    `;
    document.head.appendChild(style);
  }

  async openLiveMap(tripIdx, legIdx) {
    if (!this._hass || !this._config) return;
    this._ensureModalStyles();
    const stateObj = this._hass.states[this._config.entity];
    const trips = stateObj && stateObj.attributes && stateObj.attributes.trips || [];
    const trip = trips[tripIdx];
    const leg = trip && trip.legs && trip.legs[legIdx];
    if (!leg) return;
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
    document.body.appendChild(modal);
    this._activeMap = {
      modalEl: modal, sessionId: null, pollHandle: null,
      tripIdx, legIdx,
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

  async _ensureLeafletLoaded() {
    // Use Leaflet directly (same library HA uses internally) — gives us
    // full control over markers, polylines, and bounds without ha-map's
    // entity-machine quirks. We load from unpkg with the same pin that
    // HA frontend uses, so users on the same machine often hit cache.
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
        link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
        link.integrity = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=";
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
    // v2.15.4: store leg.product on the active-map context so
    // _applyMapData (called repeatedly from polling + interpolation)
    // can read shortCategoryName without needing leg in scope. The
    // earlier parentNode crash hid this latent ReferenceError.
    this._activeMap.legProduct = leg.product || null;
    // Prefer real GPS (ProRail OBIS via ArcGIS) when the backend
    // returns a position; fall back to wall-clock interpolation when
    // the ArcGIS feed has no recent fix for this train (briefly during
    // station dwells, or for trains without OBIS reporting).
    const trainPos = resp.train_position || this._interpolateTrainPos();
    if (!trainPos && stopsWithCoord.length === 0) {
      this._renderMapEmpty(modal);
      return;
    }

    const ok = await this._ensureLeafletLoaded();
    if (!this._activeMap || this._activeMap.modalEl !== modal) return;
    if (!ok) {
      this._renderMapEmpty(modal, "Leaflet failed to load");
      return;
    }

    const L = window.L;
    body.innerHTML = "";
    const mapDiv = document.createElement("div");
    mapDiv.className = "ns-leaflet";
    body.appendChild(mapDiv);

    const map = L.map(mapDiv, {
      zoomControl: true,
      attributionControl: true,
    });

    // Carto dark basemap — matches HA's default look.
    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: "abcd",
        maxZoom: 19,
      }
    ).addTo(map);

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

      // Build full-NL graph once. 4-decimal precision (~11 m) auto-
      // merges junction endpoints from neighbouring rail features.
      const graph = new Map();
      const nodeCoords = new Map();
      const k = c => `${c[0].toFixed(4)},${c[1].toFixed(4)}`;
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

      const result = {
        railPolylines,
        graph: { graph, nodeCoords, haversine },
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
    const layer = window.L.polyline(r.railPolylines, {
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
    const stateObj = this._hass.states[this._config.entity];
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

  // Snap a [lat,lng] to the K nearest rail-graph nodes. Returning a
  // ranked list lets us retry with the second-best candidate when
  // the closest one happens to land on a disconnected sub-graph
  // (rangeer-spoor, freight-only branch, etc).
  _railSnapCandidatesWith(g, point, k = 3, maxDist = 2000) {
    if (!g) return [];
    const out = [];
    for (const [key, c] of g.nodeCoords) {
      const d = g.haversine(point, c);
      if (d > maxDist) continue;
      out.push({ key, dist: d });
    }
    out.sort((a, b) => a.dist - b.dist);
    return out.slice(0, k);
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
      // Try larger snap distances and more candidates so isolated
      // sub-graphs don't kill the route.
      const candA = this._railSnapCandidatesWith(g, [a.lat, a.lng], 5, 5000);
      const candB = this._railSnapCandidatesWith(g, [b.lat, b.lng], 5, 5000);
      let bestPath = null;
      let bestPathSnaps = null;
      let triedCount = 0;
      outer:
      for (const sa of candA) {
        for (const sb of candB) {
          triedCount++;
          const path = this._railPathWith(g, sa.key, sb.key);
          if (path && path.length >= 2) {
            bestPath = path;
            bestPathSnaps = { sa, sb };
            break outer;
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
      console.info(
        `[ns-reisadvies] rail-snap ${a.name} → ${b.name}: `
        + `${bestPath.length} pts, snap A=${bestPathSnaps.sa.dist.toFixed(0)}m B=${bestPathSnaps.sb.dist.toFixed(0)}m`
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

    // First-time fit to all points (stops + train).
    if (!ctx.fitDone) {
      const allLatLngs = stops.map(s => [s.lat, s.lng]);
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
      const trips = this._hass.states[this._config.entity]?.attributes?.trips || [];
      const leg = trips[ctx.tripIdx]?.legs?.[ctx.legIdx];
      if (leg && Array.isArray(leg.stops)) {
        ctx.legStopsRaw = leg.stops.filter(s => !s.passing);
      }
    }

    let interp = this._interpolateTrainPos();
    try {
      const resp = await this._hass.callWS({
        type: "ns_reisadvies/track_train_poll",
        session_id: ctx.sessionId,
      });
      const real = resp && resp.train_position;
      const pos = real || interp;
      this._applyMapData(pos, resp && resp.journey_stops);
      this._updatePosLabel(pos);
    } catch (err) {
      console.warn("ns_reisadvies live map poll failed", err);
      if (interp) {
        this._applyMapData(interp);
        this._updatePosLabel(interp);
      }
    }
  }

  // Compute the train's position from leg.stops + wall clock. Only
  // actualDepartureDateTime counts as proof a train has left a stop —
  // planned times are not enough, because NS confirms departures as
  // they happen and a delay must NOT be turned into the marker
  // teleporting forward. If we have no actualDeparture for the current
  // stop, the train is still there.
  _interpolateTrainPos() {
    const ctx = this._activeMap;
    if (!ctx) return null;
    const stops = (ctx.legStopsRaw || []).filter(s => s.lat != null && s.lng != null);
    if (stops.length < 2) return null;
    const now = Date.now();
    const stamp = (s, k) => {
      const v = s && s[k];
      if (!v) return null;
      const d = Date.parse(v);
      return Number.isFinite(d) ? d : null;
    };

    // Find the LAST stop whose ACTUAL departure has happened. That's
    // where the train confirmedly left from. Anything before then is
    // history; anything after is speculation.
    let lastDepartedIdx = -1;
    for (let i = 0; i < stops.length; i++) {
      const ad = stamp(stops[i], "actualDepartureDateTime");
      if (ad != null && ad <= now) lastDepartedIdx = i;
    }

    if (lastDepartedIdx < 0) {
      // Train has not been confirmed to leave any stop yet. Place it
      // at the first stop whose actual ARRIVAL is in the past (just
      // arrived at origin) — otherwise at origin.
      let arrivedIdx = -1;
      for (let i = 0; i < stops.length; i++) {
        const aa = stamp(stops[i], "actualArrivalDateTime");
        if (aa != null && aa <= now) arrivedIdx = i;
      }
      const o = stops[Math.max(0, arrivedIdx)];
      return { lat: o.lat, lng: o.lng, station_name: o.name, source: "at-origin" };
    }

    if (lastDepartedIdx >= stops.length - 1) {
      // Past the final stop — pin at destination.
      const e = stops[stops.length - 1];
      return { lat: e.lat, lng: e.lng, station_name: e.name, source: "arrived" };
    }

    const a = stops[lastDepartedIdx];
    const b = stops[lastDepartedIdx + 1];
    // Has the train confirmedly arrived at `b` already? If yes, the
    // train is dwelling AT `b` (waiting to depart).
    const bActArr = stamp(b, "actualArrivalDateTime");
    if (bActArr != null && bActArr <= now) {
      return { lat: b.lat, lng: b.lng, station_name: b.name, source: "at-stop" };
    }

    // Still en-route between a and b. Interpolate along the chord
    // using actual departure of `a` and the (planned-if-no-actual)
    // arrival of `b`.
    const aActDep = stamp(a, "actualDepartureDateTime");
    const bArr = stamp(b, "plannedArrivalDateTime") ?? bActArr;
    if (aActDep == null || bArr == null || bArr <= aActDep) {
      return { lat: a.lat, lng: a.lng, station_name: a.name, source: "just-departed" };
    }
    const frac = Math.max(0, Math.min(1, (now - aActDep) / (bArr - aActDep)));
    return {
      lat: a.lat + (b.lat - a.lat) * frac,
      lng: a.lng + (b.lng - a.lng) * frac,
      station_name: `${a.name} → ${b.name}`,
      source: "interpolated",
      frac,
    };
  }

  closeLiveMap() {
    const ctx = this._activeMap;
    if (!ctx) return;
    this._activeMap = null;
    if (ctx.pollHandle) clearInterval(ctx.pollHandle);
    if (ctx.escHandler) document.removeEventListener("keydown", ctx.escHandler);
    if (ctx.sessionId && this._hass) {
      this._hass.callWS({
        type: "ns_reisadvies/track_train_stop",
        session_id: ctx.sessionId,
      }).catch(() => {});
    }
    // Tear down the Leaflet map so its DOM listeners and tile downloads
    // do not linger.
    if (ctx.lmap) {
      try { ctx.lmap.remove(); } catch {}
    }
    if (ctx.modalEl && ctx.modalEl.parentNode) {
      ctx.modalEl.parentNode.removeChild(ctx.modalEl);
    }
  }

  disconnectedCallback() {
    this.closeLiveMap();
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

console.info(
  "%c NS-REISADVIES-CARD %c v2.15.4 ",
  "color: white; background: #003082; font-weight: 700;",
  "color: #003082; background: #FFC917; font-weight: 700;"
);
