"""
PROJE ENDEKSLİ ÖLÇÜM — eski İnceleme / Çakışma / Kasa / OPUS 5'in yerine
========================================================================
Kullanıcı kararı (15.11.2026):
  "Analiz kısmına gerek yok, bunu proje özelinde odaklayacağız;
   ajan ve kupon düzeyinde yapmak lazım, proje endeksli."

Her tablo TEK soruya bağlı: plan tutuyor mu?

⚠️ BU SAYFANIN VAR OLMA SEBEBİ — ölçüldü (15.11.2026):
Ajan karnesini kupon AYAKLARINDAN saymak gözlem sayısını 6–9 kat şişiriyor.
Aynı bahis onlarca kupona giriyor. TEMKINLI_V1'in "59 ayağı" aslında 10
tekil bahis; üç kaybeden bahis 12, 13 ve 19 kuponda tekrarlanmış. Ayakla
ölçülen isabet %11,9 görünüyordu — tekil bahisle %30.
Bu yüzden ajan tablosu TEKİL BAHİS sayar ve tekrar katsayısını yazar.
"""
from __future__ import annotations

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent
for _p in (str(KOK), str(KOK.parent / "02_VERI")):
    if _p not in sys.path:
        sys.path.append(_p)

import streamlit as st  # noqa: E402

import proje_veri as PV  # noqa: E402

# Kanıt eşiği kasa'dan okunur — burada ayrı bir sayı tutmak, aynı sistemde
# iki farklı "kanıtlandı" tanımı doğururdu.
try:
    from kasa import ASGARI_N
except Exception:
    ASGARI_N = 30


def _pc(v, b: int = 1) -> str:
    return f"{float(v or 0)*100:.{b}f}".replace(".", ",") + "%"


def _sy(v, b: int = 2) -> str:
    """Ondalık ayracı virgül — panelin geri kalanıyla aynı."""
    return f"{float(v or 0):.{b}f}".replace(".", ",")


def _ipc(v, b: int = 1) -> str:
    """İşaretli yüzde, virgüllü."""
    return ("+" if float(v or 0) >= 0 else "−") + \
        f"{abs(float(v or 0))*100:.{b}f}".replace(".", ",") + "%"


# ── veri ──────────────────────────────────────────────────────────
def sekil_tablosu(c) -> list[dict]:
    """Kupon ŞEKLİ başına ölçüm — plan p'siyle karşılaştırmak için."""
    r = c.execute(
        "SELECT ayak, COUNT(*), "
        "       SUM(CASE WHEN durum='kazandi' THEN 1 ELSE 0 END), "
        "       AVG(oran), "
        "       SUM(CASE WHEN durum='kazandi' THEN oran-1 ELSE -1 END) "
        "FROM ferhan_kupon WHERE durum IN ('kazandi','kaybetti') "
        "GROUP BY ayak ORDER BY ayak").fetchall()
    out = []
    for ayak, n, kaz, oo, br in r:
        n, kaz = int(n), int(kaz or 0)
        out.append({"ayak": int(ayak), "n": n, "kazanan": kaz,
                    "p": kaz / n if n else 0.0,
                    "ort_oran": float(oo or 0),
                    "roi": (float(br or 0) / n) if n else 0.0})
    return out


