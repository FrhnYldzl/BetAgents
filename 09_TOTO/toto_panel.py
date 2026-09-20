"""
TOTO · PANEL SAYFALARI — BetAgents Desk içinde AYRI bölüm ("SÜPER TOTO")
======================================================================
app_v2.py yalnız gezinmeye bu sayfaları ekler; çizim burada. Veri yalnız
`toto_*` tablolarından ve 09_TOTO dosyalarından okunur. Bir hata olursa yalnız
Toto sayfası hata gösterir — BetAgents sayfaları etkilenmez (app_v2 sarmalar).

  bu_hafta      Bu hafta ne oynayalım, neden? (kupon · gerekçe · takvim · hatırlatıcı)
  ajan_pazari   Hangi ajanın sesi ne kadar, neden?
  gecmis_test   Bu sistemle geçmişte oynasaydık ne olurdu?
  arsiv         Geçen haftalar: ne oynadık, ne oldu, ne öğrendik?
"""
from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

import streamlit as st  # noqa: E402

import toto_db  # noqa: E402

TR = timezone(timedelta(hours=3))
SEC = ("1", "0", "2")
AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
GUNLER = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

CSS = """<style>
.tt-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:var(--s3);}
.tt-kutu{border:1px solid var(--line);border-radius:var(--r);padding:12px 14px;background:var(--panel-2);}
.tt-kutu .et{font-family:'JetBrains Mono',monospace;font-size:var(--t-etiket);letter-spacing:var(--ls-etiket);
  text-transform:uppercase;color:var(--muted);font-weight:var(--w-etiket);}
.tt-kutu .dg{font-family:'JetBrains Mono',monospace;font-size:var(--t-okuma);color:var(--ink);margin-top:4px;}
.tt-kutu .al{font-size:var(--t-alt);color:var(--muted);margin-top:2px;line-height:1.45;}
table.v2 td.tt-i{text-align:center;font-family:'JetBrains Mono',monospace;font-weight:700;width:34px;}
table.v2 td.tt-on{background:var(--brand-fill);color:var(--brand);}
table.v2 td.tt-off{color:var(--line-2);}
.tt-cizgi{height:6px;border-radius:3px;background:var(--panel-3);position:relative;overflow:hidden;}
.tt-cizgi b{position:absolute;left:0;top:0;bottom:0;background:var(--brand);}
.tt-not{font-size:var(--t-alt);color:var(--ink-2);line-height:1.55;}
.tt-uyari{border-left:3px solid var(--brand);padding:8px 12px;background:var(--brand-fill);
  font-size:var(--t-alt);color:var(--ink);line-height:1.5;margin:8px 0;}
table.v2 td.tt-ger{font-size:var(--t-alt);color:var(--ink-2);line-height:1.45;}
table.v2 td.tt-ger b{color:var(--ink);font-weight:600;}
.tt-kod{font-family:'JetBrains Mono',monospace;font-size:var(--t-alt);background:var(--panel-2);
  border:1px solid var(--line);padding:8px 10px;border-radius:var(--r);white-space:pre-wrap;word-break:break-word;}
</style>"""


# ── yardımcılar ───────────────────────────────────────────────────
def _e(x) -> str:
    return html.escape(str(x))


def _tl(v: float | None, kisa: bool = False) -> str:
    if v is None:
        return "—"
    if kisa and abs(v) >= 1e6:
        return f"{v / 1e6:,.1f} M TL".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{v:,.0f} TL".replace(",", ".")


def _pct(v: float | None, n: int = 0) -> str:
    return "—" if v is None else (f"%{v * 100:.{n}f}").replace(".", ",")


def _tarih(iso: str | None) -> str:
    if not iso:
        return "—"
    t = datetime.fromisoformat(iso[:19])
    return f"{t.day} {AYLAR[t.month - 1]} {GUNLER[t.weekday()]} {t:%H:%M}"


def _kalan(iso: str | None) -> str:
    if not iso:
        return "—"
    t = datetime.fromisoformat(iso[:19]).replace(tzinfo=TR)
    s = (t - datetime.now(TR)).total_seconds()
    if s <= 0:
        return "kapandı"
    g, s = divmod(int(s), 86400)
    sa = s // 3600
    return (f"{g} gün {sa} sa" if g else f"{sa} sa {(s % 3600) // 60} dk")


