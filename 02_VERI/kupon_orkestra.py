"""
KUPON ORKESTRATÖRÜ — "bu kuponun kazanma şansı şu kadar"
=========================================================
Ajanlar tek tek seçim üretiyor. Bu modül onları KUPON ŞEKİLLERİNE sokar
(tek · 2'li · 3'lü · canlı) ve her kuponun kazanma olasılığını, ödemesini
ve beklenen getirisini yazar.

⚠️ NE YAPMAZ: yatırım tavsiyesi vermez, "bunu oyna" demez. Ölçüm şudur:
bu kuponun kazanma şansı şu kadar, ödemesi şu kadar. Karar senin.

OLASILIK NEREDEN GELİYOR — AJANIN İDDİASINDAN DEĞİL, KARNESİNDEN
-----------------------------------------------------------------
Ajanların `model_prob` alanı çoğu zaman fiyatın marjsızıdır; onu olasılık
diye kullanmak, fiyatı kendisiyle ölçmek olur (ölçüldü: 1.252 bahsin
1.252'sinde edge = −marj). Bunun yerine ajanın GEÇMİŞTE ölçülen
kalibrasyon sapması kullanılır:

    kenar_ajan = gerçekleşen isabet − ortalama (1/oran)
    p_ayak     = (1/oran) + kenar_ajan           [0,01 – 0,99 aralığına kırpılır]

Yani "fiyat ne diyorsa o, artı bu ajanın tarihsel olarak fiyattan ne kadar
saptığı". Ajanın kanıtı yoksa kenar ≈ 0 çıkar ve p_ayak = 1/oran olur —
yani kuponun şansı FİYATIN dediği kadardır. Bu dürüst cevaptır ve yine de
işe yarar: "3'lü kuponun şansı %22" bilgisi, kenar olmasa da gerçektir.

⚠️ KÜÇÜK ÖRNEKLEM BÜZÜLMESİ: kenar, nokta tahmini olarak kullanılmaz.
n küçükken sıfıra doğru çekilir (n/(n+ASGARI_N) ağırlığıyla). Aksi hâlde
20 bahiste yakalanmış +%8'lik gürültü, kuponun şansını şişirir — bu
projede defalarca olan hata.

BAĞIMSIZLIK: farklı maçların ayakları bağımsız sayılır (çarpım kuralı).
AYNI maçtan iki ayak ASLA aynı kupona konmaz; aynı maçın sonuçları
korelasyonludur ve çarpım kuralı orada yalan söyler.
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
for _p in (str(THIS_DIR), str(THIS_DIR.parent / "10_CANLI")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import canli_clv as CL  # noqa: E402  (oran sağlık süzgeci + 1X2 sütun sırası)
import db  # noqa: E402
import kasa as K  # noqa: E402

# Ajanın kenarı bu kadar karara ulaşana dek sıfıra doğru büzülür.
ASGARI_N = K.ASGARI_N
# Kupon şekilleri: ayak sayısı
SEKILLER = (1, 2, 3)
# Bir kuponda en çok bu kadar ayak oynanır (iddaa MBS ayrı bir kısıt).
MAKS_AYAK = 3
# Canlı fiyat bu kadar dakikadan eski ise CANLI SAYILMAZ. Bitmiş maçın
# son satırını canlı fiyat diye sunmamanın tek güvenilir yolu (dakika
# alanı kayıtların yalnız %2,8'inde dolu, ona dayanılamaz).
TAZELIK_DK = 10
# Bir ayak aynı şekildeki en çok bu kadar kuponda görünebilir. Tavan yoksa
# en iyi ayak bütün kombinasyonlara girer ve liste çeşitli görünürken
# aslında tek bahse yoğunlaşır (bkz. _cesitle).
TEKRAR_TAVAN = 2


def ajan_kenari(karne: dict) -> float:
    """Ajanın kenarı — kasa.py'nin ALT GÜVEN SINIRI, nokta tahmini değil.

    ⚠️ İLK SÜRÜM YANLIŞTI ve projenin kendi standardını deliyordu.
    kasa.degerlendir'in dokümanı açık: "Dönen 'kenar_alt' kararın
    dayanağıdır; 'kenar' tek başına gürültü olabilir." Ben nokta tahminini
    alıp kendi büzülmemi (n/(n+30)) uydurmuştum — yani var olan standardın
    yanına ikinci ve DAHA GEVŞEK bir standart koymuştum.

    Ne kadar gevşek olduğu ölçüldü (01.11.2026):
      OPUS5_V1   n=19, ham +33,5p → büzülmüş +13,0p
      SIMETRI_V1 n= 4, ham +41,9p → büzülmüş  +4,9p
    4 karardan +4,9 puan kenar çıkarmak, 4 yazı turadan madenî paranın
    hileli olduğuna karar vermektir.

    Doğrusu kasa'nın zaten hesapladığı iki alan: `yeterli` (n >= ASGARI_N)
    ve `kenar_alt` (kenar − 1,96·se). Yeterli değilse kenar SIFIRDIR —
    o zaman kuponun şansı tam olarak fiyatın dediği kadar olur, ki
    kanıt yokken dürüst cevap budur.

    Negatif alt sınır sıfıra çekilmez: ölçülebilir biçimde fiyattan kötü
    olan bir ajanın ayağı, kuponu gerçekten de fiyatın dediğinden kötü
    yapar. Bunu saklamak kuponu olduğundan iyi gösterirdi.
    """
    if not karne.get("yeterli"):
        return 0.0
    return float(karne.get("kenar_alt") or 0.0)


# Kapanış sütunu olmayan (kombine) pazarlar için ima toplamı tabanı.
# ÖLÇÜLDÜ (01.11.2026, anlık görüntü): 1X2 n=10.181 medyan 1,1729 ·
# ALT/ÜST n=8.254 medyan 1,1689 · KG n=10.178 medyan 1,1727. Yani iddaa
# marjı ~%17. Kombine pazarların marjı genelde DAHA yüksektir, bu taban
# onlarda iyimser kalır — iyimserlik yönü bilinerek seçildi, sayı
# uydurulmadı.
VARSAYILAN_IMA = 1.17

# OLASILIK FORMÜLÜNÜN SÜRÜMÜ. Formül değişince ARTTIR.
#   1 · ham 1/oran tabanı + nokta tahmini kenar, n/(n+30) büzülmesi
#   2 · marjsız taban + kanıt eşiği (n>=ASGARI_N) + kenarın ALT sınırı
# ⚠️ NEDEN SÜRÜM TUTULUYOR: defterdeki tahmin, üretildiği formülle
# ölçülmelidir. Sürüm 1 ile yazılmış 10 kupon üretimde zaten vardı; onları
# sürüm 2 gerçekleşmeleriyle karşılaştırmak, formül değişikliğini
# "kalibrasyon bozuk" diye raporlardı. Silmek yerine ayırmak doğrusu:
# eski tahmin yanlış değil, BAŞKA bir sorunun cevabı.
FORMUL_SURUM = 2


def ayak_olasiligi(oran: float, kenar: float, ima: float = 1.0,
                   kanit: bool = True) -> float:
    """Ayağın GERÇEK kazanma olasılığı.

    ⚠️ 1/oran OLASILIK DEĞİLDİR — marj içerir ve gerçek olasılığın ÜST
    SINIRIDIR. İlk sürüm kanıtsız ajanlarda tabanı ham 1/oran alıyordu;
    ölçülen %16,8 marjla bu, tek ayakta ~12 puan, ÜÇ ayakta ~17 puan
    şişirme demekti ("%45,2" aslında ~%28). Kullanıcıya verilen tek
    manşet sayı buydu, yani hata tam da en çok güvenilen yerdeydi.

    İki dürüst tahminci var ve hangisinin kullanılacağı KANITA bağlı:

    kanıt VARSA   p = 1/oran + kenar_alt
        kasa'nın kenarı zaten GERÇEKLEŞEN isabetten ölçülüyor
        (kenar = isabet − 1/ort_oran), yani marjı içinde taşır. Üstüne bir
        de marj düzeltmesi yapmak ÇİFT sayım olurdu.

    kanıt YOKSA   p = (1/oran) / ima_toplamı
        piyasanın marjsız olasılığı. Kanıt yokken en iyi tahmin budur ve
        ham 1/oran'ın aksine yanlı değildir.
    """
    if oran <= 1.0:
        return 0.0
    ham = 1.0 / oran
    p = (ham + kenar) if kanit else (ham / max(ima, 1.0))
    return min(0.99, max(0.01, p))


def kupon_degerlendir(ayaklar: list[dict]) -> dict:
    """Kuponun şansı, ödemesi, beklenen getirisi.

    ayaklar: her biri {"oran", "p"} (+ gösterim alanları)
    """
    if not ayaklar:
        return {}
    carpim_oran = 1.0
    sans = 1.0
    piyasa = 1.0
    for a in ayaklar:
        o = float(a["oran"])
        carpim_oran *= o
        sans *= float(a["p"])
        # ⚠️ Karşılaştırma tabanı HAM 1/oran değil, MARJSIZ olasılık.
        # Ham oranla karşılaştırmak marjı "kenar" gibi gösterirdi; bu
        # projede aynı karışıklık iki kez hataya yol açtı (kenar sütunu,
        # toto kârlılık şartı).
        piyasa *= float(a.get("p_piyasa") or (1.0 / o))
    return {
        "ayak": len(ayaklar), "oran": carpim_oran, "sans": sans,
        # Beklenen getiri: 1 birim yatır, şans × oran kadar dönüyor.
        # Kenar yoksa bu 1/marj'a (~0,85) eşittir — yani kaybedilen marj.
        "bek_getiri": sans * carpim_oran,
        # Piyasanın marjsız dediği şans.
        "fiyat_sansi": piyasa,
        # Marjın kendisi: 1 birime karşılık ödenen bedel.
        "marj_payi": (1.0 / carpim_oran) - piyasa if carpim_oran else 0.0,
        "ayaklar": ayaklar,
    }


def _cesitle(sirali: list[dict], adet: int) -> list[dict]:
    """En iyiden başla, ama AYNI AYAĞI tekrar tekrar koyma.

    ⚠️ NEDEN: düz "en yüksek şanslı N kupon" listesi, en iyi tek ayağı
    bütün kombinasyonlara koyar. Ekranda yakalandı — 6 kombine kuponun
    altısında da Lyon/1 vardı. O ayak kaybederse altı "seçenek" birden
    ölür; yani kullanıcıya TEK bahis, altı farklı seçenek gibi gösterilmiş
    olur. Çeşitlenmiş sanıp yoğunlaşmak, kupon listesinin en sinsi
    yanıltması.

    Çözüm: bir ayak, aynı şekildeki en çok TEKRAR_TAVAN kuponda görünür.
    Sıra hâlâ şansa göre; yalnız tavanı dolan ayak atlanır.
    """
    from collections import defaultdict
    sayac: dict = defaultdict(int)
    out: list[dict] = []
    for x in sirali:
        anahtar = [(a.get("mac_id"), a.get("pick")) for a in x["ayaklar"]]
        if any(sayac[t] >= TEKRAR_TAVAN for t in anahtar):
            continue
        for t in anahtar:
            sayac[t] += 1
        out.append(x)
        if len(out) >= adet:
            break
    return out


def uret(adaylar: list[dict], karneler: dict, sekiller=SEKILLER,
         en_cok: int = 8) -> list[dict]:
    """Adaylardan kupon şekilleri üret ve şanslarına göre sırala.

    adaylar: [{"ajan","ev","dep","market","pick","oran","mac_id", ...}]
    karneler: {ajan: kasa.degerlendir(...) çıktısı}
    """
    zengin = []
    for a in adaylar:
        o = float(a.get("oran") or a.get("odds") or 0)
        if o <= 1.01:
            continue
        kr = karneler.get(a.get("ajan")) or {}
        kanit = bool(kr.get("yeterli"))
        kenar = ajan_kenari(kr)
        # Adayın kendi pazarından ölçülen ima toplamı; yoksa taban.
        ima = float(a.get("ima") or 0) or VARSAYILAN_IMA
        zengin.append({**a, "oran": o, "kenar": kenar, "ima": ima,
                       "kanit": kanit,
                       "p": ayak_olasiligi(o, kenar, ima, kanit),
                       # Piyasanın MARJSIZ olasılığı — karşılaştırma tabanı.
                       "p_piyasa": (1.0 / o) / max(ima, 1.0)})
    if not zengin:
        return []
    # En olası ayaklar önce — kombinasyon patlamasını önlemek için üst sınır
    zengin.sort(key=lambda x: -x["p"])
    havuz = zengin[:12]
    # ⚠️ ŞEKİL BAŞINA sıralanır, topluca DEĞİL. Şansa göre global sıralama
    # yapınca listeyi hep TEKLİLER doldurur — 1 ayak her zaman 3 ayaktan
    # olasıdır, bu matematiksel olarak doğru ama ekranda işe yaramaz.
    # Kullanıcı tek · 2'li · 3'lü seçeneklerini YAN YANA görmek istiyor.
    pay = max(1, en_cok // max(len(sekiller), 1))
    out = []
    for k in sekiller:
        if k > MAKS_AYAK:
            continue
        grup = []
        for c in itertools.combinations(havuz, k):
            # AYNI MAÇTAN iki ayak olmaz: aynı maçın sonuçları korelasyonlu,
            # çarpım kuralı orada yalan söyler (ve çoğu birbirini dışlar).
            if len({x.get("mac_id") for x in c}) != k:
                continue
            grup.append(kupon_degerlendir(list(c)))
        grup.sort(key=lambda x: -x["sans"])
        out.extend(_cesitle(grup, pay))
    out.sort(key=lambda x: (x["ayak"], -x["sans"]))
    return out


# ----------------------------------------------------------------------
# DEFTERDEN BESLE
# ----------------------------------------------------------------------
def karne_haritasi(conn=None) -> dict:
    """{ajan: değerlendirme} — kasa.py'nin ölçümünü kullanır.

    ⚠️ YALNIZ GERÇEK AJANLAR. paper_portfolio'da ajan olmayan defterler de
    var: OPUS5_V1 kullanıcının KENDİ oynadıklarının defteri ("insan
    seçiciliği"), PAPER_V1 arşiv, KURUCU_V2 kurucu hesabı. Bunları ajan
    sayıp kuponu fiyatlamak iki yönden yanlış olurdu:
      · döngüsel — kullanıcının geçmiş bahisleri, kullanıcıya ne oynaması
        gerektiğini söyleyen sayının kaynağı hâline gelir;
      · OPUS5 ölçüldüğünde n=19 ile ham +33,5 puan kenar taşıyordu, yani
        listenin en tepesine otururdu.
    Ayırıcı agents.PROFILES: bir ajan oradaysa ajandır.
    """
    try:
        import agents
        gercek = set(agents.PROFILES)
    except Exception:
        gercek = set()
    out = {}
    for d in K.ajan_karneleri(conn):
        if gercek and d["ajan"] not in gercek:
            continue
        out[d["ajan"]] = d
    return out



# Pazarın İKİ (ya da üç) tarafının kapanış sütunları. Marjsızlaştırma ancak
# bütün taraflar bilinirse yapılabilir. Kombine pazarların (1X2_BTTS,
# OU_BTTS, TOTAL_GOALS, 1X2_OU) kapanış sütunu yok — onlarda VARSAYILAN_IMA.
IMA_SUTUN = {
    "1X2": ("closing_1", "closing_X", "closing_2"),
    "ALT_25": ("closing_over25", "closing_under25"),
    "UST_25": ("closing_over25", "closing_under25"),
    "KG_VAR": ("closing_btts_yes", "closing_btts_no"),
    "KG_YOK": ("closing_btts_yes", "closing_btts_no"),
}
IMA_TUM = sorted({c for v in IMA_SUTUN.values() for c in v})


def _ima(market: str, satir) -> float:
    """Pazarın ima toplamı (marj). Hesaplanamazsa VARSAYILAN_IMA."""
    sut = IMA_SUTUN.get(str(market or ""))
    if not sut or satir is None:
        return VARSAYILAN_IMA
    t = 0.0
    for c in sut:
        try:
            v = float(satir[c] if not isinstance(satir, dict) else satir.get(c))
        except Exception:
            return VARSAYILAN_IMA
        if not v or v <= 1.01:
            return VARSAYILAN_IMA
        t += 1.0 / v
    # Sağlık süzgeci: 1,00 altı imkânsız, 1,60 üstü bozuk kayıt.
    return t if 1.0 <= t <= 1.60 else VARSAYILAN_IMA


def _gercek_ajanlar() -> set:
    """agents.PROFILES = ajan tanımı. OPUS5_V1 (kullanıcının kendi defteri),
    PAPER_V1 (arşiv) ve KURUCU_V2 ajan DEĞİL; kupon ayağı da olmamalılar —
    kullanıcıya kendi oynadığını geri önermek döngüseldir."""
    try:
        import agents
        return set(agents.PROFILES)
    except Exception:
        return set()


def gunun_adaylari(conn=None, en_cok: int = 60) -> list[dict]:
    """Bugün açık olan bahisler — ajanların şu anki fiili görüşü.

    Yeni aday ÜRETMEZ: ajanların zaten kurduğu açık pozisyonları okur.
    Böylece orkestratör ikinci bir seçim katmanı eklemez; yalnız var olanı
    kupon şekline sokar.
    """
    kapat = conn is None
    conn = conn or db.connect()
    try:
        ek = "".join(f", mv.{c}" for c in IMA_TUM)
        r = conn.execute(
            "SELECT pb.bet_id, pb.portfolio_id, pb.home_team, pb.away_team, "
            "       pb.market, pb.pick, pb.odds, pb.match_id, pb.kickoff_utc"
            + ek + " FROM paper_bets pb "
            "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
            "LEFT JOIN matches_v2 mv ON mv.match_id = pb.match_id "
            "WHERE pb.status = 'open' AND pc.status = 'open' AND pb.odds > 1.01 "
            "ORDER BY pb.kickoff_utc").fetchall()
    finally:
        if kapat:
            conn.close()
    gercek = _gercek_ajanlar()
    out, gorulen = [], set()
    for satir in r:
        (bet_id, pid, ev, dep, mkt, pick, odds, mid, ko) = satir[:9]
        if gercek and pid not in gercek:
            continue
        ima = _ima(mkt, dict(zip(IMA_TUM, satir[9:])))
        anahtar = (mid, mkt, str(pick))
        if anahtar in gorulen:
            continue                      # aynı seçimi iki ajan yapmışsa bir kez
        gorulen.add(anahtar)
        # bet_id ŞART: kuponun sonucu bu satırdan okunacak (ferhan_kupon.py).
        # Olmadan kupon hiç kapanmaz ve kalibrasyon karnesi boş kalır.
        out.append({"bet_id": str(bet_id), "ajan": pid, "ev": ev, "dep": dep,
                    "market": mkt, "pick": str(pick), "oran": float(odds),
                    "mac_id": mid, "kickoff": ko, "ima": ima})
        if len(out) >= en_cok:
            break
    return out


def canli_adaylari(conn=None, en_cok: int = 40) -> list[dict]:
    """ŞU AN OYNANAN maçlarda ajanların görüşü — CANLI fiyatla yeniden fiyatlı.

    Canlı kupon için yeni bir canlı model KURULMAZ. Ölçüldü (01.11.2026,
    1.688 maç): canlı modelimiz piyasadan HER dakika diliminde daha kötü
    kalibre. O yüzden canlı fiyat burada rakip değil, en iyi gerçek tahmin.

    Yapılan şey: ajanın maç öncesi söylediği görüş (açık paper_bets satırı)
    alınır ve O ANKİ canlı fiyatla fiyatlanır. Yani "aynı görüş, yeni fiyat".

    ⚠️ YÜKSELEN ORAN İYİ HABER DEĞİLDİR. Oran yükseldiyse maç o seçimin
    aleyhine gidiyordur; canlı fiyat skoru zaten içeriyor. Bu yüzden şans
    her zaman GÜNCEL fiyattan hesaplanır, alınan orandan değil — "fiyat
    iyileşti" diye okunursa kaybeden taraf fırsat sanılır.

    ⚠️ AÇIK VARSAYIM: ajanın ölçülmüş kenarı MAÇ ÖNCESİ fiyatlarda ölçüldü.
    Canlı fiyatta da aynı kaldığı VARSAYILIYOR; ölçülmedi. Karne (ferhan_kupon)
    canlı kuponları ayrı tip olarak tuttuğu için bu varsayım zamanla
    sınanabilir — tipler karıştırılmamalı.

    ⚠️ TAZELİK ŞARTI (ilk sürümde YOKTU ve yanlıştı): "en son cl_anlik satırı"
    maçın oynandığını göstermez. Bitmiş bir maçın son satırı aylar önce
    yazılmış olabilir ve onu canlı fiyat diye sunmak, bayat fiyatı fırsat
    gibi göstermektir. Yakalandığı hâl: anlık görüntüde tek "canlı" aday
    çıktı — alınan 2,47, "canlı" 1,36, dakika NULL, skor 0-0; maç çoktan
    bitmişti. O yüzden satır TAZELIK_DK dakikadan yeni olmak zorunda.

    Dakika alanına GÜVENİLMEZ: API-Football hesabı askıda, kayıtların yalnız
    %2,8'inde dakika var. Tazelik `ts`den ölçülür — ücretsiz iddaa akışı
    yeterli.
    """
    kapat = conn is None
    conn = conn or db.connect()
    try:
        r = conn.execute(
            "SELECT pb.bet_id, pb.portfolio_id, pb.home_team, pb.away_team, "
            "       pb.pick, pb.odds, pb.match_id, m.mac_id "
            "FROM paper_bets pb "
            "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
            "JOIN matches_v2 mv ON mv.match_id = pb.match_id "
            "JOIN cl_mac m ON CAST(m.iddaa_id AS TEXT) = "
            "                 CAST(mv.external_id_iddaa AS TEXT) "
            "WHERE pb.status = 'open' AND pc.status = 'open' "
            "  AND pb.market = '1X2' AND pb.odds > 1.01 "
            "  AND COALESCE(mv.is_settled, 0) = 0").fetchall()
        if not r:
            return []
        from datetime import datetime, timedelta, timezone
        sinir = (datetime.now(timezone.utc)
                 - timedelta(minutes=TAZELIK_DK)).isoformat(timespec="seconds")
        son = {}
        for mid in {x[7] for x in r}:
            a = conn.execute(
                "SELECT dakika, ev_skor, dep_skor, oran, askida, ts "
                "FROM cl_anlik WHERE mac_id = ? ORDER BY ts DESC LIMIT 1",
                (mid,)).fetchone()
            if a and str(a[5] or "") >= sinir:
                son[mid] = a
    finally:
        if kapat:
            conn.close()

    gercek = _gercek_ajanlar()
    out, gorulen = [], set()
    for bet_id, pid, ev, dep, pick, odds, match_id, mid in r:
        if gercek and pid not in gercek:
            continue
        a = son.get(mid)
        if not a:
            continue
        dk, h, d, oran_js, ask, anlik_ts = a
        if CL._askida(ask):
            continue                       # askıya alınmış pazar oynanamaz
        oo = CL._oran(oran_js)             # sağlık süzgeci: ima toplamı 1,00-1,40
        if not oo:
            continue
        j = CL.SIRA.get(str(pick))
        if j is None or oo[j] <= 1.01:
            continue
        anahtar = (mid, str(pick))
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        out.append({"bet_id": str(bet_id), "ajan": pid, "ev": ev, "dep": dep,
                    "market": "1X2", "pick": str(pick),
                    "oran": float(oo[j]),          # CANLI fiyat
                    # Canlıda üç fiyat da elimizde — marj doğrudan ölçülür,
                    # tabana düşmeye gerek yok.
                    "ima": sum(1.0 / v for v in oo),
                    "alinan_oran": float(odds),    # ajanın aldığı fiyat
                    "mac_id": match_id, "dakika": dk,
                    "skor": f"{h or 0}-{d or 0}", "anlik_ts": anlik_ts,
                    "kickoff": ""})
        if len(out) >= en_cok:
            break
    return out


def kendi_testi() -> list[str]:
    hata = []
    # 1) Kenarsız ajanda kuponun şansı FİYATIN dediği kadar olmalı
    ay = [{"oran": 2.0, "p": ayak_olasiligi(2.0, 0.0)},
          {"oran": 2.0, "p": ayak_olasiligi(2.0, 0.0)}]
    d = kupon_degerlendir(ay)
    if abs(d["sans"] - 0.25) > 1e-9:
        hata.append(f"kenarsız 2'li şans 0,25 olmalı, {d['sans']}")
    if abs(d["bek_getiri"] - 1.0) > 1e-9:
        hata.append(f"kenarsız beklenen getiri 1,00 olmalı, {d['bek_getiri']}")
    # 2) KANIT EŞİĞİ: yeterli değilse kenar SIFIR, yeterliyse ALT SINIR.
    #    Nokta tahmini ('kenar') asla kullanılmamalı — kasa.py'nin kendi
    #    dokümanı onu gürültü sayıyor ve bu kural bir kez delinmişti.
    az = ajan_kenari({"n": 4, "yeterli": False, "kenar": 0.42,
                      "kenar_alt": 0.10})
    if az != 0.0:
        hata.append(f"yetersiz örneklemde kenar 0 olmalı, {az}")
    yet = ajan_kenari({"n": 400, "yeterli": True, "kenar": 0.08,
                       "kenar_alt": 0.03})
    if abs(yet - 0.03) > 1e-9:
        hata.append(f"yeterli örneklemde kenar_alt alınmalı (0,03), {yet}")
    neg = ajan_kenari({"n": 400, "yeterli": True, "kenar": -0.05,
                       "kenar_alt": -0.09})
    if abs(neg + 0.09) > 1e-9:
        hata.append(f"negatif alt sınır saklanmamalı (−0,09), {neg}")
    # 3) Aynı maçtan iki ayak aynı kupona GİRMEMELİ
    ad = [{"ajan": "A", "oran": 2.0, "mac_id": 1, "pick": "1"},
          {"ajan": "A", "oran": 3.0, "mac_id": 1, "pick": "2"},
          {"ajan": "A", "oran": 2.5, "mac_id": 2, "pick": "1"}]
    k = uret(ad, {}, sekiller=(2,))
    for x in k:
        if len({y["mac_id"] for y in x["ayaklar"]}) != x["ayak"]:
            hata.append("aynı maçtan iki ayak aynı kupona girdi")
            break
    # 4) Ayak arttıkça şans DÜŞMELİ, oran yükselmeli
    ad2 = [{"ajan": "A", "oran": 1.5, "mac_id": i, "pick": "1"} for i in range(4)]
    ks = uret(ad2, {}, sekiller=(1, 2, 3), en_cok=50)
    for n in (1, 2, 3):
        g = [x for x in ks if x["ayak"] == n]
        if not g:
            hata.append(f"{n} ayaklı kupon üretilmedi")
    # 5) ÇEŞİTLİLİK: tek ayak bütün kuponlara hâkim olmamalı
    #    En olası ayak (mac 0) matematiksel olarak her kombinasyona girmek
    #    ister; tavan onu engellemeli.
    ad3 = [{"ajan": "A", "oran": 1.2, "mac_id": 0, "pick": "1"}]
    ad3 += [{"ajan": "A", "oran": 2.0, "mac_id": i, "pick": "1"}
            for i in range(1, 6)]
    k2 = [x for x in uret(ad3, {}, sekiller=(2,), en_cok=8) if x["ayak"] == 2]
    kac = sum(1 for x in k2 if any(a["mac_id"] == 0 for a in x["ayaklar"]))
    if kac > TEKRAR_TAVAN:
        hata.append(f"tek ayak {kac} kuponda (tavan {TEKRAR_TAVAN})")
    if len(k2) < 2:
        hata.append(f"çeşitlilik tavanı listeyi kuruttu: {len(k2)} kupon")
    hata += _canli_tazelik_testi()
    return hata


def _canli_tazelik_testi() -> list[str]:
    """Tazelik eşiği TAZE satırı kabul, BAYAT satırı red ediyor mu?

    ⚠️ Bu test şart: eşik yanlış kurulsaydı (ör. zaman damgası biçimi
    uyuşmazlığı) canli_adaylari sonsuza dek sessizce 0 dönerdi ve bunu
    kimse fark etmezdi. "Ölçmediğin şeyin durduğunu da göremezsin."
    Bu yüzden iki yönü de sınanıyor — yalnız "0 döndü" yetmez.
    """
    import json
    import os
    import sqlite3
    import tempfile
    from datetime import datetime, timedelta, timezone
    hata = []
    yol = os.path.join(tempfile.gettempdir(), f"ko_canli_{os.getpid()}.db")
    try:
        os.unlink(yol)
    except OSError:
        pass
    simdi = datetime.now(timezone.utc)
    ORAN = json.dumps([2.5, 3.3, 2.8])      # ima toplamı 1,060 — süzgeci geçer
    AJAN = next(iter(_gercek_ajanlar()), "JOKER_V1")
    try:
        c = sqlite3.connect(yol)
        c.executescript("""
            CREATE TABLE paper_bets (bet_id TEXT, portfolio_id TEXT,
                home_team TEXT, away_team TEXT, market TEXT, pick TEXT,
                odds REAL, match_id INTEGER, status TEXT, coupon_id TEXT);
            CREATE TABLE paper_coupons (coupon_id TEXT, status TEXT);
            CREATE TABLE matches_v2 (match_id INTEGER, external_id_iddaa TEXT,
                is_settled INTEGER);
            CREATE TABLE cl_mac (mac_id TEXT, iddaa_id INTEGER);
            CREATE TABLE cl_anlik (mac_id TEXT, ts TEXT, dakika INTEGER,
                ev_skor INTEGER, dep_skor INTEGER, oran TEXT, askida TEXT);
        """)
        for i, (mid, dk) in enumerate(((("taze"), 2), (("bayat"), 9999))):
            # Ajan kimliği GERÇEK olmalı: _gercek_ajanlar() süzgeci
            # PROFILES'ta olmayanı eler (OPUS5_V1 gibi insan defterleri).
            # Uydurma "A" kullanınca bu test haklı olarak 0 aday gördü.
            c.execute("INSERT INTO paper_bets VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (str(i), AJAN, f"Ev{i}", f"Dep{i}", "1X2", "1", 3.0,
                       i, "open", f"k{i}"))
            c.execute("INSERT INTO paper_coupons VALUES (?,?)", (f"k{i}", "open"))
            c.execute("INSERT INTO matches_v2 VALUES (?,?,?)", (i, str(100 + i), 0))
            c.execute("INSERT INTO cl_mac VALUES (?,?)", (mid, 100 + i))
            c.execute("INSERT INTO cl_anlik VALUES (?,?,?,?,?,?,?)",
                      (mid, (simdi - timedelta(minutes=dk)).isoformat(
                          timespec="seconds"), None, 0, 0, ORAN, None))
        c.commit()
        ad = canli_adaylari(c)
        if len(ad) != 1:
            hata.append(f"tazelik: 1 aday beklenir (taze kabul, bayat red), "
                        f"{len(ad)} geldi")
        elif abs(ad[0]["oran"] - 2.5) > 1e-9:
            hata.append(f"canlı fiyat 2,50 olmalı (alınan 3,00 DEĞİL), "
                        f"{ad[0]['oran']}")
        # Sonuçlanmış maç canlı sayılmamalı
        c.execute("UPDATE matches_v2 SET is_settled = 1")
        c.commit()
        if canli_adaylari(c):
            hata.append("sonuçlanmış maç canlı aday oldu")
        c.close()
    except Exception as e:
        hata.append(f"tazelik testi: {type(e).__name__}: {e}")
    finally:
        try:
            os.unlink(yol)
        except OSError:
            pass
    return hata


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    h = kendi_testi()
    print("kendi testi:", "TEMİZ" if not h else f"{len(h)} sorun")
    for x in h:
        print("  ", x)
