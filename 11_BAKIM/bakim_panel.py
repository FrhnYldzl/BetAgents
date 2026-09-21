"""
HAFTALIK BAKIM · PANEL — SİSTEM › Haftalık Bakım
=================================================
Sayfa açıldığında son çalıştırma 7 günden eskiyse denetim kendiliğinden koşar
(ayrı bir zamanlayıcı süreci gerekmez); "Şimdi çalıştır" ile her an koşturulur.
Her sonuç saklanır, böylece önceki çalıştırmaya göre eğilim görünür.

Salt okuma: BetAgents'a hiçbir şey yazılmaz, hiçbir şey düzeltilmez.
"""
from __future__ import annotations

import html
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

import streamlit as st  # noqa: E402

import bakim_db  # noqa: E402
import bakim_kontrol as K  # noqa: E402

TR = timezone(timedelta(hours=3))
ARALIK = timedelta(days=7)
ISARET = {"kirmizi": "🔴", "sari": "🟡", "yesil": "🟢", "bilgi": "🔵"}
KADEME_AD = {"alarm": "ALARM", "izle": "İZLE", "bilgi": "BİLGİ"}
CSS = """<style>
.bk-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:var(--s3);margin-bottom:var(--s3);}
.bk-kutu{border:1px solid var(--line);border-radius:var(--r);padding:12px 14px;background:var(--panel-2);}
.bk-kutu .et{font-family:'JetBrains Mono',monospace;font-size:var(--t-etiket);letter-spacing:var(--ls-etiket);
  text-transform:uppercase;color:var(--muted);font-weight:var(--w-etiket);}
.bk-kutu .dg{font-family:'JetBrains Mono',monospace;font-size:var(--t-okuma);color:var(--ink);margin-top:4px;}
.bk-kutu .al{font-size:var(--t-alt);color:var(--muted);margin-top:2px;line-height:1.45;}
.bk-not{font-size:var(--t-alt);color:var(--ink-2);line-height:1.55;}
.bk-kademe{font-family:'JetBrains Mono',monospace;font-size:var(--t-kucuk);letter-spacing:.1em;color:var(--muted);}
table.v2 td.bk-deger{font-family:'JetBrains Mono',monospace;text-align:right;white-space:nowrap;}
table.v2 td.bk-egilim{font-family:'JetBrains Mono',monospace;text-align:right;color:var(--muted);white-space:nowrap;}
table.v2 td.bk-egilim.kotu{color:var(--neg);}
table.v2 td.bk-egilim.iyi{color:var(--pos);}
.bk-ornek{font-family:'JetBrains Mono',monospace;font-size:var(--t-kucuk);color:var(--ink-2);
  border-left:2px solid var(--line-2);padding:1px 0 1px 8px;margin:2px 0;}
</style>"""


def _e(x) -> str:
    return html.escape(str(x if x is not None else ""))


def _yaz(x: dict) -> str:
    """Kontrol değerini birimine göre biçimle."""
    v = x.get("deger")
    if x.get("birim") == "oran" and isinstance(v, (int, float)):
        return f"%{v * 100:.1f}".replace(".", ",")
    if x.get("id") == "sisme" and isinstance(v, (int, float)):
        return f"×{v:.2f}".replace(".", ",")
    return f"{v}"


def _egilim(x: dict, onceki: dict | None) -> tuple[str, str]:
    """Önceki çalıştırmaya göre değişim; kademe ALARM/İZLE'de artış kötüdür (CLV hariç)."""
    if not onceki or x["kademe"] == "bilgi":
        return "—", ""
    p = next((k for k in onceki.get("kontroller", []) if k["id"] == x["id"]), None)
    if not p or not isinstance(p.get("deger"), (int, float)) or not isinstance(x.get("deger"), (int, float)):
        return "—", ""
    d = x["deger"] - p["deger"]
    if abs(d) < 1e-9:
        return "değişmedi", ""
    iyi_yon = -1 if x["id"] != "clv" else 1                 # CLV kapsamı artınca iyi
    sinif = "iyi" if (d * iyi_yon) > 0 else "kotu"
    if x.get("birim") == "oran":
        return (f"{'+' if d > 0 else ''}{d * 100:.1f} puan".replace(".", ","), sinif)
    return (f"{'+' if d > 0 else ''}{d:g}", sinif)


def _tarih(iso: str | None) -> str:
    try:
        return datetime.fromisoformat(str(iso)).astimezone(TR).strftime("%d.%m %H:%M")
    except Exception:
        return "—"


def _kart(baslik: str, govde: str, ipucu: str = "") -> None:
    st.markdown(f"<div class='v2kart'><div class='v2kb'><h3>{_e(baslik)}</h3>"
                f"<span class='v2ip'>{_e(ipucu)}</span></div>{govde}</div>", unsafe_allow_html=True)


