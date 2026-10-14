"""Bouwt data.json voor het bouwstraat-bord uit GitHub. Leest alleen; schrijft niets naar route 2 of het register.

Bronnen: PR's van route 2 met hun statussen, de telling op de tak route2/telling, de aanvoercommits, en
de prioriteiten-issues van het privé-projectenregister (alleen status en aantal reacties, geen tekst).
Statusbeschrijvingen gaan nooit naar de publieke JSON: alleen een vaste tekst uit context en status (VASTE_TEKST),
Astra NO_GO 14-10.
Een bron die niet te lezen is, komt in `bronnen` als ONBEWEZEN; er wordt dan geen nul verzonnen.
Gebruik: ROUTE2_LEES_TOKEN=... python scripts/bouw_data.py > site/data.json
"""
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

CONFIG = json.loads((Path(__file__).resolve().parent.parent / "config.json").read_text(encoding="utf-8"))
REPO = CONFIG["route2_repo"]
TOKEN = os.environ.get("ROUTE2_LEES_TOKEN", "")
TITEL = re.compile(r"^\[ROUTE2 ([a-z0-9]+)\] ([A-Z0-9][A-Z0-9-]{1,60})$")
NU = datetime.now(timezone.utc)
BEKENDE_ACCOUNTS = {a["naam"] for a in CONFIG["accounts"]}
PUBLIEKE_ORDER = re.compile(r"^BURNIN-\d{2}$")  # al het andere wordt OPDRACHT-<pr-nummer> (Astra R4)
# Alleen deze eindtoestanden zijn een echte burn-in-uitkomst; gesloten, onbekend en zonder uitkomst niet.
ECHTE_UITKOMST = {"samengevoegd", "afgekeurd", "tests rood"}
bronnen = {}



# Statusbeschrijvingen gaan NOOIT naar de publieke site (Astra 14-10): alleen een vaste tekst uit context en status.
VASTE_TEKST = {
    ("route2/tests", "success"): "tests groen", ("route2/tests", "failure"): "tests rood",
    ("route2/tests", "error"): "tests fout", ("route2/tests", "pending"): "tests bezig",
    ("route2/review", "success"): "beoordeling GO", ("route2/review", "failure"): "beoordeling NO_GO",
    ("route2/review", "error"): "beoordeling fout", ("route2/review", "pending"): "beoordeling bezig",
}


def veilige_status(s):
    """Vaste tekst uit (context, status); de vrije beschrijving van de status wordt nooit gebruikt."""
    if not s:
        return None
    return VASTE_TEKST.get((s.get("context"), s.get("state")), "onbekend")


