# Setup — van deze folder naar een werkende HACS-integratie

Deze folder is een complete, HACS-compatibele Home Assistant integratie. Hij
is bedoeld als de inhoud van een **eigen, dedicated GitHub-repo**, los van
`fun-things-to-share`. HACS pakt monorepo's niet goed; daarom is deze
splitsing nodig.

## 1. Nieuwe GitHub-repo aanmaken

Op <https://github.com/new>:

- Naam: `ha-ns-reisadvies` (suggestie — `ha-` prefix is HACS-conventie)
- Public
- Geen README/LICENSE/.gitignore — die staan al klaar in deze folder
- *Create repository*

## 2. Inhoud pushen

```bash
cd ~/Documents/Claude-Cowork/ns-reisadvies-hacs
git init
git add .
git commit -m "Initial release: NS Reisadvies HA integration"
git branch -M main
git remote add origin https://github.com/Meppies/ha-ns-reisadvies.git
git push -u origin main
```

## 3. Eigen icoontje plaatsen

Vervang de placeholder `icon.png` (256×256) en `icon@2x.png` (512×512) op
**twee** plekken:

- `custom_components/ns_reisadvies/icon.png` (en `icon@2x.png`) — gebruikt
  door HACS in zijn lijst.
- `icon.png` op repo-root — gebruikt door GitHub als sociaal preview.

```bash
# voorbeeld: vanaf je echte icon.png op je Mac
cp ~/Downloads/ns-icon-256.png  custom_components/ns_reisadvies/icon.png
cp ~/Downloads/ns-icon-512.png  custom_components/ns_reisadvies/icon@2x.png
cp ~/Downloads/ns-icon-256.png  icon.png
git add icon.png custom_components/ns_reisadvies/icon*.png
git commit -m "Add real icon"
git push
```

## 4. Eerste release taggen

HACS gebruikt git-tags als versies. Tag minimaal één keer:

```bash
git tag -a v1.3.0 -m "Initial HACS release"
git push origin v1.3.0
```

Of via de GitHub UI: *Releases → Create a new release → tag v1.3.0 →
Generate release notes → Publish*.

## 5. Aan HACS toevoegen — twee routes

### Route A: instant install via "Custom repository"

Iedereen die je integratie nu wil, kan dit zelf doen — geen review nodig.

1. HACS → *Integrations → ⋮ → Custom repositories*.
2. URL: `https://github.com/Meppies/ha-ns-reisadvies`, category
   *Integration*, *Add*.
3. Zoek "NS Reisadvies", *Download*, HA herstarten.

### Route B: in de officiële HACS Default lijst

Iedereen vindt je integratie zonder de URL te kennen. Vereisten:

- Minimaal één GitHub-release/tag.
- `hacs.json` op repo-root (✓ aanwezig).
- `manifest.json` op de juiste plek met geldige `version` (✓).
- README met installatie-instructies (✓).
- Geen Hassfest/HACS-action errors.

PR tegen <https://github.com/hacs/default>: voeg een regel toe aan
`integration` met de repo-naam `Meppies/ha-ns-reisadvies`. De HACS-bot
draait `hacs/action` op je repo. Eventuele klachten daar van fixen.

## 6. Brand icon (`Settings → Devices & services` tegel)

Een lokale `icon.png` werkt voor HACS, maar HA-core zelf trekt het tegel-
icoontje uit `home-assistant/brands`. De PR daarvoor staat klaar in
`outputs/brands-pr/`. Zie de README daar.

## 7. Hassfest CI (aanrader)

GitHub Action toevoegen die op elke push de manifest valideert:

`.github/workflows/validate.yml`:

```yaml
name: Validate

on:
  push:
  pull_request:
  schedule:
    - cron: "0 0 * * *"

jobs:
  hassfest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: home-assistant/actions/hassfest@master

  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hacs/action@main
        with:
          category: integration
```

Deze file kan ik klaarzetten, of je voegt 'm later toe — geen blocker voor
de eerste release.
