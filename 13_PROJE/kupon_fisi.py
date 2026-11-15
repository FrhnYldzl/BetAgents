"""
KUPON FİŞİ — iddaa bülten/kupon yapısına yakın gösterim
=========================================================
Kullanıcı kararı 15.11.2026:
  "Kuponlar iddaa'daki görünüm ve yapıya, deneyime benzemeli."
  "Çok karışık görünüyoruz, ilkel ve karışık."

Önceki gösterim etiket/değer çipleri (MASTER · 4 AYAK · ŞANS · DURUM) ve
tek satıra sıkışmış ayaklardı — bir bahis kuponuna hiç benzemiyordu.

Bahis kuponunun yapısı sabittir ve okuyan onu ezbere bilir:
    başlık : kupon tipi · maç sayısı · toplam oran
    ayak   : saat · lig / ev – deplasman / pazar · seçim · oran
    altlık : TOPLAM ORAN · KUPON TUTARI · MAKSİMUM KAZANÇ
Bu sıra bilinçli: göz önce ne oynadığını, sonra ne kazanacağını arar.

⚠️ ÖLÇÜM FİŞİN İÇİNE KARIŞMAZ. Şans, kanıt ve kenar ayrı bir şeritte
durur. Bahis şirketinin kuponunda o sayılar yoktur; onları fişin içine
koymak hem kalabalık yapar hem de "bu da kuponun bir parçası" izlenimi
verir. Bizim kattığımız değer orada, ama kendi yerinde.
"""
from __future__ import annotations

# ── Pazar adları: VERİDEN çıkarıldı, uydurulmadı ────────────────────
# Soldaki kodlar ferhan_kupon_ayak.market / .pick'te GERÇEKTEN geçen
# değerler (15.11.2026'da sayıldı). Yeni bir pazar eklenirse burada
# karşılığı yoksa kodun kendisi yazılır — sessizce boş kalmaz.
PAZAR_ADI = {
    "1X2": "Maç Sonucu",
    "CIFTE_SANS": "Çifte Şans",
    "ALT_25": "2,5 Alt/Üst",
    "UST_25": "2,5 Alt/Üst",
    "ALT_UST": "Alt/Üst",
    "KG_VAR": "Karşılıklı Gol",
    "KG_YOK": "Karşılıklı Gol",
    "TEK_CIFT": "Tek/Çift",
    "HANDIKAP": "Handikaplı Maç Sonucu",
    "EV_ALT_UST": "Ev Sahibi Gol",
    "DEP_ALT_UST": "Deplasman Gol",
    "TOTAL_GOALS": "Toplam Gol",
    "1X2_BTTS": "Maç Sonucu ve KG",
    "1X2_OU": "Maç Sonucu ve Alt/Üst",
    "OU_BTTS": "Alt/Üst ve KG",
    "IY_1X2": "İlk Yarı Sonucu",
    "IY_ALT_UST": "İlk Yarı Alt/Üst",
    "IY_KG": "İlk Yarı Karşılıklı Gol",
    "Y2_1X2": "2. Yarı Sonucu",
    "Y2_ALT_UST": "2. Yarı Alt/Üst",
}

# Seçim etiketleri. ⚠️ Beraberlik Türkiye bültenlerinde "0" yazılır,
# "X" değil — kullanıcı bunu "0" olarak okur.
SECIM_ADI = {
    "1": "1", "2": "2", "0": "0", "X": "0",
    "1X": "1-0", "12": "1-2", "X2": "0-2",
    "ALT": "Alt", "UST": "Üst", "ÜST": "Üst",
    "VAR": "Var", "YOK": "Yok",
    "TEK": "Tek", "CIFT": "Çift", "ÇİFT": "Çift",
}


def pazar_secim(market: str, pick: str) -> tuple[str, str]:
    """(pazar adı, seçim etiketi) — çizgi pick'in içindeyse ayıklanır.

    ALT_UST pazarında çizgi pick'e gömülü geliyor ("ÜST 1.5", "ALT 3.5").
    Çizgiyi pazar adına taşımak gerekiyor: "1,5 Alt/Üst → Üst". Çizgiyi
    seçimde bırakmak "Üst 1.5" gibi bülten dışı bir metin üretirdi.
    """
    m = str(market or "").strip().upper()
    p = str(pick or "").strip()
    pu = p.upper()
    parca = pu.split()
    if len(parca) == 2 and parca[0] in ("ALT", "ÜST", "UST"):
        cizgi = parca[1].replace(".", ",")
        return f"{cizgi} Alt/Üst", SECIM_ADI.get(parca[0], p)
    if m in ("ALT_25", "UST_25"):
        return "2,5 Alt/Üst", SECIM_ADI.get(pu, p)
    ad = PAZAR_ADI.get(m, m.replace("_", " ").title())
    return ad, SECIM_ADI.get(pu, p)


