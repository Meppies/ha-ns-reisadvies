"""Config and options flow for the NS Reisadvies integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_FROM_STATION,
    CONF_TO_STATION,
    CONF_SCAN_INTERVAL,
    CONF_FAV_HOURS,
    CONF_FETCH_COMPOSITION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_FAV_HOURS,
    DEFAULT_FETCH_COMPOSITION,
)

_LOGGER = logging.getLogger(__name__)

# Hard-coded list of Dutch railway stations (deduplicated, alphabetical).
# Long-term this would be better generated from the NS stations API,
# but a static list keeps the config flow free of network calls.
_RAW_STATIONS = [
    "'t Harde", "Aalten", "Abcoude", "Akkrum", "Alkmaar", "Alkmaar Noord", "Almelo", "Almelo de Riet",
    "Almere Buiten", "Almere Centrum", "Almere Muziekwijk", "Almere Oostvaarders", "Almere Parkwijk", "Almere Poort",
    "Alphen a/d Rijn", "Amersfoort Centraal", "Amersfoort Schothorst", "Amersfoort Vathorst", "Amstelveen",
    "Amsterdam Amstel", "Amsterdam Arena", "Amsterdam Bijlmer Arena", "Amsterdam Centraal", "Amsterdam Holendrecht",
    "Amsterdam Lelylaan", "Amsterdam Muiderpoort", "Amsterdam RAI", "Amsterdam Science Park", "Amsterdam Sloterdijk",
    "Amsterdam Zuid", "Anna Paulowna", "Apeldoorn", "Apeldoorn De Maten", "Apeldoorn Osseveld", "Appingedam",
    "Arnemuiden", "Arnhem Centraal", "Arnhem Presikhaaf", "Arnhem Velperpoort", "Arnhem Zuid", "Assen",
    "Baarn", "Baflo", "Barendrecht", "Barneveld Centrum", "Barneveld Noord", "Barneveld Zuid", "Bedum",
    "Beek-Elsloo", "Beesd", "Beilen", "Bergen op Zoom", "Best", "Beverwijk", "Bilthoven", "Blerick",
    "Bloemendaal", "Bodegraven", "Borne", "Boskoop", "Boskoop Snijdelwijk", "Bovenkarspel Flora",
    "Bovenkarspel-Grootebroek", "Boxmeer", "Boxtel", "Breda", "Breda-Prinsenbeek", "Breukelen", "Brouwhuis",
    "Buitenpost", "Bunde", "Bunnik", "Bussum Zuid", "Capelle Schollevaar", "Castricum",
    "Chevremont", "Coevorden", "Cuijk", "Culemborg", "Daarlerveen", "Dalen", "Dalfsen", "De Vink",
    "De Westereen", "Deinum", "Delden", "Delft", "Delft Campus", "Delfzijl", "Delfzijl West", "Den Dolder",
    "Den Haag Centraal", "Den Haag HS", "Den Haag Laan v NOI", "Den Haag Mariahoeve", "Den Haag Moerwijk",
    "Den Haag Ypenburg", "Den Helder", "Den Helder Zuid", "Deurne", "Deventer", "Deventer Colmschate",
    "Didam", "Diemen", "Diemen Zuid", "Dieren", "Doetinchem", "Doetinchem De Huet", "Dordrecht",
    "Dordrecht Stadspolders", "Dordrecht Zuid", "Driebergen-Zeist", "Driehuis", "Dronten", "Dronryp",
    "Duiven", "Duivendrecht", "Echt", "Ede Centrum", "Ede-Wageningen", "Eemshaven", "Eijsden",
    "Eindhoven Centraal", "Eindhoven Strijp-S", "Elst", "Emmen", "Emmen Zuid", "Enkhuizen", "Enschede",
    "Enschede Kennispark", "Enschede De Eschmarke", "Ermelo", "Etten-Leur", "Eygelshoven", "Eygelshoven Markt",
    "Feanwalden", "Gaanderen", "Geldermalsen", "Geldrop", "Geleen Oost", "Geleen-Lutterade", "Gilze-Rijen",
    "Glanerbrug", "Goes", "Goor", "Gorinchem", "Gouda", "Gouda Goverwelle", "Gramsbergen", "Grijpskerk",
    "Groningen", "Groningen Europapark", "Groningen Noord", "Grou-Jirnsum", "Haarlem", "Haarlem Spaarnwoude",
    "Halfweg-Zwanenburg", "Hardenberg", "Harderwijk", "Hardinxveld Blauwe Zoom", "Hardinxveld-Giessendam",
    "Haren", "Harlingen", "Harlingen Haven", "Heemskerk", "Heemstede-Aerdenhout", "Heerenveen",
    "Heerenveen IJsstadion", "Heerhugowaard", "Heerlen", "Heerlen Woonboulevard", "Heeze", "Heiloo",
    "Heino", "Helmond", "Helmond Brandevoort", "Helmond 't Hout", "Helmond Brouwhuis", "Hemmen-Dodewaard",
    "Hengelo", "Hengelo Gezondheidspark", "Hengelo Oost", "Hillegom", "Hilversum", "Hilversum Media Park",
    "Hilversum Sportpark", "Hindeloopen", "Hoensbroek", "Hoevelaken", "Holten", "Hoofddorp", "Hoogeveen",
    "Hoogezand-Sappemeer", "Hoogkarspel", "Hoorn", "Hoorn Kersenboogerd", "Horst-Sevenum", "Houten",
    "Houten Castellum", "Houthem-St. Gerlach", "Hurdegaryp", "IJlst", "IJmuiden", "Kampen", "Kampen Zuid",
    "Kapelle-Biezelinge", "Kerkrade Centrum", "Kesteren", "Klarenbeek", "Klimmen-Ransdaal", "Koog aan de Zaan",
    "Koudum-Molkwerum", "Krabbendijke", "Krommenie-Assendelft", "Kropswolde", "Kruiningen-Yerseke",
    "Lansingerland-Zoetermeer", "Landgraaf", "Leerdam", "Leeuwarden", "Leeuwarden Camminghaburen", "Leiden Centraal",
    "Leiden Lammenschans", "Lelystad Centrum", "Lichtenvoorde-Groenlo", "Lochem", "Loppersum", "Lunteren",
    "Maarheeze", "Maarn", "Maarssen", "Maastricht", "Maastricht Noord", "Maastricht Randwyck", "Mantgum",
    "Marienberg", "Martenshoek", "Meerssen", "Meppel", "Middelburg", "Mook-Molenhoek", "Naarden-Bussum",
    "Nieuw Amsterdam", "Nieuw Vennep", "Nieuwerkerk a/d IJssel", "Nijkerk", "Nijmegen", "Nijmegen Dukenburg",
    "Nijmegen Goffert", "Nijmegen Heyendaal", "Nijmegen Lent", "Nijverdal", "Nunspeet", "Nuth", "Obdam",
    "Oisterwijk", "Oldenzaal", "Olst", "Ommen", "Oosterbeek", "Opheusden", "Oss", "Oss West", "Oudenbosch",
    "Overveen", "Purmerend", "Purmerend Overwhere", "Purmerend Weidevenne", "Putten", "Raalte", "Ravenstein",
    "Reuver", "Rheden", "Rhenen", "Rijssen", "Rilland-Bath", "Roermond", "Roodeschool", "Roosendaal",
    "Rosmalen", "Rotterdam Alexander", "Rotterdam Blaak", "Rotterdam Centraal", "Rotterdam Lombardijen",
    "Rotterdam Noord", "Rotterdam Stadion", "Rotterdam Zuid", "Ruurlo", "Santpoort Noord", "Santpoort Zuid",
    "Sappemeer Oost", "Sassenheim", "Sauwerd", "Schagen", "Scheemda", "Schiedam Centrum", "Schin op Geul",
    "Schinnen", "Schiphol Airport", "Sittard", "Sliedrecht", "Sliedrecht Baanhoek", "Sneek", "Sneek Noord",
    "Soest", "Soest Zuid", "Soestdijk", "Spaubeek", "Stavoren", "Stedum", "Steenwijk", "Stein", "Susteren",
    "Swalmen", "Tegelen", "Terborg", "Tiel", "Tiel Passewaaij", "Tilburg", "Tilburg Reeshof",
    "Tilburg Universiteit", "Twello", "Uitgeest", "Uithuizen", "Uithuizermeeden", "Utrecht Centraal",
    "Utrecht Leidsche Rijn", "Utrecht Lunetten", "Utrecht Maliebaan", "Utrecht Overvecht", "Utrecht Terwijde",
    "Utrecht Vaartsche Rijn", "Utrecht Zuilen", "Valkenburg", "Varsseveld", "Veendam", "Veenendaal Centrum",
    "Veenendaal West", "Veenendaal-De Klomp", "Velp", "Venlo", "Venray", "Vierlingsbeek", "Vleuten",
    "Vlissingen", "Vlissingen Souburg", "Voerendaal", "Voorburg", "Voorhout", "Voorschoten", "Voorst-Empe",
    "Vorden", "Vriezenveen", "Vroomshoop", "Vught", "Waddinxveen", "Waddinxveen Noord", "Waddinxveen Triangel",
    "Warffum", "Weert", "Weesp", "Wehl", "Westervoort", "Wezep", "Wierden", "Wijchen", "Wijhe", "Winschoten",
    "Winsum", "Winterswijk", "Winterswijk West", "Woerden", "Wolfheze", "Wolvega", "Workum", "Wormerveer",
    "Zaandam", "Zaandam Kogerveld", "Zaandijk Zaanse Schans", "Zaltbommel", "Zandvoort aan Zee", "Zetten-Andelst",
    "Zevenaar", "Zevenbergen", "Zoetermeer", "Zoetermeer Oost", "Zuidbroek", "Zuidhorn", "Zutphen", "Zwolle",
    "Zwolle Stadshagen", "Zwijndrecht",
]
STATIONS = sorted(set(_RAW_STATIONS))


def _primary_entry(hass) -> config_entries.ConfigEntry | None:
    """Lowest-id entry holds the canonical shared options."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return None
    return sorted(entries, key=lambda e: e.entry_id)[0]


