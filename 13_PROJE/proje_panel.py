"""
PROJE 2027 — panel sayfaları
==============================
Excel'in altı sayfası, ama ELLE GİRİŞ YOK: p, yield ve kupon defteri
canlı veriden gelir. Plan bir temenni değil, ölçüm aleti olsun diye.

Her sayfa `sayfa_basligi` yardımcısını parametre olarak alır (app_v2'nin
_toto_sayfa kalıbı).
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


def _tl(v) -> str:
    return "{:,.0f}".format(float(v or 0)).replace(",", ".") + " ₺"


def _pc(v, b: int = 1) -> str:
    return f"{float(v or 0)*100:.{b}f}".replace(".", ",") + "%"


def _olcum():
    """Defterden ölçülen p ve yield — iki kaynaktan.

    oynanan : gerçekten oynanmış kuponlar (muhasebe)
    tum     : bütün sonuçlanmış kuponlar (kalibrasyon ve geniş örneklem)
    """
    try:
        import db
        import ferhan_kupon as FK
        import finans
        c = db.connect()
        try:
            d = finans.durum(c)
            para = FK.para_karnesi(c)
            r = c.execute(
                "SELECT durum, oran FROM ferhan_kupon "
                "WHERE durum IN ('kazandi','kaybetti')").fetchall()
        finally:
            c.close()
        n = len(r)
        kaz = sum(1 for x in r if x[0] == "kazandi")
        br = [(float(o) - 1 if s == "kazandi" else -1.0) for s, o in r]
        return {"ok": True, "finans": d, "para": para,
                "tum_n": n, "tum_p": (kaz / n) if n else 0.0,
                "tum_yield": (sum(br) / n) if n else 0.0}
    except Exception as e:
        return {"ok": False, "hata": f"{type(e).__name__}: {e}"}


# ──────────────────────────────────────────────────────────────────
def parametreler(sayfa_basligi):
    o = _olcum()
    kpi = [{"ad": "PLAN p", "deger": _pc(PV.PLAN_P, 0)},
           {"ad": "PLAN yield", "deger": _pc(PV.PLAN_YIELD, 0)}]
    if o["ok"] and o["tum_n"]:
        kpi += [{"ad": "ÖLÇÜLEN p", "deger": _pc(o["tum_p"]),
                 "cls": "ps" if o["tum_p"] >= PV.PLAN_P else "ng"},
                {"ad": "ÖLÇÜLEN yield", "deger": _pc(o["tum_yield"]),
                 "cls": "ps" if o["tum_yield"] > 0 else "ng"},
                {"ad": "Kupon", "deger": str(o["tum_n"])}]
    sayfa_basligi("Parametreler",
                  "Planın varsayımları ve defterden ÖLÇÜLEN karşılıkları.",
                  kpi)
    if o["ok"] and o["tum_n"]:
        fark = o["tum_p"] - PV.PLAN_P
        st.markdown(
            "<div class='v2card'><div class='v2body'><div class='dq'>"
            "<b>Planın motor parametresi ölçümle çelişiyor.</b> Plan "
            f"p={_pc(PV.PLAN_P, 0)} · yield {_pc(PV.PLAN_YIELD, 0)} "
            f"varsayıyor; defterde {o['tum_n']} sonuçlanmış kuponda "
            f"p={_pc(o['tum_p'])} · yield {_pc(o['tum_yield'])} ölçüldü. "
            f"Fark <b>{abs(fark)*100:.0f} puan</b>.<br>"
            "Bu sayfa farkı saklamaz: plan sütunu sabit kalır, ölçüm "
            "sütunu defterden gelir. p gerçekten yükselirse tablo "
            "kendiliğinden yeşile döner.</div></div></div>",
            unsafe_allow_html=True)
    gov = ("<table class='v2tbl'><thead><tr><th>parametre</th>"
           "<th>plan</th><th>açıklama</th></tr></thead><tbody>")
    for ad, deger, acik in PV.PARAMETRE_ACIKLAMA:
        v = (_pc(deger) if isinstance(deger, float) and deger <= 1
             else f"{deger:g}".replace(".", ","))
        gov += (f"<tr><td>{ad}</td><td><b>{v}</b></td>"
                f"<td style='opacity:.75;'>{acik}</td></tr>")
    gov += "</tbody></table>"
    st.markdown("<div class='v2card'><div class='v2head'><h2>Plan "
                "parametreleri</h2><div class='hint'>Excel · Parametreler"
                "</div></div><div class='v2body'>" + gov + "</div></div>",
                unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────
def aylik_plan(sayfa_basligi):
    o = _olcum()
    ol_y = o["tum_yield"] if (o["ok"] and o["tum_n"]) else 0.0
    sayfa_basligi("2027 Plan",
                  "Aylık hedef, stake ve bankroll — plan yield'i ile "
                  "ÖLÇÜLEN yield yan yana.",
                  [{"ad": "Yıl hedefi",
                    "deger": _tl(sum(x[2] for x in PV.AYLIK))},
                   {"ad": "Plan yield", "deger": _pc(PV.PLAN_YIELD, 0)},
                   {"ad": "Ölçülen yield", "deger": _pc(ol_y),
                    "cls": "ps" if ol_y > 0 else "ng"}])
    plan = PV.aylik_hesap(PV.PLAN_YIELD)
    gercek = PV.aylik_hesap(ol_y)
    gov = ("<table class='v2tbl'><thead><tr><th>ay</th><th>faz</th>"
           "<th>hedef</th><th>kupon</th><th>PLAN stake</th>"
           "<th>PLAN bankroll</th><th>ÖLÇÜLEN yield ile</th></tr></thead>"
           "<tbody>")
    for p, g in zip(plan, gercek):
        sag = (_tl(g["stake"]) if g["gecerli"]
               else "<span class='ng'>hesaplanamaz</span>")
        gov += (f"<tr><td><b>{p['ay']}</b></td><td style='opacity:.7;'>"
                f"{p['faz']}</td><td>{_tl(p['hedef'])}</td>"
                f"<td>{p['kupon']}</td><td>{_tl(p['stake'])}</td>"
                f"<td>{_tl(p['bankroll'])}</td><td>{sag}</td></tr>")
    gov += "</tbody></table>"
    st.markdown("<div class='v2card'><div class='v2body'>" + gov +
                "<div class='sb' style='margin-top:var(--s3);'>"
                "Stake = hedef ÷ (kupon × yield) × güvenlik payı "
                f"({PV.GUVENLIK_PAYI}). Bankroll = stake × "
                f"{PV.BANKROLL_KATSAYI}.<br>"
                "<b>Ölçülen yield eksi olduğu sürece sağ sütun sayı "
                "üretmez</b> — eksi yield'de formül negatif stake verir ve "
                "'ne kadar oynayayım' sorusunun cevabı bir sayı değil, "
                "'oynama'dır. Sayı uydurmak kaybeden bir sisteme para "
                "ölçmek olurdu.</div></div></div>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────
def nakit_akisi(sayfa_basligi):
    o = _olcum()
    para = o.get("para") or {}
    kar = float(para.get("kar") or 0)
    sayfa_basligi("Nakit Akışı",
                  "Cep ↔ bankroll. Yalnız OYNANMIŞ kuponlardan.",
                  [{"ad": "Yatan (ciro)", "deger": _tl(para.get("yatan"))},
                   {"ad": "Kâr", "deger": _tl(kar),
                    "cls": "ps" if kar >= 0 else "ng"},
                   {"ad": "Vergi tahmini",
                    "deger": _tl(max(0.0, kar) * PV.VERGI_ORANI)},
                   {"ad": "Oynanan kupon",
                    "deger": str(para.get("oynanan", 0))}])
    st.markdown(
        "<div class='v2card'><div class='v2body'><div class='vd'>"
        "<b>İki kasa ayrı:</b> CEP (çekilen, vergi sonrası) ve BANKROLL "
        "(masada duran). Ay sonunda hedef kâr cebe çekilir, yalnız "
        "ertesi ayın bankroll'u masada kalır.<br>"
        f"<b>Ocak açılışı (plan):</b> {_tl(PV.BASLANGIC_SERMAYE)} merdiven "
        f"+ {_tl(PV.YEDEK_SERMAYE)} yedek = "
        f"{_tl(PV.BASLANGIC_SERMAYE + PV.YEDEK_SERMAYE)} cepten çıkar.<br>"
        "<b>Buradaki sayılar yalnız oynanmış kuponlardan gelir.</b> "
        "İşaretlenmemiş öneri para hesabına girmez — oynamadığın kuponun "
        "kârını cebe yazmak muhasebeyi hayale çevirir.</div></div></div>",
        unsafe_allow_html=True)
    if para.get("isaretsiz"):
        st.markdown(
            f"<div class='sb'>Defterde <b>{para['isaretsiz']}</b> "
            f"işaretsiz öneri var. Oynadıklarını Kupon Defteri sayfasından "
            f"işaretlemeden nakit akışı dolmaz.</div>",
            unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────
def gorevler(sayfa_basligi):
    sayfa_basligi("Görevler", "25 görev — faz faz, bitti sayılma kriteriyle.",
                  [{"ad": "Görev", "deger": str(len(PV.GOREVLER))}])
    gov = ("<table class='v2tbl'><thead><tr><th>ID</th><th>faz</th>"
           "<th>görev</th><th>bitti sayılma kriteri</th><th>sorumlu</th>"
           "</tr></thead><tbody>")
    for gid, faz, gorev, kriter, kim in PV.GOREVLER:
        gov += (f"<tr><td><b>{gid}</b></td><td style='opacity:.7;'>{faz}"
                f"</td><td>{gorev}</td><td style='opacity:.75;'>{kriter}"
                f"</td><td>{kim}</td></tr>")
    gov += "</tbody></table>"
    st.markdown("<div class='v2card'><div class='v2body'>" + gov +
                "</div></div>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────
def kupon_defteri(sayfa_basligi):
    """Defter + OYNANDI/ATLANDI işaretleme. Gerçek muhasebe burada."""
    try:
        import db
        import ferhan_kupon as FK
        c = db.connect()
        try:
            para = FK.para_karnesi(c)
            kuponlar = FK.son_kuponlar(c, 40)
        finally:
            c.close()
    except Exception as e:
        st.markdown(f"<div class='v2bos'>Defter okunamadı: "
                    f"{type(e).__name__}: {e}</div>", unsafe_allow_html=True)
        return
    sayfa_basligi(
        "Kupon Defteri",
        "Öneri → oynandı/atlandı. İşaretlenmeyen kupon OYNANMAMIŞ sayılır.",
        [{"ad": "Öneri", "deger": str(para["oneri"])},
         {"ad": "Oynanan", "deger": str(para["oynanan"])},
         {"ad": "Atlanan", "deger": str(para["atlanan"])},
         {"ad": "İşaretsiz", "deger": str(para["isaretsiz"])},
         {"ad": "Kâr", "deger": _tl(para["kar"]),
          "cls": "ps" if para["kar"] >= 0 else "ng"}])
    for k in kuponlar[:20]:
        kid = k["kupon_id"]
        durum = k.get("durum") or "acik"
        oy = k.get("oynandi")
        etiket = ("✅ oynandı" if oy == 1 else
                  ("⏭ atlandı" if oy == 0 else "◻ işaretsiz"))
        sec = " + ".join(
            f"{str(a.get('ev') or '')[:14]} {a.get('pick')}@"
            f"{a.get('oran', 0):.2f}" for a in (k.get("ayaklar") or []))
        st.markdown(
            f"<div class='v2card' style='margin-bottom:6px;'>"
            f"<div class='v2body'><div style='display:flex;gap:var(--s4);"
            f"flex-wrap:wrap;align-items:baseline;'>"
            f"<div class='v2kpi'><span>{k['tip'].upper()} · "
            f"{k['ayak']} AYAK</span><b>{k['oran']:.2f}</b></div>"
            f"<div class='v2kpi'><span>ŞANS</span><b>{_pc(k['sans'])}</b>"
            f"</div><div class='v2kpi'><span>DURUM</span><b>{durum}</b>"
            f"</div><div class='v2kpi'><span>İŞARET</span><b>{etiket}</b>"
            f"</div></div><div style='opacity:.8;font-size:12px;"
            f"margin-top:4px;'>{sec[:150]}</div></div></div>",
            unsafe_allow_html=True)
        if oy is None:
            a, b, _ = st.columns([1, 1, 3], gap="small")
            with a:
                if st.button("Oynadım", key=f"oy_{kid}",
                             use_container_width=True):
                    import db as _d
                    cc = _d.connect()
                    try:
                        FK.isaretle(kid, True, conn=cc)
                    finally:
                        cc.close()
                    st.rerun()
            with b:
                if st.button("Atladım", key=f"at_{kid}",
                             use_container_width=True):
                    import db as _d
                    cc = _d.connect()
                    try:
                        FK.isaretle(kid, False, sebep="elle atlandı", conn=cc)
                    finally:
                        cc.close()
                    st.rerun()


# ──────────────────────────────────────────────────────────────────
def kurallar(sayfa_basligi):
    o = _olcum()
    ks = (o.get("finans") or {}).get("kill_switch") or {}
    d = ks.get("durum", "—")
    sayfa_basligi("Kurallar ve Limitler",
                  "Para kuralları, kill-switch ve dış limitler.",
                  [{"ad": "KILL-SWITCH", "deger": d,
                    "cls": "ng" if d in ("DUR", "YAVAŞLA") else "ps"},
                   {"ad": "son 20 p",
                    "deger": _pc(ks["p20"]) if ks.get("p20") is not None
                    else "—"},
                   {"ad": "son 40 p",
                    "deger": _pc(ks["p40"]) if ks.get("p40") is not None
                    else "—"}])
    if ks.get("sebep"):
        st.markdown(f"<div class='dq'><b>{d}</b> — {ks['sebep']}</div>",
                    unsafe_allow_html=True)
    grup = {}
    for tur, metin in PV.KURALLAR:
        grup.setdefault(tur, []).append(metin)
    for tur, L in grup.items():
        gov = "".join(f"<li style='margin:4px 0;'>{x}</li>" for x in L)
        st.markdown(f"<div class='v2card'><div class='v2head'><h2>{tur}</h2>"
                    f"</div><div class='v2body'><ul style='margin:0;"
                    f"padding-left:18px;'>{gov}</ul></div></div>",
                    unsafe_allow_html=True)
