# Bouwstraat-bord

Openbaar bord voor de bouwstraat (route 2). Een GitHub Action leest elke 5 minuten de stand van route 2 (alleen lezen) en publiceert deze pagina.

- Gegevens: `scripts/bouw_data.py` (PR-statussen, telling, aanvoer).
- Pagina: `index.html`, leest `data.json`.
- Instellingen: `config.json`.
