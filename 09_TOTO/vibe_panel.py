"""
VIBE BETTING · PANEL — sohbet sayfası
======================================
Sol panelin en üstündeki tek sayfa. Düzen: solda sohbet rayı (oturumlar),
sağda ya karşılama ekranı ya da konuşma. Oturumlar veritabanında kalır.

Sayfanın altında "Geliştirme paketi": panelde biriken geri bildirimleri tek bir
markdown dosyasına toplar. Kullanıcı onu geliştiriciye verir — geliştirme
oturumu üretim veritabanına bağlanmadığı için teslim yolu budur.
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

import vibe_ajan  # noqa: E402
import vibe_arac  # noqa: E402
import vibe_db  # noqa: E402

TR = timezone(timedelta(hours=3))
ORNEK = [
    ("Bu hafta kapı ne diyor?", "Bu hafta oynama kapısı ne diyor, hangi şart sağlanmadı, neden?"),
    ("Bir maçı derinlemesine aç", "14. maçta ajanlar ne düşünüyor, kalabalık nereye yığılmış?"),
    ("iddaa'da kim kâr ediyor?", "BetAgents ajanlarının birim getirisi ne? Gerçekten kâr eden var mı?"),
]
CSS = """<style>
.vb-kicker{font-family:'JetBrains Mono',monospace;font-size:var(--t-etiket);letter-spacing:.16em;
  text-transform:uppercase;color:var(--muted);display:flex;align-items:center;gap:8px;margin-bottom:14px;}
.vb-kicker b{width:7px;height:7px;border-radius:50%;background:var(--brand);display:inline-block;}
.vb-h1{font-size:clamp(30px,4.2vw,48px);line-height:1.05;letter-spacing:-.02em;color:var(--ink);
  font-weight:700;margin:0 0 14px;}
.vb-h1 i{color:var(--brand);font-style:italic;}
.vb-alt{font-size:var(--t-kart);color:var(--ink-2);line-height:1.6;max-width:560px;margin:0 0 22px;}
.vb-try{font-family:'JetBrains Mono',monospace;font-size:var(--t-etiket);letter-spacing:.16em;
  text-transform:uppercase;color:var(--muted);margin:0 0 8px;}
.vb-durum{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;
  font-family:'JetBrains Mono',monospace;font-size:var(--t-kucuk);color:var(--muted);
  border:1px solid var(--line);border-top:0;border-radius:0 0 var(--r) var(--r);
  background:var(--panel-2);padding:7px 12px;margin:-6px 0 14px;}
.vb-durum .sol{display:flex;align-items:center;gap:8px;}
.vb-durum .nokta{width:7px;height:7px;border-radius:50%;background:var(--pos);display:inline-block;}
.vb-durum .nokta.kapali{background:var(--neg);}
.vb-durum code{background:var(--brand-fill);color:var(--brand);padding:2px 7px;border-radius:2px;
  font-size:var(--t-kucuk);}
.vb-ray-bas{font-family:'JetBrains Mono',monospace;font-size:var(--t-etiket);letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted);margin:16px 0 6px;}
.vb-iz{font-family:'JetBrains Mono',monospace;font-size:var(--t-kucuk);color:var(--muted);
  border-left:2px solid var(--line-2);padding:2px 0 2px 8px;margin:6px 0 0;}
.vb-uyari{border-left:3px solid var(--brand);padding:8px 12px;background:var(--brand-fill);
  font-size:var(--t-alt);color:var(--ink);line-height:1.5;margin:6px 0 14px;}
.vb-not{font-size:var(--t-alt);color:var(--ink-2);line-height:1.55;margin-bottom:8px;}
/* sohbet rayı: düz liste görünümlü düğmeler */
.st-key-vb_ray button{justify-content:flex-start!important;text-align:left!important;border:0!important;
  background:transparent!important;color:var(--ink-2)!important;padding:5px 8px!important;
  font-size:var(--t-alt)!important;border-radius:var(--r)!important;}
