# NS Reisadvies

Live NS-reisadvies in Home Assistant. Eén hub-integratie met willekeurig
veel routes als sub-entries; één sensor per route met aankomende ritten,
vertragingen, sporen, drukte, overstappen en treinsamenstelling. Inclusief
een eigen Lovelace-kaart met favorieten, automatische tijdslots en een
opt-in live trein-kaart die de echte GPS-positie laat zien op de
spoorkaart.

## Wat krijg je

- **Eén hub, oneindig veel routes** — vul je API key één keer in, voeg
  routes toe als sub-entries (Hilversum→Duivendrecht, Aachen Hbf→
  Hilversum, ...). Elke route is één sensor.
- **689 stations** (NL, B, D, F, GB) met type-to-filter combobox.
- **Configureerbaar refresh-interval** (1–60 min).
- **Favorieten** ("hartjes") die een HA-restart overleven; instelbare
  bewaartijd (server-side TTL).
- **Automatische tijdslots** per dag-van-de-week — pin de trein die
  rond een gewenste vertrektijd vertrekt automatisch.
- **Treinsamenstelling** (opt-in): aantal bakken, materieel-type,
  plaatjes van het materieel per traject.
- **Live trein-kaart** (opt-in): klein kaart-icoontje per traject opent
  een modal met echte GPS-positie (ProRail OBIS, zelfde bron als
  treinposities.nl), het volledige spoorwegnetwerk als basislaag, en de
  route gesplitst in geel (al gereden) en blauw (nog te gaan) op de
  echte rails.
- **Check-out / check-in hint** tussen trajecten met operator-wissel.
- **Lovelace-kaart automatisch geregistreerd** — geen handmatig
  `resources:` editen.

## Wat heb je nodig

- Een gratis NS API key via <https://apiportal.ns.nl/> (subscription
  *Ns-App*).

## Configuratie

`Instellingen → Apparaten & services → Integratie toevoegen → NS Reisadvies`.

Vul je API key, vertrekstation en aankomststation in. Voeg meer routes
toe via de *Add route* knop op de integratie-tegel. Globale opties
(scan-interval, favorieten-TTL, treinsamenstelling, live-kaart) staan
onder *Configureer* op de hub.

## Lovelace-kaart toevoegen

`Add card → Custom: NS Reisadvies`. Selecteer de juiste `sensor.ns_*`
en klaar. De kaart-editor laat je het aantal ritten, de schaal en de
auto-favoriet tijdslots instellen.

## Quality scale

Deze integratie verklaart `platinum` in de manifest — full async,
DataUpdateCoordinator polling, graceful degradation bij API-outages,
type-hints, en pytest test-coverage voor de config-flow, de sensor en
de migration.

## Issues / feature requests

<https://github.com/Meppies/ha-ns-reisadvies/issues>
