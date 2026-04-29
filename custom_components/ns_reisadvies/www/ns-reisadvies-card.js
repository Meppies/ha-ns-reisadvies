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
    stop_arrival_short: "A",
    stop_departure_short: "D",
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
    stop_arrival_short: "A",
    stop_departure_short: "V",
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

    if (this._config && this._config.entity) {
      this.updateContent();
    }
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
        .tl-travel-info { padding: 4px 0 12px 12px; font-size: 0.9em; }
        .tl-direction-main { color: #FFC917; font-weight: bold; font-size: 1.05em; display: block; margin-bottom: 4px; }
        .tl-train-details { color: var(--secondary-text-color); display: flex; align-items: center; flex-wrap: wrap; }
        .detail-separator { margin: 0 6px; opacity: 0.5; font-size: 0.8em; }
        .tl-train-meta { font-size: 0.85em; color: var(--secondary-text-color); margin-top: 4px; opacity: 0.8; }
        .tl-wait-row { display: grid; grid-template-columns: 75px 25px 1fr; height: 30px; align-items: center; }
        .tl-wait-line-col { display: flex; justify-content: center; }
        .tl-wait-text { padding-left: 12px; color: var(--secondary-text-color); font-style: italic; font-size: 0.9em; display: flex; align-items: center; }
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
      </style>
      <div class="ns-container">`;

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

        html += `
          <div class="tl-grid">
            <div><div class="tl-time ${cCls}">${tDep}</div>${dDep}</div>
            <div class="tl-line-col"><div class="tl-dot ${index === 0 ? "tl-dot-fill" : ""}"></div><div class="tl-line"></div></div>
            <div class="tl-info"><div class="tl-station-header"><span class="tl-station-name ${cCls}">${leg.origin.name || unknownLabel}</span>
            <span class="${pCls} ${cCls}">${platformLabel} ${leg.origin.actualTrack || leg.origin.plannedTrack || "?"}</span></div></div>
          </div>
          <div class="tl-grid">
            <div class="tl-duration-small ${cCls}">${legDur}</div>
            <div class="tl-line-col"><div class="tl-line"></div></div>
            <div class="tl-travel-info ${cCls}"><span class="tl-direction-main ${cCls}">${leg.direction || unknownLabel}</span>
              <div class="tl-train-details">${sText}<span class="detail-separator">•</span>
              <ha-icon icon="${this.getIcon(leg.product)}" style="--mdc-icon-size:16px; margin-right:4px;"></ha-icon>${(leg.product && leg.product.displayName) || unknownLabel}
              <span class="detail-separator">•</span>${this.getCrowd(leg.crowdForecast)}</div>
              <div class="tl-train-meta">${leg.name || unknownLabel}</div>
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
    const entities = Object.keys(this._hass.states).filter(e => e.startsWith("sensor.ns_")).sort();
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

// Idempotent registration — the integration auto-registers this script
// via add_extra_js_url, but a user might also have it pinned manually
// under Settings → Dashboards → Resources. Guarding the define() calls
// prevents the "already defined" error in that case.
if (!customElements.get("ns-reisadvies-editor")) {
  customElements.define("ns-reisadvies-editor", NSReisadviesEditor);
}
if (!customElements.get("ns-reisadvies-card")) {
  customElements.define("ns-reisadvies-card", NSReisadviesCard);
}

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
  "%c NS-REISADVIES-CARD %c v1.5.2 ",
  "color: white; background: #003082; font-weight: 700;",
  "color: #003082; background: #FFC917; font-weight: 700;"
);