def _kart(baslik: str, govde: str, ipucu: str = "") -> None:
    st.markdown("<div class='v2card'><div class='v2head'><h2>" + baslik + "</h2>" +
                (f"<div class='hint'>{ipucu}</div>" if ipucu else "") + "</div><div class='v2body'>" + govde +
                "</div></div>", unsafe_allow_html=True)


@st.cache_data(ttl=60, show_spinner=False)
def _son_analiz():
    """Panel yalnız OKUR — tabloları Toto zamanlayıcısı kurar (DDL web sürecinde koşmaz)."""
    try:
        return toto_db.son_analiz()
    except Exception:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def _haftalar():
    try:
        return toto_db.haftalar_tablo(40)
    except Exception:
        return []


def _ilk_gorulme(hid) -> str:
    try:
        for h in _haftalar():
            if h["hafta_id"] == hid and h.get("ilk_gorulme"):
                t = datetime.fromisoformat(h["ilk_gorulme"][:19]).replace(tzinfo=timezone.utc).astimezone(TR)
                return f" · sistem ilk gördü: {_tarih(t.strftime('%Y-%m-%dT%H:%M:%S'))}"
    except Exception:
        pass
    return ""


def ics(A: dict) -> str:
    """Takvim dosyası: kapanıştan 24 ve 3 saat önce hatırlatır."""
    h = A["hafta"]
    kap = datetime.fromisoformat(h["kapanis"][:19]).replace(tzinfo=TR).astimezone(timezone.utc)
    ilk = A["maclar"][0] if A.get("maclar") else {}
    f = lambda t: t.strftime("%Y%m%dT%H%M%SZ")
    aciklama = (f"Spor Toto {h['sezon']} {h['ad']} · son oynama {_tarih(h['kapanis'])} (TR)\\n"
                f"İlk maç: {ilk.get('ev', '')} - {ilk.get('dep', '')}\\n"
                "Kuponu BetAgents Desk > SÜPER TOTO > Bu Hafta sayfasından al.")
    return "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//BetAgents//Toto//TR", "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT", f"UID:toto-{h['id']}@betagents", f"DTSTAMP:{f(datetime.now(timezone.utc))}",
        f"DTSTART:{f(kap - timedelta(minutes=30))}", f"DTEND:{f(kap)}",
        f"SUMMARY:Spor Toto {h['ad']} — son oynama {kap.astimezone(TR):%H:%M}",
        f"DESCRIPTION:{aciklama}",
        "BEGIN:VALARM", "TRIGGER:-PT24H", "ACTION:DISPLAY", "DESCRIPTION:Toto: son 24 saat", "END:VALARM",
        "BEGIN:VALARM", "TRIGGER:-PT3H", "ACTION:DISPLAY", "DESCRIPTION:Toto: son 3 saat — kuponu kontrol et",
        "END:VALARM", "END:VEVENT", "END:VCALENDAR", ""])


