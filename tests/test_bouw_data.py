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


def nep_api(m, prs_ok=True, scenario="verlaten", lopend=1, telling_oud=False, onvolledig=False, venster_tot_voor_t0=False, toekomst=False, bord=None):
    from datetime import timedelta as _td2
    t0 = m.CONFIG["burnin"]["t0"]
    na = m.NU.isoformat().replace("+00:00", "Z")
    prs = []
    BI = m.CONFIG["burnin"]
    namen = BI.get("orders") or [f"{BI['orders_prefix']}{i:02d}" for i in range(BI["orders_aantal"])]
    for i, naam in enumerate(namen + [BI["orders_prefix"] + "00", BI["orders_prefix"] + "98"]):  # afgesproken orders plus twee verkeerde nummers ná T0
        prs.append({"number": 100 + i, "title": f"[ROUTE2 codex1] {naam}", "created_at": t0, "merged_at": None,
                    "closed_at": None, "head": {"sha": f"s{i}" if scenario != "rood" else f"rood{i}"}})
    prs.append({"number": 200, "title": "[ROUTE2 codex1] KLANT-ACME-OFFERTE", "created_at": na, "merged_at": None,
                "closed_at": None, "head": {"sha": "k"}})
    prs.append({"number": 201, "title": "[ROUTE2 geheimaccount] PROEF-A1", "created_at": na, "merged_at": None,
                "closed_at": None, "head": {"sha": "g"}})
    oud = (m.NU - _td2(days=10)).isoformat().replace("+00:00", "Z")
    prs.append({"number": 203, "title": f"[ROUTE2 codex1] {BI['orders_prefix']}99", "created_at": oud, "merged_at": None,
                "closed_at": None, "head": {"sha": "oud"}})
    prs.append({"number": 202, "title": "[ROUTE2 codex1] PROEF-ACME", "created_at": na, "merged_at": None,
                "closed_at": None, "head": {"sha": "a"}})
    from datetime import timedelta as _td
    gem = (m.NU - _td(hours=2)).isoformat().replace("+00:00", "Z") if telling_oud else (
        (m.NU + _td(minutes=10)).isoformat().replace("+00:00", "Z") if toekomst else na)
    van = (m.tijd(t0) - _td(hours=1)).isoformat().replace("+00:00", "Z")
    tot = (m.tijd(t0) - _td(minutes=30)).isoformat().replace("+00:00", "Z") if venster_tot_voor_t0 else na
    telling = {"gemeten_om": gem, "volledig": not onvolledig, "venster": {"van": van, "tot": tot}, "stilstand": {"order_zonder_voortgang_45_minuten": False, "notitie": KANARIE},
               "vrij_veld": KANARIE, "ingrepen": {"pr_nummers": [BI["start_pr"], "57; " + KANARIE, 999], "bron": {"status": "GEMETEN"}},
               "uitkomsten": {"merged": 0, "no_go": 10, "lopend": lopend, "pogingen_totaal": 10, "notitie": KANARIE,
                              "bron": {"status": "GEMETEN"}}}
    def api(pad):
        if "/pulls" in pad:
            if not prs_ok:
                raise OSError("weg")
            return prs
        if "/contents/telling" in pad:
            return {"content": base64.b64encode(json.dumps(telling).encode()).decode()}
        if "/contents/bord/status.json" in pad:
            if bord == "weg":
                raise OSError("geen toegang")
            b = bord or {"bord": "Groeibord blog", "eigenaar": "x", "bijgewerkt": m.NU.astimezone(m.AMS).strftime("%d-%m-%Y %H:%M"),
                         "status": "ok", "bronnen_met_probleem": [], "link": "javascript:alert(1)", "kosten": KANARIE}
            return {"content": base64.b64encode(json.dumps(b).encode()).decode()}
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
_m3 = laad()
check("run-2-ordernamen (BURNIN2-01) blijven leesbaar en tellen mee", bool(_m3.PUBLIEKE_ORDER.match("BURNIN2-01")) and _m3.PUBLIEKE_ORDER.match("BURNIN-07") is not None and not _m3.PUBLIEKE_ORDER.match("BURNIN2-ACME"))
check("bord toont burn-in run 2", _m3.CONFIG["burnin"]["t0"] == "2026-10-15T19:30:58Z" and _m3.CONFIG["burnin"]["orders_prefix"] == "BURNIN2-")
check("eis-label volgt het aantal orders", "Tien echte uitkomsten" not in (ROOT_ := PAD.parent.parent / "index.html").read_text(encoding="utf-8"))


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
check("tien afgekeurde PR's en telling meldt 0 lopend: tien eindstanden", d_rood_klaar["burnin"]["uitkomsten"] == d_rood_klaar["burnin"]["orders_aantal"],
      str(d_rood_klaar["burnin"]["uitkomsten"]))
