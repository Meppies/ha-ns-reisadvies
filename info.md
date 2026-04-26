# NS Reisadvies

Live NS-reisadvies in Home Assistant. Eén sensor per route met aankomende
ritten, vertragingen, sporen, drukte en overstappen. Inclusief een eigen
Lovelace-kaart met favorieten en automatische tijdslots.

## Wat krijg je

- Eén sensor per van/naar combinatie.
- Configureerbaar refresh-interval (1–60 minuten).
- Favorieten die een HA-restart overleven, met instelbare bewaartijd
  (server-side TTL).
- Lovelace-kaart die automatisch geregistreerd wordt onder
  `Custom: NS Reisadvies` in de card-picker.

## Wat heb je nodig

- Een gratis NS API key via <https://apiportal.ns.nl/> (subscription `NsApp`).

## Configuratie

`Instellingen → Apparaten & services → Integratie toevoegen → NS Reisadvies`.
Vul je API key, vertrekstation en aankomststation in. Opties zoals interval
en bewaartijd staan onder *Configureer* op de integratie-tegel.

## Issues / feature requests

<https://github.com/Meppies/ha-ns-reisadvies/issues>