# ⚠️ KAYITLI SAAT UTC, EKRANDAKİ SAAT TÜRKİYE SAATİ OLMALI.
# Kullanıcı (15.11.2026): "bazı maçlar yine geçmiş, iddaa.com'da
# bulamıyorum, saat vs." — sebep buydu: `kickoff_utc` UTC tutuluyor ama
# fişe olduğu gibi basılıyordu. Kullanıcı onu TR saati sanıp maçı 3 saat
# erken görüyor; bültende o saatte maç olmadığı için de bulamıyor.
#
# Verinin UTC olduğu ÖLÇÜLDÜ, sütun adına güvenilmedi:
#   · kickoff saat dağılımı 17-19'da tepe yapıyor. TR olsaydı Avrupa
#     akşam maçları 14-16 UTC'ye düşerdi — o saatte oynanmıyor.
#     UTC kabul edilince TR 20-22 çıkıyor: bülten saatleri tam bu.
#   · settled_at − kickoff en küçük +1,8 saat (maç ~1,9 saat sürer).
#     İkisi farklı dilimde olsa bu fark eksi ya da +4,8 olurdu.
#
# Türkiye 2016'dan beri yaz saati uygulamıyor; sabit UTC+3 güvenli.
TR_FARKI_SAAT = 3


def _saat(kickoff) -> str:
    """UTC kickoff → '02.11  23:15' (Türkiye saati).

    Biçim bozuksa BOŞ döner; uydurma tarih yazmak kuponun en güvenilen
    alanını yalan yapardı.
    """
    import datetime as _dt
    s = str(kickoff or "")
    if len(s) < 16 or "T" not in s:
        return ""
    try:
        t = _dt.datetime.fromisoformat(s[:19])
    except Exception:
        return ""
    t = t + _dt.timedelta(hours=TR_FARKI_SAAT)
    return f"{t.day:02d}.{t.month:02d}  {t.hour:02d}:{t.minute:02d}"


def simdi_iso(pay_dk: int = 0) -> str:
    """Şimdi + pay, kickoff ile AYNI biçimde (saat dilimsiz ISO)."""
    import datetime as _dt
    t = _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
    return (t + _dt.timedelta(minutes=pay_dk)).isoformat(timespec="seconds")


def basladi_mi(ayak: dict, esik: str = None) -> bool:
    """Bu ayağın maçı başladı mı? Saati bilinmiyorsa BAŞLAMIŞ sayılır.

    ⚠️ Bilinmeyeni "oynanabilir" saymak, oynanamayacak kuponu karar
    bekleyen listesine koyar — kullanıcının şikâyeti tam buydu.
    """
    ko = str(ayak.get("kickoff") or "")
    return (not ko) or ko <= (esik or simdi_iso())


def oynanabilir(kupon: dict, esik: str = None) -> bool:
    """Kuponun BÜTÜN ayakları henüz başlamamışsa oynanabilir."""
    esik = esik or simdi_iso()
    ayaklar = kupon.get("ayaklar") or []
    return bool(ayaklar) and not any(basladi_mi(a, esik) for a in ayaklar)


def _n(v, b: int = 2) -> str:
    return f"{float(v or 0):.{b}f}".replace(".", ",")


def kupon_orani(oran) -> float:
    """Kupon oranını 2 haneye AŞAĞI yuvarla (bülten davranışı).

    ⚠️ Yuvarlama yönü önemli. Ayakların çarpımı 1,8172 iken ekranda
    "1,82" yazıp ödemeyi 1,8172'den hesaplarsak kullanıcı 100 × 1,82 =
    182 bekler, 181,72 görür — aritmetiği tutmayan bir fiş. Yukarı
    yuvarlayıp 182,00 yazmak ise kazancı OLDUĞUNDAN FAZLA gösterir.
    Aşağı yuvarlama ikisini de çözer: ekranda 1,81 ve 181,00, hem
    tutarlı hem de asla fazla vaat etmiyor.
    """
    return int(float(oran or 0) * 100) / 100.0