check("alleen BURNIN2-01..06 tellen; 00 en 98 ná T0 niet, 06 wel", d_rood_klaar["burnin"]["uitkomsten"] == 6 and laad().CONFIG["burnin"]["orders"][-1] == "BURNIN2-06" and "BURNIN2-00" not in laad().CONFIG["burnin"]["orders"])
_mf = laad(); _mf.CONFIG = dict(_mf.CONFIG, burnin={k: v for k, v in _mf.CONFIG["burnin"].items() if k != "orders"})
nep_api(_mf, scenario="rood", lopend=0); _of = io.StringIO()
with contextlib.redirect_stdout(_of):
    _mf.main()
check("zonder orderlijst telt elk uniek nummer met het voorvoegsel (oude runs): 00..05 + 98 = 7", json.loads(_of.getvalue())["burnin"]["uitkomsten"] == 7)
check("oude telling (2 uur) met 0 lopend maakt open afgekeurde PR's geen eindstand",
      draai("rood", 0, telling_oud=True)["burnin"]["uitkomsten"] == 0)
check("onvolledige telling met 0 lopend maakt open afgekeurde PR's geen eindstand",
      draai("rood", 0, onvolledig=True)["burnin"]["uitkomsten"] == 0)
check("venster dat vóór de burn-in-start eindigt telt niet",
      draai("rood", 0, venster_tot_voor_t0=True)["burnin"]["uitkomsten"] == 0)
check("meettijd in de toekomst telt niet", draai("rood", 0, toekomst=True)["burnin"]["uitkomsten"] == 0)
check("open PR ouder dan 3 dagen blijft zichtbaar als lopend", any(o["pr"] == 203 and o["uitkomst"] is None for o in d["orders"]))
d_verl = draai("verlaten", 1)
check("verlaten opdrachten blijven zichtbaar als lopend (geen uitkomst)", all(o["uitkomst"] is None for o in d_verl["orders"] if o["order"].startswith(m.CONFIG["burnin"]["orders_prefix"])))
check("telling-uitkomsten alleen gehele getallen, geen notitie", d_rood_klaar["telling"]["uitkomsten"] == {"merged": 0, "no_go": 10, "lopend": 0, "pogingen_totaal": 10})

# Andere borden (groeibord blog, SEO/GEO 16-10; Astra NO_GO 16-10 punten 1-5).
from datetime import datetime as _dt, timezone as _tz


def draai_bord(bord, nu=None):
    """Volledige run met een vaste klok; geeft (geldige JSON, foutcode)."""
    mm = laad()
    if nu:
        mm.NU = _dt.fromisoformat(nu).replace(tzinfo=_tz.utc)
    nep_api(mm, bord=bord)
    o = io.StringIO()
    try:
        with contextlib.redirect_stdout(o):
            mm.main()
    except SystemExit as exc:
        return None, exc.code
    except Exception as exc:  # een crash is precies wat punt 1 verbiedt
        return None, type(exc).__name__
    return json.loads(o.getvalue()), 0


def st(bij, status="ok", **x):
    return dict({"bord": "Groeibord blog", "eigenaar": "x", "bijgewerkt": bij, "status": status,
                 "bronnen_met_probleem": [KANARIE], "link": "javascript:alert(1)", "kosten": KANARIE}, **x)


