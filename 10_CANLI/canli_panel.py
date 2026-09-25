"""
CANLI · PANEL — "CANLI" bölümü (BetAgents ve Toto'dan ayrı)
============================================================
Sayfa: Canlı Maçlar — sahadaki maçlar, iddaa'nın o anki 1/0/2 fiyatı, bizim
maç içi modelimizin olasılığı ve ikisi arasındaki sapma.

Önemli dürüstlük notu: modelin tek sağlam girdisi MAÇ ÖNCESİ fiyattır. O fiyat
kaydedilmeden başlamış maçlarda model lig-nötr varsayıma düşer ve tahmini
zayıftır — tabloda açıkça işaretlenir. Bu sayfa bahis önerisi değil, SAPMA
ÖLÇÜMÜDÜR: piyasayı yenip yenemediğimizi ancak biriken veriyle söyleyebiliriz.
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

import canli_ajan as AJAN  # noqa: E402
import canli_db  # noqa: E402
import canli_model as MODEL  # noqa: E402

TR = timezone(timedelta(hours=3))
SEC = ("1", "0", "2")
CSS = """<style>
.cl-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:var(--s3);
  margin-bottom:var(--s3);}
.cl-kutu{border:1px solid var(--line);border-radius:var(--r);padding:12px 14px;background:var(--panel-2);}
.cl-kutu .et{font-family:'JetBrains Mono',monospace;font-size:var(--t-etiket);letter-spacing:var(--ls-etiket);
  text-transform:uppercase;color:var(--muted);font-weight:var(--w-etiket);}
.cl-kutu .dg{font-family:'JetBrains Mono',monospace;font-size:var(--t-okuma);color:var(--ink);margin-top:4px;}
.cl-kutu .al{font-size:var(--t-alt);color:var(--muted);margin-top:2px;line-height:1.45;}
.cl-not{font-size:var(--t-alt);color:var(--ink-2);line-height:1.55;}
.cl-uyari{border-left:3px solid var(--brand);padding:8px 12px;background:var(--brand-fill);
  font-size:var(--t-alt);color:var(--ink);line-height:1.5;margin:8px 0;}
table.v2 td.cl-dk{font-family:'JetBrains Mono',monospace;color:var(--brand);text-align:center;width:44px;}
table.v2 td.cl-sk{font-family:'JetBrains Mono',monospace;font-weight:700;text-align:center;width:52px;}
table.v2 td.cl-zayif{color:var(--muted);}
table.v2 tr.cl-toto td.rk{box-shadow:inset 3px 0 0 var(--brand);}
.cl-rozet{font-family:'JetBrains Mono',monospace;font-size:var(--t-kucuk);color:var(--brand);
  background:var(--brand-fill);padding:1px 6px;border-radius:2px;margin-left:6px;}