def _tl(v) -> str:
    return "{:,.2f}".format(float(v or 0)).replace(",", "#") \
        .replace(".", ",").replace("#", ".") + " ₺"


def _kacir(s) -> str:
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


TIP_ADI = {"master": "KOMBİNE", "normal": "KOMBİNE", "canli": "CANLI",
           "hedef": "KOMBİNE"}
DURUM_ADI = {"acik": ("Açık", "ac"), "kazandi": ("Kazandı", "kz"),
             "kaybetti": ("Kaybetti", "kb"), "iptal": ("İptal", "ip")}
AYAK_IM = {"won": ("✓", "kz"), "lost": ("✗", "kb"), "void": ("—", "ip")}


def fis(k: dict, bahis: float = 100.0) -> str:
    """Tek kuponu BAHİS FİŞİ olarak çiz (HTML)."""
    ayaklar = k.get("ayaklar") or []
    n = len(ayaklar)
    oran = kupon_orani(k.get("oran"))
    tip = TIP_ADI.get(str(k.get("tip") or ""), "KUPON")
    if n == 1:
        tip = "TEK MAÇ"
    durum = str(k.get("durum") or "acik")
    d_ad, d_cls = DURUM_ADI.get(durum, ("", ""))
    b = float(k.get("gercek_bahis") or k.get("bahis") or bahis)
    # Ödeme EKRANDAKİ orandan hesaplanır: fişin aritmetiği kendi içinde
    # tutmalı. Defterin muhasebesi ham oranı kullanmaya devam ediyor.
    pot = b * oran

    esik = simdi_iso()
    satir = []
    for a in ayaklar:
        pz, sc = pazar_secim(a.get("market"), a.get("pick"))
        im = AYAK_IM.get(str(a.get("durum") or ""), ("", ""))
        rozet = (f"<i class='kf-im {im[1]}'>{im[0]}</i>" if im[0] else "")
        # Sonucu henüz yokken maçı başlamışsa bunu SÖYLE: saati geçmiş
        # ayağı sessizce normal göstermek kuponu oynanabilir sanmaya
        # yol açıyordu.
        if not im[0] and basladi_mi(a, esik):
            rozet = "<i class='kf-im gec'>başladı</i>"
        ust = _saat(a.get("kickoff"))
        # ⚠️ Lig kodu bu veride %94 oranında 'ALL' — yani lig bilgisi
        # yok demek. "ALL" yazmak bilgi vermiyor, satırı kirletiyor.
        lig = str(a.get("lig") or "").strip()
        lig = "" if lig.upper() in ("ALL", "NONE", "-") else _kacir(lig)
        if lig:
            ust = (ust + "  ·  " + lig) if ust else lig
        satir.append(
            "<div class='kf-ayak'>"
            "<div class='kf-ust'>" + _kacir(ust) + "</div>"
            "<div class='kf-mac'>" + _kacir(a.get("ev")) +
            " <span>–</span> " + _kacir(a.get("dep")) + rozet + "</div>"
            "<div class='kf-alt'><span class='kf-pz'>" + _kacir(pz) +
            "</span><span class='kf-sc'>" + _kacir(sc) +
            "</span><span class='kf-or'>" + _n(a.get("oran")) + "</span>"
            "</div></div>")

    return (
        "<div class='kf'>"
        "<div class='kf-bas'><span class='kf-tip'>" + tip + "</span>"
        "<span class='kf-mac-adet'>" + str(n) + " MAÇ</span>"
        "<span class='kf-durum " + d_cls + "'>" + d_ad + "</span></div>"
        + "".join(satir) +
        "<div class='kf-dip'>"
        "<div class='kf-dip-s'><span>TOPLAM ORAN</span><b>" + _n(oran) +
        "</b></div>"
        "<div class='kf-dip-s'><span>KUPON TUTARI</span><b>" + _tl(b) +
        "</b></div>"
        "<div class='kf-dip-s kf-kazanc'><span>MAKSİMUM KAZANÇ</span><b>"
        + _tl(pot) + "</b></div>"
        "</div></div>")