NU_T = "2026-10-16T12:00:00"  # 14:00 Amsterdamse zomertijd
gb = (d.get("borden") or [{}])[0]
check("groeibord: verse ok-status is ok, link uit config", gb.get("stand") == "ok" and gb.get("link", "").startswith("https://rvanhooijdonk-png.github.io/"), str(gb))
check("groeibord: alleen vaste velden", set(gb) == {"naam", "eigenaar", "link", "bijgewerkt", "stand", "reden"}, str(sorted(gb)))
GEVALLEN = [  # (omschrijving, bijgewerkt, status, klok, verwachte stand, verwachte reden)
    ("precies 26 uur oud blijft ok", "15-10-2026 12:00", "ok", NU_T, "ok", "bijgewerkt"),
    ("26 uur en 1 minuut is let op", "15-10-2026 11:59", "ok", NU_T, "let_op", "ouder dan 26 uur"),
    ("ongeldige kalenderdatum 31-02", "31-02-2026 07:15", "ok", NU_T, "let_op", "status ongeldig"),
    ("niet-bestaand uur zomertijdwissel", "29-03-2026 02:30", "ok", "2026-03-29T08:00:00", "let_op", "status ongeldig"),
    ("dubbel uur wintertijdwissel", "25-10-2026 02:30", "ok", "2026-10-25T08:00:00", "let_op", "status ongeldig"),
    ("controle: gewoon uur op de wisseldag", "25-10-2026 03:30", "ok", "2026-10-25T08:00:00", "ok", "bijgewerkt"),
    ("tijd een uur in de toekomst", "16-10-2026 15:00", "ok", NU_T, "let_op", "status ongeldig"),
    ("tijd een minuut in de toekomst", "16-10-2026 14:01", "ok", NU_T, "let_op", "status ongeldig"),
    ("controle: precies nu is ok", "16-10-2026 14:00", "ok", NU_T, "ok", "bijgewerkt"),
    ("onbekende status", "16-10-2026 13:00", "groen", NU_T, "let_op", "status ongeldig"),
    ("let_op: vaste tekst, geen telling", "16-10-2026 13:00", "let_op", NU_T, "let_op", "bord meldt let op"),
]
basis, _ = draai_bord(st("16-10-2026 13:00"), NU_T)
for oms, bij, status, klok, stand, reden in GEVALLEN:
    uitv, code = draai_bord(st(bij, status), klok)
    t = (uitv or {}).get("borden", [{}])[0]
    check(f"groeibord: {oms}", code == 0 and t.get("stand") == stand and t.get("reden") == reden, f"code={code} {t}")
for oms, bord in (("onleesbaar", "weg"), ("geen datum", {"bord": "x", "status": "ok"}), ("geen object", ["x"])):
    uitv, code = draai_bord(bord, NU_T)
    t = (uitv or {}).get("borden", [{}])[0]
    check(f"groeibord: {oms} geeft volledige JSON met let op", code == 0 and t.get("stand") == "let_op", f"code={code} {t}")
    check(f"groeibord: {oms} laat de bronnen exact gelijk",
          uitv is not None and uitv["bronnen"] == basis["bronnen"], str(uitv and uitv["bronnen"]))
_tekst = json.dumps(basis)
check("groeibord: link, kosten en probleembronnen uit status.json komen er niet in", "javascript:" not in _tekst and KANARIE not in _tekst)
_mm = laad(); _vraag = []
_mm.CONFIG = dict(_mm.CONFIG, borden=[{"naam": "Zonder status", "eigenaar": "SEA", "link": "https://rvanhooijdonk-png.github.io/x/"}])
nep_api(_mm); _api = _mm.api; _mm.api = lambda pad: (_vraag.append(pad), _api(pad))[1]; _o = io.StringIO()
with contextlib.redirect_stdout(_o):
    _mm.main()
_t = json.loads(_o.getvalue())["borden"]
check("bord zonder statusbestand: tegel met alleen link, stand 'link', geen statusverzoek",
      _t == [{"naam": "Zonder status", "eigenaar": "SEA", "link": "https://rvanhooijdonk-png.github.io/x/", "bijgewerkt": None,
              "stand": "link", "reden": "geen status gekoppeld"}] and not any("/contents/" in v and "telling" not in v for v in _vraag), str(_t))
check("alle borden uit config hebben een https-link en een eigenaar",
      all(str(b.get("link", "")).startswith("https://") and b.get("eigenaar") for b in laad().CONFIG["borden"]) and len(laad().CONFIG["borden"]) >= 9)