def haftalik_bakim(baslik) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        bakim_db.kur()
        gecmis = bakim_db.son(12)
    except Exception as e:
        baslik("Haftalık Bakım", "Kayıt okunamadı.", [])
        st.markdown(f"<div class='v2bos'>{_e(type(e).__name__)}: {_e(e)}</div>", unsafe_allow_html=True)
        return

    son = gecmis[0] if gecmis else None
    eski = (not son) or (datetime.now(timezone.utc) - datetime.fromisoformat(son["ts"]) > ARALIK)
    zorla = st.session_state.pop("bk_zorla", False)
    if eski or zorla:
        with st.spinner("Denetim çalışıyor…"):
            try:
                R = K.kos()
                bakim_db.kaydet(R)
                gecmis = bakim_db.son(12)
                son = gecmis[0]
            except Exception as e:
                st.markdown(f"<div class='v2bos'>Denetim çalıştırılamadı: {_e(type(e).__name__)}: {_e(e)}</div>",
                            unsafe_allow_html=True)
    if not son:
        baslik("Haftalık Bakım", "Henüz çalıştırma yok.", [])
        return
    onceki = gecmis[1] if len(gecmis) > 1 else None

    baslik("Haftalık Bakım", "Ajanların aldığı bahisler, sonuçları ve filtreleri tutarlı mı? Her hafta kendiliğinden "
           "koşar; yalnız okur, hiçbir şeyi değiştirmez.",
           [{"ad": "Alarm", "deger": str(son["kirmizi"]), "cls": ("ng" if son["kirmizi"] else "ps")},
            {"ad": "İzlenecek", "deger": str(son["sari"])},
            {"ad": "Son denetim", "deger": _tarih(son["ts"])}])

    a, b = st.columns([3, 1])
    with a:
        sonraki = datetime.fromisoformat(son["ts"]) + ARALIK
        adet = f"{son['bahis']:,}".replace(",", ".")
        st.markdown(f"<div class='bk-not'>{adet} bahis tarandı. Bir sonraki otomatik denetim "
                    f"<b>{_tarih(sonraki.isoformat())}</b> sonrası sayfa ilk açıldığında. "
                    "Sağlık › Defter sekmesini tamamlar: o kupon düzeyinde erken ödemeyi, bu sayfa bahis düzeyinde "
                    "her sonucu skordan yeniden hesaplar.</div>", unsafe_allow_html=True)
    with b:
        if st.button("Şimdi çalıştır", use_container_width=True, key="bk_calistir"):
            st.session_state["bk_zorla"] = True
            st.rerun()

    kontroller = son.get("kontroller", [])
    satir = ""
    for x in kontroller:
        if x["kademe"] == "bilgi":
            continue
        eg, sinif = _egilim(x, onceki)
        esik = "" if x.get("esik") in (None, 0) else (
            f"%{x['esik'] * 100:.0f}" if x.get("birim") == "oran" else str(x["esik"]))
        satir += (f"<tr><td>{ISARET[x['durum']]}</td>"
                  f"<td><span class='ag'>{_e(x['ad'])}</span>"
                  f"<span class='bk-kademe'>{KADEME_AD[x['kademe']]}{' · eşik ' + _e(esik) if esik else ''}"
                  f"</span></td><td class='bk-deger'>{_e(_yaz(x))}</td>"
                  f"<td class='bk-egilim {sinif}'>{_e(eg)}</td></tr>")
    _kart("Denetim sonucu",
          "<div class='bk-not'><b>ALARM</b> sıfır olmalı — sıfır değilse hemen bakılır. <b>İZLE</b> kalemlerinde "
          "önemli olan eğilim: sağdaki sütun önceki çalıştırmaya göre değişimi gösterir.</div>"
          "<table class='v2' style='margin-top:8px'><thead><tr><th></th><th>Kontrol</th><th>Değer</th>"
          f"<th>Önceki çalıştırmaya göre</th></tr></thead><tbody>{satir}</tbody></table>",
          f"{son['kirmizi']} alarm · {son['sari']} izlenecek")

    for x in kontroller:
        if x["kademe"] == "bilgi" or x["durum"] == "yesil":
            continue
        with st.expander(f"{ISARET[x['durum']]} {x['ad']} — {_yaz(x)}", expanded=(x["durum"] == "kirmizi")):
            st.markdown(f"<div class='bk-not'>{_e(x['aciklama'])}</div>", unsafe_allow_html=True)
            if x.get("ornek"):
                st.markdown("".join(f"<div class='bk-ornek'>{_e(o)}</div>" for o in x["ornek"]),
                            unsafe_allow_html=True)

    # bilgi: ajan karnesi
    filtre = next((x for x in kontroller if x["id"] == "filtre"), None)
    sisme = next((x for x in kontroller if x["id"] == "sisme"), None)
    if filtre and filtre.get("tablo"):
        sm = {s["ajan"]: s for s in (sisme or {}).get("tablo", [])}
        rows = ""
        for t in filtre["tablo"]:
            s = sm.get(t["ajan"], {})
            sis = s.get("sisme")
            rows += (f"<tr><td><span class='ag'>{_e(t['ajan'])}</span>"
                     f"<span class='sb'>{_e(', '.join(t['pazar'])[:60])}</span></td>"
                     f"<td class='n'>{t['bahis']}</td>"
                     f"<td class='n'>{t['en_dusuk']:.2f} – {t['en_yuksek']:.2f}</td>"
                     f"<td class='n'>{t['medyan']:.2f}</td>"
                     f"<td class='n'>{('×' + format(sis, '.2f')) if sis else '—'}</td></tr>")
        _kart("Ajan karnesi · filtre uyumu ve istatistik şişmesi",
              f"<div class='bk-not'>{_e(filtre['aciklama'])} {_e((sisme or {}).get('aciklama', ''))}</div>"
              "<table class='v2' style='margin-top:8px'><thead><tr><th>Ajan · pazarlar</th><th>Bahis</th>"
              "<th>Oran bandı</th><th>Medyan</th><th>Şişme</th></tr></thead>"
              f"<tbody>{rows}</tbody></table>", "bilgi")