# ── 1 · BU HAFTA ──────────────────────────────────────────────────
def bu_hafta(baslik) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    A = _son_analiz()
    if not A:
        baslik("Süper Toto", "Analiz henüz yok — Toto zamanlayıcısı ilk koşusunu yapınca burada görünür.", [])
        return
    h = A["hafta"]
    havuz15 = A["havuz"].get("15") if isinstance(A["havuz"], dict) else None
    havuz15 = havuz15 if havuz15 is not None else A["havuz"].get(15)
    kpi = [{"ad": "Kapanış", "deger": _kalan(h["kapanis"])},
           {"ad": "15 havuzu", "deger": _tl(havuz15, True) if A["devir_kesin"] else
            _tl(havuz15, True) + " / " + _tl(havuz15 + (A["devir_senaryo"] or {}).get("15", 0), True)},
           {"ad": "iddaa fiyatı", "deger": f"{A['iddaa_kapsam']}/15"},
           {"ad": "Kolon", "deger": _tl(A["fiyat"])}]
    baslik(f"{h['sezon']} · {h['ad']}", "Olasılığı ajan pazarı, kalabalığın ne oynadığını kalabalık modeli "
           "söyler; kupon ikisinin farkından kurulur. Her işaretin gerekçesi aşağıda.", kpi)

    # takvim + nasıl oynanır
    ilk = A["maclar"][0]
    devir_metni = (f"Devir kesin: 15'liğe <b>{_tl((A['devir'] or {}).get('15', 0), True)}</b>." if A["devir_kesin"]
                   else f"<b>{_e(A['onceki_hafta']['ad'])} henüz sonuçlanmadı.</b> O hafta 15 bilen çıkmazsa bu haftanın "
                        f"15 havuzuna yaklaşık <b>{_tl((A['devir_senaryo'] or {}).get('15', 0), True)}</b> devir eklenir; "
                        "sonuç gelince analiz kendiliğinden yenilenir.")
    govde = ("<div class='tt-grid'>"
             f"<div class='tt-kutu'><div class='et'>Son oynama</div><div class='dg'>{_tarih(h['kapanis'])}</div>"
             f"<div class='al'>İlk maç {_e(ilk['ev'])} - {_e(ilk['dep'])} · kalan {_kalan(h['kapanis'])}</div></div>"
             f"<div class='tt-kutu'><div class='et'>Maçlar</div><div class='dg'>{_tarih(A['maclar'][0]['tarih'])[:6]} → "
             f"{_tarih(max(m['tarih'] for m in A['maclar']))[:6]}</div><div class='al'>15 maç · sonuç maç sonunda (90 dk)</div></div>"
             f"<div class='tt-kutu'><div class='et'>Nerede</div><div class='dg'>iddaa · bayi</div>"
             "<div class='al'>iddaa.com Spor Toto, yetkili uygulamalar (Nesine, Bilyoner, Misli…) ya da Spor Toto bayisi</div></div>"
             f"<div class='tt-kutu'><div class='et'>Satışa açılış</div><div class='dg'>{_tarih(A.get('satis_acilis'))}</div>"
             f"<div class='al'>Önceki program kapanınca açılır (oyun planı m.9/1){_ilk_gorulme(h['id'])}</div></div>"
             f"<div class='tt-kutu'><div class='et'>Analiz</div><div class='dg'>{_e(A['olusturma'][11:16])}</div>"
             f"<div class='al'>{_e(A['olusturma'][:10])} · günde 3 kez + kapanışa 3 saat kala son kez</div></div>"
             "</div>"
             f"<div class='tt-uyari'>{devir_metni}</div>"
             "<div class='tt-not'><b>Nasıl oynanır.</b> 15 maçın her birine 1 (ev), 0 (beraberlik) ya da 2 (deplasman) "
             "işaretlenir. Bir maça birden çok işaret koymak <b>sistem</b> oynamaktır: kolon sayısı çarpılır "
             "(ör. 3 maçta ikili = 2×2×2 = 8 kolon). Kolon " + _tl(A["fiyat"]) + ", bir bilette en çok 2.500 kolon. "
             "12, 13, 14 ve 15 doğru ödül alır; her kolon yalnız bildiği EN ÜST dereceden ödenir. Oyun ilk maçın "
             "başlamasıyla kapanır.</div>")
    _kart("Oynama takvimi", govde, "Spor Toto oyun planı m.8–11")
    st.download_button("Takvime ekle (.ics · 24 ve 3 saat önce hatırlatır)", data=ics(A).encode("utf-8"),
                       file_name=f"toto-{h['id']}.ics", mime="text/calendar", key="tt_ics")

    # kupon seçici
    prof_ad = {"15_AVCISI": "15 Avcısı", "DENGELİ": "Dengeli", "FAVORİ": "Favori"}
    c1, c2 = st.columns([3, 2])
    with c1:
        prof = st.radio("Profil", list(prof_ad), format_func=lambda x: prof_ad[x], horizontal=True, key="tt_prof")
    butceler = sorted({k["butce"] for k in A["kuponlar"]})
    with c2:
        B = st.selectbox("Bütçe (en çok kolon)", butceler, index=0, key="tt_butce",
                         format_func=lambda b: f"{b} kolon · en çok {_tl(b * A['fiyat'])}")
    k = next(x for x in A["kuponlar"] if x["profil"] == prof and x["butce"] == B)
    satirlar = ""
    for i, m in enumerate(A["maclar"]):
        isr = set(k["S"][i])
        hucre = "".join(f"<td class='tt-i {'tt-on' if j in isr else 'tt-off'}'>{SEC[j]}</td>" for j in range(3))
        ger = k["gerekce"][i].split(" — ", 1)[-1] if k.get("gerekce") else ""
        satirlar += (f"<tr><td class='rk'>{i + 1}</td><td><span class='ag'>{_e(m['ev'])} - {_e(m['dep'])}</span>"
                     f"<span class='sb'>{_tarih(m['tarih'])} · {_e(m['turnuva'])}</span></td>{hucre}"
                     f"<td class='tt-ger'>{_e(ger)}</td></tr>")
    ozet = ("<div class='tt-grid' style='margin-bottom:12px'>"
            f"<div class='tt-kutu'><div class='et'>Kupon</div><div class='dg'>{k['kolon']} kolon</div>"
            f"<div class='al'>{_tl(k['maliyet'])}</div></div>"
            f"<div class='tt-kutu'><div class='et'>15 şansı</div><div class='dg'>{_pct(k['p15'], 3)}</div>"
            f"<div class='al'>{_e(k['sans15'])} · 15 gelirse ≈ {_tl(k['odul15'], True)}</div></div>"
            f"<div class='tt-kutu'><div class='et'>12+ şansı</div><div class='dg'>{_pct(k['p12p'], 1)}</div>"
            f"<div class='al'>{_e(k['sans12'])}</div></div>"
            f"<div class='tt-kutu'><div class='et'>Beklenen dönüş</div><div class='dg'>{k['ev_tl']:.2f} / TL</div>"
            f"<div class='al'>{'devir gelirse ' + format(k['ev_tl_devirli'], '.2f') + ' / TL · ' if k.get('ev_tl_devirli') else ''}"
            "ortalama oyuncu ≈ 0,64</div></div></div>")
    kopya = " · ".join(f"{i + 1}:{'/'.join(SEC[j] for j in k['S'][i])}" for i in range(15))
    _kart(f"Kupon · {prof_ad[prof]}", ozet + f"<div class='tt-not'>{_e(k['profil_aciklama'])}</div>"
          "<table class='v2' style='margin-top:10px'><thead><tr><th></th><th>Maç</th><th>1</th><th>0</th><th>2</th>"
          f"<th>Neden</th></tr></thead><tbody>{satirlar}</tbody></table>"
          f"<div class='et' style='margin-top:12px'>Kupona geçir</div><div class='tt-kod'>{_e(kopya)}</div>",
          f"{k['kolon']} kolon · {_tl(k['maliyet'])}")
    st.markdown("<div class='tt-uyari'><b>Beklenti ayarı.</b> Beklenen dönüşün büyük kısmı 14 ve 15 isabetinden gelir. "
                "Bunlar tek haftada çok seyrektir; kâr ancak uzun sürede ve seyrek büyük vuruşlarla gerçekleşir. "
                "Geçmiş Test sayfası bunun geçmişte nasıl sonuçlandığını gösterir. Bu bir yatırım tavsiyesi değildir; "
                "karar ve bütçe sınırı sizindir.</div>", unsafe_allow_html=True)

    # maç analizi
    rows = ""
    for i, m in enumerate(A["maclar"]):
        P, Q = A["P"][i], A["Q"][i]
        g = m["gerekce"]
        idd = m.get("iddaa") or {}
        oran = " / ".join(f"{x:.2f}" for x in idd["oran"]) if idd.get("oran") else "fiyat yok"
        pq = " · ".join(f"{SEC[j]} {_pct(P[j])}/{_pct(Q[j])}" for j in range(3))
        rows += (f"<tr><td class='rk'>{i + 1}</td><td><span class='ag'>{_e(m['ev'])} - {_e(m['dep'])}</span>"
                 f"<span class='sb'>{_e(m['turnuva'])} · bilgi: {_e(m['bilgi'])}</span></td>"
                 f"<td class='n'>{_e(oran)}</td><td class='tt-ger'>{pq}</td>"
                 f"<td class='n'>{_e(g['deger'])} · {max(g['deger_orani']):.2f}</td></tr>")
    _kart("Maç analizi", "<div class='tt-not'>Her maçta: gerçek olasılık (ajan pazarı) / kalabalığın işaretleme "
          "payı. Değer oranı = olasılık ÷ kalabalık; 1'in üstü, o sonucun kalabalıkça az oynandığı demektir.</div>"
          "<table class='v2' style='margin-top:8px'><thead><tr><th></th><th>Maç</th><th>iddaa 1/0/2</th>"
          f"<th>Olasılık / kalabalık</th><th>Değerli</th></tr></thead><tbody>{rows}</tbody></table>",
          "P / q")
    secenek = [f"{i + 1}. {m['ev']} - {m['dep']}" for i, m in enumerate(A["maclar"])]
    sec = st.selectbox("Maç ayrıntısı · ajan görüşleri", secenek, index=0, key="tt_mac_sec")
    i = secenek.index(sec)
    m = A["maclar"][i]
    sat = "".join(f"<div class='tt-not'>• {_e(x)}</div>" for x in m["gerekce"]["satirlar"])
    aj = ""
    for t in m.get("islemler") or []:
        aj += (f"<tr><td class='ag'>{_e(t['ajan'])}</td><td class='n'>{_pct(t['pay'])}</td>"
               f"<td class='n'>{' · '.join(_pct(x) for x in t['gorus'])}</td>"
               f"<td class='n'>{_e(t['aldigi'])} (+{t['fark'] * 100:.0f} puan)</td></tr>")
    notlar = m.get("not") or {}
    ek = []
    if notlar.get("elo"):
        ek.append(f"Elo {notlar['elo'][0]} - {notlar['elo'][1]}")
    if "h2h_n" in notlar:
        ek.append(f"son 8 yılda aralarındaki maç: {notlar['h2h_n']}")
    idd = m.get("iddaa") or {}
    if idd.get("oran"):
        ek.append("iddaa " + " / ".join(f"{x:.2f}" for x in idd["oran"]))
    kd = notlar.get("kadro")
    kadro_html = ""
    if kd:
        kadro_html = ("<table class='v2' style='margin-top:10px'><thead><tr><th>Eksik oyuncular</th>"
                      f"<th>{_e(m['ev'])}</th><th>{_e(m['dep'])}</th></tr></thead><tbody>"
                      f"<tr><td>Kaç oyuncu</td><td class='n'>{kd['ev_eksik']}</td><td class='n'>{kd['dep_eksik']}</td></tr>"
                      f"<tr><td>Ağırlık (kesin yok = 1)</td><td class='n'>{_e(kd['ev_agirlik'])}</td>"
                      f"<td class='n'>{_e(kd['dep_agirlik'])}</td></tr>"
                      f"<tr><td>İsimler</td><td class='tt-ger'>{_e(', '.join(kd['ev_liste']) or '—')}</td>"
                      f"<td class='tt-ger'>{_e(', '.join(kd['dep_liste']) or '—')}</td></tr></tbody></table>")
    elif notlar.get("kadro_hata"):
        kadro_html = "<div class='sb' style='margin-top:8px'>Kadro verisi alınamadı.</div>"
    kr = m.get("karne") or {}
    kev, kdp = kr.get("ev", {}), kr.get("dep", {})
    def _k(d, a, b=None):
        v = d.get(a)
        if v is None:
            return "—"
        v = f"{v:.2f}".replace(".", ",") if isinstance(v, float) else f"{v}"
        return _e(v + (f" · {d.get(b)}" if b and d.get(b) else ""))
    karne = ("<table class='v2' style='margin-top:10px'><thead><tr><th>Takım karnesi</th>"
             f"<th>{_e(m['ev'])}</th><th>{_e(m['dep'])}</th></tr></thead><tbody>"
             f"<tr><td>Elo · sıra</td><td class='n'>{_k(kev, 'elo', 'elo_sira')}</td><td class='n'>{_k(kdp, 'elo', 'elo_sira')}</td></tr>"
             f"<tr><td>Hücum · sıra</td><td class='n'>{_k(kev, 'hucum', 'hucum_sira')}</td><td class='n'>{_k(kdp, 'hucum', 'hucum_sira')}</td></tr>"
             f"<tr><td>Savunma · sıra (düşük iyi)</td><td class='n'>{_k(kev, 'savunma', 'savunma_sira')}</td><td class='n'>{_k(kdp, 'savunma', 'savunma_sira')}</td></tr>"
             f"<tr><td>Toto'da görünme</td><td class='n'>{_k(kev, 'toto_n')}</td><td class='n'>{_k(kdp, 'toto_n')}</td></tr>"
             f"<tr><td>Toto'daki son 5 (G/B/M)</td><td class='n'>{_k(kev, 'toto_son')}</td><td class='n'>{_k(kdp, 'toto_son')}</td></tr>"
             "</tbody></table>")
    _kart(f"{i + 1}. {_e(m['ev'])} - {_e(m['dep'])}", sat + "<table class='v2' style='margin-top:8px'><thead><tr>"
          "<th>Ajan</th><th>Pazar payı</th><th>Görüş 1/0/2</th><th>Fiyata göre aldığı</th></tr></thead>"
          f"<tbody>{aj}</tbody></table>{karne}{kadro_html}<div class='sb' style='margin-top:6px'>{_e(' · '.join(ek))}</div>",
          _tarih(m["tarih"]))