def api(pad):
    req = urllib.request.Request("https://api.github.com/" + pad, headers={
        "Authorization": "Bearer " + TOKEN, "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "bouwstraat-bord"})
    for poging in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or poging == 2:
                raise
        except urllib.error.URLError:
            if poging == 2:
                raise
    return None


def lees(naam, functie):
    try:
        waarde = functie()
        bronnen[naam] = {"status": "GEMETEN", "gemeten_om": NU.isoformat()}
        return waarde
    except Exception as exc:  # alleen het type, nooit inhoud
        code = getattr(exc, "code", None)
        bronnen[naam] = {"status": "ONBEWEZEN", "fout": type(exc).__name__ + (f" {code}" if code else ""),
                         "gemeten_om": NU.isoformat()}
        return None


def tijd(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def prs():
    uit = []
    for pagina in (1, 2, 3):
        rij = api(f"repos/{REPO}/pulls?state=all&per_page=100&page={pagina}")
        uit += rij
        if len(rij) < 100:
            break
    return uit


def statussen(sha):
    return api(f"repos/{REPO}/commits/{sha}/statuses?per_page=100")


def telling():
    inhoud = api(f"repos/{REPO}/contents/telling/laatste.json?ref=route2/telling")
    return json.loads(base64.b64decode(inhoud["content"]))


def telling_commits():
    return api(f"repos/{REPO}/commits?sha=route2/telling&per_page=40")


def aanvoer_commits():
    return api(f"repos/{REPO}/commits?sha=integratie&path=aanvoer&per_page=20")


def prioriteiten():
    """Titels uit config; status, labels en reacties uit de privé-issues als het token daar mag lezen."""
    repo = CONFIG.get("prioriteiten_repo")
    lijst = [dict(p, url=f"https://github.com/{repo}/issues/{p['nr']}", status=None, reacties=None,
                  open=True) for p in CONFIG.get("prioriteiten", [])]
    issues = lees("prioriteiten", lambda: api(f"repos/{repo}/issues?state=all&per_page=100")) if repo else None
    if issues:
        per_nr = {i["number"]: i for i in issues if "pull_request" not in i}
        for p in lijst:
            i = per_nr.get(p["nr"])
            if not i:
                continue
            labels = [l["name"] for l in i.get("labels", [])]
            p["wie"] = next((l for l in ("bij-jou", "overleg", "bezig", "stack", "klaar") if l in labels), p["wie"])
            # Besluit (14-10): publiek alleen wie, open/dicht en het aantal reacties; geen tekst en geen bijwerktijd.
            p.update(reacties=i.get("comments") if isinstance(i.get("comments"), int) else None, open=i.get("state") == "open")
    return lijst


def main():
    alle = lees("pull_requests", prs) or []
    stand = lees("telling", telling)
    tcommits = lees("telling_geschiedenis", telling_commits) or []
    acommits = lees("aanvoer", aanvoer_commits) or []
    beoordelaar = CONFIG["standaard_beoordelaar"]
    t0 = tijd(CONFIG["burnin"]["t0"])

    # Een afkeuring of rode test is pas een eindstand als de telling van route 2 aantoonbaar 0 lopende workflows meldt
    # (route 2 sluit een NO_GO-PR niet; de workflow eindigt wel). Zonder leesbare telling telt een open PR nooit mee.
    u = stand.get("uitkomsten") if isinstance(stand, dict) and isinstance(stand.get("uitkomsten"), dict) else {}
    # De nul telt alleen uit een volledige, verse telling (≤ 30 min) waarvan het venster de burn-in-start omvat (Astra R5).
    tel_tijd = tijd(stand.get("gemeten_om")) if isinstance(stand, dict) and isinstance(stand.get("gemeten_om"), str) else None
    venster = stand.get("venster") if isinstance(stand, dict) and isinstance(stand.get("venster"), dict) else {}
    venster_van = tijd(venster.get("van")) if isinstance(venster.get("van"), str) else None
    telling_geldig = (isinstance(stand, dict) and stand.get("volledig") is True and tel_tijd is not None
                      and NU - tel_tijd <= timedelta(minutes=30) and venster_van is not None and venster_van <= t0)
    niets_lopend = (telling_geldig and u.get("bron", {}).get("status") == "GEMETEN" and isinstance(u.get("lopend"), int)
                    and not isinstance(u.get("lopend"), bool) and u.get("lopend") == 0)
    orders, ticker = [], []
    for pr in alle:
        m = TITEL.match(pr["title"])
        if not m:
            continue
        bouwer, order_id = m.group(1), m.group(2)
        # Publieke ID's (Astra R3): bouwer alleen uit de bekende accounts, ordernaam alleen in een vaste vorm.
        if bouwer not in BEKENDE_ACCOUNTS:
            bouwer = "onbekend"
        if not PUBLIEKE_ORDER.match(order_id):
            order_id = f"OPDRACHT-{pr['number']}"
        geopend, merged, gesloten = tijd(pr["created_at"]), tijd(pr.get("merged_at")), tijd(pr.get("closed_at"))
        recent = geopend >= NU - timedelta(days=3)
        st = (lees(f"statussen_pr_{pr['number']}", lambda: statussen(pr["head"]["sha"])) or []) if recent else []
        laatste = {}
        for s in st:  # GitHub geeft nieuwste eerst
            laatste.setdefault(s["context"], s)
            if s["context"] in ("route2/tests", "route2/review") and s["state"] != "pending":
                acc = bouwer if s["context"] == "route2/tests" else beoordelaar
                ticker.append({"t": s["created_at"], "soort": "goed" if s["state"] == "success" else "fout",
                               "tekst": f"{order_id}: {veilige_status(s)}", "account": acc,
                               "pr": pr["number"]})
            elif s["context"] == "route2/review" and s["state"] == "pending":
                ticker.append({"t": s["created_at"], "soort": "bezig", "tekst": f"{order_id}: beoordeling gestart",
                               "account": beoordelaar, "pr": pr["number"]})
        ticker.append({"t": pr["created_at"], "soort": "start", "tekst": f"{order_id}: opgepakt, bouw gestart",
                       "account": bouwer, "pr": pr["number"]})
        if merged:
            ticker.append({"t": pr["merged_at"], "soort": "goed", "tekst": f"{order_id}: samengevoegd",
                           "account": None, "pr": pr["number"]})
        tests, review = laatste.get("route2/tests", {}), laatste.get("route2/review", {})
        if merged:
            fase, uitkomst = "samengevoegd", "samengevoegd"
        elif review.get("state") in ("failure", "error"):
            fase, uitkomst = "beoordeling", "afgekeurd"
        elif tests.get("state") in ("failure", "error"):
            fase, uitkomst = "tests", "tests rood"
        elif gesloten:
            fase, uitkomst = "gesloten", "gesloten"
        elif review.get("state") == "pending" or tests.get("state") == "success":
            fase, uitkomst = "beoordeling", None
        elif not recent:
            fase, uitkomst = "onbekend", "onbekend"
        else:
            fase, uitkomst = "bouw", None
        if uitkomst is None and geopend < NU - timedelta(minutes=90):
            # Een open PR zonder statussen na anderhalf uur is verlaten (bijvoorbeeld een geblokkeerde run).
            fase, uitkomst = "zonder voortgang", None  # blijft zichtbaar bij Lopend; geen eindstand (Astra R5)
        eind = bool(merged) or bool(gesloten) or (uitkomst in ("afgekeurd", "tests rood") and niets_lopend)
        orders.append({"pr": pr["number"], "order": order_id, "bouwer": bouwer, "eind": eind,
                       "beoordelaar": beoordelaar, "fase": fase, "uitkomst": uitkomst,
                       "geopend": pr["created_at"], "afgerond": pr.get("merged_at") or (
                           (review.get("created_at") or tests.get("created_at")) if uitkomst else None),
                       "tests": veilige_status(tests), "review": veilige_status(review),
                       "na_t0": geopend >= t0})

    for c in tcommits:
        ticker.append({"t": c["commit"]["committer"]["date"], "soort": "telling",
                       "tekst": "tellingronde gepubliceerd", "account": None, "pr": None})
    for c in acommits:
        ticker.append({"t": c["commit"]["committer"]["date"], "soort": "aanvoer",
                       "tekst": "opdracht(en) in de aanvoer gezet", "account": None, "pr": None})
    ticker.sort(key=lambda r: r["t"], reverse=True)

    accounts = []
    for a in CONFIG["accounts"]:
        mijn = [r for r in ticker if r.get("account") == a["naam"]]
        bezig = next((o for o in orders if o["uitkomst"] is None and (
            (o["fase"] == "bouw" and o["bouwer"] == a["naam"]) or
            (o["fase"] == "beoordeling" and o["beoordelaar"] == a["naam"]))), None)
        accounts.append({**a, "laatst": mijn[0]["t"] if mijn else None,
                         "stappen_24u": sum(1 for r in mijn if tijd(r["t"]) >= NU - timedelta(hours=24)),
                         "bezig": f"{bezig['fase']} · {bezig['order']}" if bezig else None})

    bi = CONFIG["burnin"]
    bi_orders = [o for o in orders if o["order"].startswith(bi["orders_prefix"]) and o["na_t0"]]
    uniek = {}
    for o in sorted(bi_orders, key=lambda o: o["geopend"]):
        uniek[o["order"]] = o
    burnin = {**bi, "uitkomsten": sum(1 for o in uniek.values() if o["eind"] and o["uitkomst"] in ECHTE_UITKOMST),
              "samengevoegd": sum(1 for o in uniek.values() if o["uitkomst"] == "samengevoegd"),
              "afgekeurd": sum(1 for o in uniek.values() if o["eind"] and o["uitkomst"] in ("afgekeurd", "tests rood")),
              "verstreken_uur": round(max(0.0, (min(NU, tijd(bi["einde"])) - tijd(bi["t0"])).total_seconds()) / 3600, 1)}
    if stand:
        ing = stand.get("ingrepen", {})
        na = [n for n in (ing.get("pr_nummers") or []) if isinstance(n, int) and not isinstance(n, bool) and n not in bi["vooraf_ingrepen"]]
        burnin["ingrepen_na_t0"] = None if ing.get("bron", {}).get("status") == "ONBEWEZEN" else len(na)
        burnin["ingrepen_prs"] = na

    if bronnen.get("pull_requests", {}).get("status") != "GEMETEN":
        for a in accounts:
            a["onbekend"] = True
    if bronnen.get("pull_requests", {}).get("status") != "GEMETEN":
        # Zonder leesbare PR's geen nieuwe publicatie: het oude bord blijft staan en toont "loopt achter".
        print("AFGEBROKEN: pull_requests niet gemeten; geen nieuwe data.json", file=sys.stderr)
        sys.exit(3)
    telling_publiek = None
    if isinstance(stand, dict):
        stil = stand.get("stilstand") if isinstance(stand.get("stilstand"), dict) else {}
        telling_publiek = {"gemeten_om": stand.get("gemeten_om") if isinstance(stand.get("gemeten_om"), str) else None,
                           "volledig": stand.get("volledig") if isinstance(stand.get("volledig"), bool) else None,
                           "stilstand": {"order_zonder_voortgang_45_minuten": stil.get("order_zonder_voortgang_45_minuten") is True},
                           "uitkomsten": {k: u.get(k) for k in ("merged", "no_go", "lopend", "pogingen_totaal")
                                          if isinstance(u.get(k), int) and not isinstance(u.get(k), bool)}}
    json.dump({"gemeten_om": NU.isoformat(), "bronnen": bronnen, "telling": telling_publiek, "orders": orders,
               "accounts": accounts, "ticker": ticker[:150], "burnin": burnin,
               "projecten": CONFIG["projecten"], "prioriteiten": prioriteiten(), "clusters": CONFIG.get("clusters", []), "register_url": CONFIG.get("register_url"), "wacht_op_richard": CONFIG["wacht_op_richard"], "werkvoorraad": CONFIG.get("werkvoorraad", [])},
              sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