class NSReisadviesOptionsFlowHandler(config_entries.OptionsFlow):
    """Edit integration-wide settings.

    Even though Home Assistant launches this flow on a specific entry,
    the values are stored on the *primary* entry (lowest id) and read
    back by every entry. So whether the user clicks Configure on route
    Hilversum→Duivendrecht or Emmen→Hilversum, they see and edit the
    same fields. Saving propagates to all routes via a reload.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.entry = config_entry

    async def async_step_init(self, user_input=None):
        primary = _primary_entry(self.hass) or self.entry

        if user_input is not None:
            # Sla globale opties op de primary entry op zodat alle andere
            # entries ze bij volgende setup kunnen lezen.
            self.hass.config_entries.async_update_entry(
                primary, options={**primary.options, **user_input}
            )
            # Reload de andere entries handmatig. De primary wordt door
            # de update_listener gereload, en self.entry door HA wanneer
            # we async_create_entry returnen.
            for e in self.hass.config_entries.async_entries(DOMAIN):
                if e.entry_id not in (primary.entry_id, self.entry.entry_id):
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(e.entry_id)
                    )
            # Eigen entry: schrijf user_input ook naar zijn options zodat
            # deze entry, mocht de primary verwijderd worden, zijn eigen
            # globalen kan leveren als fallback.
            return self.async_create_entry(title="", data=user_input)

        # Lees default-waarden uit primary (zodat alle entries dezelfde
        # getallen tonen). Fall back op eigen entry als primary leeg is.
        source = primary if (primary.options or primary.data) else self.entry
        opts = source.options
        data = source.data
        api_val = opts.get(CONF_API_KEY, data.get(CONF_API_KEY, ""))
        int_val = int(opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        fav_val = int(opts.get(CONF_FAV_HOURS, DEFAULT_FAV_HOURS))
        comp_val = bool(opts.get(CONF_FETCH_COMPOSITION, DEFAULT_FETCH_COMPOSITION))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_API_KEY, default=str(api_val)): str,
                vol.Required(
                    CONF_SCAN_INTERVAL, default=int_val
                ): vol.All(int, vol.Range(min=1, max=60)),
                vol.Required(
                    CONF_FAV_HOURS, default=fav_val
                ): vol.All(int, vol.Range(min=0, max=72)),
                vol.Required(CONF_FETCH_COMPOSITION, default=comp_val): bool,
            }),
        )


class NSReisadviesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NS Reisadvies."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return NSReisadviesOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Initial setup: ask for API key, departure and arrival station."""
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)

        # Re-use the API key across multiple route entries.
        stored_api_key = None
        for entry in existing_entries:
            if entry.data.get(CONF_API_KEY):
                stored_api_key = entry.data[CONF_API_KEY]
                break

        errors: dict[str, str] = {}

        if user_input is not None:
            raw_act = user_input.get(CONF_FROM_STATION) or ""
            raw_arr = user_input.get(CONF_TO_STATION) or ""
            new_act = raw_act.lower()
            new_arr = raw_arr.lower()

            # custom_value=True on the selector means the user can type
            # anything — validate against the canonical list here.
            station_lookup = {s.lower(): s for s in STATIONS}
            if new_act and new_act not in station_lookup:
                errors[CONF_FROM_STATION] = "unknown_station"
            if new_arr and new_arr not in station_lookup:
                errors[CONF_TO_STATION] = "unknown_station"

            if not errors and new_act and new_arr and new_act == new_arr:
                errors["base"] = "same_station"

            if not errors:
                # Normalise to the canonical casing from the list
                user_input[CONF_FROM_STATION] = station_lookup[new_act]
                user_input[CONF_TO_STATION] = station_lookup[new_arr]
                for entry in existing_entries:
                    existing_act = (entry.data.get(CONF_FROM_STATION, "") or "").lower()
                    existing_arr = (entry.data.get(CONF_TO_STATION, "") or "").lower()
                    if existing_act == new_act and existing_arr == new_arr:
                        return self.async_abort(reason="already_configured")

            if not errors:
                final_api_key = user_input.get(CONF_API_KEY, stored_api_key)
                return self.async_create_entry(
                    title=f"NS {user_input[CONF_FROM_STATION]} -> {user_input[CONF_TO_STATION]}",
                    data={
                        CONF_API_KEY: final_api_key,
                        CONF_FROM_STATION: user_input[CONF_FROM_STATION],
                        CONF_TO_STATION: user_input[CONF_TO_STATION],
                    },
                )

        schema: dict = {}
        if not stored_api_key:
            schema[vol.Required(CONF_API_KEY)] = str
        # IMPORTANT: ha-selector-select only renders ha-combo-box (with
        # type-to-filter) when custom_value=True. With custom_value=False
        # it falls back to the legacy ha-select (scroll-only Material
        # dropdown), regardless of mode=DROPDOWN. Allow custom values so
        # the user can type, and validate against STATIONS below.
        station_selector = SelectSelector(
            SelectSelectorConfig(
                options=STATIONS,
                mode=SelectSelectorMode.DROPDOWN,
                custom_value=True,
            )
        )
        schema[vol.Required(CONF_FROM_STATION)] = station_selector
        schema[vol.Required(CONF_TO_STATION)] = station_selector

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema),
            errors=errors,
        )