</style>"""


def _e(x) -> str:
    return html.escape(str(x if x is not None else ""))


def _pct(v, n=0) -> str:
    return "—" if v is None else f"%{v * 100:.{n}f}".replace(".", ",")


def _saat(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        t = datetime.fromisoformat(str(iso)[:19])
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t.astimezone(TR).strftime("%H:%M")
    except Exception:
        return str(iso)[11:16]


def _kart(baslik: str, govde: str, ipucu: str = "") -> None:
    st.markdown(f"<div class='v2kart'><div class='v2kb'><h3>{_e(baslik)}</h3>"
                f"<span class='v2ip'>{_e(ipucu)}</span></div>{govde}</div>", unsafe_allow_html=True)


MOD_AD = {"kapali": "Kapalı", "otomatik": "Otomatik (saat penceresi)", "acik": "Açık (sürekli)"}


def _anahtar_kutusu() -> bool:
    """Toplayıcı yönetimi: kapalı · otomatik · açık. Maliyet buradan kontrol edilir."""
    mod = canli_db.ayar_oku("toplayici")
    if mod not in MOD_AD:
        mod = "otomatik"
    topluyor, neden = canli_db.toplasin_mi()
    with st.expander(f"Toplayıcı · {MOD_AD[mod]} — şu an "
                     f"{'TOPLUYOR' if topluyor else 'beklemede'}", expanded=False):
        st.markdown("<div class='cl-not'>Toplamadığı anda hiçbir istek yapılmaz. "
                    "<b>Otomatik</b> modda yalnız aşağıdaki saat penceresinde çalışır — maçların "
                    "yoğun olduğu saatler. Pencere dışında kaynak da API kotası da harcanmaz.</div>",
                    unsafe_allow_html=True)
        yeni = st.radio("Mod", list(MOD_AD), index=list(MOD_AD).index(mod),
                        format_func=lambda x: MOD_AD[x], horizontal=True, key="cl_mod")
        a, b = st.columns(2)
        with a:
            hi = st.text_input("Hafta içi penceresi (TR)", canli_db.ayar_oku("pencere_hafta_ici"),
                               key="cl_p_hi")
        with b:
            hs = st.text_input("Hafta sonu penceresi (TR)", canli_db.ayar_oku("pencere_hafta_sonu"),
                               key="cl_p_hs")
        if st.button("Kaydet", key="cl_ayar_kaydet"):
            canli_db.ayar_yaz("toplayici", yeni)
            canli_db.ayar_yaz("pencere_hafta_ici", hi.strip())
            canli_db.ayar_yaz("pencere_hafta_sonu", hs.strip())
            st.rerun()
        st.markdown(f"<div class='cl-not' style='margin-top:6px'><b>Şu anki karar:</b> "
                    f"{'topluyor' if topluyor else 'beklemede'} — {_e(neden)}. "
                    "Değişiklik en geç bir dakika içinde toplayıcıya geçer.</div>",
                    unsafe_allow_html=True)
    return topluyor


def ajan_maclari(baslik) -> None:
    """BetAgents'ın açık bahisleri — alınan fiyat · kapanış · canlı."""
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        canli_db.kur()
        S = AJAN.ajan_maclari(80)
        o = AJAN.ozet(S)
    except Exception as e:
        baslik("Ajan Maçları", "Okunamadı.", [])
        st.markdown(f"<div class='cl-uyari'>{_e(type(e).__name__)}: {_e(e)}</div>", unsafe_allow_html=True)
        return
    baslik("Ajan Maçları · Canlı", "BetAgents'ın açık bahisleri: alınan fiyat, kapanış fiyatı ve o anki canlı fiyat.",
           [{"ad": "Açık bahis", "deger": str(o["bahis"])},
            {"ad": "Sahada", "deger": str(o["sahada"])},
            {"ad": "CLV ölçülen", "deger": f"{o['clv_olculen']}/{o['bahis']}"}])
    _anahtar_kutusu()

    if not S:
        st.markdown("<div class='v2bos'>BetAgents'ın açık kâğıt bahsi yok.</div>", unsafe_allow_html=True)
        return

    rows = ""
    for x in S:
        dk = (f"{x['dakika']}'" if x.get("dakika") is not None else ("sahada" if x["sahada"] else "—"))
        sk = (f"{x['ev_skor']}-{x['dep_skor']}" if x.get("ev_skor") is not None else "")
        clv = (f"<b>{x['clv'] * 100:+.1f}%</b>" if x.get("clv") is not None else
               ("<span class='cl-zayif'>—</span>"))
        canli = f"{x['canli_oran']:.2f}" if x.get("canli_oran") else "—"
        kapanis = f"{x['kapanis_oran']:.2f}" if x.get("kapanis_oran") else "—"
        pazar_not = "" if x["pazar_var"] else " <span class='cl-zayif'>(toplanmayan pazar)</span>"
        rows += (f"<tr><td class='cl-dk'>{_e(dk)}</td>"
                 f"<td><span class='ag'>{_e(x['ev'])} - {_e(x['dep'])}</span>"
                 f"<span class='sb'>{_e(x['ajan'])} · {_e(x['market'])} → {_e(x['pick'])}{pazar_not}</span></td>"
                 f"<td class='cl-sk'>{_e(sk)}</td>"
                 f"<td class='n'>{(x['oran'] or 0):.2f}</td><td class='n'>{_e(kapanis)}</td>"
                 f"<td class='n'>{_e(canli)}</td><td class='n'>{clv}</td></tr>")

    clv_ort = "—" if o["clv_ort"] is None else f"{o['clv_ort'] * 100:+.2f}%".replace(".", ",")
    ozet_html = ("<div class='cl-grid'>"
                 f"<div class='cl-kutu'><div class='et'>Ortalama CLV</div>"
                 f"<div class='dg'>{clv_ort}</div>"
                 "<div class='al'>alınan fiyatın kapanışa üstünlüğü</div></div>"
                 f"<div class='cl-kutu'><div class='et'>Pozitif CLV oranı</div>"
                 f"<div class='dg'>{(_pct(o['clv_pozitif']) if o['clv_pozitif'] is not None else '—')}</div>"
                 "<div class='al'>%50'nin üstü iyi fiyat yakalıyor demektir</div></div>"
                 f"<div class='cl-kutu'><div class='et'>Toplanmayan pazar</div>"
                 f"<div class='dg'>{o['pazar_disi']}</div>"
                 "<div class='al'>kombine/skor bahisleri — fiyatı izlenmiyor</div></div></div>")

    _kart("Açık bahisler", ozet_html
          + "<div class='cl-not'><b>Üç fiyat üç farklı şey söyler.</b> "
            "<b>Alınan</b>: ajanın bahsi aldığı fiyat. <b>Kapanış</b>: ilk düdükteki fiyat — "
            "<u>CLV cetveli budur</u>, alınan bundan yüksekse ajan piyasadan iyi fiyat yakalamıştır. "
            "<b>Canlı</b>: şu anki fiyat, maçın <u>durumunu</u> yansıtır, yargı değildir — 2-0 geride olan "
            "takımın fiyatı açılır, bu ajanın hatası değildir.</div>"
            "<table class='v2' style='margin-top:8px'><thead><tr><th>Dk</th><th>Bahis</th><th>Skor</th>"
            "<th>Alınan</th><th>Kapanış</th><th>Canlı</th><th>CLV</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>",
          f"{o['clv_olculen']} bahiste CLV ölçülebildi")

    if o["clv_olculen"] == 0:
        st.markdown("<div class='cl-uyari'>Henüz CLV ölçülemiyor: kapanış fiyatı yalnız toplayıcı "
                    "açıkken maç <i>başlamadan önce</i> kaydedilebiliyor. Toplayıcıyı açık tutarsan "
                    "bundan sonra oynanan bahisler için cetvel dolmaya başlar.</div>",
                    unsafe_allow_html=True)