def bant_tablosu(c) -> list[dict]:
    """HEDEF BANDINA göre ölçüm — kullanıcı kararı 15.11.2026.

    "Tekli maçlar var, eksiklik var... böyle bağımsız şekilde amaca hizmet
     etmiyorlar. Hedefi gerçekleştirmeye yönelik kuponlar üretilmeli."

    Şekil (1'li/2'li/3'lü) yanlış eksen: 1,10 oranlı bir tekli de, 1,39
    oranlı bir üçlü de planın 1,60-2,00 bandına hiç girmiyor. Asıl soru
    kuponun HEDEFE oturup oturmadığı.
    """
    out = []
    for ad, kos in (("hedef bandı ALTI (<1,60)", "oran < 1.60"),
                    ("HEDEF BANDI (1,60–2,00)",
                     "oran >= 1.60 AND oran <= 2.00"),
                    ("hedef bandı ÜSTÜ (>2,00)", "oran > 2.00")):
        r = c.execute(
            "SELECT COUNT(*), SUM(CASE WHEN durum='kazandi' THEN 1 ELSE 0 END), "
            "       AVG(oran), AVG(ayak), "
            "       SUM(CASE WHEN durum='kazandi' THEN oran-1 ELSE -1 END) "
            "FROM ferhan_kupon WHERE durum IN ('kazandi','kaybetti') "
            f"AND {kos}").fetchone()
        n = int(r[0] or 0)
        if not n:
            continue
        out.append({"ad": ad, "n": n, "p": int(r[1] or 0) / n,
                    "ort_oran": float(r[2] or 0), "ort_ayak": float(r[3] or 0),
                    "roi": float(r[4] or 0) / n,
                    "hedef": "HEDEF" in ad})
    return out


def ajan_tablosu(c) -> list[dict]:
    """Ajan başına TEKİL bahis karnesi — ayak değil, bahis sayılır."""
    r = c.execute(
        "SELECT a.ajan, COUNT(*), COUNT(DISTINCT a.bet_id) "
        "FROM ferhan_kupon_ayak a "
        "JOIN paper_bets b ON CAST(b.bet_id AS TEXT) = a.bet_id "
        "WHERE b.status IN ('won','lost') AND a.ajan IS NOT NULL "
        "GROUP BY a.ajan").fetchall()
    out = []
    for ajan, ayak, tekil in r:
        t = c.execute(
            "SELECT COUNT(*), SUM(CASE WHEN b.status='won' THEN 1 ELSE 0 END), "
            "       AVG(b.odds) "
            "FROM (SELECT DISTINCT bet_id FROM ferhan_kupon_ayak "
            "      WHERE ajan = ?) d "
            "JOIN paper_bets b ON CAST(b.bet_id AS TEXT) = d.bet_id "
            "WHERE b.status IN ('won','lost')", (ajan,)).fetchone()
        n, kaz, oo = int(t[0] or 0), int(t[1] or 0), float(t[2] or 0)
        if not n:
            continue
        ima = (1.0 / oo) if oo > 1 else 0.0
        out.append({"ajan": str(ajan), "ayak": int(ayak),
                    "tekil": int(tekil), "tekrar": ayak / max(int(tekil), 1),
                    "n": n, "kazanan": kaz, "p": kaz / n,
                    "ort_oran": oo, "ima": ima, "fark": (kaz / n) - ima})
    out.sort(key=lambda x: -x["n"])
    return out


def yogunlasma(c, en_cok: int = 8) -> list[dict]:
    """Tek bahis kaç kuponda? Yoğunlaşma riski burada görünür."""
    r = c.execute(
        "SELECT a.bet_id, COUNT(*) k, MIN(b.home_team), MIN(b.away_team), "
        "       MIN(b.market), MIN(b.odds), MIN(b.status) "
        "FROM ferhan_kupon_ayak a "
        "JOIN paper_bets b ON CAST(b.bet_id AS TEXT) = a.bet_id "
        "GROUP BY a.bet_id ORDER BY k DESC LIMIT ?", (en_cok,)).fetchall()
    return [{"kupon": int(x[1]), "ev": x[2], "dep": x[3], "market": x[4],
             "oran": float(x[5] or 0), "durum": x[6]} for x in r]


