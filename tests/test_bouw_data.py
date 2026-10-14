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


def nep_api(m, prs_ok=True, scenario="verlaten", lopend=1, telling_oud=False, onvolledig=False, venster_tot_voor_t0=False, toekomst=False):
    from datetime import timedelta as _td2
    t0 = m.CONFIG["burnin"]["t0"]
    na = m.NU.isoformat().replace("+00:00", "Z")
    prs = []
    for i in range(10):  # tien burn-in-opdrachten na t0
        prs.append({"number": 100 + i, "title": f"[ROUTE2 codex1] BURNIN-{i:02d}", "created_at": t0, "merged_at": None,
                    "closed_at": None, "head": {"sha": f"s{i}" if scenario != "rood" else f"rood{i}"}})
    prs.append({"number": 200, "title": "[ROUTE2 codex1] KLANT-ACME-OFFERTE", "created_at": na, "merged_at": None,
                "closed_at": None, "head": {"sha": "k"}})
    prs.append({"number": 201, "title": "[ROUTE2 geheimaccount] PROEF-A1", "created_at": na, "merged_at": None,
                "closed_at": None, "head": {"sha": "g"}})
    oud = (m.NU - _td2(days=10)).isoformat().replace("+00:00", "Z")
    prs.append({"number": 203, "title": "[ROUTE2 codex1] BURNIN-99", "created_at": oud, "merged_at": None,
                "closed_at": None, "head": {"sha": "oud"}})
    prs.append({"number": 202, "title": "[ROUTE2 codex1] PROEF-ACME", "created_at": na, "merged_at": None,
                "closed_at": None, "head": {"sha": "a"}})
    from datetime import timedelta as _td
    gem = (m.NU - _td(hours=2)).isoformat().replace("+00:00", "Z") if telling_oud else (
        (m.NU + _td(minutes=10)).isoformat().replace("+00:00", "Z") if toekomst else na)
    van = (m.tijd(t0) - _td(hours=1)).isoformat().replace("+00:00", "Z")
    tot = (m.tijd(t0) - _td(minutes=30)).isoformat().replace("+00:00", "Z") if venster_tot_voor_t0 else na
    telling = {"gemeten_om": gem, "volledig": not onvolledig, "venster": {"van": van, "tot": tot}, "stilstand": {"order_zonder_voortgang_45_minuten": False, "notitie": KANARIE},
               "vrij_veld": KANARIE, "ingrepen": {"pr_nummers": [55, "57; " + KANARIE, 999], "bron": {"status": "GEMETEN"}},
               "uitkomsten": {"merged": 0, "no_go": 10, "lopend": lopend, "pogingen_totaal": 10, "notitie": KANARIE,
                              "bron": {"status": "GEMETEN"}}}
    def api(pad):
        if "/pulls" in pad:
            if not prs_ok:
                raise OSError("weg")
            return prs
        if "/contents/telling" in pad:
            return {"content": base64.b64encode(json.dumps(telling).encode()).decode()}
        if "/statuses" in pad:
            if "/rood" in pad:  # open PR met rode tests en afwijzende beoordeling
                return [{"context": "route2/review", "state": "failure", "description": KANARIE, "created_at": na},
                        {"context": "route2/tests", "state": "failure", "description": KANARIE, "created_at": na}]
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
check("telling alleen gekozen velden", set(d["telling"]) == {"gemeten_om", "volledig", "stilstand", "uitkomsten"})

check("korte privé-ordernaam PROEF-ACME geneutraliseerd", "ACME" not in tekst)


def draai(scenario, lopend, **kw):
    mm = laad(); nep_api(mm, scenario=scenario, lopend=lopend, **kw)
    o = io.StringIO()
    with contextlib.redirect_stdout(o):
        mm.main()
    return json.loads(o.getvalue())


d_rood_lopend = draai("rood", 1)
check("tien open rode PR's terwijl er nog workflows lopen: geen uitkomst", d_rood_lopend["burnin"]["uitkomsten"] == 0,
      str(d_rood_lopend["burnin"]["uitkomsten"]))
d_rood_klaar = draai("rood", 0)
check("tien afgekeurde PR's en telling meldt 0 lopend: tien eindstanden", d_rood_klaar["burnin"]["uitkomsten"] == 10,
      str(d_rood_klaar["burnin"]["uitkomsten"]))