def olcu_seridi(k: dict) -> str:
    """Bizim kattığımız sayılar — fişin DIŞINDA, kendi şeridinde."""
    sans = float(k.get("sans") or 0)
    fiyat = float(k.get("fiyat_sansi") or 0)
    ayaklar = k.get("ayaklar") or []
    kanitli = sum(1 for a in ayaklar if a.get("kanit"))
    # ⚠️ Etiketler BÜYÜK HARFLE yazılı, CSS text-transform ile değil.
    # CSS'in uppercase'i Türkçe'de bozuyor: "dediği" → "DEDIĞI" (noktalı
    # i büyük harfte İ olmalı). Tarayıcı dil kuralını uygulamıyor.
    p = []
    p.append("<span><i>KAZANMA ŞANSI</i><b>" + _n(sans * 100, 1) +
             "%</b></span>")
    if fiyat:
        p.append("<span><i>FİYATIN DEDİĞİ</i><b>" + _n(fiyat * 100, 1) +
                 "%</b></span>")
    p.append("<span><i>KANITLI AYAK</i><b>" + str(kanitli) + "/" +
             str(len(ayaklar)) + "</b></span>")
    return "<div class='kf-olcu'>" + "".join(p) + "</div>"


CSS = """
<style>
.kf{border:1px solid var(--line-2);border-radius:0;overflow:hidden;
    background:var(--panel);margin:0 0 2px;}
/* ⚠️ BÜLTEN ŞERİDİ: iddaa'da lig adı koyu bantta beyaz yazar; kupon
   fişinin başlığı da o bandın karşılığı. --serit ile app_v2'nin kart
   başlıkları AYNI şeridi kullanıyor — iki ayrı gri ton, aynı ürünün iki
   ayrı yerden tasarlandığı izlenimi verirdi. */
.kf-bas{display:flex;align-items:center;gap:10px;padding:6px 12px;
    background:var(--serit,#282F33);border-bottom:0;}
.kf-tip{font-family:var(--mono,ui-monospace,monospace);font-size:10px;
    letter-spacing:.12em;font-weight:700;color:var(--serit-ink,#fff);}
.kf-mac-adet{font-family:var(--mono,ui-monospace,monospace);font-size:10px;
    letter-spacing:.12em;color:var(--serit-dim,#c9d4da);}
.kf-durum{margin-left:auto;font-size:11px;font-weight:600;padding:1px 8px;
    border-radius:10px;border:1px solid rgba(255,255,255,.25);
    color:var(--serit-ink,#fff);background:transparent;}
.kf-durum.kz{color:var(--pos);background:var(--pos-fill);border-color:transparent;}
.kf-durum.kb{color:var(--neg);background:var(--neg-fill);border-color:transparent;}
.kf-ayak{padding:7px 12px;border-bottom:1px solid var(--line);}
.kf-ayak:nth-child(even){background:var(--satir-alt,#eef2f4);}
.kf-ust{font-family:var(--mono,ui-monospace,monospace);font-size:10px;
    letter-spacing:.06em;color:var(--muted);}
.kf-mac{font-size:13.5px;font-weight:600;color:var(--ink);margin:1px 0 3px;
    line-height:1.3;}
.kf-mac span{font-weight:400;color:var(--muted);margin:0 2px;}
.kf-im{font-style:normal;margin-left:6px;font-weight:700;}
.kf-im.kz{color:var(--pos);} .kf-im.kb{color:var(--neg);}
.kf-im.ip{color:var(--muted);}
.kf-im.gec{font-size:10px;font-weight:600;color:var(--neg);
    background:var(--neg-fill);padding:0 6px;border-radius:9px;
    letter-spacing:.02em;}
.kf-alt{display:flex;align-items:center;gap:8px;}
.kf-pz{font-size:12px;color:var(--ink-2);flex:1 1 auto;}
.kf-sc{font-size:12px;font-weight:700;color:var(--ink);padding:1px 9px;
    border:1px solid var(--line-2);border-radius:3px;background:var(--panel-2);
    flex:0 0 auto;min-width:40px;text-align:center;}
.kf-or{font-family:var(--mono,ui-monospace,monospace);font-size:13.5px;
    font-weight:700;color:var(--ink);flex:0 0 auto;min-width:46px;
    text-align:right;}
.kf-dip{padding:8px 12px;background:var(--panel-2);}
.kf-dip-s{display:flex;justify-content:space-between;align-items:baseline;
    padding:2px 0;}
.kf-dip-s span{font-family:var(--mono,ui-monospace,monospace);font-size:10px;
    letter-spacing:.12em;color:var(--muted);}
.kf-dip-s b{font-family:var(--mono,ui-monospace,monospace);font-size:13px;
    font-weight:600;color:var(--ink);}
.kf-kazanc{border-top:1px solid var(--line-2);margin-top:4px;padding-top:6px;}
.kf-kazanc b{font-size:15px;color:var(--brand);}
.kf-olcu{display:flex;gap:18px;flex-wrap:wrap;padding:5px 12px 9px;}
.kf-olcu span{display:flex;flex-direction:column;gap:1px;}
.kf-olcu i{font-style:normal;font-family:var(--mono,ui-monospace,monospace);
    font-size:9.5px;letter-spacing:.12em;color:var(--muted);}
.kf-olcu b{font-family:var(--mono,ui-monospace,monospace);font-size:12.5px;
    font-weight:600;color:var(--ink-2);}
</style>
"""