_mm = laad(); _mm.CONFIG = dict(_mm.CONFIG, borden=[dict(_mm.CONFIG["borden"][0], link="javascript:alert(1)")])
nep_api(_mm); _o = io.StringIO()
with contextlib.redirect_stdout(_o):
    _mm.main()
check("groeibord: een niet-https-link in config geeft geen tegel", json.loads(_o.getvalue())["borden"] == [])

m2 = laad(); nep_api(m2, prs_ok=False)
uit2 = io.StringIO()
try:
    with contextlib.redirect_stdout(uit2):
        m2.main()
    code = 0
except SystemExit as e:
    code = e.code
check("onleesbare PR's blokkeren de publicatie", code not in (0, None) and not uit2.getvalue().strip(), f"code={code}")

# Privacygrens publieke site (OB-0952, Astra R8): scan alle gepubliceerde tekst, zonder vrijstellingen.
import re as _re
GEVOELIG = _re.compile(r"wachtwoord|password|\broot\b|\bssh\b|\b\d{1,3}(\.\d{1,3}){3}\b|gelekt|lekte|onversleuteld|open_basedir|vhost"
                       r"|api[_-]?key|ghp_|sk-[A-Za-z0-9]|AIza|heinmaas|sheheryar|jasper|BEEHIIV_API_KEY|GRANOLA_API_KEY"
                       r"|\b[a-z]+_[a-z0-9]+_[a-z0-9_]+\b|\bwp_[a-z0-9_]+\b", _re.I)


def alle_tekst(x):
    if isinstance(x, str): return [x]
    if isinstance(x, dict): return [s for v in x.values() for s in alle_tekst(v)]  # alleen waarden, geen sleutels
    if isinstance(x, list): return [s for v in x for s in alle_tekst(v)]
    return []


def zichtbare_html(html):
    html = _re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    return _re.sub(r"<[^>]+>", " ", html)


def stack_data(html):
    m = _re.search(r"<script>([\s\S]*?)</script>", html)
    return _re.findall(r'"([^"\n]{2,})"', m.group(1)) if m else []


def privacyscan(cfg, htmls, data_json):
    teksten = alle_tekst({k: v for k, v in cfg.items() if k != "publieke_velden_besluit"})
    teksten += alle_tekst(json.loads(data_json))
    for naam, html in htmls.items():
        teksten.append(zichtbare_html(html))
        if naam == "stack.html":
            teksten += stack_data(html)
    teksten = [_re.sub(r"https?://\S+", " ", x) for x in teksten]  # links naar het register zijn geen login
    return [x[:80] for x in teksten if GEVOELIG.search(x)]


ROOT = PAD.parent.parent
cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
htmls = {n: (ROOT / n).read_text(encoding="utf-8") for n in ("index.html", "voorstel.html", "stack.html", "publishing.html")}
fouten = privacyscan(cfg, htmls, tekst)
check("publieke site bevat geen geheimen, systeemlogins of exploiteerbare details", not fouten, str(fouten[:5]))
_cfg2 = dict(cfg, wacht_op_richard=cfg.get("wacht_op_richard", []) + [{"wat": "login wp_beheerder_42 aanpassen", "wanneer": "-", "duur": "-"}])
check("proef: verzonnen systeemlogin in wacht_op_richard maakt de volledige scan rood", bool(privacyscan(_cfg2, htmls, tekst)))
_htmls2 = dict(htmls, **{"stack.html": htmls["stack.html"].replace('["Back-ups en herstelproef","deels"]', '["Back-ups en herstelproef wp_beheerder_42","deels"]')})
check("proef: verzonnen systeemlogin in stack.html maakt de volledige scan rood", bool(privacyscan(cfg, _htmls2, tekst)))
check("open afgekeurde PR zonder geldige nul is geen eindstand (UI-contract eind=false)",
      all(not o["eind"] for o in d_rood_lopend["orders"] if o["order"].startswith(m.CONFIG["burnin"]["orders_prefix"])))

print("\nALLE PROEVEN GROEN" if not FOUT else "\nER ZIJN FOUTEN")
sys.exit(FOUT)