check("oude telling (2 uur) met 0 lopend maakt open afgekeurde PR's geen eindstand",
      draai("rood", 0, telling_oud=True)["burnin"]["uitkomsten"] == 0)
check("onvolledige telling met 0 lopend maakt open afgekeurde PR's geen eindstand",
      draai("rood", 0, onvolledig=True)["burnin"]["uitkomsten"] == 0)
check("venster dat vóór de burn-in-start eindigt telt niet",
      draai("rood", 0, venster_tot_voor_t0=True)["burnin"]["uitkomsten"] == 0)
check("meettijd in de toekomst telt niet", draai("rood", 0, toekomst=True)["burnin"]["uitkomsten"] == 0)
check("open PR ouder dan 3 dagen blijft zichtbaar als lopend", any(o["pr"] == 203 and o["uitkomst"] is None for o in d["orders"]))
d_verl = draai("verlaten", 1)
check("verlaten opdrachten blijven zichtbaar als lopend (geen uitkomst)", all(o["uitkomst"] is None for o in d_verl["orders"] if o["order"].startswith("BURNIN-")))
check("telling-uitkomsten alleen gehele getallen, geen notitie", d_rood_klaar["telling"]["uitkomsten"] == {"merged": 0, "no_go": 10, "lopend": 0, "pogingen_totaal": 10})

m2 = laad(); nep_api(m2, prs_ok=False)
uit2 = io.StringIO()
try:
    with contextlib.redirect_stdout(uit2):
        m2.main()
    code = 0
except SystemExit as e:
    code = e.code
check("onleesbare PR's blokkeren de publicatie", code not in (0, None) and not uit2.getvalue().strip(), f"code={code}")

# Publieke werkvoorraad: geen beveiligings-, back-up-, sleutel-, account-, outreach- of adresdetails (Astra R5).
import re as _re
# OB-0952: taken mogen publiek; exploiteerbare details en geheimen niet.
GEVOELIG = _re.compile(r"wachtwoord|password|\broot\b|\bssh\b|\b\d{1,3}(\.\d{1,3}){3}\b|gelekt|lekte|onversleuteld|open_basedir|vhost|api[_-]?key|ghp_|sk-[A-Za-z0-9]|AIza|heinmaas|sheheryar|jasper|BEEHIIV_API_KEY|GRANOLA_API_KEY|KANARIE-SYSTEEMACCOUNT", _re.I)
cfg = json.loads((PAD.parent.parent / "config.json").read_text(encoding="utf-8"))
def alle_tekst(x):
    if isinstance(x, str): return [x]
    if isinstance(x, dict): return [s for v in x.values() for s in alle_tekst(v)]
    if isinstance(x, list): return [s for v in x for s in alle_tekst(v)]
    return []
# Alle statische publieke velden, behalve het besluit zelf (dat noemt de regel), plus de gegenereerde data.json.
teksten = alle_tekst({k: v for k, v in cfg.items() if k != "publieke_velden_besluit"})
teksten += [tekst]
ct = cfg.get("content", {})
teksten += [open(PAD.parent.parent / "stack.html", encoding="utf-8").read()]
fout_titels = [x[:80] for x in teksten if GEVOELIG.search(x) and "alleen in het privé-register" not in x and "details privé" not in x and "details alleen in het privé-register" not in x]
check("publieke tekst bevat geen geheimen of exploiteerbare details", not fout_titels, str(fout_titels))
_proef = dict(cfg, wacht_op_richard=cfg.get("wacht_op_richard", []) + [{"wat": "inlog heinmaas_x", "wanneer": "-", "duur": "-"}])
check("proef: een systeemaccount in wacht_op_richard wordt gevangen", any(GEVOELIG.search(x) for x in alle_tekst(_proef)))
check("open afgekeurde PR zonder geldige nul is geen eindstand (UI-contract eind=false)",
      all(not o["eind"] for o in d_rood_lopend["orders"] if o["order"].startswith("BURNIN-")))

print("\nALLE PROEVEN GROEN" if not FOUT else "\nER ZIJN FOUTEN")
sys.exit(FOUT)