def canli_maclar(baslik) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        canli_db.kur()
        M = canli_db.canli_maclar(60)
        say = canli_db.sayim()
    except Exception as e:
        baslik("Canlı Maçlar", "Canlı veri okunamadı.", [])
        st.markdown(f"<div class='cl-uyari'>{_e(type(e).__name__)}: {_e(e)}</div>", unsafe_allow_html=True)
        return

    durumlu = sum(1 for m in M if m.get("dakika") is not None)
    capali = sum(1 for m in M if m.get("oran_once"))
    try:
        import canli_kaynak as KAYNAK
        af_hata = KAYNAK.AF_SON_HATA
    except Exception:
        af_hata = ""
    if af_hata:
        st.markdown(f"<div class='cl-uyari'><b>Durum akışı kesik.</b> Skor ve dakika API-Football'dan "
                    f"geliyor ve şu an gelmiyor: <code>{_e(af_hata)}</code>. Fiyat toplama sürüyor, ama "
                    "maç içi model durum olmadan çalışamaz.</div>", unsafe_allow_html=True)
    baslik("Canlı Maçlar", "iddaa'nın canlı fiyatı, bizim maç içi modelimiz ve aradaki sapma.",
           [{"ad": "Sahada", "deger": str(len(M))},
            {"ad": "Durumu bilinen", "deger": f"{durumlu}/{len(M)}"},
            {"ad": "Arşiv", "deger": f"{say['anlik']:,}".replace(",", ".")}])
    _anahtar_kutusu()

    if not M:
        st.markdown("<div class='v2bos'>Şu an sahada maç yok ya da toplayıcı henüz çalışmadı. "
                    "Toplayıcı ayrı bir süreç olarak çalışır (10_CANLI/canli_worker.py) ve maçlar "
                    "başlayınca kendiliğinden dolar.</div>", unsafe_allow_html=True)
        return

    ozet = ("<div class='cl-grid'>"
            f"<div class='cl-kutu'><div class='et'>Maç öncesi fiyatı olan</div>"
            f"<div class='dg'>{capali}/{len(M)}</div>"
            "<div class='al'>modelin sağlam çalıştığı maç sayısı</div></div>"
            f"<div class='cl-kutu'><div class='et'>Toplanan maç</div>"
            f"<div class='dg'>{say['mac']:,}</div>".replace(",", ".")
            + "<div class='al'>maç öncesi fiyatı saklanmış olanlar dâhil</div></div>"
            f"<div class='cl-kutu'><div class='et'>Anlık görüntü</div>"
            f"<div class='dg'>{say['anlik']:,}</div>".replace(",", ".")
            + "<div class='al'>fiyat + durum kaydı (arşiv büyüdükçe ölçüm güçlenir)</div></div></div>")

    rows = ""
    for m in M:
        o, pp, pm = m.get("oran"), m.get("p_piyasa"), m.get("p_model")
        zayif = not m.get("oran_once")
        s = MODEL.sapma(pm, pp) if (pm and pp) else {}
        oran_s = " / ".join(f"{x:.2f}" for x in o) if o else "fiyat yok"
        piy = " · ".join(f"{SEC[j]} {pp[j]:.0%}" for j in range(3)) if pp else "—"
        mod = (" · ".join(f"{SEC[j]} {pm[j]:.0%}" for j in range(3))) if pm else "durum yok"
        sap = (f"<b>{_e(s['en_cok'])}</b> {'+' if s['buyukluk'] >= 0 else ''}{s['buyukluk'] * 100:.0f} puan"
               if s else "—")
        toto = f"<span class='cl-rozet'>TOTO {m['toto_sira']}</span>" if m.get("toto_sira") else ""
        rows += (f"<tr class='{'cl-toto' if m.get('toto_sira') else ''}'>"
                 f"<td class='cl-dk'>{_e(m['dakika']) if m.get('dakika') is not None else '—'}</td>"
                 f"<td><span class='ag'>{_e(m['ev'])} - {_e(m['dep'])}</span>{toto}"
                 f"<span class='sb'>{_e((m.get('lig') or '')[:30])} · {_saat(m.get('baslangic'))}</span></td>"
                 f"<td class='cl-sk'>{_e(m['ev_skor'])}-{_e(m['dep_skor'])}</td>"
                 f"<td class='n'>{_e(oran_s)}</td><td class='n'>{_e(piy)}</td>"
                 f"<td class='n{' cl-zayif' if zayif else ''}'>{_e(mod)}{' *' if zayif and pm else ''}</td>"
                 f"<td class='n'>{sap}</td></tr>")

    _kart("Sahadaki maçlar", ozet
          + "<div class='cl-not'>Piyasa sütunu iddaa fiyatının marjı temizlenmiş hâli; model sütunu bizim "
            "maç içi Poisson hesabımız (maç öncesi fiyattan çözülen gol beklentisi, kalan süreye ölçeklenir, "
            "skora ve kırmızı karta göre güncellenir). Sapma, modelin piyasadan en çok ayrıldığı sonuç.</div>"
            "<table class='v2' style='margin-top:8px'><thead><tr><th>Dk</th><th>Maç</th><th>Skor</th>"
            "<th>iddaa 1/0/2</th><th>Piyasa</th><th>Model</th><th>Sapma</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
            + ("<div class='cl-not' style='margin-top:8px'>* Maç öncesi fiyatı kaydedilmeden başlayan maçlar. "
               "Model bunlarda lig-nötr varsayıma düşer ve aynı skor/dakikadaki maçlara aynı olasılığı verir — "
               "tahmin zayıftır, ölçüme katılmamalıdır. Toplayıcı çalıştıkça bu sayı azalır.</div>"
               if capali < len(M) else ""),
          f"{durumlu}/{len(M)} maçta durum bilgisi var")

    st.markdown("<div class='cl-uyari'><b>Bu sayfa bahis önerisi değildir.</b> Amaç sapmayı ölçmek: "
                "canlı piyasada marj ön maçtan yüksektir ve ön maçta piyasayı yenemediğimizi ölçtük "
                "(+%0,06 üstünlük, gereken %13). Modelin piyasayı yenmesi beklenmiyor; biriken arşivle "
                "nerede ve ne kadar ayrıştığını <i>öğreniyoruz</i>. Sapma büyük diye bahis yapılmaz.</div>",
                unsafe_allow_html=True)