# ── 2 · AJAN PAZARI ───────────────────────────────────────────────
def ajan_pazari(baslik) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    A = _son_analiz()
    CZ = (A or {}).get("cuzdan") or {}
    if CZ and "KULUP" not in CZ:
        CZ = {"KULUP": CZ}
    W = CZ.get("KULUP") or {}
    baslik("Ajan Pazarı", "Ajanlar her maçta inandıkları kadar pozisyon alır; haklı çıkanın cüzdanı büyür, pazar "
           "fiyatı servet ağırlıklıdır (Kelly bahisçileri pazarı). Kulüp ve milli maçlar ayrı pazarlarda yarışır.",
           [{"ad": a, "deger": _pct(w)} for a, w in sorted(W.items(), key=lambda x: -x[1])])
    acik = ("<div class='tt-not'><b>Nasıl çalışır.</b> Her maç 3 sonuçlu bir pazardır. Her ajan servetinin %10'unu "
            "kendi olasılıklarına göre sonuçlara dağıtır. Pazar fiyatı = servetle ağırlıklı görüş ortalaması. "
            "Maç bitince cüzdan, ajanın doğru sonuca verdiği olasılık ÷ pazar fiyatı oranında büyür ya da küçülür. "
            "Böylece geçmişte gerçekten bilgi katan ajanın sesi kendiliğinden artar, boş konuşan fakirleşir. "
            "Noterle belirlenen maçlar cüzdanları değiştirmez.</div>"
            "<div class='tt-not' style='margin-top:8px'><b>Ajanlar.</b> PİYASA: iddaa'nın marjı temizlenmiş fiyatı. "
            "ELO: takım gücü (kulüpte lig içi, millide Dünya Futbol Elo kuralları). FORM: son bir yılın gol verisinden "
            "hücum/savunma modeli. H2H: aralarındaki maçlar (Elo'ya doğru büzülmüş).</div>")
    def _bar(Wx):
        b = ""
        for a, w in sorted(Wx.items(), key=lambda x: -x[1]):
            b += (f"<tr><td class='ag'>{_e(a)}</td><td style='width:60%'><div class='tt-cizgi'><b style='width:{w * 100:.1f}%'>"
                  f"</b></div></td><td class='n'>{_pct(w, 1)}</td></tr>")
        return b
    ek = ("<div class='tt-not' style='margin-top:8px'><b>Neden iki pazar.</b> Geçmiş testte milli maçlarda en isabetli "
          "ajan H2H çıktı (log-kayıp 0,813), kulüp maçlarında piyasa fiyatı. Ortak cüzdan H2H'nin sesini kulüp "
          "maçlarındaki başarısına göre kısıyordu; ayrı milli pazar bu kaybı giderdi.</div>")
    _kart("Cüzdanlar · kulüp maçları", acik + ek + f"<table class='v2' style='margin-top:10px'><tbody>{_bar(W)}</tbody></table>",
          "2022–2026 geçmişinde öğrenildi · her hafta güncellenir")
    if CZ.get("MILLI"):
        _kart("Cüzdanlar · milli maçlar", f"<table class='v2'><tbody>{_bar(CZ['MILLI'])}</tbody></table>",
              "kesir 0,3 · 329 milli maçla öğrenildi")
    try:
        gec = toto_db.cuzdan_gecmisi()
    except Exception:
        gec = []
    if gec:
        import pandas as pd
        df = pd.DataFrame(gec, columns=["hafta", "ajan", "servet"])
        df = df[~df["ajan"].str.startswith("M:")].pivot(index="hafta", columns="ajan", values="servet")
        st.line_chart(df)
    if A:
        rows = ""
        for m in A["maclar"]:
            for t in (m.get("islemler") or [])[:4]:
                rows += (f"<tr><td class='rk'>{m['sira']}</td><td>{_e(m['ev'])} - {_e(m['dep'])}</td><td>{_e(t['ajan'])}</td>"
                         f"<td class='n'>{_pct(t['pay'])}</td><td class='n'>{_e(t['aldigi'])} +{t['fark'] * 100:.0f}</td></tr>")
        _kart("Bu haftanın işlemleri", "<table class='v2'><thead><tr><th></th><th>Maç</th><th>Ajan</th><th>Pay</th>"
              f"<th>Fiyata göre aldığı</th></tr></thead><tbody>{rows}</tbody></table>", "görüş − pazar fiyatı")


