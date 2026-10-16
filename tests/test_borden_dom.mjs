// DOM-proef voor tekenBorden in index.html (Astra 16-10 punt 4/5): tekst via textContent, href alleen https.
import { readFileSync } from "node:fs";
const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const treffer = html.match(/function tekenBorden\(d\)\{[\s\S]*?\n\}/);
if (!treffer) { console.log("FAIL tekenBorden ontbreekt in index.html: tegels niet als losse, toetsbare tekenfunctie\n\nER ZIJN FOUTEN"); process.exit(1); }
const bron = treffer[0];
const helpers = html.match(/const el=.*\n/)[0] + html.match(/const geleden=.*\n/)[0];
let fout = 0;
const check = (naam, ok, x = "") => { console.log((ok ? "PASS " : "FAIL ") + naam + (ok ? "" : ": " + x)); if (!ok) fout = 1; };
class N { constructor(t) { this.tag = t; this.children = []; this.className = ""; this._t = ""; }
  set textContent(v) { this._t = String(v); this.children = []; } get textContent() { return this._t + this.children.map(c => typeof c === "string" ? c : c.textContent).join(""); }
  set innerHTML(v) { throw new Error("innerHTML gebruikt"); }
  append(...x) { this.children.push(...x); } replaceChildren() { this.children = []; } }
const els = { borden: new N("div"), "borden-blok": new N("section") };
const document = { createElement: t => new N(t), getElementById: id => els[id] };
const teken = new Function("document", helpers + bron + "\nreturn tekenBorden;")(document);
const alle = n => [n, ...n.children.filter(c => typeof c !== "string").flatMap(alle)];
const kwaad = "<img src=x onerror=alert(1)>";
teken({ borden: [
  { naam: kwaad, eigenaar: "SEO/GEO", link: "https://rvanhooijdonk-png.github.io/blog-voorstellen/groeibord/", bijgewerkt: new Date().toISOString(), stand: "ok", reden: "bijgewerkt" },
  { naam: "B", eigenaar: "x", link: "javascript:alert(1)", bijgewerkt: null, stand: "let_op", reden: "status niet leesbaar" }] });
const knopen = alle(els.borden), links = knopen.filter(n => n.tag === "a");
check("twee tegels getekend", els.borden.children.length === 2);
check("kwaadaardige naam staat er als tekst", els.borden.children[0].textContent.includes(kwaad) && !knopen.some(n => n.tag === "img"));
check("https-link wordt href", links.length === 1 && links[0].href === "https://rvanhooijdonk-png.github.io/blog-voorstellen/groeibord/" && links[0].rel === "noopener");
check("javascript-link krijgt geen knop", !links.some(a => String(a.href).startsWith("javascript:")));
check("ok is groen, let_op is oranje", knopen.some(n => n.className === "pil goed" && n.textContent === "ok") && knopen.some(n => n.className === "pil let" && n.textContent === "let op"));
check("blok zichtbaar met tegels", els["borden-blok"].hidden === false);
teken({ borden: [{ naam: "C", eigenaar: "SEA", link: "https://rvanhooijdonk-png.github.io/x/", bijgewerkt: null, stand: "link", reden: "geen status gekoppeld" }] });
const k2 = alle(els.borden);
check("bord zonder status: grijze pil 'geen status' en wel een knop", k2.some(n => n.className === "pil uit" && n.textContent === "geen status") && k2.some(n => n.tag === "a" && n.href === "https://rvanhooijdonk-png.github.io/x/"));
teken({}); check("blok verborgen zonder tegels", els["borden-blok"].hidden === true);
console.log(fout ? "\nER ZIJN FOUTEN" : "\nALLE PROEVEN GROEN"); process.exit(fout);