def kendi_testi() -> list[str]:
    hata = []
    # 1) Çizgi pick'ten pazar adına taşınmalı
    for mkt, pick, bek_pz, bek_sc in (
            ("ALT_UST", "ÜST 1.5", "1,5 Alt/Üst", "Üst"),
            ("ALT_UST", "ALT 3.5", "3,5 Alt/Üst", "Alt"),
            ("UST_25", "UST", "2,5 Alt/Üst", "Üst"),
            ("ALT_25", "ALT", "2,5 Alt/Üst", "Alt"),
            ("1X2", "1", "Maç Sonucu", "1"),
            ("CIFTE_SANS", "12", "Çifte Şans", "1-2"),
            ("KG_YOK", "YOK", "Karşılıklı Gol", "Yok")):
        pz, sc = pazar_secim(mkt, pick)
        if (pz, sc) != (bek_pz, bek_sc):
            hata.append(f"{mkt}/{pick} → ({pz}, {sc}) ≠ ({bek_pz}, {bek_sc})")
    # 2) Beraberlik "0" olmalı, "X" değil
    if pazar_secim("1X2", "X")[1] != "0":
        hata.append("beraberlik 'X' gösteriliyor, bültende '0' yazar")
    # 3) Bozuk kickoff uydurma tarih üretmemeli
    for k in (None, "", "abc", "2026-11-02"):
        if _saat(k) != "":
            hata.append(f"bozuk kickoff'tan tarih uyduruldu: {k!r}")
    # ⚠️ SAAT DİLİMİ: kayıt UTC, ekran TÜRKİYE saati. Bu dönüşüm
    # atlanırsa maç 3 saat ERKEN görünür; kullanıcı onu geçmiş sanar ve
    # bültende o saatte bulamaz (yaşandı, 15.11.2026).
    if _saat("2026-11-02T20:15:00") != "02.11  23:15":
        hata.append(f"UTC→TR dönüşümü yok: {_saat('2026-11-02T20:15:00')}")
    # Gün sınırı: 22:30 UTC ertesi gün 01:30 TR
    if _saat("2026-11-15T22:30:00") != "16.11  01:30":
        hata.append(f"gün sınırı yanlış: {_saat('2026-11-15T22:30:00')}")
    # Ay/yıl sınırı
    if _saat("2026-12-31T22:00:00") != "01.01  01:00":
        hata.append(f"yıl sınırı yanlış: {_saat('2026-12-31T22:00:00')}")
    # ⚠️ KARŞILAŞTIRMA UTC'de KALMALI — başlamış mı sorusu ekran saatine
    # göre sorulursa 3 saatlik kayma filtreyi de bozar.
    import datetime as _d
    gelecek = (_d.datetime.now(_d.timezone.utc).replace(tzinfo=None)
               + _d.timedelta(hours=1)).isoformat(timespec="seconds")
    if basladi_mi({"kickoff": gelecek}):
        hata.append("1 saat sonraki maç başlamış sayıldı — karşılaştırma "
                    "UTC'den çıkmış olabilir")
    # 4) Fiş: maksimum kazanç bahis × oran
    k = {"tip": "master", "oran": 1.82, "durum": "acik", "bahis": 100.0,
         "ayaklar": [{"ev": "A", "dep": "B", "market": "1X2", "pick": "1",
                      "oran": 1.82, "kickoff": "2026-11-02T20:15:00",
                      "lig": "TR1", "kanit": True}]}
    h = fis(k)
    if "182,00 ₺" not in h:
        hata.append("maksimum kazanç yanlış hesaplandı")
    if "TEK MAÇ" not in h:
        hata.append("tek ayaklı kupon 'TEK MAÇ' demiyor")
    # 5) XSS: takım adı HTML olarak çalışmamalı
    k2 = dict(k)
    k2["ayaklar"] = [dict(k["ayaklar"][0], ev="<script>x</script>")]
    if "<script>" in fis(k2):
        hata.append("takım adı kaçırılmadan basıldı")
    # 6) Ölçüm fişin İÇİNDE olmamalı
    if "şans" in h.lower():
        hata.append("ölçüm fişin içine karışmış")
    # 7) Oran AŞAĞI yuvarlanmalı ve fişin aritmetiği tutmalı
    if kupon_orani(1.8172) != 1.81:
        hata.append(f"kupon oranı aşağı yuvarlanmadı: {kupon_orani(1.8172)}")
    if kupon_orani(1.829) != 1.82:
        hata.append("kupon oranı yukarı yuvarlandı — kazanç fazla görünür")
    k3 = dict(k, oran=1.8172)
    h3 = fis(k3)
    if "1,81" not in h3 or "181,00 ₺" not in h3:
        hata.append("fiş aritmetiği tutmuyor: ekrandaki oran × tutar "
                    "ekrandaki kazancı vermiyor")
    # 8) Kirli lig kodu 'ALL' basılmamalı
    k4 = dict(k, ayaklar=[dict(k["ayaklar"][0], lig="ALL")])
    if "ALL" in fis(k4):
        hata.append("lig kodu 'ALL' fişe basıldı — bilgi değil gürültü")
    # 9) CSS Türkçe büyük harfi bozmamalı
    if "text-transform:uppercase" in CSS:
        hata.append("CSS uppercase Türkçe'de bozuyor (dediği → DEDIĞI)")
    o = olcu_seridi({"sans": 0.5, "fiyat_sansi": 0.3, "ayaklar": []})
    if "DEDIĞI" in o or "DEDİĞİ" not in o:
        hata.append("ölçüm şeridi etiketi Türkçe değil")

    # ── BAŞLAMIŞ MAÇ (kullanıcı şikâyeti 15.11.2026) ─────────────
    gec = {"kickoff": "2020-01-01T12:00:00"}
    ger = {"kickoff": "2099-01-01T12:00:00"}
    if not basladi_mi(gec):
        hata.append("geçmiş maç başlamamış sayıldı")
    if basladi_mi(ger):
        hata.append("gelecek maç başlamış sayıldı")
    # ⚠️ Saati BİLİNMEYEN ayak oynanabilir sayılmamalı
    for bos in ({}, {"kickoff": None}, {"kickoff": ""}):
        if not basladi_mi(bos):
            hata.append(f"saati bilinmeyen ayak oynanabilir sayıldı: {bos}")
    # Tek ayağı bile başlamışsa kupon oynanamaz
    if oynanabilir({"ayaklar": [ger, gec]}):
        hata.append("bir ayağı başlamış kupon oynanabilir sayıldı")
    if not oynanabilir({"ayaklar": [ger, ger]}):
        hata.append("hepsi gelecekte olan kupon oynanamaz sayıldı")
    if oynanabilir({"ayaklar": []}):
        hata.append("ayaksız kupon oynanabilir sayıldı")
    # Fişte "başladı" rozeti görünmeli
    k5 = {"tip": "master", "oran": 1.50, "durum": "acik", "bahis": 100.0,
          "ayaklar": [dict(k["ayaklar"][0], kickoff="2020-01-01T12:00:00")]}
    if "başladı" not in fis(k5):
        hata.append("başlamış ayak fişte işaretlenmedi")
    # Sonuçlanmış ayakta sonuç rozeti kazanır, "başladı" yazmaz
    k6 = {"tip": "master", "oran": 1.50, "durum": "kazandi", "bahis": 100.0,
          "ayaklar": [dict(k["ayaklar"][0], kickoff="2020-01-01T12:00:00",
                           durum="won")]}
    if "başladı" in fis(k6):
        hata.append("sonuçlanmış ayakta 'başladı' yazıldı")
    return hata


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    h = kendi_testi()
    print("kendi testi:", "TEMİZ" if not h else f"{len(h)} sorun")
    for x in h:
        print("  ", x)
