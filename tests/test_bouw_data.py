#!/usr/bin/env python3
"""Offline proef voor scripts/bouw_data.py (Astra R3, 14-10): nep-GitHub-API, geen netwerk.

Toetst: alle bronnen worden gelezen; vrije privétekst (kanaries) komt nergens in de JSON; klantnaam in een
PR-titel wordt geneutraliseerd; alleen echte eindtoestanden tellen als burn-in-uitkomst; onleesbare PR's
blokkeren de publicatie. Draaien: python3 tests/test_bouw_data.py
"""
import base64, contextlib, importlib.util, io, json, sys
from pathlib import Path

PAD = Path(__file__).resolve().parent.parent / "scripts" / "bouw_data.py"
KANARIE = "KANARIE-Klant-Acme-Dorpsstraat-1"
FOUT = 0


def check(naam, ok, detail=""):
    global FOUT
    print(("PASS " if ok else "FAIL ") + naam + ("" if ok else f": {detail}"))
    FOUT |= (not ok)


def laad():
    spec = importlib.util.spec_from_file_location("bouw_data", PAD)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def nep_api(m, prs_ok=True):
    t0 = m.CONFIG["burnin"]["t0"]
    na = m.NU.isoformat().replace("+00:00", "Z")
    prs = []
    for i in range(10):  # tien verlaten opdrachten na t0, zonder statussen
        prs.append({"number": 100 + i, "title": f"[ROUTE2 codex1] BURNIN-{i:02d}", "created_at": t0, "merged_at": None,
                    "closed_at": None, "head": {"sha": f"s{i}"}})
    prs.append({"number": 200, "title": "[ROUTE2 codex1] KLANT-ACME-OFFERTE", "created_at": na, "merged_at": None,
                "closed_at": None, "head": {"sha": "k"}})
    prs.append({"number": 201, "title": "[ROUTE2 geheimaccount] PROEF-A1", "created_at": na, "merged_at": None,
                "closed_at": None, "head": {"sha": "g"}})
    telling = {"gemeten_om": na, "volledig": True, "stilstand": {"order_zonder_voortgang_45_minuten": False, "notitie": KANARIE},
               "vrij_veld": KANARIE, "ingrepen": {"pr_nummers": [55, "57; " + KANARIE, 999], "bron": {"status": "GEMETEN"}}}
    def api(pad):
        if "/pulls" in pad:
            if not prs_ok:
                raise OSError("weg")
            return prs
        if "/contents/telling" in pad:
            return {"content": base64.b64encode(json.dumps(telling).encode()).decode()}
        if "/statuses" in pad:
            return [{"context": "route2/tests", "state": "success", "description": KANARIE, "created_at": na}]
        if "/commits" in pad:
            return [{"commit": {"committer": {"date": na}, "message": KANARIE}}]
        if "/issues" in pad:
            return [{"number": p["nr"], "comments": 2, "state": "open", "updated_at": na, "title": KANARIE, "body": KANARIE,
                     "labels": [{"name": "bezig"}]} for p in m.CONFIG.get("prioriteiten", [])]
        raise AssertionError("onverwacht pad " + pad)
    m.api = api


m = laad(); nep_api(m)
uit = io.StringIO()
with contextlib.redirect_stdout(uit):
    m.main()
tekst = uit.getvalue(); d = json.loads(tekst)
niet = [k for k, v in d["bronnen"].items() if v["status"] != "GEMETEN"]
check("alle bronnen gelezen (geen kapotte lezer)", not niet, str(niet))
check("kanarie komt nergens in de JSON", KANARIE not in tekst)
check("klantnaam uit PR-titel geneutraliseerd", "KLANT-ACME" not in tekst and any(o["order"] == "OPDRACHT-200" for o in d["orders"]))
check("onbekend account wordt 'onbekend'", "geheimaccount" not in tekst)
check("tien verlaten opdrachten tellen niet als uitkomst", d["burnin"]["uitkomsten"] == 0, str(d["burnin"]["uitkomsten"]))
check("ingrepen alleen gehele PR-nummers", d["burnin"]["ingrepen_prs"] == [999], str(d["burnin"].get("ingrepen_prs")))
check("telling alleen gekozen velden", set(d["telling"]) == {"gemeten_om", "volledig", "stilstand"})

m2 = laad(); nep_api(m2, prs_ok=False)
uit2 = io.StringIO()
try:
    with contextlib.redirect_stdout(uit2):
        m2.main()
    code = 0
except SystemExit as e:
    code = e.code
check("onleesbare PR's blokkeren de publicatie", code not in (0, None) and not uit2.getvalue().strip(), f"code={code}")

print("\nALLE PROEVEN GROEN" if not FOUT else "\nER ZIJN FOUTEN")
sys.exit(FOUT)