.st-key-vb_ray button:hover{background:var(--panel-2)!important;color:var(--ink)!important;}
.st-key-vb_ray button p{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
/* öneri çipleri */
.st-key-vb_cip button{justify-content:flex-start!important;text-align:left!important;
  background:var(--panel-2)!important;border:1px solid var(--line)!important;font-size:var(--t-alt)!important;}
.st-key-vb_cip button:hover{border-color:var(--brand)!important;color:var(--brand)!important;}
</style>"""


@st.cache_resource(show_spinner=False)
def _kur() -> bool:
    vibe_db.kur()
    return True


def _e(x) -> str:
    return html.escape(str(x if x is not None else ""))


def _tarih(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        t = datetime.fromisoformat(str(iso)[:19]).replace(tzinfo=timezone.utc).astimezone(TR)
        return t.strftime("%d.%m %H:%M")
    except Exception:
        return str(iso)[:16]


def _iz_metni(arac: list) -> str:
    if not arac:
        return ""
    p = []
    for a in arac:
        g = a.get("girdi") or {}
        ek = ""
        for alan in ("sira", "desen", "dosya", "bolum", "durum"):
            if g.get(alan) not in (None, ""):
                ek = f"({str(g[alan])[:30]})"
                break
        p.append(("⚠ " if a.get("hata") else "") + a.get("ad", "?") + ek)
    return "baktığı yerler: " + " · ".join(p)


def _ray(oturum: str | None) -> str | None:
    """Sol ray: yeni sohbet + oturum listesi."""
    with st.container(key="vb_ray"):
        if st.button("＋  Yeni sohbet", use_container_width=True, key="vb_yeni"):
            st.session_state["vb_oturum"] = None
            st.rerun()
        liste = vibe_db.oturumlar(30)
        st.markdown("<div class='vb-ray-bas'>// Sohbetler</div>", unsafe_allow_html=True)
        if not liste:
            st.markdown("<div class='vb-not' style='opacity:.7'>Henüz sohbet yok.</div>", unsafe_allow_html=True)
        for o in liste:
            etiket = ("• " if o["oturum_id"] == oturum else "") + (o["baslik"] or "Yeni oturum")
            if st.button(etiket, key="vb_o_" + o["oturum_id"], use_container_width=True,
                         help=f"{_tarih(o['guncelleme'])} · {o['n_mesaj']} mesaj"):
                st.session_state["vb_oturum"] = o["oturum_id"]
                st.rerun()
        if oturum and any(o["oturum_id"] == oturum for o in liste):
            if st.button("Bu sohbeti sil", key="vb_sil", use_container_width=True):
                vibe_db.oturum_sil(oturum)
                st.session_state["vb_oturum"] = None
                st.rerun()
    return oturum


def _karsilama() -> None:
    st.markdown(
        "<div style='padding:26px 0 0'>"
        "<div class='vb-kicker'><b></b>Vibe Betting</div>"
        "<div class='vb-h1'>Veriye ne <i>soralım?</i></div>"
        "<div class='vb-alt'>Toto'nun 15 maçı, ajan pazarı, kalabalık modeli, 204 haftalık geçmiş test, "
        "iddaa tarafı ve yazılımın kendisi — hepsine bakabilir. Sayı uydurmaz, kaynağına bakar ve "
        "nereye baktığını gösterir.</div>"
        "<div class='vb-try'>Dene →</div></div>", unsafe_allow_html=True)
    with st.container(key="vb_cip"):
        for s, (kisa, tam) in zip(st.columns(len(ORNEK)), ORNEK):
            with s:
                if st.button(kisa, use_container_width=True, key="vb_c_" + kisa[:12]):
                    st.session_state["vb_hazir"] = tam
                    st.rerun()


def _durum_cubugu(d: str) -> None:
    acik = d == "hazır"
    st.markdown(
        f"<div class='vb-durum'><div class='sol'><span class='nokta{'' if acik else ' kapali'}'></span>"
        f"{'HAZIR' if acik else _e(d).upper()}<code>{_e(vibe_ajan.MODEL)}</code></div>"
        "<div>⏎ gönder · araç izi cevabın altında</div></div>", unsafe_allow_html=True)


def _paket_bolumu() -> None:
    gb = vibe_db.geri_bildirimler("acik", 80)
    with st.expander(f"Geliştirme paketi · {len(gb)} açık madde", expanded=False):
        st.markdown("<div class='vb-not'>Panelde biriken geri bildirimler. Paketi indirip geliştiriciye ver — "
                    "geliştirme oturumu üretim veritabanına bağlanmadığı için teslim yolu budur.</div>",
                    unsafe_allow_html=True)
        p = vibe_arac.gelistirme_paketi("acik")
        st.code(p["paket"], language="markdown")
        a, b = st.columns([3, 2])
        with a:
            st.download_button("Paketi indir (.md)", data=p["paket"].encode("utf-8"),
                               file_name=f"vibe-paket-{datetime.now(TR).strftime('%Y%m%d-%H%M')}.md",
                               mime="text/markdown", use_container_width=True, key="vb_indir")
        with b:
            if gb and st.button("Teslim ettim — kapat", use_container_width=True, key="vb_kapat"):
                for x in gb:
                    vibe_db.geri_bildirim_kapat(x["gb_id"])
                st.rerun()


def _sor(oturum: str | None, soru: str, gecmis: list) -> None:
    if not oturum:
        oturum = vibe_db.oturum_ac(vibe_ajan.baslik_oner(soru))
        st.session_state["vb_oturum"] = oturum
    elif not gecmis:
        vibe_db.baslik_yaz(oturum, vibe_ajan.baslik_oner(soru))
    vibe_db.mesaj_yaz(oturum, "user", soru)
    with st.chat_message("user"):
        st.markdown(soru)
    with st.chat_message("assistant"):
        with st.spinner("Veriye bakıyorum…"):
            y = vibe_ajan.yanitla(gecmis, soru, oturum)
        if y.get("hata"):
            vibe_db.mesaj_yaz(oturum, "assistant", f"_{y['hata']}_", y.get("arac"))
        else:
            vibe_db.mesaj_yaz(oturum, "assistant", y["metin"], y.get("arac"))
    st.rerun()


def vibe(baslik) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    _kur()
    d = vibe_ajan.durum()
    baslik("Vibe Betting", "Bütün veriye bakabilen asistan — Toto, iddaa ve yazılımın kendisi.",
           [{"ad": "Model", "deger": vibe_ajan.MODEL}, {"ad": "Durum", "deger": d},
            {"ad": "Açık geri bildirim", "deger": str(len(vibe_db.geri_bildirimler("acik", 80)))}])

    ray, ana = st.columns([1, 3.4], gap="large")
    with ray:
        oturum = _ray(st.session_state.get("vb_oturum"))

    with ana:
        if d != "hazır":
            st.markdown(f"<div class='vb-uyari'><b>Asistan kapalı.</b> {_e(d)}. Railway'de "
                        "<code>ANTHROPIC_API_KEY_BET_AGENTS</code> değişkenini ekleyip dağıtınca "
                        "kendiliğinden açılır; panelin geri kalanı etkilenmez.</div>", unsafe_allow_html=True)
        gecmis = vibe_db.mesajlar(oturum) if oturum else []
        if not gecmis:
            _karsilama()
        for m in gecmis:
            with st.chat_message("user" if m["rol"] == "user" else "assistant"):
                st.markdown(m["metin"])
                iz = _iz_metni(m.get("arac") or [])
                if iz:
                    st.markdown(f"<div class='vb-iz'>{_e(iz)}</div>", unsafe_allow_html=True)

        soru = st.chat_input("Bir hafta, bir maç, bir ajan, geçmiş test ya da kodun kendisi…",
                             disabled=(d != "hazır"), key="vb_giris")
        _durum_cubugu(d)
        hazir = st.session_state.pop("vb_hazir", None)
        if soru or hazir:
            _sor(oturum, soru or hazir, gecmis)
        _paket_bolumu()