# ── sayfa ─────────────────────────────────────────────────────────
def olcum(sayfa_basligi):
    try:
        import db
        import ferhan_kupon as FK
        c = db.connect()
        try:
            FK.kur(c)
            sekil = sekil_tablosu(c)
            bant = bant_tablosu(c)
            ajan = ajan_tablosu(c)
            yog = yogunlasma(c)
            # Kalibrasyon — eski "Kuponlar Ferhan" sayfasından taşındı
            # (sayfa 15.11.2026'da kaldırıldı; üretim tarafı defterle
            # çakışıyordu, kalibrasyon ise başka hiçbir yerde yoktu).
            kal = FK.karne(c)
        finally:
            c.close()
    except Exception as e:
        st.markdown(f"<div class='v2bos'>Ölçüm okunamadı: "
                    f"{type(e).__name__}: {e}</div>", unsafe_allow_html=True)
        return

    tn = sum(x["n"] for x in sekil)
    tk = sum(x["kazanan"] for x in sekil)
    tp = (tk / tn) if tn else 0.0
    troi = (sum(x["roi"] * x["n"] for x in sekil) / tn) if tn else 0.0
    sayfa_basligi(
        "Proje · Ölçüm",
        "Kupon hedefe oturuyor mu, hangi ajan taşıyor — proje endeksli.",
        [{"ad": "Sonuçlanmış kupon", "deger": str(tn)},
         {"ad": "Ölçülen p", "deger": _pc(tp),
          "cls": "ps" if tp >= PV.PLAN_P else "ng"},
         {"ad": "Plan p", "deger": _pc(PV.PLAN_P, 0)},
         {"ad": "ROI", "deger": _pc(troi),
          "cls": "ps" if troi >= 0 else "ng"}])
    if not tn:
        st.markdown("<div class='v2bos'>Henüz sonuçlanmış kupon yok.</div>",
                    unsafe_allow_html=True)
        return

    # ── 1 · HEDEF BANDI (asıl eksen)
    bantta = sum(x["n"] for x in bant if x["hedef"])
    gov = ("<table class='v2tbl'><thead><tr><th>bant</th><th>n</th>"
           "<th>pay</th><th>isabet</th><th>ort. oran</th><th>ort. ayak</th>"
           "<th>ROI</th></tr></thead><tbody>")
    for x in bant:
        ks = "ps" if x["roi"] >= 0 else "ng"
        ad = ("<b>" + x["ad"] + "</b>") if x["hedef"] else x["ad"]
        gov += ("<tr><td>" + ad + "</td><td>" + str(x["n"]) + "</td><td>"
                + _pc(x["n"] / tn, 0) + "</td><td>" + _pc(x["p"])
                + "</td><td>" + _sy(x["ort_oran"]) + "</td><td>"
                + _sy(x["ort_ayak"], 1) + "</td><td class='" + ks + "'>"
                + _ipc(x["roi"]) + "</td></tr>")
    gov += "</tbody></table>"
    st.markdown(
        "<div class='v2card'><div class='v2head'><h2>Hedef bandı</h2>"
        "<div class='hint'>kupon hedefe oturuyor mu</div></div>"
        "<div class='v2body'>" + gov +
        "<div class='dq' style='margin-top:var(--s3);'>"
        "Sonuçlanmış " + str(tn) + " kuponun yalnız <b>" + str(bantta)
        + "'i</b> (" + _pc(bantta / tn, 0) + ") planın 1,60–2,00 bandında. "
        "Gerisi hedefe hiç yaklaşmıyor — ne kadar isabetli olursa olsun "
        "plandaki getiriyi döndüremez.<br>"
        "<b>Sebebi ölçüldü:</b> üretici hedefe değil ŞEKLE bakıyordu "
        "(1'li, 2'li, 3'lü). 15.11.2026'da hedef odaklı üretime geçildi: "
        "artık hedef sürücü, kaç ayak gerekiyorsa o kadar ayak kuruluyor. "
        "Aşağıdaki şekil tablosu eski rejimin kaydıdır."
        "</div></div></div>", unsafe_allow_html=True)

    # ── 2 · KUPON ŞEKLİ
    gov = ("<table class='v2tbl'><thead><tr><th>şekil</th><th>n</th>"
           "<th>isabet</th><th>ort. oran</th><th>ROI</th>"
           "<th>plan p=%90</th></tr></thead><tbody>")
    for x in sekil:
        tut = x["p"] >= PV.PLAN_P
        ks = "ps" if x["roi"] >= 0 else "ng"
        gov += ("<tr><td><b>" + str(x["ayak"]) + " ayak</b></td><td>"
                + str(x["n"]) + "</td><td>" + _pc(x["p"]) + "</td><td>"
                + _sy(x["ort_oran"]) + "</td><td class='" + ks + "'>"
                + _ipc(x["roi"]) + "</td><td class='"
                + ("ps" if tut else "ng") + "'>"
                + ("tutuyor" if tut else "tutmuyor") + "</td></tr>")
    gov += "</tbody></table>"
    st.markdown(
        "<div class='v2card'><div class='v2head'><h2>Kupon şekli</h2>"
        "<div class='hint'>hangi şekil plana yaklaşıyor</div></div>"
        "<div class='v2body'>" + gov +
        "<div class='sb' style='margin-top:var(--s3);'>Plan tek bir şekil "
        "varsayıyor: p=%90 · oran 1,80. Bir şeklin planı yürütebilmesi için "
        "isabetin ve oranın AYNI ANDA o seviyeye çıkması gerekir; yüksek "
        "isabet düşük oranla gelirse hedefi döndürmez.</div></div></div>",
        unsafe_allow_html=True)

    # ── 3 · AJAN DÜZEYİ
    gov = ("<table class='v2tbl'><thead><tr><th>ajan</th><th>ayak</th>"
           "<th>TEKİL bahis</th><th>tekrar</th><th>tekil isabet</th>"
           "<th>ort. oran</th><th>fiyatın ima ettiği</th><th>fark</th>"
           "</tr></thead><tbody>")
    for x in ajan:
        gov += ("<tr><td><b>" + x["ajan"].rsplit("_", 1)[0] + "</b></td>"
                "<td style='opacity:.55;'>" + str(x["ayak"]) + "</td>"
                "<td><b>" + str(x["n"]) + "</b></td><td>"
                + _sy(x["tekrar"], 1) + "×</td><td>" + _pc(x["p"], 0)
                + "</td><td>" + _sy(x["ort_oran"]) + "</td><td>"
                + _pc(x["ima"], 0) + "</td><td class='"
                + ("ps" if x["fark"] >= 0 else "ng") + "'>"
                + f"{x['fark']*100:+.0f}" + "p</td></tr>")
    gov += "</tbody></table>"
    st.markdown(
        "<div class='v2card'><div class='v2head'><h2>Ajan düzeyi</h2>"
        "<div class='hint'>tekil bahis — ayak değil</div></div>"
        "<div class='v2body'>" + gov +
        "<div class='dq' style='margin-top:var(--s3);'>"
        "<b>Ayak sütunu kanıt sayısı DEĞİL.</b> Aynı bahis onlarca kupona "
        "giriyor; tekrar katsayısı çoğu ajanda 6–9×. Ayakla ölçülen isabet "
        "tek bir bahsin kaderini defalarca sayar ve ajanı olduğundan iyi ya "
        "da kötü gösterir. <b>Tekil bahis</b> sütunu gerçek gözlem "
        "sayısıdır — ve çoğu ajanda hâlâ " + str(ASGARI_N) + "'un "
        "altında, yani kanıtlanmış sayılmaz.<br>"
        "<b>Fark</b> = tekil isabet − fiyatın ima ettiği olasılık. İma "
        "edilen olasılık marj içerdiği için nötr nokta sıfır değil, eksi "
        "birkaç puandır.</div></div></div>", unsafe_allow_html=True)

    # ── 4 · KALİBRASYON — "şans %60 dedim, %60'ı tuttu mu?"
    sat = [x for x in (kal.get("satirlar") or []) if x["n"]]
    if sat:
        nt = sum(x["n"] for x in sat)
        soy = sum(x["soylenen"] * x["n"] for x in sat) / nt
        ger = sum(x["gercek"] * x["n"] for x in sat) / nt
        gov = ("<table class='v2tbl'><thead><tr><th>tip</th><th>ayak</th>"
               "<th>n</th><th>söylenen</th><th>gerçek</th><th>fark</th>"
               "<th>z</th><th>birim getiri</th></tr></thead><tbody>")
        for x in sorted(sat, key=lambda z: -z["n"]):
            zc = "ng" if abs(x["z"]) >= 2 else ""
            gov += ("<tr><td>" + str(x["tip"]) + "</td><td>"
                    + str(x["ayak"]) + "</td><td>" + str(x["n"])
                    + ("" if x["yeterli"] else
                       " <span style='opacity:.5;'>(az)</span>")
                    + "</td><td>" + _pc(x["soylenen"]) + "</td><td>"
                    + _pc(x["gercek"]) + "</td><td>"
                    + f"{x['fark']*100:+.1f}".replace(".", ",") + "p"
                    + "</td><td class='" + zc + "'>"
                    + f"{x['z']:+.2f}".replace(".", ",") + "</td><td class='"
                    + ("ps" if x["getiri"] >= 0 else "ng") + "'>"
                    + _ipc(x["getiri"]) + "</td></tr>")
        gov += "</tbody></table>"
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Kalibrasyon</h2>"
            "<div class='hint'>söylenen şans → gerçekleşen isabet</div>"
            "</div><div class='v2body'>" + gov +
            "<div class='sb' style='margin-top:var(--s3);'>Ağırlıklı "
            "ortalama: <b>söylenen " + _pc(soy) + " → gerçek " + _pc(ger)
            + "</b>.<br>Bu tablo kârı değil <b>dürüstlüğü</b> ölçer: "
            "kupon kaybetse de söylenen şans tutuyorsa sayı doğrudur. "
            "|z| ≥ 2 olan satır, farkın şansla açıklanamadığı yerdir. "
            "Yalnız güncel formül sürümüyle üretilmiş kuponlar sayılır — "
            "eski formülün tahminini bugünün sonuçlarıyla karşılaştırmak "
            "formül değişikliğini kalibrasyon bozukluğu diye raporlardı."
            + (f" Eski sürümde {kal['eski_surum']} kupon var, dışarıda."
               if kal.get("eski_surum") else "")
            + "</div></div></div>", unsafe_allow_html=True)

    # ── 5 · YOĞUNLAŞMA
    gov = ("<table class='v2tbl'><thead><tr><th>maç</th><th>pazar</th>"
           "<th>oran</th><th>sonuç</th><th>kaç kuponda</th></tr></thead>"
           "<tbody>")
    for x in yog:
        d = {"won": "kazandı", "lost": "kaybetti"}.get(x["durum"], "açık")
        ks = ("ps" if x["durum"] == "won"
              else ("ng" if x["durum"] == "lost" else ""))
        gov += ("<tr><td>" + str(x["ev"])[:20] + " – " + str(x["dep"])[:20]
                + "</td><td>" + str(x["market"]) + "</td><td>"
                + _sy(x["oran"]) + "</td><td class='" + ks + "'>" + d
                + "</td><td><b>" + str(x["kupon"]) + "</b></td></tr>")
    gov += "</tbody></table>"
    tepe = max((x["kupon"] for x in yog), default=0)
    st.markdown(
        "<div class='v2card'><div class='v2head'><h2>Yoğunlaşma</h2>"
        "<div class='hint'>tek bahis kaç kuponda</div></div>"
        "<div class='v2body'>" + gov +
        "<div class='sb' style='margin-top:var(--s3);'>En çok tekrarlanan "
        "bahis <b>" + str(tepe) + " kuponda</b>. O kuponlar bağımsız "
        "değildir: maç kaybedince hepsi birden gider. Kupon sayısı "
        "çeşitlilik sanılır, oysa risk tek maçta toplanmıştır."
        "</div></div></div>", unsafe_allow_html=True)