# ── 3 · GEÇMİŞ TEST ───────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def _gt():
    p = KOK / "geri_test_ozet.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def gecmis_test(baslik) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    G = _gt()
    if not G:
        baslik("Geçmiş Test", "Geçmiş test özeti henüz yok.", [])
        return
    baslik("Geçmiş Test", G.get("alt", ""), [{"ad": x["ad"], "deger": x["deger"]} for x in G.get("kpi", [])])
    for blok in G.get("bloklar", []):
        _kart(blok["baslik"], blok["html"], blok.get("ipucu", ""))


# ── 4 · ARŞİV ─────────────────────────────────────────────────────
def arsiv(baslik) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    baslik("Toto Arşivi", "Geçen haftalar: ne önerdik, ne oldu, ne öğrendik.", [])
    try:
        dersler = toto_db.dersler(20)
        kup = toto_db.kuponlar()
    except Exception:
        dersler, kup = [], []
    if not dersler:
        st.markdown("<div class='v2bos'>Henüz sonuçlanmış Toto haftası yok — ilk hafta kapanınca burada ders yazılır.</div>",
                    unsafe_allow_html=True)
    for d in dersler:
        maclar = "".join(
            f"<tr><td class='rk'>{m['sira']}</td><td>{_e(m['mac'])}</td><td class='n'>{_e(m['sonuc'])}</td>"
            f"<td class='n'>{_pct(m['p'])}</td><td class='n'>{_pct(m['q'])}</td>"
            f"<td class='sb'>{'SÜRPRİZ · ' if m['surpriz'] else ''}{'noter · ' if m['noter'] else ''}"
            f"{_e(', '.join(m['bilen_ajan']) or '—')}</td></tr>" for m in d.get("mac", []))
        _pa = {"15_AVCISI": "15 Avcısı", "DENGELİ": "Dengeli", "FAVORİ": "Favori"}
        kp = "".join(f"<tr><td>{_e(_pa.get(k['profil'], k['profil']))}</td><td class='n'>{k['kolon']}</td><td class='n'>{k['dogru']}</td>"
                     f"<td class='n'>{_tl(k['odeme'])}</td><td class='n'>{_tl(k['maliyet'])}</td></tr>"
                     for k in d.get("kupon", []))
        kal = d.get("kalabalik") or {}
        ek = (f"Kalabalık modeli (sonuç bilinince): 15/14/13/12 kazanan tahmini {kal.get('tahmin')} · gerçek "
              f"{kal.get('gercek')}" if kal else "")
        ozet_satir = "".join(f"<div class='tt-not'>• {_e(x.replace('15_AVCISI', '15 Avcısı').replace('DENGELİ', 'Dengeli').replace('FAVORİ', 'Favori'))}</div>"
                             for x in d.get("ozet", []))
        ust = ozet_satir or f"<div class='tt-not'>Sürpriz sonuç: {d.get('surpriz_sayisi', '—')}. {ek}</div>"
        _kart(f"{_e(d['hafta'])}", ust +
              "<table class='v2' style='margin-top:8px'><thead><tr><th>Profil</th><th>Kolon</th><th>En çok doğru</th>"
              f"<th>Ödeme</th><th>Maliyet</th></tr></thead><tbody>{kp}</tbody></table>"
              "<table class='v2' style='margin-top:8px'><thead><tr><th></th><th>Maç</th><th>Sonuç</th><th>Olasılık</th>"
              f"<th>Kalabalık</th><th>Not · bilen ajan</th></tr></thead><tbody>{maclar}</tbody></table>", "kâğıt kupon")
    try:
        kay = toto_db.son_kayitlar(15)
    except Exception:
        kay = []
    if kay:
        _kart("Olay günlüğü", "".join(f"<div class='sb'>{_e(t[:16])} · {_e(tr)} · {_e(m)}</div>" for t, tr, m in kay))
