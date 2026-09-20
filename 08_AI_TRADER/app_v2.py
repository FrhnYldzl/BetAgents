"""
◉ BETAGENTS DESK — V2
=======================================================================
Mevcut uygulamaya (app_unified, 8500) DOKUNMAZ. Ayrı dosya, ayrı port.
Son hâli oturunca geçiş yapılır.

  python -m streamlit run app_v2.py --server.port 8600

TASARIM: açık ekran finansal panel. Bloomberg terminalinin beyaz hâli —
koyu tek eleman üstteki durum şeridi, gerisi kâğıt. Rakamlar tabular
figürlü monospace (sütunlar hizalansın), metin Archivo.

ÜRÜN TEZİ — bu sayfanın var olma sebebi:
    İSABET ORANI YANILTIR. %75 isabet, oran 1,24'te KÖTÜDÜR (fiyat
    zaten %80,6 bekliyordu). %59 isabet, oran 1,84'te İYİDİR. Doğru
    ölçü isabet değil, FİYATIN BEKLEDİĞİNDEN NE KADAR FAZLASI.
    Moneyball'ın vuruş ortalaması → on-base yüzdesi geçişinin karşılığı.

    Ve kombine kupon, marjı ÇARPAR. Tek ayakta -%13, iki ayakta -%28,
    üç ayakta -%38 — hiçbir şeyde yanılmadan önce. Kupon tezgahı bunu
    ekleme yaptıkça canlı gösterir; sezginin fiyatı görünür olur.
"""
from __future__ import annotations

import math
import os
import sys
import threading
from pathlib import Path

import streamlit as st

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(THIS_DIR.parent / "02_VERI"))

# ── YEREL GELİŞTİRME: üretimin bağlantısını çalma ─────────────
# ⚠️ Railway'in genel proxy'si eşzamanlı bağlantıyı sert kısıtlıyor.
# Bu uygulama yerelde `streamlit run` ile açıldığında üretimin kullandığı
# AYNI proxy'ye bağlanıyordu ve canlı site donuyordu — bu oturumda iki
# kez yaşandı, yerel doğrulama hiç yapılamadı.
#
# Çözüm UYGULAMA DÜZEYİNDE, db.py düzeyinde DEĞİL: db.py "üretimde
# değilsen localhost'a düş" deseydi bütün ölçüm ve onarım betikleri de
# (olcum_defteri, fix_early_settled, audit_*) sessizce başka bir
# veritabanına giderdi — onlar .env üzerinden ÜRETİME bağlanmalı, çünkü
# ölçülecek veri orada. Uzun ömürlü bağlantı tutan tek şey BU uygulama.
#
# Kullanıcı açıkça bir kip seçtiyse ona dokunulmaz.
if (not os.environ.get("RAILWAY_ENVIRONMENT_NAME")
        and not os.environ.get("BETAGENTS_DB")):
    os.environ["BETAGENTS_DB"] = "local"   # `railway tunnel 5432` bekler

# ⚠️ "expanded": kenar cubugu masaustunde ACIK baslar. "auto" yanlis
# karar veriyordu — 1600px'te bile kapali aciliyor ve kullanici
# hamburger aramak zorunda kaliyordu. Mobil davranis (uzerine acilan
# cekmece) zaten standarttir ve CSS ile ele aliniyor.
try:
    st.set_page_config(page_title="BetAgents Desk", page_icon="◉",
                       layout="wide", initial_sidebar_state="expanded")
except Exception:
    pass


# ══════════════════════════════════════════════════════════════
# VERİ
# ══════════════════════════════════════════════════════════════

def _load_env() -> None:
    """Proje kökündeki .env'i ortama al (API anahtarları). DATABASE_URL
    orada YOKSA db.py yerel SQLite'a düşer — bu meşru bir yerel geliştirme
    yolu, ama hangi veritabanına baktığın EKRANDA yazmalı."""
    import os
    for p in (THIS_DIR.parent / ".env", THIS_DIR.parent.parent / ".env"):
        if not p.exists():
            continue
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except Exception:
            pass


_load_env()


def _kaynak() -> str:
    """Hangi veritabanı? Yanlış kaynağı üretim sanmak, yanlış rakama
    güvenmektir — bu yüzden durum şeridinde açıkça yazar."""
    import os
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if url.startswith("postgres"):
        return "PostgreSQL · Railway"
    if os.environ.get("PGHOST"):
        return "PostgreSQL · PG*"
    return "SQLite · YEREL"


# ⚠️ PAYLASILAN BAGLANTI ESZAMANLILIK KILIDI
# @st.cache_resource nesneyi TUM oturumlar arasinda paylasir. psycopg2
# baglantisi es zamanli sorguya uygun DEGILDIR: iki oturum ayni anda
# sorgu acarsa baglanti kilitlenir ve sayfa sonsuza kadar "calisiyor"
# kalir. Yerelde tek oturum oldugu icin gorunmedi; canlida ilk deploy'da
# sayfa hic acilmadi. Kilit sorgulari siraya sokar — baglanti kurma
# maliyetinden (~1,5 sn) kacinmanin bedeli budur ve ucuzdur.
_SORGU_KILIDI = threading.Lock()


@st.cache_resource(show_spinner=False)
def _conn():
    """TEK paylasilan baglanti — rerun'lar arasinda yasar.

    NEDEN: Railway PG proxy'sinde baglanti KURMAK pahali (~1,5 sn),
    sorgunun kendisi ucuz. Eskiden her sorgu yeni baglanti aciyordu:
    Sistem sayfasi 10 baglanti ~ 15 sn soguk acilis demekti. Sayfa
    gecislerindeki SOLMA bundandi — Streamlit ekrani soldurup baglanti
    kurulmasini bekliyordu.

    Bayat baglanti riski var (proxy dusurebilir), o yuzden _rows hata
    alinca onbellegi temizleyip TAZE baglantiyla bir kez daha dener.

    ⚠️ AUTOCOMMIT — 13 Eylul 2026 olayi. psycopg2 her SELECT'i ortuk bir
    islem icinde calistirir ve biz hic commit etmiyorduk: baglanti
    "idle in transaction" kaliyor, okudugu tablolarin kilidini SURESIZ
    tutuyordu. Worker'in ALTER TABLE'i bu kilidin arkasinda, kupon
    kapatma da ALTER'in arkasinda bekledi — oynanmis maclar saatlerce
    "acik" gorundu. Bu uygulama YALNIZ OKUR: her sorgu kendi islemi
    olmali ve bitince kilidi birakmali.
    lock_timeout: bir sorgu kilit beklerse sayfa sonsuza dek donmasin;
    8 sn sonra hata versin (_rows yakalar, panel bos kalir, sayfa acilir)."""
    import db as _db
    c = _db.connect()
    if getattr(c, "is_postgres", False):
        try:
            c.raw.autocommit = True
            c.execute("SET lock_timeout = '8s'")
        except Exception:
            pass
    return c


def _sahadaki_ajanlar() -> set:
    """PROFILES'ta olan ve EMEKLİ OLMAYAN portföyler.

    ⚠️ Neden gerekli: sorgulardaki dönem koşulu
        (pp.era_start IS NULL OR ... >= pp.era_start)
    İZİN VERİCİ bir yedek ve HER ŞEYİ SIZDIRIYOR:
      · ajan olmayan portföyler (PAPER_V1 arşiv, OPUS5_V1 gerçek
        defter, KURUCU_V2) — era_start'ları NULL, koşul onları geçirir
      · emekli ajanlar — dönem 2'de kaldılar, kendi era_start'larına
        göre eski kuponları hâlâ "dönem içi" sayılır
    Sonuç canlıda görüldü: Ajan Ligi "yürürlükteki dönem" diyor ama
    kasa eğrisi MAYIS'a kadar uzanıyor ve NET −4.706 ₺ gösteriyordu;
    KURUCU (ajan değil) Mavi Takım'da n=80 ile listeleniyordu.
    """
    try:
        from agents import PROFILES as _AGP
        return {k for k, v in _AGP.items() if not v.get("retired")}
    except Exception:
        return set()


def _sahada_sql(kolon: str = "pb.portfolio_id") -> str:
    """SQL parçası: yalnız sahadaki ajanlar. Boşsa filtre uygulanmaz."""
    a = _sahadaki_ajanlar()
    if not a:
        return ""
    return (" AND " + kolon + " IN (" +
            ",".join("'" + x.replace("'", "") + "'" for x in sorted(a)) + ")")


def _rows(sql: str, params: tuple = (), sessiz: bool = False) -> list[dict]:
    """Paylasilan baglanti uzerinden sorgu + bayatlarsa 1 tazeleme.

    sessiz=True: tablo henuz yoksa bos liste don. Olcum defteri tablosu
    (measurement_runs) ilk kosudan once yoktur; bunun yuzunden tum sayfa
    cokmemeli — eksik bir panel, coken bir sayfadan iyidir."""
    last = None
    for deneme in (1, 2):
        try:
            with _SORGU_KILIDI:
                return [dict(r) for r in _conn().execute(sql, params).fetchall()]
        except Exception as e:
            last = e
            msg = str(e).lower()
            yok = ("no such table" in msg or "does not exist" in msg
                   or "undefinedtable" in msg)
            # PG'de basarisiz ifade islemi ABORT eder — sonraki her sorgu
            # da patlar. Geri almadan devam etmek tum sayfayi cokertir.
            try:
                with _SORGU_KILIDI:
                    _conn().rollback()
            except Exception:
                _conn.clear()
            if sessiz and yok:
                return []
            if deneme == 1 and not yok:
                _conn.clear()          # bayat/kirik baglanti: taze ac
    if sessiz:
        return []
    raise last


# ölçülen marj katsayıları (31.08.2026, iddaa kapanış fiyatları)
MARGIN = {
    "1X2": 1.176, "UST_25": 1.174, "ALT_25": 1.174, "OU2.5": 1.174,
    "KG_VAR": 1.164, "KG_YOK": 1.164, "BTTS": 1.164,
    "1X2_OU": 1.195, "1X2_BTTS": 1.204, "OU_BTTS": 1.186,
    "TOTAL_GOALS": 1.196, "HT_FT": 1.258,
}
CODE = {"E0": "ENG", "I1": "ITA", "SP1": "ESP", "D1": "GER", "T1": "TUR",
        "F1": "FRA", "BRA1": "BRA", "USA1": "USA", "N1": "NED", "P1": "POR"}
LEAGUE = {"E0": "Premier Lig", "I1": "Serie A", "SP1": "La Liga",
          "D1": "Bundesliga", "T1": "Süper Lig", "F1": "Ligue 1",
          "BRA1": "Brasileirão", "USA1": "MLS"}
# Ajan monogramlari — emoji yerine borsa sembolu mantigi.
# Emoji finansal panelde laubali durur ve Windows'ta bir kismi
# render olmaz (bayraklar harf ciftine duser). Iki harf her yerde
# ayni gorunur, hizalanir ve takima gore renklenir.
MONO = {
    "TEMKINLI_V1": "TK", "AVCI_V1": "AV", "MEMUR_V1": "MM", "HOCA_V1": "HC",
    "SIMYACI_V1": "SM", "POPULER_V1": "PP", "ERKENKUS_V1": "EK",
    "CESUR_V1": "CS", "JOKER_V1": "JK", "KALECI_V1": "KL", "KONSEY_V1": "KN",
    "TERS_V1": "TR", "CARPAN_V1": "KM", "SIMETRI_V1": "SI", "KAVSAK_V1": "KV",
    "BANT_V1": "BN", "DEVRE_V1": "DV", "TRIVOX_V1": "TV", "EUVOX_V1": "EU",
    "OPUS5_V1": "O5", "KURUCU_V2": "KU", "PAPER_V1": "PA",
    "TEMEL_V1": "TM", "DAR_V1": "DR", "GENIS_V1": "GN", "GOLBANT_V1": "GB",
    "HARMAN_V1": "HR",
}
_KIRMIZI_PID = {"CARPAN_V1", "SIMETRI_V1", "KAVSAK_V1", "BANT_V1", "DEVRE_V1"}
_TURUNCU_PID = {"TEMEL_V1", "DAR_V1", "GENIS_V1", "GOLBANT_V1", "HARMAN_V1"}


def _rozet(pid: str) -> str:
    """Ajan monogramı — kırmızı takım sıcak, turuncu ılık, mavi nötr."""
    m = MONO.get(pid)
    if not m:
        m = str(pid or "?")[:2].upper()
    k = (" kr" if pid in _KIRMIZI_PID else
         (" tu" if pid in _TURUNCU_PID else ""))
    # Sondaki bosluk KASITLI: gorsel araligi margin verir ama metin
    # olarak bitisik okunuyordu ("EUEUVOX"). Ekran okuyucu icin ayrilmali.
    return "<i class='mono" + k + "'>" + m + "</i> "


@st.cache_data(ttl=180, show_spinner=False)
def load_agents() -> list[dict]:
    """Ajan güveni — İSABET DEĞİL, fiyata göre üstünlük.

    beklenen isabet = ortalama(1/oran)   → fiyatın ima ettiği
    üstünlük        = gerçek isabet − beklenen
    hüküm           = flat_skill'in t değeri (stake-bağımsız)

    ⚠️ Kusursuz seri (hepsi kazandı/kaybetti) standart hatayı sıfıra
    çökertir ve t sonsuza gider. Bu anlamlılık DEĞİLDİR — ÖLÇÜLEMEZ."""
    # ⚠️ DÖNEM SÜZGECİ YOKTU — tablo bütün zamanları topluyordu.
    # ERA 3 tasfiyesinden sonra kullanıcı 9 ajan bekledi, ekran 16
    # gösterdi: emekli ajanlar ve önceki dönem sayıları duruyordu.
    # Dönem sıfırlaması KASAYI sıfırlıyor ama tabloyu sıfırlamıyorsa
    # ekran ile gerçek ayrışır — ve hangisine güvenileceği belirsizleşir.
    # Dönem ölçütü KUPONUN KURULDUĞU an — load_lig ile AYNI. Eskiden maç
    # saatine bakılıyordu: önceki dönemde kurulup yeni dönemde oynanan bir
    # kupon burada sayılıyor, Ajan Ligi'nde sayılmıyordu. Aynı ajan iki
    # sayfada iki farklı isabet gösterebilirdi.
    rows = _rows(
        "SELECT pb.portfolio_id p, pb.odds o, pb.status s FROM paper_bets pb "
        "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pb.portfolio_id "
        "WHERE pb.status IN ('won','lost') AND pb.odds > 1.01 "
        "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start)"
        + _sahada_sql("pb.portfolio_id"),
        sessiz=True)
    # EMEKLİ ajanlar tabloda görünmez: yeni bahis üretmiyorlar, sıralamada
    # yer tutmaları "kime güvenirim" sorusunu bulandırır. Geçmişleri
    # arşivde duruyor (İnceleme ve Ölçüm Defteri onları hâlâ görür).
    # ⚠️ TABLO YALNIZ AJANLARI GÖSTERİR — "beyaz liste", kara liste DEĞİL.
    # İlk halim yalnız emeklileri eliyordu ve OPUS5 / KURUCU / PAPER
    # tabloya girdi: bunlar AJAN DEĞİL — sırasıyla gerçek para defteri,
    # kurucu portföyü ve eski dönem arşivi. Üstelik era_start'ları NULL
    # olduğu için dönem süzgeci de onları durduramadı ve ERA 3'te
    # ajanlar boşken tabloyu SADECE onlar doldurdu: "kime güvenirim"
    # sorusuna cevap veren yerde ajan olmayan üç satır.
    # Kara liste yerine BEYAZ LİSTE: PROFILES'ta olan ve emekli
    # olmayan. Yarın eklenen bir defter portföyü de kendiliğinden dışarıda.
    _sahada: set = set()
    try:
        from agents import PROFILES as _AGP
        _sahada = {k for k, v in _AGP.items() if not v.get("retired")}
    except Exception:
        pass
    by: dict[str, list] = {}
    for r in rows:
        if _sahada and r["p"] not in _sahada:
            continue
        by.setdefault(r["p"], []).append(r)
    out = []
    # ⚠️ SAHADAKI HER AJAN LISTEDE OLMALI — oynamis olsun ya da olmasin.
    # Kullanici "EUVOX'u goremiyorum" dedi ve hakliydi: tablo yalniz
    # kapanmis bahsi OLAN ajanlari gosteriyordu (n<5 atiliyordu). EUVOX
    # donem 3'te henuz bahis kurmadi (lig kisitli, ligleri arada) ve
    # tamamen kayboldu. Kullanici acisindan "kadroda ama bekliyor" ile
    # "gitti" ayirt edilemez hale geldi — bu bir guven sorunudur.
    # Artik sahadaki her ajan n=0 ile de gorunur, hukmu BEKLIYOR olur.
    for pid in (_sahada or set(by)):
        v = by.get(pid, [])
        n = len(v)
        if n == 0:
            out.append({
                "pid": pid, "ad": pid.rsplit("_", 1)[0], "em": pid,
                "n": 0, "won": 0, "hit": 0.0, "exp": 0.0, "edge": 0.0,
                "odds": 0.0, "skill": 0.0, "t": None, "perfect": False,
                "bekliyor": True,
            })
            continue
        won = sum(1 for x in v if x["s"] == "won")
        hit = won / n
        exp = sum(1.0 / float(x["o"]) for x in v) / n
        ret = [((float(x["o"]) - 1.0) if x["s"] == "won" else -1.0) for x in v]
        skill = sum(ret) / n
        var = sum((x - skill) ** 2 for x in ret) / max(n - 1, 1)
        se = math.sqrt(var / n) if var > 0 else 0.0
        perfect = (won == 0 or won == n)
        t = (skill / se) if (se > 1e-9 and not perfect) else None
        out.append({
            "pid": pid, "ad": pid.rsplit("_", 1)[0], "em": pid,
            "n": n, "won": won, "hit": hit, "exp": exp, "edge": hit - exp,
            "odds": sum(float(x["o"]) for x in v) / n,
            "skill": skill, "t": t, "perfect": perfect,
            "bekliyor": False,
        })
    # Oynayanlar ustte (uste gore siralı), bekleyenler altta.
    out.sort(key=lambda z: (z["bekliyor"], -z["edge"]))
    return out


# Türkiye saati: 2016'dan beri SABİT UTC+3 (yaz saati yok). zoneinfo
# yerine sabit fark — ince konteynerde tzdata olmayabilir.
_TR_FARK = 3


def _ko_dt(ko):
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(ko).replace("Z", "")[:19])
    except Exception:
        return None


def _tr_saat(ko) -> str:
    """kickoff_utc → okunur Türkiye saati: bugünse "21:45", değilse
    "14.09 21:45".

    ⚠️ Eskiden yalnız saat yazılıyordu, üstelik UTC: 30 Ağustos'ta
    oynanmış bir maç 13 Eylül'de "12:30" diye bugünün maçı gibi
    görünüyordu (ve Türkiye saatinden 3 saat geriydi). Tarih bugün
    değilse GÖSTERİLİR."""
    from datetime import datetime, timedelta
    t = _ko_dt(ko)
    if t is None:
        return str(ko)[11:16]
    tr = t + timedelta(hours=_TR_FARK)
    bugun = (datetime.utcnow() + timedelta(hours=_TR_FARK)).date()
    return tr.strftime("%H:%M") if tr.date() == bugun else tr.strftime("%d.%m %H:%M")


def _basladi_mi(ko) -> bool:
    """Maç başladı mı? Başlamış maç kupona EKLENEMEZ."""
    from datetime import datetime
    t = _ko_dt(ko)
    return bool(t is not None and t <= datetime.utcnow())


@st.cache_data(ttl=120, show_spinner=False)
def load_board() -> list[dict]:
    """Açık pozisyonlar — bugünün tahtası."""
    # ⚠️ YALNIZ AÇIK KUPONUN AYAĞI. Ölü kombinenin (bir ayağı kaybetmiş,
    # kupon 'lost' yazılmış) kalan ayağı paper_bets'te 'open' kalır ama
    # pozisyon DEĞİLDİR — kupon zaten karara bağlandı. Eski sorgu bunları
    # da alıyordu: 30 Ağustos'ta oynanmış bir KALECI ayağı 13 Eylül'de
    # tahtanın EN ÜSTÜNDE, bugünün maçı gibi duruyordu.
    rows = _rows(
        "SELECT pb.bet_id, pb.portfolio_id p, pb.home_team h, "
        "pb.away_team a, pb.league lg, pb.market mk, pb.pick pk, "
        "pb.odds o, pb.kickoff_utc ko FROM paper_bets pb "
        "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
        "WHERE pb.status='open' AND pc.status='open' AND pb.odds > 1.01 "
        "ORDER BY pb.kickoff_utc LIMIT 60",
        sessiz=True)
    # iddaa'nın SÖYLEDİĞİ lig adı — kanonik koda çevrilemeyen ligler için
    # tek bilgi. Fetcher bunu eskiden atıyordu: kodu 'ALL' yazıp adı çöpe
    # gönderiyordu, yani bilgiyi iki kez kaybediyorduk. Sütun ilk fetch'te
    # oluşuyor; yoksa sessizce boş sözlük döner ve tahta eskisi gibi çalışır.
    _ad = {}
    for x in _rows("SELECT home_team h, away_team a, iddaa_league_name ln "
                   "FROM matches_v2 WHERE iddaa_league_name IS NOT NULL "
                   "AND kickoff_utc > NOW() - INTERVAL '3 days'", sessiz=True):
        _ad[(x["h"], x["a"])] = x["ln"]
    seen, out = set(), []
    for r in rows:
        key = (r["h"], r["a"], r["mk"], r["pk"])
        if key in seen:            # aynı seçimi birden çok ajan oynamış olabilir
            continue
        seen.add(key)
        lg = (r["lg"] or "ALL")
        _iddaa_ad = _ad.get((r["h"], r["a"]))
        out.append({
            "id": str(r["bet_id"]), "pid": r["p"],
            "em": r["p"], "ad": str(r["p"]).rsplit("_", 1)[0],
            "h": r["h"], "a": r["a"], "lg": lg,
            "iddaa_lig": _iddaa_ad,
            "code": CODE.get(lg, "—"),
            "lig": (LEAGUE.get(lg) or _iddaa_ad or "lig kodlanmamış"),
            "mk": r["mk"], "pk": r["pk"], "o": float(r["o"]),
            "m": MARGIN.get(str(r["mk"]).upper(), 1.18),
            "ko": _tr_saat(r["ko"]),
            "ko_ham": str(r["ko"]),
            "gecti": _basladi_mi(r["ko"]),
        })
    return out


@st.cache_data(ttl=180, show_spinner=False)
def load_era_ozet() -> dict:
    """Yürürlükteki dönem — kaç ajan sahada, ne zaman başladı.

    Dönem sıfırlaması kasayı sıfırlar ama tablo dolana kadar sayfa
    "hiçbir şey yok" gibi görünür. İkisi çok farklı: veri yokluğu bir
    arıza olabilir, dönem başlangıcı değildir. Sayfa hangisi olduğunu
    söylemeli."""
    # EN ERKEN başlangıç: tek bir ajana yeni ölçüm penceresi açılabilir
    # (CESUR v1.2 kredisi). MAX, dönemi o gün başlamış gibi gösterirdi.
    r = _rows("SELECT COALESCE(era_no,1) e, COUNT(*) n, MIN(era_start) bas "
              "FROM paper_portfolio GROUP BY COALESCE(era_no,1) "
              "ORDER BY 1 DESC LIMIT 1", sessiz=True)
    if not r:
        return {}
    return {"era": int(r[0]["e"] or 1), "ajan": int(r[0]["n"] or 0),
            "bas": str(r[0]["bas"] or "")[:16].replace("T", " ")}


@st.cache_data(ttl=300, show_spinner=False)
def load_rail() -> dict:
    p = _rows("SELECT COALESCE(SUM(current_bankroll),0) cb, COUNT(*) n "
              "FROM paper_portfolio", sessiz=True)
    # Açık pozisyon = AÇIK KUPONUN açık ayağı. Ölü kombinenin ayağı (kupon
    # zaten 'lost') sayılırsa sayaç şişer — load_board ile AYNI ölçüt.
    o = _rows("SELECT COUNT(*) n FROM paper_bets pb JOIN paper_coupons pc "
              "ON pc.coupon_id = pb.coupon_id "
              "WHERE pb.status='open' AND pc.status='open'", sessiz=True)
    c = _rows("SELECT COUNT(*) n FROM paper_bets WHERE status IN ('won','lost')",
              sessiz=True)
    # ölçüm defteri tablosu ilk koşudan önce YOKTUR — sessiz geç
    m = _rows("SELECT finding_id f, value v, passed g FROM measurement_runs "
              "WHERE finding_id='K_BECERI' ORDER BY ts DESC LIMIT 1", sessiz=True)
    k = m[0] if m else None
    return {"kasa": float(p[0]["cb"] or 0) if p else 0.0,
            "portfoy": int(p[0]["n"] or 0) if p else 0,
            "acik": int(o[0]["n"] or 0) if o else 0,
            "kapali": int(c[0]["n"] or 0) if c else 0,
            "kaynak": _kaynak(),
            "k": (float(k["v"]) if k else None),
            "k_gecti": (bool(k["g"]) if k else None)}


# ══════════════════════════════════════════════════════════════
# TASARIM
# ══════════════════════════════════════════════════════════════

V2_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

/* ══════════════════════════════════════════════════════════════
   BETAGENTS DESK — AÇIK TEMA (tek tema, koyu dal YOK)
   Kullanıcı açıkça "beyaz arka plan · Bloomberg'ün açık ekran hâli"
   istedi. Tema-duyarlı yazmak hataydı: işletim sistemi koyu temadaysa
   uygulama koyu açılıyordu. Tek yol var, o da açık.
   ══════════════════════════════════════════════════════════════ */
:root{
  /* ölçek */
  --s1:4px;  --s2:8px;  --s3:12px; --s4:16px; --s5:22px; --s6:30px;
  /* TİPOGRAFİ — SOL PANELİN STANDARDI, BÜTÜN ARAYÜZDE (19.09.2026).
     Kullanıcı: "sol paneldeki punto ve standardı genelleştirelim —
     minimal yaklaşım, yalnız punto, font, renk." Önceden 18 farklı punto
     ve büyük harfli etiketlerde 9 farklı harf aralığı vardı. Kural:
       etiket  9,5 px · mono · büyük harf · .14em · soluk (panel bölüm başlığı)
       gövde  13,5 px · Archivo (panel menü öğesi)
       değer   mono — sayılar hizalı durur
     Metin Archivo, etiket ve sayı mono. Amber yalnız vurgu/aktif. */
  --t-etiket:9.5px; --t-kucuk:11px; --t-alt:12px; --t-govde:13.5px;
  --t-metin:13.5px; --t-kart:14px; --t-okuma:18px; --t-sayfa:22px;
  --t-dev:26px; --ls-etiket:.14em; --w-etiket:600;
  --r:3px; --satir-y:13px; --kart-ic:18px 20px;

  /* AÇIK PALET — kâğıt beyazı, serin nötrler, tek amber vurgu */
  --ground:#ffffff;
  --panel:#ffffff;
  --panel-2:#f5f8fa;
  --panel-3:#eaf0f4;
  --ink:#0d1620;
  --ink-2:#3a4a5a;
  /* ⚠️ ÖLÇÜLDÜ (WCAG AA, canlı sayfada hesaplanmış kontrast):
     #6a7b8c beyazda 4,35 · en koyu panelde 3,79 — ikisi de 4,5 eşiğinin
     ALTINDA ve bu renk ~67 öğede kullanılıyor (tablo alt satırları,
     kart ipuçları, KPI etiketleri, ray perde adları). Yani ürünün
     ikincil metinlerinin TAMAMI okunabilirlik eşiğinin altındaydı.
     #5b6b7b: beyazda 5,48 · panel-2'de 5,14 · panel-3'te 4,77.
     Hiyerarşi korunuyor: ink 18,2 → ink-2 9,1 → muted 5,5. */
  --muted:#5b6b7b;
  --line:#e6ecf1;
  --line-2:#ccd7e0;
  --brand:#8a5c0c;
  --brand-fill:#fbf1de;
  /* Amber KOYU zeminde okunmuyor: #8a5c0c koyu şeritte 3,14. Aynı rengi
     hem beyazda hem koyuda kullanmak mümkün değil — beyazda iyi olan
     koyuda kötü. #c08a1c koyu zeminde 5,98 (beyazda 3,05, o yüzden
     YALNIZ koyu zeminde kullanılır). */
  --brand-koyu:#c08a1c;
  --pos:#0a6a47;
  --pos-fill:#e2f2eb;
  --neg:#a52a1c;
  --neg-fill:#fbe9e6;
  /* Turuncu takım: #d9730d beyazda 3,0 (okunmaz) — metin için #a8520a
     (beyazda 5,4 · kendi dolgusunda 4,9). Kenar şeridi parlak kalabilir. */
  --tu:#a8520a;
  --tu-fill:#fdf0e3;
  --warn:#7d590e;
  --warn-fill:#faf2de;
  /* koyu şerit — kenar çubuğu ve marka için tek koyu yüzey */
  --koyu:#0d1620;
  --koyu-ink:#eaf0f5;
  --koyu-dim:#8798a8;
}

/* ── TEMEL ─────────────────────────────────────────────── */
.stApp,[data-testid="stAppViewContainer"],
[data-testid="stMain"]{background:var(--ground)!important;}
[data-testid="stHeader"]{background:transparent;height:0;}
.block-container{padding:var(--s4) var(--s6) var(--s6)!important;
  max-width:1720px;}
/* ⚠️ FONT TEKLIGI: Streamlit'in kendi "Source Sans" kurali, markdown
   icine yazdigimiz HTML'e de sizip tablo hucrelerini ele geciriyordu —
   ayni ekranda iki yazi tipi. Kendi bilesenlerimiz ACIKCA adlandirilir.
   ⚠️ BU LISTE KIRILGAN ve bir kez daha sizdi: hikaye rayini eklerken
   buton ETIKETLERI (Streamlit onlari stMarkdownContainer > p icine
   koyuyor), perde aciklamalari ve soru kutusu listeye girmedi — sol
   rayin TAMAMI Source Sans ciziliyordu. Olculdu: 13 gorunur ogede.
   p ve li eklendi (buton etiketi + markdown metni buradan gecer).
   div/span BILEREK EKLENMEDI: [stMarkdownContainer] span (0,1,1)
   ozgullugu .gr / .dp / .cc gibi mono rozetlerini (0,1,0) EZERDI —
   bu sefer sayilar seri fonta duserdi. */
html,body,[class*="css"],.stApp,button,input,select,textarea,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
.ray-soru,.ray-perde .alt,
.v2card,.v2card *,.v2ph,.v2ph *,.v2ust,.v2ust *,
table.v2,table.v2 td,table.v2 .ag,.v2mb,.vd,.pick,.pick *,
.v2sepet-satir,.v2sepet-satir *,.v2bos,.dq,.dq *,.v2dip,.v2dip *,
.tk-kart,.tk-kart *,.v2ajan-bas,.v2ajan-bas *,.sb,
[data-testid="stSelectbox"] div[data-baseweb="select"] *,
[data-testid="stMultiSelect"] div[data-baseweb="select"] *,
[data-testid="stExpander"] summary *,
[data-baseweb="popover"] [role="option"],[data-baseweb="popover"] [role="option"] *{
  font-family:Archivo,"Segoe UI",system-ui,sans-serif!important;}
[data-baseweb="popover"] [role="option"]{font-size:var(--t-govde)!important;}
/* ⚠️ SİMGELER bu kuralın DIŞINDA. Yukarıdaki "… summary *" gibi yıldızlı
   seçiciler Archivo'yu simgelere de dayatıyordu; Streamlit simgeleri ligatür
   olduğu için açılır başlığındaki ok "_arrow_right_" diye METİN basılıyordu
   (20.09.2026, Toto sayfasında görüldü — Çakışma ve Arşiv'deki açılır da
   aynı hatayı taşıyordu, orada emekli ajan olmadığı için görünmüyordu).
   Kenar çubuğunda zaten istisna vardı; aynısı öbür yıldızlı kurallar için. */
[data-testid="stExpander"] summary [data-testid="stIconMaterial"],
[data-testid="stSelectbox"] [data-testid="stIconMaterial"],
[data-testid="stMultiSelect"] [data-testid="stIconMaterial"],
[data-baseweb="popover"] [data-testid="stIconMaterial"]{
  font-family:"Material Symbols Rounded"!important;}
/* Simge rengi temadan geliyordu: koyu tema tercihi olan tarayıcıda beyaz
   zeminde beyaz kalıyordu. Panel tek temalı (açık) — rengi biz veriyoruz. */
[data-testid="stExpander"] summary [data-testid="stIconMaterial"]{
  color:var(--muted)!important;}
/* TEK istisna: sayılar. Hizalanmaları için tabular monospace. */
.mono,.v2kpi b,.v2kpi span,.ro b,.ro span,table.v2 td.n,table.v2 th,
.gr,.dp,.dm,.cc,.v2suz,.v2gez-orta,table.v2 .sb,.v2grup,.v2head .hint,
.v2ust .marka span,.v2ust-durum,.v2ust-durum *,.v2yan-alt,
.pick .odds,.pick .meta,.v2sepet-satir .alt,.gs-sec,.gs-tarih,
.gs-et,.gs-sonuc,.ro span,.v2ph-ust .perde,.v2ph-ust .sf,
.tk-sayi span,.v2ajan-bas .alt,
.bant-not,.tk-sayi b,.tk-ust span,.kc-sat b,.kc-baslik,
[data-testid="stNavSectionHeader"]{
  font-family:"JetBrains Mono",ui-monospace,monospace!important;
  font-variant-numeric:tabular-nums;}

/* ── ÜST GEZİNME — HER ZAMAN GÖRÜNÜR ───────────────────
   Kenar çubuğu Streamlit'te kullanıcı tarafından kapatılabiliyor
   ve kapalı kalıyor: gezinme kayboluyordu. Birincil gezinme artık
   ana akışta, kapatılamaz.                                      */
.v2ust{
  display:flex;align-items:center;gap:var(--s5);flex-wrap:wrap;
  background:var(--koyu);margin:calc(var(--s4) * -1) calc(var(--s6) * -1) var(--s5);
  padding:0 var(--s6);min-height:52px;}
.v2ust .marka{display:flex;align-items:center;gap:9px;flex:0 0 auto;
  padding:var(--s2) 0;}
.v2ust .marka .mark{width:28px;height:28px;border-radius:var(--r);
  background:var(--brand);color:#fff;display:flex;align-items:center;
  justify-content:center;font-family:"JetBrains Mono",monospace;
  font-size:12px;font-weight:700;}
.v2ust .marka b{color:var(--koyu-ink);font-size:15px;font-weight:700;
  letter-spacing:-0.015em;}
.v2ust .marka span{color:var(--brand-koyu);font-family:"JetBrains Mono",monospace;
  font-size:9px;letter-spacing:0.18em;text-transform:uppercase;
  margin-left:2px;}

/* ── SAYFA BAŞLIĞI ─────────────────────────────────────── */
.v2ph{display:flex;align-items:flex-end;justify-content:space-between;
  gap:var(--s5);flex-wrap:wrap;padding:0 0 var(--s3);margin:0 0 var(--s4);
  border-bottom:1px solid var(--line-2);}
.v2ph .sol h1{margin:0;font-size:var(--t-sayfa);font-weight:700;
  letter-spacing:-0.02em;color:var(--ink);line-height:1.2;}
.v2ph .sol p{margin:4px 0 0;font-size:var(--t-alt);color:var(--muted);
  max-width:64ch;}
.v2ph .sag{display:flex;gap:var(--s5);flex-wrap:wrap;}
.v2kpi{display:flex;flex-direction:column;gap:2px;align-items:flex-end;}
.v2kpi span{font-size:var(--t-etiket);letter-spacing:var(--ls-etiket);
  text-transform:uppercase;color:var(--muted);font-weight:var(--w-etiket);}
.v2kpi b{font-size:var(--t-okuma);font-weight:500;color:var(--ink);
  line-height:1.15;}
.v2kpi b.ps{color:var(--pos);} .v2kpi b.ng{color:var(--neg);}

/* ── ÜST DURUM ŞERİDİ ─────────────────────────────────── */
.v2ust-durum{margin-left:auto;display:flex;align-items:baseline;
  gap:var(--s2);flex-wrap:wrap;padding:var(--s2) 0;}
.v2ust-durum span{font-family:"JetBrains Mono",monospace;font-size:9px;
  letter-spacing:0.15em;text-transform:uppercase;color:var(--koyu-dim);
  margin-left:var(--s3);}
.v2ust-durum b{font-family:"JetBrains Mono",monospace;font-size:12.5px;
  font-weight:500;color:var(--koyu-ink);}

/* ── SOL PANEL (SaaS) — st.navigation ─────────────────────
   Kullanıcı (19.09): "Sol SaaS paneli yap — kimliğine ve görünümüne,
   navigasyona uygun." Koyu zemin + amber vurgu = markanın terminal
   kimliği. Seçiciler Streamlit 1.57'nin data-testid'lerine bağlı (DOM'dan
   okundu: stSidebarNavLink · aria-current="page" · stNavSectionHeader).
   ⚠️ Metin rengi AÇIKÇA verilir: varsayılan koyu metin koyu zeminde
   görünmüyordu — ilk denemede 13 bağlantının 12'si görünmezdi. */
[data-testid="stSidebar"]{background:var(--koyu);border-right:1px solid #1c2835;
  width:248px!important;min-width:248px!important;max-width:248px!important;}
[data-testid="stSidebarContent"]{background:var(--koyu);}
[data-testid="stSidebarHeader"]{padding:18px 16px 4px 18px;}
[data-testid="stSidebarLogo"]{height:30px;max-width:180px;}
[data-testid="stSidebarNav"]{padding:0 10px;}
[data-testid="stNavSectionHeader"]{font-size:var(--t-etiket)!important;
  font-weight:700!important;letter-spacing:var(--ls-etiket);text-transform:uppercase;color:var(--koyu-dim)!important;
  padding:12px 10px 3px!important;margin:0!important;line-height:1.2!important;}
/* Ölçüldü: başlık 38 px, her satırın iki yanında 2 px — menü 726 px idi ve
   durum kartı son öğeyi örtüyordu. Sıkılaştırıldı (~590 px). */
[data-testid="stSidebarNavItems"] li{margin:0!important;}
[data-testid="stNavSectionHeader"] *{color:var(--koyu-dim)!important;}
[data-testid="stSidebarNavLink"]{border-radius:6px;min-height:30px;height:30px;margin:1px 0;
  padding:0 10px!important;color:rgba(234,240,245,.80)!important;
  transition:background .12s ease;}
[data-testid="stSidebarNavLink"] *{color:inherit!important;}
[data-testid="stSidebarNavLink"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebarNavLink"] span{font-size:var(--t-govde)!important;
  font-weight:500;}
[data-testid="stSidebarNavLink"] [data-testid="stIconMaterial"]{
  color:var(--koyu-dim)!important;font-size:18px!important;}
[data-testid="stSidebarNavLink"]:hover{background:rgba(255,255,255,.06)!important;
  color:#ffffff!important;}
[data-testid="stSidebarNavLink"][aria-current="page"]{
  background:rgba(192,138,28,.16)!important;color:#ffffff!important;
  box-shadow:inset 3px 0 0 var(--brand-koyu);}
[data-testid="stSidebarNavLink"][aria-current="page"] [data-testid="stIconMaterial"]{
  color:var(--brand-koyu)!important;}
[data-testid="stSidebarNavSeparator"]{display:none!important;}
/* Durum kartı kenar çubuğunun DİBİNE sabit (sticky) — menü uzunsa
   altından kayar, kart hep görünür. Ölçüldü: 1440×900'de kart 831–991 px
   aralığındaydı, yani ekran dışında; 1366×768 dizüstünde daha da aşağıda. */
[data-testid="stSidebarUserContent"]{position:sticky;bottom:0;z-index:2;
  padding:18px 14px 14px!important;
  background:linear-gradient(to bottom,rgba(13,22,32,0),var(--koyu) 16px);}
[data-testid="stSidebarCollapseButton"] *{color:var(--koyu-dim)!important;}
/* Masaüstünde KAPATILAMAZ — eski ders: kullanıcı kapatıyor, gezinme
   ekrandan kayboluyordu. Mobilde standart açılır çekmece kalır. */
@media (min-width:992px){
  [data-testid="stSidebarCollapseButton"]{display:none!important;}
}
/* Mobilde kenar çubuğu kapalıyken logo + açma düğmesi sol üstte YÜZER
   (üst başlık 0 yükseklikte) — sayfa başlığının etiketini örtüyordu.
   İçerik o denetimlerin altından başlar. */
@media (max-width:991px){
  .block-container{padding-top:64px!important;}
}
/* Kenar çubuğunun dibi — canlı durum */
.kc-durum{padding:9px 11px;border-radius:6px;
  border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.03);}
.kc-baslik{font-size:9px;font-weight:700;letter-spacing:.14em;
  text-transform:uppercase;color:var(--koyu-dim);display:flex;
  align-items:center;gap:6px;white-space:nowrap;overflow:hidden;}
.kc-baslik::before{content:"";flex:0 0 6px;height:6px;border-radius:50%;
  background:#3fb37f;box-shadow:0 0 0 3px rgba(63,179,127,.18);}
.kc-baslik b{color:var(--koyu-ink);font-weight:600;letter-spacing:.04em;
  text-transform:none;overflow:hidden;text-overflow:ellipsis;}
.kc-sat{margin-top:5px;font-size:10.5px;color:var(--koyu-dim);line-height:1.5;}
.kc-sat b{font-size:11.5px;font-weight:600;color:var(--koyu-ink);}
.v2grup{font-size:9.5px;letter-spacing:0.18em;text-transform:uppercase;
  color:var(--koyu-dim)!important;padding:var(--s4) var(--s2) 5px;}
.v2yan-alt{margin-top:var(--s4);padding-top:var(--s4);
  border-top:1px solid rgba(255,255,255,.09);line-height:1.85;
  font-size:10.5px!important;color:var(--koyu-dim)!important;}
.v2yan-alt b{color:var(--koyu-ink)!important;}
.v2yan-alt b.uyari{color:#f0907e!important;}

/* ── KART ──────────────────────────────────────────────── */
.v2card{background:var(--panel);border:1px solid var(--line);
  border-radius:var(--r);margin-bottom:var(--s4);
  box-shadow:0 1px 2px rgba(13,22,32,.04);}
.v2head{display:flex;justify-content:space-between;align-items:baseline;
  gap:var(--s3);padding:var(--s3) 20px;border-bottom:1px solid var(--line);
  background:var(--panel-2);border-radius:var(--r) var(--r) 0 0;}
.v2head h2{margin:0;font-size:var(--t-kart);font-weight:700;
  letter-spacing:-0.01em;color:var(--ink);}
.v2head .hint{font-size:var(--t-etiket);color:var(--muted);
  letter-spacing:var(--ls-etiket);font-weight:var(--w-etiket);
  text-transform:uppercase;white-space:nowrap;}
.v2body{padding:var(--kart-ic);overflow-x:auto;}

/* ── TABLO ─────────────────────────────────────────────── */
table.v2{width:100%;border-collapse:collapse;table-layout:auto;}
table.v2 th{font-size:var(--t-etiket);letter-spacing:var(--ls-etiket);
  text-transform:uppercase;color:var(--muted);font-weight:var(--w-etiket);
  text-align:left;white-space:nowrap;padding:0 var(--s3) 9px 0;
  border-bottom:1px solid var(--line-2);}
table.v2 th:last-child,table.v2 td:last-child{padding-right:0;}
table.v2 th.r,table.v2 td.r{text-align:right;}
table.v2 td{padding:var(--satir-y) var(--s3) var(--satir-y) 0;
  border-bottom:1px solid var(--line);font-size:var(--t-govde);
  color:var(--ink);vertical-align:middle;}
table.v2 tbody tr:hover{background:var(--panel-2);}
table.v2 tbody tr:last-child td{border-bottom:0;}
table.v2 td.n{font-size:var(--t-govde);}
table.v2 .rk{font-size:var(--t-kucuk);color:var(--muted);width:20px;
  padding-right:var(--s2);}
table.v2 .ag{font-weight:600;font-size:var(--t-govde);display:block;
  white-space:nowrap;}
table.v2 .sb{display:block;font-size:var(--t-alt);color:var(--muted);
  margin-top:3px;white-space:nowrap;}
/* Tablo DIŞINDAKİ alt satır (kart dipnotu) — yalnız tablo içi tanımlıydı,
   dışarıdakiler 16 px'e düşüyordu (Defter, Çakışma dipnotları). */
.sb{font-size:var(--t-alt);color:var(--muted);line-height:1.55;}
/* Streamlit seçim kutuları ve açılır bölüm başlığı — gövde puntosu.
   Çoklu seçimdeki yer tutucu ("tümü") 16 px Source Sans'a düşüyordu —
   kasa eğrisi süzgeçleri; yalnız canlıda görüldü (önizlemede çizilmiyor). */
[data-testid="stSelectbox"] div[data-baseweb="select"] *,
[data-testid="stMultiSelect"] div[data-baseweb="select"] *,
[data-testid="stExpander"] summary *{font-size:var(--t-govde)!important;}
/* ...ama seçilmiş değer ÇİPİ mono kalır (sayı/etiket) — üstteki genel
   kuraldan SONRA ve daha ÖZGÜL (0,3,1 > 0,2,1), yoksa çip de Archivo 13,5
   olurdu. ⚠️ Çip öğesi SPAN (Streamlit 1.57 DOM'undan okundu); eski kural
   div[data-baseweb="tag"] diyordu ve amber çip stili HİÇ uygulanmıyordu. */
[data-testid="stMultiSelect"] div[data-baseweb="select"] [data-baseweb="tag"],
[data-testid="stMultiSelect"] div[data-baseweb="select"] [data-baseweb="tag"] *{
  font-family:"JetBrains Mono",monospace!important;
  font-size:var(--t-kucuk)!important;color:var(--brand)!important;}
/* Ajan dosyası başlığı */
.v2ajan-bas{display:flex;align-items:baseline;flex-wrap:wrap;
  gap:var(--s3);margin:var(--s4) 0 var(--s3);}
.v2ajan-bas .ad{font-size:var(--t-sayfa);font-weight:700;
  letter-spacing:-0.02em;color:var(--ink);}
.v2ajan-bas .alt{font-size:var(--t-alt);color:var(--muted);}

/* ── SEMANTİK ──────────────────────────────────────────── */
.dp{color:var(--pos);font-weight:700;background:var(--pos-fill);
  padding:3px 8px;border-radius:var(--r);display:inline-block;
  white-space:nowrap;font-size:var(--t-alt);}
.dm{color:var(--neg);font-weight:500;white-space:nowrap;font-size:var(--t-alt);}
.dp::before{content:"▲ ";font-size:8px;vertical-align:1.5px;}
.dm::before{content:"▼ ";font-size:8px;vertical-align:1.5px;opacity:.5;}
table.v2 tr.adv td:first-child{box-shadow:inset 2px 0 0 var(--pos);}
table.v2 tr.adv .ag{color:var(--pos);}
.gr{display:inline-block;font-size:var(--t-etiket);font-weight:700;
  letter-spacing:0.06em;padding:4px 7px;border-radius:var(--r);
  white-space:nowrap;}
.g1{background:var(--pos-fill);color:var(--pos);}
.g2{background:var(--warn-fill);color:var(--warn);}
.g3{background:var(--neg-fill);color:var(--neg);}
.mono{font-style:normal;font-size:var(--t-etiket);font-weight:700;
  letter-spacing:0.03em;display:inline-flex;align-items:center;
  justify-content:center;width:23px;height:19px;margin-right:3px;
  vertical-align:-4px;border:1px solid var(--line-2);border-radius:var(--r);
  color:var(--ink-2);background:var(--panel-2);flex:0 0 auto;
  font-family:"JetBrains Mono",monospace;}
.mono.kr{color:var(--neg);border-color:var(--neg);background:var(--neg-fill);}
.mono.tu{color:var(--tu);border-color:var(--tu);background:var(--tu-fill);}

/* ── GEREKÇE VE SONUÇ — liste (tablo değil) ──────────────
   Kullanıcı (19.09): "sağa çek sola çek tablo gibi oluyor". Metin tam ve
   SARILARAK gösterilir; yatay kaydırma yok, bir punto küçük. */
.gs-list{display:flex;flex-direction:column;}
.gs{padding:10px 0;border-bottom:1px solid var(--line);}
.gs:last-child{border-bottom:0;padding-bottom:0;}
.gs:first-child{padding-top:0;}
.gs-ust{display:flex;flex-wrap:wrap;align-items:baseline;gap:5px 10px;
  font-size:var(--t-govde);line-height:1.35;}
.gs-ust b{font-weight:600;color:var(--ink);}
.gs-sec{font-size:var(--t-alt);color:var(--ink-2);}
.gs-tarih{font-size:var(--t-kucuk);color:var(--muted);margin-left:auto;}
.gs-sonuc{font-size:var(--t-etiket);font-weight:700;letter-spacing:.06em;
  padding:3px 7px;border-radius:var(--r);align-self:center;}
.gs-sonuc.won{background:var(--pos-fill);color:var(--pos);}
.gs-sonuc.lost{background:var(--neg-fill);color:var(--neg);}
.gs-sat{font-size:var(--t-alt);line-height:1.55;color:var(--ink-2);margin-top:5px;
  white-space:normal;overflow-wrap:anywhere;}
.gs-et{display:inline-block;min-width:66px;font-size:var(--t-etiket);
  font-weight:var(--w-etiket);letter-spacing:var(--ls-etiket);
  text-transform:uppercase;color:var(--muted);}

/* ── TAKIM KARTI (Lig Tablosu) ─────────────────────────── */
.tk-kart{background:var(--panel);border:1px solid var(--line);
  border-top:3px solid var(--brand);border-radius:var(--r);
  padding:14px 16px 12px;margin-bottom:8px;}
.tk-ust{display:flex;justify-content:space-between;align-items:baseline;
  gap:8px;margin-bottom:10px;flex-wrap:wrap;}
.tk-ust b{font-size:var(--t-kart);font-weight:700;color:var(--ink);}
.tk-ust span{font-size:var(--t-etiket);letter-spacing:var(--ls-etiket);
  font-weight:var(--w-etiket);text-transform:uppercase;color:var(--muted);}
.tk-sayi{display:grid;grid-template-columns:repeat(3,1fr);gap:10px 12px;}
.tk-sayi span{display:block;font-size:var(--t-etiket);
  letter-spacing:var(--ls-etiket);font-weight:var(--w-etiket);
  text-transform:uppercase;color:var(--muted);margin-bottom:1px;}
.tk-sayi b{font-size:var(--t-kart);font-weight:500;color:var(--ink);}
.tk-sayi b.ps{color:var(--pos);} .tk-sayi b.ng{color:var(--neg);}
.tk-alt{margin-top:10px;padding-top:8px;border-top:1px solid var(--line);
  font-size:var(--t-alt);color:var(--ink-2);}

/* ── İŞLEM BANDI — ajanın altında, borsa işlem şeridi ──── */
table.v2 tr.ust td{border-bottom:0;padding-bottom:4px;}
table.v2 tr.bant-satir td{padding-top:0;padding-bottom:12px;}
table.v2 tbody tr.bant-satir:hover{background:transparent;}
.bant-kap{display:flex;align-items:center;gap:12px;flex-wrap:wrap;}
.bant{display:block;flex:0 1 auto;}
.bant-not{font-size:var(--t-kucuk);color:var(--muted);}
.bant-not b{font-weight:600;}
.dp0{color:var(--pos);} .dm0{color:var(--neg);}
.bant-buyuk{overflow-x:auto;padding:4px 0 8px;}
table.v2 tr.adv .mono{border-color:var(--pos);color:var(--pos);
  background:var(--pos-fill);}
.cc{display:inline-block;font-size:var(--t-etiket);font-weight:700;
  letter-spacing:0.04em;min-width:29px;text-align:center;padding:3px 5px;
  margin-right:8px;border:1px solid var(--line-2);border-radius:var(--r);
  color:var(--ink-2);background:var(--panel-2);}
.cc.no{color:var(--muted);border-style:dashed;opacity:.7;}
/* açık kupon — riskteki pozisyon, nötr ama görünür */
.ak{display:inline-block;font-family:"JetBrains Mono",monospace;
  font-size:var(--t-govde);font-weight:600;color:var(--ink);
  background:var(--panel-3);border-radius:var(--r);padding:2px 9px;}
.fl{display:none;} .em{display:none;}

/* ── KUTULAR ───────────────────────────────────────────── */
.v2mb{border:1px solid var(--line);border-left:3px solid var(--brand);
  background:var(--panel-2);padding:var(--s3) var(--s4);margin:0 0 var(--s4);
  font-size:var(--t-metin);color:var(--ink-2);line-height:1.6;
  border-radius:0 var(--r) var(--r) 0;}
.v2mb b{color:var(--ink);font-weight:600;}
.dq{font-size:var(--t-alt);line-height:1.6;color:var(--ink-2);
  background:var(--warn-fill);border:1px solid var(--line);
  border-left:3px solid var(--warn);padding:10px var(--s3);
  margin:0 0 var(--s3);border-radius:0 var(--r) var(--r) 0;}
.dq b{color:var(--warn);}
.vd{font-size:var(--t-metin);line-height:1.6;padding:var(--s3) var(--s4);
  border:1px solid var(--line);background:var(--panel-2);color:var(--ink-2);
  border-radius:var(--r);}
.vd b{color:var(--ink);font-weight:600;}
/* Dipnot — kart dışında duran kısa açıklama satırı */
.v2dip{font-size:var(--t-kucuk);color:var(--muted);padding:14px 2px;
  line-height:1.6;}
.v2bos{border:1px dashed var(--line-2);border-radius:var(--r);
  padding:var(--s5) var(--s3);text-align:center;color:var(--muted);
  font-size:var(--t-alt);line-height:1.7;}

/* ── OKUMA SATIRLARI ───────────────────────────────────── */
.ro{display:flex;justify-content:space-between;align-items:baseline;
  padding:11px 0;border-bottom:1px solid var(--line);}
.ro:last-of-type{border-bottom:0;}
.ro span{font-size:var(--t-etiket);letter-spacing:var(--ls-etiket);
  font-weight:var(--w-etiket);text-transform:uppercase;color:var(--muted);}
.ro b{font-size:var(--t-okuma);font-weight:500;color:var(--ink);}
.ro.big b{font-size:var(--t-dev);letter-spacing:-0.02em;}
.ro b.ps{color:var(--pos);} .ro b.ng{color:var(--neg);}
.meter{height:5px;background:var(--line);margin:var(--s1) 0 var(--s3);
  border-radius:99px;overflow:hidden;}
.meter i{display:block;height:100%;background:var(--neg);}

/* ── TAHTA ─────────────────────────────────────────────── */
.pick{display:grid;grid-template-columns:1fr auto;gap:4px var(--s3);
  padding:11px var(--s3);border:1px solid var(--line);border-radius:var(--r);
  background:var(--panel);margin-bottom:var(--s2);cursor:pointer;
  align-items:center;}
.pick:hover{border-color:var(--brand);background:var(--panel-2);}
.pick.on{border-color:var(--brand);background:var(--brand-fill);}
.pick .match{font-weight:600;font-size:var(--t-govde);}
.pick .meta{font-size:var(--t-alt);color:var(--muted);margin-top:2px;}
.pick .odds{font-size:var(--t-okuma);font-weight:500;text-align:right;line-height:1.1;}

/* ── SEPET ─────────────────────────────────────────────── */
.v2sepet-satir{display:flex;align-items:center;justify-content:space-between;
  gap:var(--s3);padding:11px var(--s3);border:1px solid var(--line);
  border-radius:var(--r);background:var(--panel-2);margin-bottom:6px;}
.v2sepet-satir .ad{font-size:var(--t-govde);font-weight:600;}
.v2sepet-satir .alt{font-family:"JetBrains Mono",monospace;
  font-size:var(--t-alt);color:var(--muted);margin-top:2px;}

/* ── SÜZGEÇ / GEZİNME ──────────────────────────────────── */
.v2suz{display:flex;align-items:center;gap:var(--s2);
  font-size:var(--t-etiket);letter-spacing:var(--ls-etiket);
  font-weight:var(--w-etiket);text-transform:uppercase;color:var(--muted);
  margin:0 0 var(--s2);}
.v2gez{border-top:1px solid var(--line);margin-top:var(--s5);
  padding-top:var(--s4);}
.v2gez-orta{font-size:var(--t-etiket);letter-spacing:var(--ls-etiket);
  font-weight:var(--w-etiket);text-transform:uppercase;
  color:var(--muted);text-align:center;padding-top:9px;}

/* ── STREAMLIT BİLEŞENLERİ ─────────────────────────────── */
[data-testid="stMain"] [data-testid="stMarkdownContainer"] p,
[data-testid="stMain"] [data-testid="stMarkdownContainer"] li{
  color:var(--ink);}
/* ⚠️ GENİŞ SEÇİCİ SIZINTISI — bu projede altıncı kez.
   Streamlit buton ETİKETİNİ de stMarkdownContainer içine koyuyor, yani
   yukarıdaki kural her buton yazısını --ink boyuyordu. Buton kuralı
   color:#fff diyordu ama <p>'ye DOĞRUDAN kural uygulandığı için kalıtım
   kaybediyordu: amber dolu aktif butonda koyu metin kalıyordu ve
   kontrast 3,14'e düşüyordu (beyaz metinle 5,81 olurdu).
   Sabit renk yerine INHERIT: etiket butonun kendi rengini alır, yani
   primary/secondary/gelecekteki her varyantta doğru çalışır. */
[data-testid="stMain"] .stButton>button [data-testid="stMarkdownContainer"] p{
  color:inherit;font-size:var(--t-govde);}
[data-testid="stCheckbox"]{margin:0!important;}
[data-testid="stCheckbox"] label p{
  font-family:Archivo,sans-serif!important;font-size:var(--t-govde)!important;
  color:var(--ink)!important;margin:0!important;line-height:1.5!important;
  text-transform:none!important;letter-spacing:normal!important;}
[data-testid="stCheckbox"] label:hover p{color:var(--brand)!important;}
div[data-testid="column"]{padding:0 var(--s2);min-width:0;}
div[data-testid="column"]:first-child{padding-left:0;}
div[data-testid="column"]:last-child{padding-right:0;}

/* butonlar — kenar çubuğu ve ana alan ayrı */
[data-testid="stSidebar"] .stButton>button{
  position:relative;width:100%;text-align:left;justify-content:flex-start;
  background:transparent;border:0;border-radius:var(--r);
  padding:0 var(--s3) 0 32px;margin:1px 0;min-height:38px;height:38px;
  font-weight:500;color:var(--koyu-ink)!important;}
[data-testid="stSidebar"] .stButton>button::before{
  content:"";position:absolute;left:13px;top:50%;transform:translateY(-50%);
  width:5px;height:5px;border-radius:50%;background:var(--koyu-dim);opacity:.45;}
[data-testid="stSidebar"] .stButton>button:hover{background:rgba(255,255,255,.06);}
[data-testid="stSidebar"] .stButton>button[kind="primary"]{
  background:rgba(255,255,255,.10);}
[data-testid="stSidebar"] .stButton>button[kind="primary"]::before{
  background:var(--brand);opacity:1;box-shadow:0 0 0 3px rgba(138,92,12,.28);}
[data-testid="stMain"] .stButton>button{
  border-radius:var(--r);border:1px solid var(--line-2);background:var(--panel);
  color:var(--ink);font-size:var(--t-govde);font-weight:500;min-height:38px;
  padding:0 var(--s4);}
[data-testid="stMain"] .stButton>button:hover{
  border-color:var(--brand);color:var(--brand);background:var(--panel-2);}
[data-testid="stMain"] .stButton>button:focus-visible{
  outline:2px solid var(--brand);outline-offset:2px;}
[data-testid="stMain"] .stButton>button[kind="primary"]{
  background:var(--brand);border-color:var(--brand);color:#fff;font-weight:600;}
[data-testid="stMain"] .stButton>button[kind="primary"]:hover{
  filter:brightness(1.1);color:#fff;}
/* sekme çubuğu */
[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(.v2sekme-isaret)
  .stButton>button{border:0;border-bottom:2px solid transparent;
  border-radius:0;background:transparent;color:var(--muted);min-height:36px;}
[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(.v2sekme-isaret)
  .stButton>button[kind="primary"]{background:transparent;color:var(--ink);
  font-weight:700;border-bottom-color:var(--brand);}
/* form alanları */
[data-testid="stSelectbox"] div[data-baseweb="select"]>div,
[data-testid="stMultiSelect"] div[data-baseweb="select"]>div{
  background:var(--panel)!important;border-color:var(--line-2)!important;
  border-radius:var(--r)!important;min-height:38px;}
[data-testid="stSelectbox"] [data-testid="stWidgetLabel"] p,
[data-testid="stMultiSelect"] [data-testid="stWidgetLabel"] p,
[data-testid="stNumberInput"] [data-testid="stWidgetLabel"] p{
  font-family:"JetBrains Mono",monospace!important;
  font-size:var(--t-etiket)!important;font-weight:var(--w-etiket)!important;
  color:var(--muted)!important;letter-spacing:var(--ls-etiket);
  text-transform:uppercase;margin-bottom:5px!important;}
[data-testid="stNumberInput"] input{background:var(--panel)!important;
  border-radius:var(--r)!important;
  font-family:"JetBrains Mono",monospace!important;}
[data-baseweb="tag"]{background:var(--brand-fill)!important;
  color:var(--brand)!important;border-radius:var(--r)!important;
  font-family:"JetBrains Mono",monospace!important;font-size:var(--t-kucuk)!important;}

/* Kart başlığı kelime ORTASINDAN bölünmesin — "Seçtiklerin" dar
   panelde "Seçtikl / erin" oluyordu. Sığmıyorsa küçülsün, kırılmasın. */
.v2head h2{overflow-wrap:normal;word-break:keep-all;hyphens:none;}

/* Panel içi genişliğe göre sütun gizleme.
   ⚠️ .opt ekran genişliğine bakar (@media) — ama bir tablo GENİŞ
   ekranda da DAR bir panelin içinde olabilir. Karar Masası'nda tam
   bu oldu: 1280px ekranda Ajan Güveni paneli 323px ve HÜKÜM sütunu
   kırpıldı. Konteyner sorgusu gerçek kapsayıcı genişliğini ölçer. */
.v2body{container-type:inline-size;}
@container (max-width:430px){
  table.v2 th.dar,table.v2 td.dar{display:none;}
}

/* Sayfa başlığı üst satırı — zincirdeki konum */
.v2ph-ust{display:flex;align-items:center;gap:8px;margin-bottom:5px;}
.v2ph-ust .perde{font-family:"JetBrains Mono",monospace;
  font-size:var(--t-etiket);font-weight:700;letter-spacing:var(--ls-etiket);
  color:var(--brand);
  background:var(--brand-fill);padding:2px 7px;border-radius:var(--r);}
.v2ph-ust .sf{font-family:"JetBrains Mono",monospace;
  font-size:var(--t-etiket);letter-spacing:var(--ls-etiket);
  font-weight:var(--w-etiket);text-transform:uppercase;color:var(--muted);}
.v2gez-orta .sonraki-soru{display:block;font-size:var(--t-kucuk);
  color:var(--muted);margin-top:3px;letter-spacing:0;text-transform:none;}

/* ── HİKÂYE RAYI ───────────────────────────────────────── */
/* Seçiciler bilerek DAR: geçmişte beş kez geniş seçici başka
   bileşene sızdı. Hepsi .ray- öneki taşır.                     */
.ray-perde{display:grid;grid-template-columns:auto 1fr;
  gap:1px 8px;align-items:baseline;
  margin:var(--s5) 0 8px;padding-bottom:7px;
  border-bottom:1px solid var(--line);}
.ray-perde:first-of-type{margin-top:2px;}
.ray-perde .no{grid-row:1 / span 2;align-self:center;
  font-family:"JetBrains Mono",monospace;font-size:10px;font-weight:700;
  color:var(--muted);background:var(--panel-3);
  width:19px;height:19px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;}
.ray-perde .ad{font-family:"JetBrains Mono",monospace;font-size:10.5px;
  font-weight:700;letter-spacing:.13em;color:var(--muted);}
.ray-perde .alt{font-size:10.5px;color:var(--muted);opacity:.8;
  line-height:1.3;}
/* Yürürlükteki perde — kullanıcı zincirde nerede olduğunu görsün */
.ray-perde.aktif{border-bottom-color:var(--brand);}
.ray-perde.aktif .no{background:var(--brand);color:#fff;}
.ray-perde.aktif .ad{color:var(--brand);}
.ray-perde.aktif .alt{color:var(--ink-2);opacity:1;}

/* Aktif sayfanın CEVAPLADIĞI SORU — sayfanın kimliği budur */
.ray-soru{font-size:11.5px;line-height:1.45;color:var(--brand);
  background:var(--brand-fill);border-left:2px solid var(--brand);
  border-radius:0 var(--r) var(--r) 0;
  padding:6px 9px;margin:-2px 0 8px 3px;}

/* Ray butonları: sola dayalı, menü gibi okunsun.
   ⚠️ Seçici YAPISAL KONUMA değil, verdiğim ANAHTARA bağlı.
   div[data-testid="column"]:first-child yazsaydım iç içe sütunların
   ilkini de yakalardı — Sepet'teki "Sil" butonları gibi. Geniş seçici
   bu projede beş kez başka bileşene sızdı; Streamlit anahtarı DOM'a
   st-key-<anahtar> sınıfı olarak yazıyor, tek eşleşen o. */
[class*="st-key-ray_"] button{
  justify-content:flex-start;text-align:left;font-size:13px;
  padding-left:11px;}

/* ── MOBİL ─────────────────────────────────────────────── */
@media (max-width:900px){
  :root{--s6:18px;}
  .v2ph{flex-direction:column;align-items:flex-start;gap:var(--s3);}
  .v2ph .sag{gap:var(--s4);}
  .v2kpi{align-items:flex-start;}
}
@media (max-width:640px){
  :root{--kart-ic:14px 15px;--t-sayfa:19px;}
  table.v2 th.opt,table.v2 td.opt{display:none;}
  /* Mobilde Streamlit sütunları yığar: ray içeriğin ÜSTÜNE geçer ve
     üst menü gibi çalışır. Perde açıklaması ve soru kutusu orada yer
     israfı — sayfa başlığı zaten aynı soruyu büyük yazıyor. */
  .ray-perde .alt{display:none;}
  .ray-soru{display:none;}
  .ray-perde{margin:var(--s4) 0 6px;}
  /* Acik kupon: telefonda rozet (kupon sayisi) kalir, "N ayak · X TL"
     alt satiri gider. Olculdu: alt satir tek basina 74px genislik
     yiyordu (480 -> 406), tablo taskini 143px'ten 69px'e dusuruyor.
     Secici DAR tutuldu: sadece .ak rozetinin hemen ardindaki .sb. */
  table.v2 td .ak + .sb{display:none;}
  :root{--t-okuma:16px;--t-dev:23px;}
  [data-testid="stCheckbox"] label{min-height:44px;}

  /* ⚠️ MOBİL TAŞMANIN ASIL SEBEBİ — ölçüldü.
     table.v2 .sb hiç sarılmıyordu (white-space:nowrap). Ölçüm
     Defteri'nde alt satır uzun bulgu açıklamasını taşıyor ("ortalama
     +0,60% (t=+6,10) · kapanışı geçen %30,9 · ...") ve tek satırda
     kalınca tabloyu 378px taşırıyordu — 337px'lik kapsayıcıda BİR
     EKRAN GENİŞLİĞİNDEN fazla yatay kaydırma. Telefonda dikey alan
     ucuz, yatay pahalı: alt satır sarılsın.
     .ag (ajan adı) nowrap KALIYOR — kısa ve kırılırsa okunmaz. */
  table.v2 .sb{white-space:normal;line-height:1.35;}
  table.v2 td{vertical-align:top;}

  /* Dokunma hedefi: sayfa başına 9–13 buton 44px eşiğinin altındaydı
     (38px), parmakla ıskalanıyor.
     ⚠️ İKİ KEZ SESSİZCE BAŞARISIZ OLDU, İKİSİ DE ÖZGÜLLÜKTEN.
     Yukarıda (satır ~571) şu kural var:
         [data-testid="stMain"] .stButton>button{min-height:38px}   (0,2,1)
     Denediklerim:
         .stButton button              (0,1,1)  → kaybetti
         [data-testid^="stBaseButton"] (0,1,0)  → kaybetti
     Medya sorgusu ÖZGÜLLÜK EKLEMEZ; sonra gelmek yetmiyor, eşit ya da
     yüksek özgüllük gerekiyor. Hiçbiri hata vermedi — canlıda ölçmemiş
     olsam "düzeltildi" sanacaktım. Aynı seçiciyi kullanmak tek doğru yol
     (!important yerine: !important sonraki okuyucuyu yanıltır). */
  [data-testid="stMain"] .stButton>button{min-height:44px;}
  [data-testid="stMain"] [data-testid="stNumberInput"] input{min-height:44px;}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;}}
</style>
"""




def _sekmeler(anahtar: str, adlar: list) -> str:
    """Sayfa içi sekme çubuğu — bir sayfada dört ayrı soru varsa
    dördünü üst üste yığmak 'kompakt' değil OKUNMAZ yapar."""
    st.markdown("<span class='v2sekme-isaret'></span>",
                unsafe_allow_html=True)
    k = "v2sek_" + anahtar
    if k not in st.session_state:
        st.session_state[k] = adlar[0]
    kol = st.columns(len(adlar) + 2, gap="small")
    for i, ad in enumerate(adlar):
        with kol[i]:
            if st.button(ad, key=k + "_" + str(i), use_container_width=True,
                         type=("primary" if st.session_state[k] == ad
                               else "secondary")):
                st.session_state[k] = ad
                st.rerun()
    st.markdown("<div style='height:1px;background:var(--line-2);"
                "margin:-6px 0 var(--s4);'></div>", unsafe_allow_html=True)
    return st.session_state[k]


def _suzgec_basligi(metin: str) -> None:
    st.markdown("<div class='v2suz'>" + metin + "</div>",
                unsafe_allow_html=True)


def _sayfa_basligi(baslik: str, alt: str, kpi: list | None = None) -> None:
    """Sayfa başlığı + O SAYFAYA ait ölçüler.

    Genel durum şeridi kaldırıldı: sol panelin bilgisini tekrar ediyordu
    ve sayfa başlığı yoktu — kullanıcı nerede olduğunu sadece menüden
    anlıyordu. Şerit artık sayfaya ait."""
    k = ""
    for x in (kpi or []):
        cls = x.get("cls", "")
        k += ("<div class='v2kpi'><span>" + x["ad"] + "</span><b class='" +
              cls + "'>" + x["deger"] + "</b></div>")
    # HİKÂYE: üst satır kullanıcının zincirde nerede olduğunu söyler,
    # başlık sayfanın CEVAPLADIĞI SORUDUR. Sayfa adı bir etiket; soru
    # ise sayfanın neden var olduğudur — kullanıcı "sayfalar bir hikâye
    # anlatmalı" dedi, hikâyeyi taşıyan şey sorudur.
    # Arama BAŞLIK METNİNE değil KANONİK SAYFA ADINA dayanır: sayfalar
    # başlığı serbestçe yazıyor ("OPUS 5 Defteri", "Sistem Sağlığı") ve
    # metin eşleşmesi bu yüzden sessizce düşerdi — soru kaybolur, kimse
    # fark etmez. session_state her zaman kanonik adı tutar.
    _sf = st.session_state.get("v2_page", "")
    _s = SORU.get(_sf, {})
    ust = ""
    if _s:
        ust = ("<div class='v2ph-ust'><span class='perde'>" +
               _s["perde"] + "</span><span class='sf'>" + _sf +
               "</span></div>")
    _h1 = _s.get("soru") or baslik
    st.markdown(
        "<div class='v2ph'><div class='sol'>" + ust +
        "<h1>" + _h1 + "</h1>"
        "<p>" + alt + "</p></div>"
        "<div class='sag'>" + k + "</div></div>", unsafe_allow_html=True)



def _pct(v: float) -> str:
    return f"{v*100:.1f}".replace(".", ",") + "%"


def _sgn(v: float) -> str:
    return ("+" if v >= 0 else "−") + f"{abs(v)*100:.1f}".replace(".", ",") + "p"


def _num(v: float, d: int = 2) -> str:
    return f"{v:.{d}f}".replace(".", ",")


# ─────────────────────────────────────────────────────────────
# KANIT EŞİĞİ — ürünün TEK standardı
# ─────────────────────────────────────────────────────────────
# ⚠️ Denetimde bulundu: Ölçüm Defteri titiz (kural sonuç görülmeden
# yazılıyor, n=17 ÖLÇÜLEMEZ etiketini alıyor) ama diğer her panel kendi
# eşiğini uyduruyordu:
#     Kayıp Anatomisi  n>=5   → n=15'te 4–4 BERABERLİKTEN hüküm çıkardı
#     OPUS 5           eşik yok → n=19'da "saha kâğıdı geçiyor" dedi
#     Mihenk           n>=12  → "EUVOX kanıt eşiğini geçti" dedi
# Aynı ajan hakkında üç farklı hüküm çıktı, ikisi aynı sayfada.
# Bir sistem kendi kanıt eşiğini çiğniyorsa DOĞRU bulgularına da
# güvenilmez — kaybedilen şey bir sayı değil, okuyanın güveni.
KANIT_ESIGI = 30


def _hukum(a: dict) -> tuple:
    """TEK hüküm kuralı — Karar Masası tablosu, tahta satırı ve Ajan Ligi
    AYNI dili konuşur.

    ⚠️ Bu kural üç yerde ayrı ayrı kopyalanmıştı ve ikisi kanıt eşiğini
    unutmuştu: CESUR n=17 ile güven tablosunda ÖLÇÜLEMEZ, tahtada KÖTÜ
    görünüyordu. Aynı ajana iki sayfada iki hüküm, hiçbirine
    güvenilmemesi demektir."""
    if a.get("bekliyor") or not a.get("n"):
        return "g2", "BEKLİYOR"
    if a["n"] < KANIT_ESIGI or a.get("perfect"):
        return "g2", "ÖLÇÜLEMEZ"
    if a.get("t") is None:
        return "g2", "GÜRÜLTÜ"
    if a["t"] <= -1.96:
        return "g3", "KÖTÜ"
    if a["t"] >= 1.96:
        return "g1", "İYİ"
    return "g2", "GÜRÜLTÜ"


def _isabet(a) -> str:
    """İsabet oranı — HER ZAMAN örneklemiyle: "isabet 63,6% (7/11)".

    Kullanıcı isabeti hiçbir yerde göremiyordu: sütunlar dar panelde ve
    telefonda gizleniyordu. Artık ajan adının altındaki satırda, her
    genişlikte görünür. Sayı n'siz yazılmaz — 1/1 "%100" diye okunur."""
    if not a or not a.get("n"):
        return "isabet —"
    k = a.get("won")
    if k is None:
        k = round(a["hit"] * a["n"])
    return "isabet " + _pct(a["hit"]) + " (" + str(k) + "/" + str(a["n"]) + ")"


@st.cache_data(ttl=120, show_spinner=False)
def _isabet_toplam(kisa: bool = False) -> str:
    """Sahadaki ajanların DÖNEM içi toplam isabeti (seçim bazında).

    ⚠️ Dönemin başından sayılır, ajanların kendi pencerelerinden DEĞİL.
    CESUR'a 17.09'da yeni pencere açılınca eski 5/17'si ajan satırından
    düştü (doğru: v1.2 ayrı ölçülüyor) — ama sistem toplamından da düşseydi
    toplam isabet bir gecede %56'dan %68'e "iyileşmiş" görünürdü."""
    r = _rows(
        "SELECT COUNT(*) n, "
        "COALESCE(SUM(CASE WHEN pb.status='won' THEN 1 ELSE 0 END),0) k "
        "FROM paper_bets pb "
        "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pb.portfolio_id "
        "WHERE pb.status IN ('won','lost') AND pb.odds > 1.01 "
        "AND pp.era_start IS NOT NULL "
        "AND pc.created_at >= (SELECT MIN(p2.era_start) FROM paper_portfolio p2 "
        "WHERE p2.era_no = pp.era_no)"
        + _sahada_sql("pb.portfolio_id"), sessiz=True)
    n = int(r[0]["n"] or 0) if r else 0
    k = int(r[0]["k"] or 0) if r else 0
    if not n:
        return "—"
    return _pct(k / n) if kisa else _pct(k / n) + " · " + str(k) + "/" + str(n)


def _olculebilir(n: int, esik: int = KANIT_ESIGI) -> bool:
    """Bu örneklem bir hüküm taşıyabilir mi?"""
    return int(n or 0) >= esik


def _esik_notu(n: int, esik: int = KANIT_ESIGI) -> str:
    """Yetersiz örneklemde hükmün yerine geçen dürüst cümle."""
    return ("Örneklem hüküm için yetersiz: <b>n=" + str(int(n or 0)) +
            "</b>, gereken <b>" + str(esik) + "</b>. Aşağıdaki sayılar "
            "doğru ama bir <b>eğilim değil</b> — bu kadar veriyle "
            "rastlantıdan ayrılamaz.")


def _ayrisiyor_mu(a: float, b: float, n: int) -> bool:
    """İki sayaç gerçekten ayrışıyor mu, yoksa fark gürültü mü?

    Eşitlik ya da bir birimlik fark AYRIŞMA DEĞİLDİR. Üretimde 4–4
    beraberlikten "zayıf halka SONUÇ" hükmü çıktı çünkü karşılaştırma
    `>=` idi — beraberlik sessizce ilk seçeneğe yazılıyordu.
    """
    if not _olculebilir(n):
        return False
    fark = abs(float(a) - float(b))
    return fark >= max(2.0, (float(n) ** 0.5))


@st.cache_data(ttl=120, show_spinner=False)
def load_opus() -> dict:
    """OPUS 5 defteri — GERÇEKTE oynananlar.

    Yol haritasının kapatılması gereken tek sorusu burada ölçülür:
    kâğıt ajanlar ucuz bölgede -%12,5 gösteriyor, ama sahada kazanç
    bildiriliyor. İkisi birden doğru olabilir — gerçekte oynananlar,
    kâğıt ajanların oynadıklarından farklı olabilir. FARK ÖLÇÜLMELİ.

    Ve asıl soru: KOMBİNE YAPMAK, ayakları TEK TEK oynamaktan iyi mi?
    Her çok-ayaklı kupon için karşı-olgusal hesaplanır: aynı ayaklar
    tek tek oynansaydı ne getirirdi? Marj analizine göre kombine
    pahalı olmalı; bu, tezin kendi verinle sınanması."""
    cs = _rows(
        "SELECT coupon_id cid, status st, combined_odds co, stake sk, "
        "COALESCE(pnl,0) pnl, reasoning rs FROM paper_coupons "
        "WHERE portfolio_id='OPUS5_V1'", sessiz=True)
    if not cs:
        return {"var": False}
    ids = [c["cid"] for c in cs]
    qs = ",".join("?" for _ in ids)
    legs = _rows(
        f"SELECT coupon_id cid, odds o, status st, market mk, pick pk, "
        f"home_team h, away_team a FROM paper_bets WHERE coupon_id IN ({qs})",
        tuple(ids), sessiz=True)
    by: dict = {}
    for l in legs:
        by.setdefault(l["cid"], []).append(l)

    dec = [c for c in cs if c["st"] in ("won", "lost")]
    kombo_r, tek_r, n_multi = [], [], 0
    for c in dec:
        L = by.get(c["cid"], [])
        if not L:
            continue
        co = float(c["co"] or 1)
        kombo_r.append((co - 1.0) if c["st"] == "won" else -1.0)
        # karşı-olgusal: aynı ayaklar tek tek, eşit paylı
        sing = [((float(l["o"]) - 1.0) if l["st"] == "won" else -1.0)
                for l in L if l["st"] in ("won", "lost")]
        tek_r.append(sum(sing) / len(sing) if sing else 0.0)
        if len(L) >= 2:
            n_multi += 1

    # ayak düzeyi: fiyata göre üstünlük (ajan tablosuyla aynı ölçü)
    fl = [l for l in legs if l["st"] in ("won", "lost") and float(l["o"] or 0) > 1.01]
    hit = (sum(1 for l in fl if l["st"] == "won") / len(fl)) if fl else 0.0
    exp = (sum(1.0 / float(l["o"]) for l in fl) / len(fl)) if fl else 0.0

    def _m(v):
        return (sum(v) / len(v)) if v else 0.0

    return {
        "var": True, "kupon": len(cs),
        "acik": sum(1 for c in cs if c["st"] == "open"),
        "karar": len(dec), "cok_ayakli": n_multi,
        "ayak": len(fl), "hit": hit, "exp": exp, "edge": hit - exp,
        "kombo": _m(kombo_r), "tek": _m(tek_r),
        "fark": _m(kombo_r) - _m(tek_r), "n_kars": len(kombo_r),
        "pnl": sum(float(c["pnl"] or 0) for c in dec),
    }


@st.cache_data(ttl=180, show_spinner=False)
def load_havuz() -> dict:
    """Tüm kâğıt ajanların ayak düzeyi ortalaması — OPUS 5 kıyas tabanı."""
    rows = _rows("SELECT odds o, status s FROM paper_bets "
                 "WHERE status IN ('won','lost') AND odds > 1.01 "
                 "AND portfolio_id <> 'OPUS5_V1'", sessiz=True)
    if not rows:
        return {"n": 0}
    n = len(rows)
    hit = sum(1 for r in rows if r["s"] == "won") / n
    exp = sum(1.0 / float(r["o"]) for r in rows) / n
    flat = sum(((float(r["o"]) - 1.0) if r["s"] == "won" else -1.0)
               for r in rows) / n
    return {"n": n, "hit": hit, "exp": exp, "edge": hit - exp, "flat": flat}


KIRMIZI = {"CARPAN_V1", "SIMETRI_V1", "KAVSAK_V1", "BANT_V1", "DEVRE_V1"}
TURUNCU = {"TEMEL_V1", "DAR_V1", "GENIS_V1", "GOLBANT_V1", "HARMAN_V1"}


@st.cache_data(ttl=180, show_spinner=False)
def load_lig() -> dict:
    """Dönem-kapsamlı ajan ligi — mavi, kırmızı ve turuncu AYRI.

    ⚠️ Dönem (era) filtresi şart: Era-1 arşivlendi, Era-2 2026-08-23'te
    1.000 TL ile başladı. Era-1 sonuçlarını Era-2 karnesine karıştırmak,
    kapanmış bir hesabı açık gibi göstermektir.

    Sıralama İSABETE göre değil, FİYATA GÖRE ÜSTÜNLÜĞE göre — Desk ile
    aynı ölçü. İkisi farklı sıralama verdiği için tutarlılık şart."""
    rows = _rows(
        "SELECT pb.portfolio_id p, pb.odds o, pb.status s "
        "FROM paper_bets pb "
        "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pb.portfolio_id "
        "WHERE pb.status IN ('won','lost') AND pb.odds > 1.01 "
        "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start)",
        sessiz=True)
    pf = _rows("SELECT portfolio_id p, current_bankroll cb, initial_bankroll ib, "
               "era_no, benched, ihtar_count ih FROM paper_portfolio", sessiz=True)
    # AÇIK POZİSYON — lig tablosu kapanmış performansı gösterir; bu sütun
    # "şu an sahada ne var"ı söyler. İkisi farklı sorulardır: iyi bir karne
    # ile sıfır açık pozisyon, ajanın bugün PAS geçtiği anlamına gelir.
    # ⚠️ TEK SORGUDA JOIN + SUM YAPMA: SUM(DISTINCT stake) ayni tutarli
    # kuponlari TEK sayar (iki kupon da 100 ₺ ise toplam 100 cikar), JOIN'siz
    # SUM ise ayak sayisi kadar katlar. Iki aggregate AYRI alinir.
    ac = _rows("SELECT portfolio_id p, COUNT(*) kupon, "
               "COALESCE(SUM(stake),0) riskte FROM paper_coupons "
               "WHERE status='open' GROUP BY portfolio_id", sessiz=True)
    # Ayak sayimi ACIK KUPONA bagli olanlarla sinirli: olu kombinenin
    # (kaybeden ayagi olan, kupon 'lost') acik ayagi RISKTE DEGILDIR —
    # kupon zaten karara baglandi, PnL yazildi. Duz "paper_bets WHERE
    # status='open'" saymak riski oldugundan buyuk gosterir.
    ay = _rows("SELECT pb.portfolio_id p, COUNT(*) ayak FROM paper_bets pb "
               "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
               "WHERE pb.status='open' AND pc.status='open' "
               "GROUP BY pb.portfolio_id", sessiz=True)
    _ayak = {x["p"]: int(x["ayak"] or 0) for x in ay}
    acik = {x["p"]: {**x, "ayak": _ayak.get(x["p"], 0)} for x in ac}
    kasa = {x["p"]: x for x in pf}
    by: dict = {}
    for r in rows:
        by.setdefault(r["p"], []).append(r)

    def kur(pid, v):
        n = len(v)
        won = sum(1 for x in v if x["s"] == "won")
        hit = won / n if n else 0.0
        exp = (sum(1.0 / float(x["o"]) for x in v) / n) if n else 0.0
        ret = [((float(x["o"]) - 1.0) if x["s"] == "won" else -1.0) for x in v]
        skill = (sum(ret) / n) if n else 0.0
        var = (sum((x - skill) ** 2 for x in ret) / max(n - 1, 1)) if n > 1 else 0.0
        se = math.sqrt(var / n) if (var > 0 and n) else 0.0
        perfect = n > 0 and (won == 0 or won == n)
        k = kasa.get(pid, {})
        a_ = acik.get(pid, {})
        ib = float(k.get("ib") or 1000)
        cb = float(k.get("cb") or 0)
        return {"pid": pid, "ad": pid.rsplit("_", 1)[0],
                "em": pid, "n": n, "won": won, "hit": hit, "exp": exp,
                "edge": hit - exp, "skill": skill,
                "t": (skill / se) if (se > 1e-9 and not perfect) else None,
                "perfect": perfect, "kasa": cb, "ilk": ib,
                "yuzde": (cb / ib * 100) if ib else 0.0,
                "acik_kupon": int(a_.get("kupon") or 0),
                "acik_ayak": int(a_.get("ayak") or 0),
                "riskte": float(a_.get("riskte") or 0),
                "era": k.get("era_no"), "benched": bool(k.get("benched")),
                "ihtar": int(k.get("ih") or 0),
                "odds": (sum(float(x["o"]) for x in v) / n) if n else 0.0}

    tum = [kur(p, v) for p, v in by.items()]
    # ⚠️ SAHADAKI HER AJAN LISTEDE — oynamis olsun ya da olmasin.
    # Kullanici "EUVOX'u goremiyorum" dedi: lig kisitli oldugu icin donem
    # 3'te henuz bahis kurmadi ve tablodan tamamen dustu. "Kadroda ama
    # bekliyor" ile "gitti" ayirt edilemez hale geliyor.
    _aktif: set = set()
    _emekli: set = set()
    try:
        from agents import PROFILES as _AGP
        _aktif = {k for k, v in _AGP.items() if not v.get("retired")}
        _emekli = {k for k, v in _AGP.items() if v.get("retired")}
    except Exception:
        pass
    for p in kasa:
        if p not in by and (p in _aktif or p in KIRMIZI or p in TURUNCU
                            or p in acik):
            tum.append(kur(p, []))

    # ⚠️ EMEKLILER ARSIVE — kullanici "listeyi kalabalik gosteriyor" dedi.
    # Emekli ajan yeni bahis uretmiyor; siralamada yer tutmasi "kime
    # guvenirim" sorusunu bulandirir. Ama SILINMIYOR: gecmisi arsivde
    # duruyor ve ayri bir bolumde okunabiliyor.
    arsiv = [x for x in tum if x["pid"] in _emekli]
    tum = [x for x in tum if x["pid"] not in _emekli]

    # ⚠️ AJAN OLMAYAN PORTFOYLER: PAPER_V1 (arsiv), OPUS5_V1 (gercek
    # para defteri), KURUCU_V2 (kurucu portfoyu). KURUCU listede yoktu
    # ve Mavi Takim'da n=80 ile "KADRO DISI" olarak goruunuyordu.
    mavi = [x for x in tum if x["pid"] not in KIRMIZI
            and x["pid"] not in TURUNCU
            and x["pid"] not in ("PAPER_V1", "OPUS5_V1", "KURUCU_V2")]
    kirmizi = [x for x in tum if x["pid"] in KIRMIZI]
    turuncu = [x for x in tum if x["pid"] in TURUNCU]
    mavi.sort(key=lambda z: (z["n"] == 0, -z["edge"]))
    kirmizi.sort(key=lambda z: (z["n"] == 0, -z["edge"]))
    turuncu.sort(key=lambda z: (z["n"] == 0, -z["edge"]))
    arsiv.sort(key=lambda z: -z["edge"])
    return {"mavi": mavi, "kirmizi": kirmizi, "turuncu": turuncu,
            "arsiv": arsiv}


# Para piyasası yıllık getirisi — belge §2.3'te 35/40/45 senaryoları
# var, orta senaryo alındı. Değiştirilebilir olması önemli: bu sayı
# karşılaştırma TABANIDIR ve yanlışsa bütün kıyas yanlış olur.
PARA_PIYASASI = 0.40


@st.cache_data(ttl=300, show_spinner=False)
def load_alternatif() -> dict:
    """ALTERNATİF MALİYET — bahis getirisi neye karşı ölçülüyor?

    ⚠️ Belge §2.3: günlük maruziyet tavanı %5 ise bankroll'un yaklaşık
    %95'i her an NAKİT bekler. O sermaye faizsiz tutulursa reel kayıp
    yaratır; para piyasasında değerlendirilirse P&L'e doğrudan katkıdır.
    Belgenin sert cümlesi şu: "düşük yield senaryolarında bu kalem
    bahis operasyonunun kendisinden daha büyük olabilir."

    Sistem bunu HİÇ hesaba katmıyordu. Yani kâr eğrisine bakıp
    "kazanıyoruz" demek, alternatif maliyeti sıfır saymak demekti —
    yıllık %40 faiz ortamında bu ciddi bir yanılgı.
    """
    r = _rows("SELECT COALESCE(SUM(initial_bankroll),0) ib, "
              "COALESCE(SUM(current_bankroll),0) cb, MIN(era_start) bas "
              "FROM paper_portfolio WHERE era_no = "
              "(SELECT MAX(COALESCE(era_no,1)) FROM paper_portfolio)",
              sessiz=True)
    if not r:
        return {}
    ib = float(r[0]["ib"] or 0)
    cb = float(r[0]["cb"] or 0)
    bas = str(r[0]["bas"] or "")[:19]
    if ib <= 0 or not bas:
        return {}
    from datetime import datetime
    try:
        gun = max((datetime.utcnow() - datetime.fromisoformat(bas)).days, 0)
    except Exception:
        return {}
    # Aynı sermaye para piyasasında dururken ne olurdu (basit oranlı)
    faiz = ib * PARA_PIYASASI * (gun / 365.0)
    # ⚠️ BAHİS GETİRİSİ KUPONLARDAN, KASA FARKINDAN DEĞİL. Kasa farkı
    # (güncel − başlangıç) bir ajana kredi açılınca bozulur: CESUR'a 17.09'da
    # yeni kasa verildi ve 869 ₺'lik kaybı kasa farkından silindi. Kupon
    # PnL'i dönemin başından toplanır — kredi kâr sayılmaz.
    pn = _rows("SELECT COALESCE(SUM(pc.pnl),0) t FROM paper_coupons pc "
               "WHERE pc.status IN ('won','lost') AND pc.created_at >= ?"
               + _sahada_sql("pc.portfolio_id"), (bas,), sessiz=True)
    bahis = float(pn[0]["t"] or 0) if pn else (cb - ib)
    return {"ib": ib, "cb": cb, "gun": gun, "bahis": bahis, "faiz": faiz,
            "fark": bahis - faiz, "oran": PARA_PIYASASI}


@st.cache_data(ttl=240, show_spinner=False)
def load_kanit() -> dict:
    """KANIT KAPISI — Šidák eşiği, etkin ajan sayısı, CLV bölgesi.

    Kaynak: kullanıcının TAHMİN SİSTEMİ v3 belgesi §1.4, §1.5, §3.4.
    Sistem bu üç hesabı YAPMIYORDU: ajan "İYİ" hükmü alırken çoklu
    karşılaştırma cezası ödenmiyordu, CLV ölçülüp karara bağlanmıyordu,
    ajan sayısı bağımsızlık varsayımıyla sayılıyordu.

    §1.4'ün özü şu: hiçbir ajanın gerçek edge'i olmasa bile 20 ajandan
    birkaçı TESADÜFEN mükemmel görünür. O yüzden eşik, kaç ajan test
    edildiğine göre yükselir. Ve §3.4: korelasyonlu ajanlar tek ajan
    gibi davranır, yani asıl soru "kaç ajan" değil "kaç BAĞIMSIZ ajan".
    """
    import kanit as K
    ags = load_agents()
    if not ags:
        return {}
    ck = load_cakisma() or {}
    m = len([a for a in ags if not a.get("bekliyor")]) or len(ags)
    ro = float(ck.get("ro") or 0.0)
    m_etkin = K.etkin_ajan(m, ro)
    # ⚠️ Eşik ETKİN ajan sayısına göre — nominal sayıya göre değil.
    # Nominal kullanmak cezayı OLDUĞUNDAN AĞIR yapar (kopyalar ayrı
    # hipotez sayılır); etkin sayı doğru olanı verir.
    alpha = K.sidak_alpha(max(round(m_etkin), 1))

    satir = []
    for a in ags:
        if a.get("bekliyor") or a["n"] <= 0:
            satir.append({"ad": a["ad"], "pid": a["pid"], "n": 0,
                          "hit": None, "p0": None, "ger": None,
                          "gecti": None})
            continue
        g = K.gereken_isabet(a["n"], a["exp"], alpha)
        ger = g[1] if g else None
        satir.append({
            "ad": a["ad"], "pid": a["pid"], "n": a["n"],
            "hit": a["hit"], "p0": a["exp"], "ger": ger,
            "gecti": (a["hit"] >= ger) if ger is not None and ger <= 1 else False,
        })

    cl = _rows("SELECT COUNT(*) n, AVG(clv) ort FROM paper_bets "
               "WHERE clv IS NOT NULL", sessiz=True)
    c_n = int(cl[0]["n"] or 0) if cl else 0
    c_ort = float(cl[0]["ort"]) if (cl and cl[0]["ort"] is not None) else None
    return {"m": m, "ro": ro, "m_etkin": m_etkin, "alpha": alpha,
            "satir": satir, "clv": K.clv_kapisi(c_ort, c_n),
            "cift": int(ck.get("cift_sayisi") or 0)}


@st.cache_data(ttl=300, show_spinner=False)
def load_defter() -> list[dict]:
    """Ölçüm defteri — her bulgunun son hükmü + değişim geçmişi."""
    rows = _rows("SELECT ts, finding_id f, n, value v, passed g, detail d "
                 "FROM measurement_runs ORDER BY ts", sessiz=True)
    if not rows:
        return []
    # 🔒 Tek seferlik kararı verilmiş bulgular. Kaynak defterin KENDİ kaydı
    # (FINDINGS[...]["kapandi"]); arayüzde ayrı liste tutulmaz — tutulursa
    # zamanla defterle çelişir. Modül hafif: math, sys, pathlib, db.
    try:
        from olcum_defteri import FINDINGS as _FD
        _kapali = {k: v["kapandi"] for k, v in _FD.items() if v.get("kapandi")}
    except Exception:
        _kapali = {}
    by: dict = {}
    for r in rows:
        by.setdefault(r["f"], []).append(r)
    out = []
    for fid, v in by.items():
        son = v[-1]
        degisim = sum(1 for i in range(1, len(v))
                      if bool(v[i]["g"]) != bool(v[i - 1]["g"]))
        onceki = v[-2] if len(v) > 1 else None
        out.append({
            "id": fid, "ts": str(son["ts"])[:16], "n": son["n"],
            "v": float(son["v"] or 0), "gecti": bool(son["g"]),
            "detay": son["d"], "kosu": len(v), "degisim": degisim,
            "kapandi": _kapali.get(fid),
            "trend": (float(son["v"] or 0) - float(onceki["v"] or 0))
                     if onceki else None,
        })
    out.sort(key=lambda z: (not z["gecti"], z["id"]))
    return out


@st.cache_data(ttl=180, show_spinner=False)
def load_sistem() -> dict:
    """Sistem sağlığı — sessizlik meşru mu, arıza mı?

    Bu sayfanın tezi: bir ajanın oynamaması iki farklı şey olabilir ve
    ikisini karıştırmak haftalarca sürebilir. 'Meşru PAS' (aday yok) ile
    'TIKANIKLIK' (kod/veri kırık) ayrı ayrı işaretlenir. Bir kez fetch
    çöktüğünde tüm ajanlar masum sessizlik gibi görünmüştü — SİSTEM
    satırı tam bunun için var."""
    diag = _rows(
        "SELECT DISTINCT ON (pid) pid, ts, status, detail FROM agent_diag "
        "ORDER BY pid, ts DESC", sessiz=True)
    if not diag:                        # SQLite: DISTINCT ON yok
        diag = _rows(
            "SELECT d.pid, d.ts, d.status, d.detail FROM agent_diag d "
            "JOIN (SELECT pid p, MAX(ts) m FROM agent_diag GROUP BY pid) x "
            "ON x.p = d.pid AND x.m = d.ts", sessiz=True)
    sistem = next((d for d in diag if d["pid"] == "SISTEM"), None)
    ajan = [d for d in diag if d["pid"] != "SISTEM"]

    def sinif(st_):
        t = str(st_ or "")
        if "TIKANIKLIK" in t:
            return 0
        if "🟠" in t or "MONTAJ" in t or "KUYRUK" in t:
            return 1
        if "MEŞRU PAS" in t or "SESSİZ" in t:
            return 2
        return 3

    ajan.sort(key=lambda d: (sinif(d["status"]), d["pid"]))

    # veri doluluk — yol haritasının Faz 1 listesi
    tot = _rows("SELECT COUNT(*) n FROM matches_v2 WHERE is_settled=1",
                sessiz=True)
    T = int(tot[0]["n"]) if tot else 0
    alanlar = []
    for kol, ad, neden in (
        ("external_id_af", "api-football kimliği",
         "keskin fiyat hattının önkoşulu"),
        ("home_score_ht", "ilk yarı skoru",
         "çıpaların ulaşamadığı tek boyut · HT_FT marjı %25,8"),
        ("closing_btts_yes", "KG kapanış fiyatı", "KG pazarı fiyatlaması"),
        ("home_xg", "xG", "hareket öngörüsü için girdi"),
        ("h2h_n", "karşılaşma geçmişi", "zenginleştirme"),
    ):
        r = _rows(f"SELECT COUNT(*) n FROM matches_v2 WHERE is_settled=1 "
                  f"AND {kol} IS NOT NULL", sessiz=True)
        n = int(r[0]["n"]) if r else 0
        alanlar.append({"kol": kol, "ad": ad, "neden": neden, "n": n,
                        "pay": (n / T) if T else 0.0})

    lig = _rows("SELECT COUNT(*) n FROM matches_v2 "
                "WHERE kickoff_utc > '2026-08-24' AND league_code = 'ALL'",
                sessiz=True)
    lig_tum = _rows("SELECT COUNT(*) n FROM matches_v2 "
                    "WHERE kickoff_utc > '2026-08-24'", sessiz=True)
    la = int(lig[0]["n"]) if lig else 0
    lt = int(lig_tum[0]["n"]) if lig_tum else 0
    alanlar.append({"kol": "league_code", "ad": "lig sınıflandırması",
                    "neden": "ülke rozeti · lig bazlı analiz",
                    "n": lt - la, "pay": ((lt - la) / lt) if lt else 0.0})
    return {"sistem": sistem, "ajan": ajan, "alan": alanlar, "mac": T}


@st.cache_data(ttl=240, show_spinner=False)
def load_inceleme() -> dict:
    """Kazanan/kaybeden ayrıştırması — DATA · MODEL · TRADE.

    V1'in kupon analizi sayfasının yerine geçer, üç farkla:
      1) Edge MARJSIZ ölçülür (mp/q − 1). V1 marjlı edge kullanıyordu;
         o tanımda varyansın çoğu marj farkıdır, tahmin hatası değil.
      2) Dönem kapsamlı — arşivlenen dönem karneye karışmaz.
      3) KAYIP ANATOMİSİ eklendi: kombine kaybettiğinde hangi ayak
         düşürdü? Ölçüldü ki altı hücrenin altısında zayıf halka
         SONUÇ (1X2) ayağı — kaybın ~yarısı gol ayağı tuttuğu hâlde.
    """
    rows = _rows(
        "SELECT pb.market mk, pb.pick pk, pb.odds o, pb.model_prob mp, "
        "pb.status s, pb.league lg, pb.home_score hs, pb.away_score aws, "
        "pb.reason rsn, pb.postmortem pm, pb.settled_at sat, "
        "pb.home_team h, pb.away_team a, pb.portfolio_id p, "
        "pc.coupon_type ct, "
        "m.closing_1 c1, m.closing_X cx, m.closing_2 c2, "
        "m.closing_over25 cu, m.closing_under25 ca, "
        "m.closing_btts_yes bv, m.closing_btts_no bn "
        "FROM paper_bets pb "
        "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pb.portfolio_id "
        "LEFT JOIN matches_v2 m ON m.match_id = pb.match_id "
        "WHERE pb.status IN ('won','lost') AND pb.odds > 1.01 "
        "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start)",
        sessiz=True)
    if not rows:
        return {"n": 0}

    D = []
    for r in rows:
        try:
            o = float(r["o"])
        except Exception:
            continue
        mk = str(r["mk"] or "").upper()
        pk = str(r["pk"] or "").strip()
        # marjsız fiyat — pazarın tam vektöründen
        q = None
        try:
            if mk == "1X2":
                v = [r["c1"], r["cx"], r["c2"]]
                i = {"1": 0, "0": 1, "X": 1, "2": 2}.get(pk.upper())
            elif mk in ("UST_25", "ALT_25", "OU2.5"):
                v = [r["cu"], r["ca"]]
                i = 0 if (mk == "UST_25" or pk.upper() in ("UST", "ÜST")) else 1
            elif mk in ("KG_VAR", "KG_YOK"):
                v = [r["bv"], r["bn"]]
                i = 0 if mk == "KG_VAR" else 1
            else:
                v, i = None, None
            if v and i is not None and not any(
                    x is None or float(x) <= 1.01 for x in v):
                inv = [1.0 / float(x) for x in v]
                q = inv[i] / sum(inv)
        except Exception:
            q = None
        mp = None
        try:
            mp = float(r["mp"]) if r["mp"] is not None else None
            if mp is not None and not (0 < mp < 1):
                mp = None
        except Exception:
            mp = None
        won = r["s"] == "won"
        D.append({
            "mk": mk, "pk": pk, "o": o, "q": q, "mp": mp, "won": won,
            "ret": (o - 1.0) if won else -1.0,
            "e": (mp / q - 1.0) if (mp and q) else None,
            "lg": (r["lg"] or "—"), "ct": str(r["ct"] or "?"),
            "rsn": r["rsn"], "pm": r["pm"], "sat": str(r["sat"] or "")[:16],
            "h": r["h"], "a": r["a"], "p": r["p"],
            "hs": r["hs"], "aws": r["aws"],
        })

    def blok(sel):
        n = len(sel)
        if not n:
            return None
        return {"n": n,
                "hit": sum(1 for x in sel if x["won"]) / n,
                "bek": sum(1.0 / x["o"] for x in sel) / n,
                "roi": sum(x["ret"] for x in sel) / n}

    # ── MODEL: kalibrasyon (model olasılığı bandına göre) ──
    kal = []
    for lo, hi, ad in ((0, .40, "%0-40"), (.40, .55, "%40-55"),
                       (.55, .70, "%55-70"), (.70, .85, "%70-85"),
                       (.85, 1.01, "%85+")):
        g = [x for x in D if x["mp"] and lo <= x["mp"] < hi]
        if len(g) < 5:
            kal.append({"ad": ad, "n": len(g)})
            continue
        pr = sum(x["mp"] for x in g) / len(g)
        ac = sum(1 for x in g if x["won"]) / len(g)
        kal.append({"ad": ad, "n": len(g), "tah": pr, "ger": ac,
                    "fark": ac - pr})

    # ── MODEL: marjsız edge → gerçekleşen getiri ──
    eb = []
    ed = [x for x in D if x["e"] is not None]
    if len(ed) >= 25:
        ed.sort(key=lambda z: z["e"])
        m = len(ed)
        for i in range(5):
            g = ed[i * m // 5:(i + 1) * m // 5] if i < 4 else ed[4 * m // 5:]
            eb.append({"ad": f"Q{i+1}", "n": len(g),
                       "e": sum(x["e"] for x in g) / len(g),
                       "roi": sum(x["ret"] for x in g) / len(g)})

    # ── EDGE TERSLİĞİ NEREDE? ──
    # Denetim bulgusu K1: edge sıralaması TERS (Q1 +%1,2 · Q5 −%7,9).
    # Bir sonraki soru "her yerde mi, bir dilimde mi" — çünkü cevap
    # düzeltmenin nerede yapılacağını söyler. Pazar bazında Q1 ve Q5
    # ayrı ayrı hesaplanır; ikisi arasındaki fark POZİTİF olmalıydı.
    eb_kirilim = []
    for anahtar, ad_f in (("mk", lambda x: str(x)),):
        gr = {}
        for x in ed:
            gr.setdefault(x.get(anahtar) or "?", []).append(x)
        for k, g in gr.items():
            if len(g) < 40:              # dilimlere bölmek için taban
                continue
            g = sorted(g, key=lambda z: z["e"])
            n = len(g)
            alt = g[:n // 3]
            ust = g[-(n // 3):]
            r_alt = sum(x["ret"] for x in alt) / len(alt)
            r_ust = sum(x["ret"] for x in ust) / len(ust)
            eb_kirilim.append({
                "ad": ad_f(k), "n": n,
                "alt": r_alt, "ust": r_ust, "fark": r_ust - r_alt,
                "e_alt": sum(x["e"] for x in alt) / len(alt),
                "e_ust": sum(x["e"] for x in ust) / len(ust)})
    eb_kirilim.sort(key=lambda z: z["fark"])

    # ── TRADE: pazar · kupon türü · lig ──
    def grupla(key, en_az=8):
        d = {}
        for x in D:
            d.setdefault(x[key], []).append(x)
        out = [{"ad": k, **blok(v)} for k, v in d.items()
               if blok(v) and len(v) >= en_az]
        out.sort(key=lambda z: -z["n"])
        return out[:9]

    # ── KAYIP ANATOMİSİ: kombine kaybettiğinde hangi ayak düşürdü? ──
    anat = {"sonuc": 0, "gol": 0, "iki": 0, "n": 0}
    for x in D:
        if x["won"] or " ve " not in str(x["pk"]):
            continue
        if x["hs"] is None or x["aws"] is None:
            continue
        try:
            hs, aws = int(x["hs"]), int(x["aws"])
        except Exception:
            continue
        parts = [p.strip() for p in str(x["pk"]).split(" ve ", 1)]
        if len(parts) != 2:
            continue
        a1, b1 = parts
        res = "1" if hs > aws else ("0" if hs == aws else "2")
        ok_a = (a1 == res) if a1 in ("1", "0", "2") else (
            (hs + aws > 2.5) == (a1.upper() in ("ÜST", "UST")))
        bu = b1.upper()
        if bu in ("ÜST", "UST"):
            ok_b = hs + aws > 2.5
        elif bu == "ALT":
            ok_b = hs + aws < 2.5
        elif bu == "VAR":
            ok_b = hs > 0 and aws > 0
        elif bu == "YOK":
            ok_b = not (hs > 0 and aws > 0)
        else:
            continue
        anat["n"] += 1
        if ok_a and not ok_b:
            anat["gol"] += 1
        elif ok_b and not ok_a:
            anat["sonuc"] += 1
        else:
            anat["iki"] += 1

    # ── gerekçe defteri: son kayıtlar ──
    gd = [x for x in D if (x["rsn"] or x["pm"])]
    gd.sort(key=lambda z: z["sat"], reverse=True)

    return {"n": len(D), "genel": blok(D), "kal": kal, "eb": eb,
            "eb_kirilim": eb_kirilim,
            "pazar": grupla("mk"), "tur": grupla("ct", 5),
            "lig": grupla("lg"), "anat": anat, "defter": gd[:22]}


@st.cache_data(ttl=300, show_spinner=False)
def load_clv() -> dict:
    """CLV kırılımı — pazar ve lig bazında kapanış çizgisi performansı.

    CLV neden önemli: girdiğin fiyat kapanıştan iyiyse, piyasadan ÖNCE
    doğru tarafı görmüşsün demektir. Sonuçtan bağımsızdır — kaybettiğin
    bahiste bile pozitif CLV seçimin doğruluğunu söyler.

    ⚠️ Tek başına marjı YENMEZ. iddaa'nın %17,6'sını aşmak için +%17,6
    CLV gerekir; öyle bir şey yok. CLV bir kâr vaadi değil, ÖNCÜ
    GÖSTERGEDİR."""
    rows = _rows(
        "SELECT market mk, league lg, clv FROM paper_bets "
        "WHERE clv IS NOT NULL", sessiz=True)
    if len(rows) < 50:
        return {"n": len(rows)}
    v = []
    for r in rows:
        try:
            v.append({"mk": str(r["mk"] or "—"), "lg": str(r["lg"] or "—"),
                      "c": float(r["clv"])})
        except Exception:
            continue
    n = len(v)
    m = sum(x["c"] for x in v) / n
    sd = math.sqrt(sum((x["c"] - m) ** 2 for x in v) / max(n - 1, 1)) / math.sqrt(n)

    def kir(key, en_az=30):
        d = {}
        for x in v:
            d.setdefault(x[key], []).append(x["c"])
        out = []
        for k, g in d.items():
            if len(g) < en_az:
                continue
            mm = sum(g) / len(g)
            out.append({"ad": k, "n": len(g), "ort": mm,
                        "beat": sum(1 for z in g if z > 0) / len(g)})
        out.sort(key=lambda z: -z["ort"])
        return out[:8]

    return {"n": n, "ort": m, "t": (m / sd) if sd > 1e-12 else 0.0,
            "beat": sum(1 for x in v if x["c"] > 0) / n,
            "sifir": sum(1 for x in v if abs(x["c"]) < 1e-9) / n,
            "pazar": kir("mk"), "lig": kir("lg")}


@st.cache_data(ttl=600, show_spinner=False)
def load_mihenk() -> dict:
    """Mihenk — 2 günde bir arşivlenen yönetici özeti (V1'den taşındı).

    V2 raporu yeniden ÜRETMEZ, arşivi okur. Rapor üretimi
    02_VERI/exec_report.py'de kalır; burası okuma yüzeyidir. Bir işin
    iki yerde yapılması, V1'in en büyük hatasıydı."""
    rows = _rows("SELECT report_no no, ts, payload FROM exec_reports "
                 "ORDER BY report_no DESC LIMIT 6", sessiz=True)
    if not rows:
        return {"var": False}
    import json
    son = rows[0]
    try:
        p = json.loads(son["payload"])
    except Exception:
        p = {}
    return {"var": True, "no": son["no"], "ts": str(son["ts"])[:16],
            "payload": p, "gecmis": [{"no": r["no"], "ts": str(r["ts"])[:16]}
                                     for r in rows]}


@st.cache_data(ttl=240, show_spinner=False)
def load_egri() -> dict:
    """Kasa eğrisi ve düşüş — dönem kapsamlı, tüm ajanlar birleşik.

    ⚠️ Sıralama kuponun SONUÇLANDIĞI ana göre yapılır, kurulduğu ana
    göre değil. Kasa gerçekte para değiştiğinde hareket eder; kurulma
    sırasına göre çizilen eğri, olmamış bir geçmişi gösterir."""
    rows = _rows(
        "SELECT pc.settled_at sa, pc.pnl, pc.stake, pc.status st "
        "FROM paper_coupons pc "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pc.portfolio_id "
        "WHERE pc.status IN ('won','lost') AND pc.settled_at IS NOT NULL "
        "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start) "
        + _sahada_sql("pc.portfolio_id") + " "
        "ORDER BY pc.settled_at", sessiz=True)
    if len(rows) < 10:
        return {"n": len(rows)}
    kum, tepe, dusus = 0.0, 0.0, 0.0
    nokta, ciro = [], 0.0
    for r in rows:
        try:
            kum += float(r["pnl"] or 0)
            ciro += float(r["stake"] or 0)
        except Exception:
            continue
        tepe = max(tepe, kum)
        dusus = min(dusus, kum - tepe)
        nokta.append({"t": str(r["sa"])[:10], "k": kum, "tepe": tepe})
    son = nokta[-1]["k"] if nokta else 0.0
    return {"n": len(nokta), "nokta": nokta, "son": son, "tepe": tepe,
            "dusus": dusus, "ciro": ciro,
            "roi": (son / ciro) if ciro else 0.0,
            "dusus_pay": (dusus / tepe) if tepe > 0 else 0.0}


def _svg_egri(d: dict, w: int = 560, h: int = 150) -> str:
    """Kasa eğrisi — satır içi SVG, temaya duyarlı.

    Kütüphane yok: plotly bir grafik için 3 MB bağımlılık demek. Alan
    dolgusu, sıfır çizgisi, vurgulanmış son nokta ve düşüş gölgesi
    elle çizilir — okunurluk kütüphaneden değil, seçimlerden gelir."""
    p = d["nokta"]
    if len(p) < 2:
        return ""
    ys = [x["k"] for x in p] + [0.0]
    lo, hi = min(ys), max(ys)
    if hi - lo < 1e-9:
        hi = lo + 1
    pad = (hi - lo) * 0.12
    lo, hi = lo - pad, hi + pad
    n = len(p)

    def X(i):
        return 4 + i * (w - 8) / max(n - 1, 1)

    def Y(v):
        return h - 6 - (v - lo) / (hi - lo) * (h - 12)

    cizgi = " ".join(f"{X(i):.1f},{Y(x['k']):.1f}" for i, x in enumerate(p))
    alan = (f"{X(0):.1f},{Y(0):.1f} " + cizgi +
            f" {X(n-1):.1f},{Y(0):.1f}")
    y0 = Y(0)
    poz = d["son"] >= 0
    renk = "var(--pos)" if poz else "var(--neg)"
    return (
        f"<svg viewBox='0 0 {w} {h}' width='100%' height='{h}' "
        f"preserveAspectRatio='none' role='img' "
        f"aria-label='Kasa eğrisi, son değer {d['son']:.0f} lira'>"
        f"<line x1='0' y1='{y0:.1f}' x2='{w}' y2='{y0:.1f}' "
        f"stroke='var(--line-2)' stroke-width='1' stroke-dasharray='3 3'/>"
        f"<polygon points='{alan}' fill='{renk}' opacity='0.10'/>"
        f"<polyline points='{cizgi}' fill='none' stroke='{renk}' "
        f"stroke-width='1.8' stroke-linejoin='round'/>"
        f"<circle cx='{X(n-1):.1f}' cy='{Y(p[-1]['k']):.1f}' r='3.5' "
        f"fill='{renk}'/></svg>")


@st.cache_data(ttl=120, show_spinner=False)
def load_pozisyon() -> list[dict]:
    """Açık kuponlar — kupon düzeyinde, ayaklarıyla (V1 pozisyon+emir).

    Tahta tek tek seçimleri gösterir; burası KUPONU gösterir: kaç ayak,
    toplam oran, ne kadar yatırıldı, tutarsa ne döner. İkisi farklı
    sorulara cevap verir."""
    kup = _rows(
        "SELECT pc.coupon_id cid, pc.portfolio_id p, pc.num_legs nl, "
        "pc.combined_odds co, pc.stake sk, pc.potential_return pr, "
        "pc.created_at ca FROM paper_coupons pc "
        "WHERE pc.status='open' ORDER BY pc.created_at DESC LIMIT 40",
        sessiz=True)
    if not kup:
        return []
    ids = [k["cid"] for k in kup]
    qs = ",".join("?" for _ in ids)
    ayak = _rows(
        f"SELECT coupon_id cid, home_team h, away_team a, market mk, "
        f"pick pk, odds o, kickoff_utc ko FROM paper_bets "
        f"WHERE coupon_id IN ({qs}) ORDER BY kickoff_utc", tuple(ids),
        sessiz=True)
    by: dict = {}
    for x in ayak:
        by.setdefault(x["cid"], []).append(x)
    out = []
    for k in kup:
        L = by.get(k["cid"], [])
        if not L:
            continue
        out.append({
            "p": k["p"], "em": k["p"],
            "ad": str(k["p"]).rsplit("_", 1)[0],
            "n": len(L), "co": float(k["co"] or 0), "sk": float(k["sk"] or 0),
            # Başlangıç = SIRADAKİ (henüz başlamamış) ayağın saati. İlk
            # ayağın saati, o ayak oynandıktan sonra kuponu "geçmiş"
            # gösteriyordu; kupon ise kalan ayaklar yüzünden hâlâ açık.
            # Hepsi başladıysa kupon sonucunu bekliyordur — öyle yazılır.
            "pr": float(k["pr"] or 0),
            "ko": next((_tr_saat(x["ko"]) for x in L
                        if not _basladi_mi(x["ko"])), "sonuç bekleniyor"),
            "ko_ham": str(L[0]["ko"]),
            "ayak": [{"h": x["h"], "a": x["a"], "mk": x["mk"],
                      "pk": x["pk"], "o": float(x["o"] or 0),
                      "basladi": _basladi_mi(x["ko"])} for x in L],
        })
    # Gösterim metni ("14.09 21:45") sıralanamaz — ham UTC ile sırala.
    out.sort(key=lambda z: z["ko_ham"])
    return out


@st.cache_data(ttl=300, show_spinner=False)
def load_risk() -> list[dict]:
    """Ajan risk durumu — kasa tabanı, dönem, ihtar, lisans (V1 risk+ayarlar).

    Prop-firm mantığı: her ajanın kendi kasası, kendi tabanı ve kendi
    sözleşmesi var. Taban altına düşen ajan koruma moduna girer; iki
    ihtar kadro dışı demektir. Bu sayfa o sözleşmenin durumunu gösterir."""
    rows = _rows(
        "SELECT portfolio_id p, current_bankroll cb, initial_bankroll ib, "
        "peak_bankroll pk, period_status ps, period_start_bankroll pb, "
        "ihtar_count ih, benched bn, era_no en, status st "
        "FROM paper_portfolio ORDER BY current_bankroll DESC", sessiz=True)
    out = []
    for r in rows:
        ib = float(r["ib"] or 1000)
        cb = float(r["cb"] or 0)
        pk = float(r["pk"] or ib)
        oran = (cb / ib) if ib else 0
        if bool(r["bn"]):
            dur, sev = "KADRO DIŞI", "g3"
        elif oran < 0.50:
            dur, sev = "TABAN FRENİ", "g3"
        elif int(r["ih"] or 0) >= 2:
            dur, sev = "2 İHTAR", "g3"
        elif int(r["ih"] or 0) == 1:
            dur, sev = "1 İHTAR", "g2"
        elif oran >= 1.0:
            dur, sev = "SAĞLIKLI", "g1"
        else:
            dur, sev = "İZLEMEDE", "g2"
        out.append({
            "p": r["p"], "em": r["p"],
            "ad": str(r["p"]).rsplit("_", 1)[0], "cb": cb, "ib": ib,
            "oran": oran, "tepe": pk,
            "dusus": ((cb - pk) / pk) if pk > 0 else 0.0,
            "ihtar": int(r["ih"] or 0), "era": r["en"],
            "dur": dur, "sev": sev,
        })
    return out


@st.cache_data(ttl=240, show_spinner=False)
def load_ajan_egri() -> dict:
    """Her ajanın kendi kasa eğrisi — dönem kapsamlı.

    Finansal terminalin küçük-çoklu (small multiples) mantığı: yan yana
    duran küçük eğriler, tek büyük grafikten daha çok şey söyler. Göz
    şekli karşılaştırır — hangisi yükseliyor, hangisi düz, hangisi
    uçurumdan düşmüş."""
    rows = _rows(
        "SELECT pc.portfolio_id p, pc.settled_at sa, pc.pnl "
        "FROM paper_coupons pc "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pc.portfolio_id "
        "WHERE pc.status IN ('won','lost') AND pc.settled_at IS NOT NULL "
        "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start) "
        + _sahada_sql("pc.portfolio_id") + " "
        "ORDER BY pc.settled_at", sessiz=True)
    by: dict = {}
    for r in rows:
        try:
            by.setdefault(r["p"], []).append(float(r["pnl"] or 0))
        except Exception:
            continue
    out = {}
    for pid, v in by.items():
        kum, seri, tepe, dus = 0.0, [], 0.0, 0.0
        for x in v:
            kum += x
            tepe = max(tepe, kum)
            dus = min(dus, kum - tepe)
            seri.append(kum)
        out[pid] = {"seri": seri, "son": kum, "dusus": dus, "n": len(seri)}
    return out


@st.cache_data(ttl=180, show_spinner=False)
def load_islem_bandi() -> dict:
    """Her ajanın İŞLEM BANDI — dönem içi kuponlar kronolojik, borsa işlem
    şeridi gibi (kullanıcı, 19.09: "ajanların altına seri gibi bir bant —
    ne kazanıyor ne kaybediyor, kronolojik, borsa trade'leri gibi").

    Kapanmış kupon kapanış sırasıyla; açık kuponlar sonda. Etiket ilk
    ayaktan ('Maç · pazar seçim'), çok ayaklı kuponda '+N ayak'."""
    kup = _rows(
        "SELECT pc.portfolio_id p, pc.coupon_id cid, pc.status s, pc.pnl, "
        "pc.stake, pc.combined_odds o, pc.created_at ca, pc.settled_at sa, "
        "pc.num_legs nl FROM paper_coupons pc "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pc.portfolio_id "
        "WHERE pc.status IN ('won','lost','open') "
        "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start)",
        sessiz=True)
    ayak = _rows(
        "SELECT pb.coupon_id cid, pb.home_team h, pb.away_team a, "
        "pb.market mk, pb.pick pk FROM paper_bets pb "
        "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pc.portfolio_id "
        "WHERE pc.status IN ('won','lost','open') "
        "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start)",
        sessiz=True)
    ilk: dict = {}
    for x in ayak:
        ilk.setdefault(x["cid"], x)
    out: dict = {}
    for k in kup:
        a = ilk.get(k["cid"]) or {}
        et = (str(a.get("h") or "?") + " — " + str(a.get("a") or "?") + " · " +
              str(a.get("mk") or "") + " " + str(a.get("pk") or ""))
        if int(k.get("nl") or 1) > 1:
            et += " +" + str(int(k["nl"]) - 1) + " ayak"
        try:
            pnl = float(k["pnl"] or 0)
        except Exception:
            pnl = 0.0
        out.setdefault(k["p"], []).append({
            "s": k["s"], "pnl": pnl, "stake": float(k.get("stake") or 0),
            "o": float(k.get("o") or 0), "et": et,
            "t": str(k.get("sa") or k.get("ca") or ""),
            "sira": (0 if k["s"] != "open" else 1,
                     str(k.get("sa") or k.get("ca") or ""))})
    for v in out.values():
        v.sort(key=lambda z: z["sira"])
    return out


def _islem_bandi(islem: list, son: int = 40, h: int = 30,
                 adim: float = 8.0) -> str:
    """İşlem bandı — her kupon bir çubuk: kazanç YUKARI yeşil, kayıp AŞAĞI
    kırmızı, boy tutarla orantılı; açık pozisyon sonda gri, içi boş.

    Kıvılcım çizgisi (Seyir) kümülatif ŞEKLİ söyler; bant tek tek İŞLEMLERİ
    — seri mi kazanıyor, büyük bir kayıp mı yedi, açığı ne kadar. Üzerine
    gelince maç, seçim, oran ve kâr/zarar görünür (SVG <title>)."""
    import html as _h
    if not islem:
        return ""
    goster = islem[-son:]
    n = len(goster)
    w = max(n * adim, adim)
    mx = max((abs(x["pnl"]) for x in goster if x["s"] != "open"), default=0.0)
    mx = max(mx, max((x["stake"] for x in goster), default=0.0), 1.0)
    orta = h / 2.0
    parca = [f"<line x1='0' y1='{orta:.1f}' x2='{w:.1f}' y2='{orta:.1f}' "
             f"stroke='var(--line-2)' stroke-width='1'/>"]
    for i, x in enumerate(goster):
        x0 = i * adim + 1
        tarih = x["t"][8:10] + "." + x["t"][5:7] if len(x["t"]) >= 10 else ""
        if x["s"] == "open":
            y, bh, renk, dolgu = orta - 4, 8.0, "var(--muted)", "none"
            ipucu = (f"{tarih} · AÇIK · {x['et']} · @{x['o']:.2f} · "
                     f"risk {x['stake']:.0f} ₺")
        else:
            oran = min(abs(x["pnl"]) / mx, 1.0)
            bh = max(oran * (orta - 2), 2.0)
            kaz = x["s"] == "won"
            y = orta - bh if kaz else orta
            renk = "var(--pos)" if kaz else "var(--neg)"
            dolgu = renk
            ipucu = (f"{tarih} · {'KAZANDI' if kaz else 'KAYBETTİ'} · {x['et']} · "
                     f"@{x['o']:.2f} · {'+' if x['pnl'] >= 0 else '−'}"
                     f"{abs(x['pnl']):.0f} ₺")
        parca.append(
            f"<rect x='{x0:.1f}' y='{y:.1f}' width='{adim - 2:.1f}' "
            f"height='{bh:.1f}' fill='{dolgu}' stroke='{renk}' "
            f"stroke-width='{1 if dolgu == 'none' else 0}' rx='1'>"
            f"<title>{_h.escape(ipucu)}</title></rect>")
    # Çubuk genişliği SABİT (esnetilmez): 3 işlemli ajanın çubukları satır
    # boyu kalın olmasın, ajanlar arası kıyas bozulmasın. Dar ekranda
    # orantılı küçülür (max-width).
    return (f"<svg class='bant' viewBox='0 0 {w:.0f} {h}' width='{w:.0f}' "
            f"height='{h}' style='max-width:100%;height:auto;' role='img' "
            f"aria-label='son {n} işlem'>" + "".join(parca) + "</svg>")


def _bant_ozet(islem: list, son: int = 40) -> str:
    """Bandın yanındaki tek satır: işlem sayısı · K/Z · net · seri."""
    if not islem:
        return ""
    goster = islem[-son:]
    kap = [x for x in goster if x["s"] != "open"]
    k = sum(1 for x in kap if x["s"] == "won")
    z = len(kap) - k
    net = sum(x["pnl"] for x in kap)
    acik = len(goster) - len(kap)
    seri, yon = 0, None
    for x in reversed(kap):
        if yon is None:
            yon = x["s"]
        if x["s"] != yon:
            break
        seri += 1
    return ("son " + str(len(goster)) + " işlem · <b class='dp0'>" + str(k) +
            " K</b> · <b class='dm0'>" + str(z) + " Z</b> · net <b class='" +
            ("dp0" if net >= 0 else "dm0") + "'>" + ("+" if net >= 0 else "−") +
            "{:,.0f}".format(abs(net)).replace(",", ".") + " ₺</b>" +
            (" · seri " + str(seri) + ("K" if yon == "won" else "Z") if seri > 1 else "") +
            (" · " + str(acik) + " açık" if acik else ""))


def _kivilcim(seri: list, w: int = 96, h: int = 26) -> str:
    """Kıvılcım çizgisi — tablo hücresine sığan mini eğri.

    Eksen yok, etiket yok: bu bir grafik değil, bir ŞEKİL. Rakam zaten
    yanındaki sütunda; buradan okunması gereken tek şey yön ve pürüz."""
    if not seri or len(seri) < 2:
        return "<span style='color:var(--muted);font-size:var(--t-kucuk);'>—</span>"
    lo, hi = min(seri + [0.0]), max(seri + [0.0])
    if hi - lo < 1e-9:
        hi = lo + 1
    n = len(seri)
    pts = " ".join(
        f"{2 + i * (w - 4) / max(n - 1, 1):.1f},"
        f"{h - 2 - (v - lo) / (hi - lo) * (h - 4):.1f}"
        for i, v in enumerate(seri))
    y0 = h - 2 - (0 - lo) / (hi - lo) * (h - 4)
    renk = "var(--pos)" if seri[-1] >= 0 else "var(--neg)"
    sx = 2 + (n - 1) * (w - 4) / max(n - 1, 1)
    sy = h - 2 - (seri[-1] - lo) / (hi - lo) * (h - 4)
    return (
        f"<svg viewBox='0 0 {w} {h}' width='{w}' height='{h}' "
        f"style='display:block;' aria-hidden='true'>"
        f"<line x1='0' y1='{y0:.1f}' x2='{w}' y2='{y0:.1f}' "
        f"stroke='var(--line-2)' stroke-width='1'/>"
        f"<polyline points='{pts}' fill='none' stroke='{renk}' "
        f"stroke-width='1.4' stroke-linejoin='round'/>"
        f"<circle cx='{sx:.1f}' cy='{sy:.1f}' r='2' fill='{renk}'/></svg>")


@st.cache_data(ttl=180, show_spinner=False)
def load_ajan_detay(pid: str) -> dict:
    """Tek ajanın dosyası — V1'de ayrı sayfaydı, artık aynı yerde açılır.

    Ayrı sayfa yerine açılır panel: bağlamı kaybetmeden inceleme.
    Ligden çıkıp geri dönmek, karşılaştırmayı bozar."""
    bet = _rows(
        "SELECT pb.home_team h, pb.away_team a, pb.market mk, pb.pick pk, "
        "pb.odds o, pb.status s, pb.reason rsn, pb.postmortem pm, "
        "pb.settled_at sat, pb.league lg, pb.result res, pb.kickoff_utc ko "
        "FROM paper_bets pb "
        "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pb.portfolio_id "
        "WHERE pb.portfolio_id = ? AND pb.status IN ('won','lost') "
        "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start) "
        "ORDER BY pb.settled_at DESC LIMIT 14", (pid,), sessiz=True)
    # Yalnız AÇIK kuponun ayağı — ölü kombinenin ayağı pozisyon değildir.
    acik = _rows(
        "SELECT pb.home_team h, pb.away_team a, pb.market mk, pb.pick pk, "
        "pb.odds o, pb.kickoff_utc ko FROM paper_bets pb "
        "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
        "WHERE pb.portfolio_id = ? AND pb.status = 'open' "
        "AND pc.status = 'open' ORDER BY pb.kickoff_utc LIMIT 8",
        (pid,), sessiz=True)
    tes = _rows(
        "SELECT status, detail, ts FROM agent_diag WHERE pid = ? "
        "ORDER BY ts DESC LIMIT 1", (pid,), sessiz=True)
    return {"bet": bet, "acik": acik, "teshis": (tes[0] if tes else None)}


# ttl KISA: bu bir denetimdir, sunum degil. Uzun onbellek "temiz"
# gorunurken bozuk bir defteri saklayabilir — tam da onlemeye
# calistigi sey. 30 sn, ayni ekranda tiklarken her seferinde bes
# sorgu kosmasini engelleyecek kadar; bozulmayi geciktirmeyecek kadar.
@st.cache_data(ttl=30, show_spinner=False)
def load_defter_denetim() -> list[dict]:
    """Defter kendi kendini tutuyor mu — canli veritabanindan okur.

    Bunlar sunum degil DENETIM satiridir. 2026-09-01'de uretimde
    verify_settlements.py'nin acik ayaklari suzup atip kuponu erken
    "won" yazdigi bulundu: SIMYACI'nin kuponu 1 Eylul'de odendi, iki
    maci 2 ve 4 Eylul'de oynanacakti. Kasaya var olmayan para girdi.
    Kok neden duzeltildi; bu sekme o hatanin SESSIZCE geri donmemesi
    icin var. Bir sayi buyurse burada kirmizi yanar.
    """
    d: list[dict] = []

    # 1) Erken kapanmis kupon: kapandi, acik ayagi var, kaybeden ayagi YOK.
    #    Kaybeden ayagi olan (olu kombine) mesrudur — ayri satirda sayilir.
    ek = _rows(
        "SELECT COUNT(*) n FROM (SELECT pc.coupon_id "
        "FROM paper_coupons pc JOIN paper_bets pb ON pb.coupon_id=pc.coupon_id "
        "WHERE pc.status IN ('won','lost','void') GROUP BY pc.coupon_id "
        "HAVING SUM(CASE WHEN pb.status='open' THEN 1 ELSE 0 END)>0 "
        "AND SUM(CASE WHEN pb.status='lost' THEN 1 ELSE 0 END)=0) t",
        sessiz=True)
    d.append({"ad": "Erken kapanmış kupon",
              "aciklama": "Kupon ödendi ama ayağı hâlâ açık ve kaybeden ayak "
                          "yok — maç oynanmadan para yazılmış demektir.",
              "n": int(ek[0]["n"]) if ek else 0, "esik": 0})

    # 2) Olu kombine: kaybeden ayak var, kalan ayaklar acik. MESRU.
    ok = _rows(
        "SELECT COUNT(*) n FROM (SELECT pc.coupon_id "
        "FROM paper_coupons pc JOIN paper_bets pb ON pb.coupon_id=pc.coupon_id "
        "WHERE pc.status='lost' GROUP BY pc.coupon_id "
        "HAVING SUM(CASE WHEN pb.status='open' THEN 1 ELSE 0 END)>0 "
        "AND SUM(CASE WHEN pb.status='lost' THEN 1 ELSE 0 END)>0) t",
        sessiz=True)
    d.append({"ad": "Ölü kombine (meşru)",
              "aciklama": "Bir ayak kaybetti, kupon bitti; kalan ayaklar "
                          "sonucu degistiremez. Hata degil — bilgi.",
              "n": int(ok[0]["n"]) if ok else 0, "esik": None})

    # 3) Oksuz bahis: kupon satiri olmayan bahis.
    ob = _rows(
        "SELECT COUNT(*) n FROM paper_bets pb LEFT JOIN paper_coupons pc "
        "ON pc.coupon_id=pb.coupon_id WHERE pc.coupon_id IS NULL", sessiz=True)
    d.append({"ad": "Öksüz bahis",
              "aciklama": "Kupon satırı olmayan bahis. Stake kuponda "
                          "tutuluyor; kuponsuz bahsin riski ölçülemez.",
              "n": int(ob[0]["n"]) if ob else 0, "esik": 0})

    # 4) Ayak sayisi uyusmazligi: num_legs != gercek ayak.
    au = _rows(
        "SELECT COUNT(*) n FROM (SELECT pc.coupon_id "
        "FROM paper_coupons pc JOIN paper_bets pb ON pb.coupon_id=pc.coupon_id "
        "GROUP BY pc.coupon_id, pc.num_legs "
        "HAVING COUNT(*) <> pc.num_legs) t", sessiz=True)
    d.append({"ad": "Ayak sayısı uyuşmuyor",
              "aciklama": "Kuponun beyan ettiği ayak sayısı ile gerçek ayak "
                          "sayısı farklı — kombine oran yanlış hesaplanır.",
              "n": int(au[0]["n"]) if au else 0, "esik": 0})

    # 5) Kasa mutabakati: current_bankroll = initial + Σpnl(won/lost, era ici)
    km = _rows(
        "SELECT COUNT(*) n FROM (SELECT pp.portfolio_id "
        "FROM paper_portfolio pp LEFT JOIN paper_coupons pc "
        "ON pc.portfolio_id=pp.portfolio_id AND pc.status IN ('won','lost') "
        "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start) "
        "GROUP BY pp.portfolio_id, pp.current_bankroll, pp.initial_bankroll "
        "HAVING ABS(pp.current_bankroll - (pp.initial_bankroll + "
        "COALESCE(SUM(pc.pnl),0))) > 0.5) t", sessiz=True)
    d.append({"ad": "Kasa mutabakatsız ajan",
              "aciklama": "Kasa = başlangıç + Σ PnL olmalı. Tutmuyorsa "
                          "sayaç kaymıştır; recompute_portfolio düzeltir.",
              "n": int(km[0]["n"]) if km else 0, "esik": 0})

    return d


@st.cache_data(ttl=600, show_spinner=False)
def load_cakisma() -> dict:
    """AJAN ÇAKIŞMASI — kaç ajan gerçekten farklı bir şey yapıyor?

    ⚠️ Denetimde canlı kanıt bulundu: MEMUR ve TEMKİNLİ'nin açık kuponu
    BİREBİR aynıydı — aynı iki ayak, aynı 1,66 oran, aynı tutar. Yol
    haritasının "ayırt edici olmayan ajanları ele" maddesi o güne kadar
    teorikti.

    Neden önemli: on altı ajanın çoğu aynı seçimi yapıyorsa elimizde on
    altı bağımsız görüş YOK, tek görüşün on altı kopyası var. Ortalama
    almak, çoğunluğa bakmak, "ajanlar hemfikir" demek — hepsi yanıltıcı
    olur. Çeşitlilik bir tercih değil, ölçümün ön koşuludur.

    Ölçüt: iki ajanın AYNI (maç, pazar, seçim) üçlüsünü oynama oranı,
    daha az bahis yapanın toplamına bölünür (Szymkiewicz–Simpson örtüşme
    katsayısı). Az oynayan bir ajanın tamamı diğerinin içindeyse bu %100
    çakışmadır — asimetrik böleni bilerek seçtim, çünkü soru "bu ajan
    bağımsız bir şey söylüyor mu" sorusudur.
    """
    rows = _rows(
        "SELECT pb.portfolio_id p, m.matchday d, m.home_team h, "
        "m.away_team a, pb.market mk, pb.pick pk "
        "FROM paper_bets pb JOIN matches_v2 m ON m.match_id = pb.match_id "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pb.portfolio_id "
        "WHERE (pp.era_start IS NULL OR pb.kickoff_utc >= pp.era_start)",
        sessiz=True)
    if not rows:
        return {"ciftler": [], "ro": 0.0, "m": 0, "cift_sayisi": 0}
    kume: dict = {}
    for r in rows:
        kume.setdefault(r["p"], set()).add(
            (r["d"], r["h"], r["a"], r["mk"], r["pk"]))
    # Yalniz SAHADAKI ajanlar — emeklinin cakismasi bugunun kararini
    # etkilemez ve ortalama ρ'yu bozar.
    try:
        from agents import PROFILES as _AGP
        _aktif = {k for k, v in _AGP.items() if not v.get("retired")}
        if _aktif:
            kume = {k: v for k, v in kume.items() if k in _aktif}
    except Exception:
        pass
    ajanlar = sorted(kume, key=lambda p: -len(kume[p]))
    out, tum_oran = [], []
    for i, x in enumerate(ajanlar):
        for y in ajanlar[i + 1:]:
            ax, ay = kume[x], kume[y]
            kucuk = min(len(ax), len(ay))
            if kucuk < 8:          # az örneklemde örtüşme oranı gürültü
                continue
            ortak = len(ax & ay)
            oran = ortak / kucuk
            tum_oran.append(oran)      # ORTALAMA icin HEPSI sayilir
            if oran >= 0.35:
                out.append({"a": x, "b": y, "ortak": ortak,
                            "na": len(ax), "nb": len(ay), "oran": oran})
    out.sort(key=lambda z: -z["oran"])
    # ⚠️ Ortalama ρ, ETKİN AJAN SAYISI hesabının girdisi (belge §3.4).
    # Panelde gösterilen eşiğin (%35) üstündekiler değil, TÜM çiftlerin
    # ortalaması alınır — eşik sunum içindir, hesap için değil.
    ro = (sum(tum_oran) / len(tum_oran)) if tum_oran else 0.0
    return {"ciftler": out, "ro": ro, "m": len(ajanlar),
            "cift_sayisi": len(tum_oran)}


@st.cache_data(ttl=300, show_spinner=False)
def load_veri_ozet() -> dict:
    """Verinin ÖZETİ, KALİTESİ ve TAZELİĞİ.

    Doluluk oranı tek başına yetmez: 26.000 satırın %90'ı dolu olabilir
    ama hepsi iki yıl önceden ise sistem kördür. Üç soru ayrı ayrı
    sorulmalı — ne kadar var, ne kadarı dolu, ne kadarı taze."""
    t = _rows("SELECT COUNT(*) n FROM matches_v2", sessiz=True)
    st_ = _rows("SELECT COUNT(*) n FROM matches_v2 WHERE is_settled=1",
                sessiz=True)
    ac = _rows("SELECT COUNT(*) n FROM matches_v2 WHERE is_settled=0 "
               "AND kickoff_utc > ?", (_simdi(),), sessiz=True)
    tz = _rows("SELECT MAX(refreshed_at) v FROM matches_v2", sessiz=True)
    # kaynak dagilimi ve tarih araligi
    kay = _rows("SELECT closing_source k, COUNT(*) n, "
                "MIN(substr(CAST(kickoff_utc AS TEXT),1,7)) ilk, "
                "MAX(substr(CAST(kickoff_utc AS TEXT),1,7)) son "
                "FROM matches_v2 WHERE is_settled=1 AND closing_1 IS NOT NULL "
                "GROUP BY closing_source ORDER BY n DESC", sessiz=True)
    # tablo boyutlari — sistemin hafizasi
    tablolar = []
    for tb, ad in (("matches_v2", "maç"), ("market_odds", "pazar fiyatı"),
                   ("paper_bets", "bahis"), ("paper_coupons", "kupon"),
                   ("odds_history", "fiyat geçmişi"),
                   ("measurement_runs", "ölçüm koşusu"),
                   ("injuries", "sakatlık"), ("xg_data", "xG")):
        r = _rows(f"SELECT COUNT(*) n FROM {tb}", sessiz=True)
        if r:
            tablolar.append({"ad": ad, "tb": tb, "n": int(r[0]["n"] or 0)})
    return {
        "toplam": int(t[0]["n"]) if t else 0,
        "sonuclanmis": int(st_[0]["n"]) if st_ else 0,
        "yaklasan": int(ac[0]["n"]) if ac else 0,
        "tazelik": str(tz[0]["v"])[:16] if (tz and tz[0]["v"]) else None,
        "kaynak": kay, "tablolar": tablolar,
    }


def _simdi() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


@st.cache_data(ttl=240, show_spinner=False)
def load_egri_ham() -> list[dict]:
    """Ham kupon akışı — süzgeç uygulanabilsin diye toplanmadan.

    Eğri sunucuda değil, süzgeçten SONRA hesaplanır. Önceden toplanmış
    seri süzülemez: ajan çıkarınca eğrinin baştan kurulması gerekir."""
    return _rows(
        "SELECT pc.portfolio_id p, pc.settled_at sa, pc.pnl, pc.stake, "
        "pc.coupon_type ct, pc.num_legs nl, "
        "(SELECT string_agg(DISTINCT pb.market, ',') FROM paper_bets pb "
        " WHERE pb.coupon_id = pc.coupon_id) mk "
        "FROM paper_coupons pc "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pc.portfolio_id "
        "WHERE pc.status IN ('won','lost') AND pc.settled_at IS NOT NULL "
        # ⚠️ DÖNEMİN başlangıcı — ajanın KENDİ penceresi değil. Bir ajana
        # kredi + yeni pencere açılınca (CESUR v1.2, 17.09) eski penceresinin
        # kayıpları sistem eğrisinden DÜŞMEMELİ: yoksa kredi, sistem kârı gibi
        # görünür (NET −821 ₺ bir gecede +48 ₺ olacaktı). Ajan hükmü kendi
        # penceresinden; sistemin parası dönemin başından.
        "AND pp.era_start IS NOT NULL "
        "AND pc.created_at >= (SELECT MIN(p2.era_start) FROM paper_portfolio p2 "
        "WHERE p2.era_no = pp.era_no) "
        + _sahada_sql("pc.portfolio_id") + " "
        "ORDER BY pc.settled_at", sessiz=True)


def _svg_zaman(nokta: list, w: int = 900, h: int = 260) -> str:
    """Zaman eksenli kasa eğrisi — Bloomberg/Alpaca usulü.

    Eksen olmadan grafik bir şekilden ibarettir: 'yükseliyor' dersin ama
    'ne zaman' diyemezsin. Burada X tarih, Y para; ikisi de etiketli,
    seyrek ızgaralı. Izgara soluk çünkü işi hizalamak, dikkat çekmek
    değil."""
    if len(nokta) < 2:
        return ("<div class='dq'>Eğri için en az iki sonuçlanmış kupon "
                "gerekiyor.</div>")
    SOL, ALT, UST, SAG = 58, 26, 10, 12
    gw, gh = w - SOL - SAG, h - ALT - UST
    ys = [p["k"] for p in nokta] + [0.0]
    lo, hi = min(ys), max(ys)
    if hi - lo < 1e-9:
        hi = lo + 1
    pad = (hi - lo) * 0.10
    lo, hi = lo - pad, hi + pad
    n = len(nokta)

    def X(i):
        return SOL + i * gw / max(n - 1, 1)

    def Y(v):
        return UST + gh - (v - lo) / (hi - lo) * gh

    parts = []
    # yatay izgara + para etiketleri
    for f in (0.0, 0.25, 0.5, 0.75, 1.0):
        v = lo + (hi - lo) * f
        y = Y(v)
        parts.append(
            f"<line x1='{SOL}' y1='{y:.1f}' x2='{w-SAG}' y2='{y:.1f}' "
            f"stroke='var(--line)' stroke-width='1'/>"
            f"<text x='{SOL-8}' y='{y+3.5:.1f}' text-anchor='end' "
            f"font-size='10' fill='var(--muted)' "
            f"font-family='JetBrains Mono,monospace'>"
            f"{('+' if v>=0 else '−')}{abs(v):,.0f}</text>".replace(",", "."))
    # sifir cizgisi belirgin
    parts.append(
        f"<line x1='{SOL}' y1='{Y(0):.1f}' x2='{w-SAG}' y2='{Y(0):.1f}' "
        f"stroke='var(--line-2)' stroke-width='1.2' stroke-dasharray='4 3'/>")
    # dikey izgara + tarih etiketleri (en fazla 6)
    adim = max(1, n // 6)
    for i in range(0, n, adim):
        x = X(i)
        t = str(nokta[i]["t"])[5:10].replace("-", ".")
        parts.append(
            f"<line x1='{x:.1f}' y1='{UST}' x2='{x:.1f}' y2='{UST+gh}' "
            f"stroke='var(--line)' stroke-width='1'/>"
            f"<text x='{x:.1f}' y='{h-8}' text-anchor='middle' font-size='10' "
            f"fill='var(--muted)' font-family='JetBrains Mono,monospace'>"
            f"{t}</text>")
    cizgi = " ".join(f"{X(i):.1f},{Y(p['k']):.1f}" for i, p in enumerate(nokta))
    alan = f"{X(0):.1f},{Y(0):.1f} {cizgi} {X(n-1):.1f},{Y(0):.1f}"
    poz = nokta[-1]["k"] >= 0
    renk = "var(--pos)" if poz else "var(--neg)"
    parts.append(f"<polygon points='{alan}' fill='{renk}' opacity='0.09'/>")
    parts.append(f"<polyline points='{cizgi}' fill='none' stroke='{renk}' "
                 f"stroke-width='1.9' stroke-linejoin='round'/>")
    parts.append(f"<circle cx='{X(n-1):.1f}' cy='{Y(nokta[-1]['k']):.1f}' "
                 f"r='4' fill='{renk}'/>")
    return (f"<svg viewBox='0 0 {w} {h}' width='100%' height='{h}' "
            f"role='img' aria-label='Kasa eğrisi, zaman eksenli'>"
            + "".join(parts) + "</svg>")


# ══════════════════════════════════════════════════════════════
# SAYFA
# ══════════════════════════════════════════════════════════════

def _rail() -> None:
    """Durum şeridi — iki sayfa da kullanır. Veri kaynağı burada
    YAZAR: yanlış kaynağı üretim sanmak, yanlış rakama güvenmektir."""

    r = load_rail()
    kcell = ("henüz yok" if r["k"] is None
             else f"{r['k']:+.3f}".replace(".", ","))
    kasa = f"{r['kasa']:,.0f}".replace(",", ".")
    kapali = f"{r['kapali']:,}".replace(",", ".")
    yerel = r["kaynak"].startswith("SQLite")
    st.markdown(f"""
    <div class="v2rail">
      <div class="bm"><b>BETAGENTS</b><span>Desk · v2</span></div>
      <div class="st"><label>Veri kaynağı</label>
        <b class="{'dn' if yerel else ''}">{r['kaynak']}</b></div>
      <div class="st"><label>Toplam kasa</label><b>{kasa} ₺</b></div>
      <div class="st"><label>Portföy</label><b>{r['portfoy']}</b></div>
      <div class="st"><label>Açık pozisyon</label><b>{r['acik']}</b></div>
      <div class="st"><label>Kapanmış bahis</label><b>{kapali}</b></div>
      <div class="st"><label>Beceri katsayısı k</label>
        <b class="{'up' if r['k_gecti'] else 'dn'}">{kcell}</b></div>
    </div>""", unsafe_allow_html=True)
    if yerel:
        st.markdown(
            "<div class='dq' style='margin:0 0 12px;'><b>YEREL SQLITE</b> — "
            "üretim verisi değil. Canlı rakamlar için <code>DATABASE_URL</code> "
            "ortam değişkeni gerekiyor. Aşağıdaki her sayı bu kaynaktan.</div>",
            unsafe_allow_html=True)


def page_desk() -> None:
    r = load_rail()
    _sayfa_basligi(
        "Karar Masası",
        "Kime güvenilir, bugün ne var, ne kuruyorsun — üçü bir arada.",
        [{"ad": "Açık pozisyon", "deger": str(r["acik"])},
         {"ad": "Kapanmış bahis",
          "deger": "{:,}".format(r["kapali"]).replace(",", ".")},
         {"ad": "İsabet (dönem)", "deger": _isabet_toplam()},
         {"ad": "Beceri k",
          "deger": ("henüz yok" if r["k"] is None
                    else ("%+.3f" % r["k"]).replace(".", ",")),
          "cls": ("ps" if r["k_gecti"] else "ng")}])
    # Ajan Güveni tablosu 5 sütun taşıyor ve panelin en dar olanıydı;
    # "Seçtiklerin" paneli seçim yapılana kadar neredeyse boş. Genişlik
    # ihtiyaca göre dağıtıldı.
    # Ölçüldü (1280px ekran): 1.62/1.42/0.78 sağ paneli 185px'e
    # düşürüyordu ve "Seçtiklerin" başlığı kelime ortasından bölünüyordu.
    # Güven tablosu yine de eskisinden geniş (346px → ~420px).
    left, mid, right = st.columns([1.50, 1.42, 0.95], gap="medium")

    ags = load_agents()
    # DÖNEM YENİ BAŞLADIYSA tablo boş olur — bu bir arıza değil, dönemin
    # kendisidir. Boş bir tablo göstermek yerine NE OLDUĞUNU söylüyoruz:
    # kaç ajan sahada, dönem ne zaman başladı, neden sayı yok.
    _era = load_era_ozet()
    # ⚠️ Denetim bulgusu O1: sol panel ajanları sıralıyor, orta panel
    # seçimleri listeliyordu — ikisi birbirini TANIMIYORDU. Üretimde
    # tahtadaki 22 seçimin 8'i KALECİ'dendi ve KALECİ güven tablosunda
    # 16 ajan içinde 13. sıradaydı (−11,0p). Solda okuduğun uyarı, sağda
    # seçim yaparken kayboluyordu. Sıra ve hüküm artık seçim satırında.
    _sira_h = {}
    _ag_h = {_a["pid"]: _a for _a in ags}      # isabet: tahta + kuponlar
    for _i, _a in enumerate(ags, 1):
        # Hüküm TEK kuraldan (_hukum) — tablo ile tahta ayrışmasın.
        _sira_h[_a["pid"]] = {"sira": _i, "hukum": _hukum(_a)[1],
                              "toplam": len(ags), "edge": _a["edge"]}

    # ── SOL: ajan güveni ──────────────────────────────────────
    with left:
        by_hit = sorted(ags, key=lambda z: -z["hit"])
        swap = ""
        for a in ags:
            i_hit = by_hit.index(a) + 1
            i_edge = ags.index(a) + 1
            if abs(i_hit - i_edge) >= 5:
                swap = (f"<b>{a['ad']}</b> isabette {i_hit}. sırada, "
                        f"üstünlükte {i_edge}. sırada.")
                break
        body = []
        for i, a in enumerate(ags, 1):
            g, txt = _hukum(a)
            # 0,5 puandan kucuk fark isaretlenmez — +0,0p yesil
            # gostermek, olcum gurultusunu avantaj gibi sunmaktir.
            adv = " class='adv'" if a["edge"] >= 0.005 else ""
            body.append(
                f"<tr{adv}><td class='rk'>{i}</td>"
                f"<td><span class='ag'>{_rozet(a['pid'])}{a['ad']}</span>"
                + (f"<span class='sb'>henüz bahis kurmadı</span></td>"
                   if a.get("bekliyor") else
                   # İsabet alt satırda: sütunu bu dar panelde gizleniyordu.
                   f"<span class='sb'>{_isabet(a)} · oran {_num(a['odds'])}</span></td>")
                + (f"<td class='r n opt dar'>—</td>"
                   f"<td class='r n opt dar'>—</td>"
                   f"<td class='r'><span class='sb'>—</span></td>"
                   if a.get("bekliyor") else
                   f"<td class='r n opt dar'>{_pct(a['hit'])}</td>"
                   f"<td class='r n opt dar'>{_pct(a['exp'])}</td>"
                   f"<td class='r'><span class='{'dp' if a['edge']>=0.005 else 'dm'}'>"
                   f"{_sgn(a['edge'])}</span></td>") +
                f"<td class='r'><span class='gr {g}'>{txt}</span></td></tr>")
        # ── RASTGELE KONTROL ÇİZGİSİ ─────────────────────────────
        # ⚠️ Denetim bulgusu K1'in üçüncü ayağı: JOKER bir AJAN DEĞİL,
        # deterministik-rastgele seçim yapan KONTROL çizgisidir. Her
        # ajanın geçmesi gereken taban odur. Bu bilgi yalnızca Mihenk
        # raporunda bir madde işaretiydi; ana sayfada JOKER sıradan bir
        # satır gibi duruyordu. Rastgeleyi geçemeyen bir ajan sıralamada
        # kaçıncı olursa olsun bir şey bilmiyor demektir — bu, güven
        # tablosunun EN ÖNEMLİ okuma anahtarı.
        _sira = next((i for i, x in enumerate(ags, 1)
                      if x["pid"] == "JOKER_V1"), None)
        _kontrol = ""
        if _sira:
            _gecen = _sira - 1
            _kalan = len(ags) - _sira
            _ok = _gecen <= max(1, len(ags) // 4)
            _kontrol = (
                "<div class='" + ("dq" if _ok else "v2mb") + "' "
                "style='margin-bottom:var(--s3);'>"
                "<b>Rastgele kontrol çizgisi: JOKER " + str(_sira) +
                ". sırada.</b> JOKER bir ajan değil — <b>rastgele seçim</b> "
                "yapan taban çizgisi. Onu geçemeyen bir ajan, sıralamada "
                "kaçıncı olursa olsun bir şey bilmiyor demektir. Şu an "
                "<b>" + str(_gecen) + " ajan</b> rastgeleyi geçiyor, <b>" +
                str(_kalan) + " ajan</b> geçemiyor.</div>")
        # ⚠️ BOŞ DURUM METNİ F-STRING DIŞINDA KURULUR.
        # İlk halim bunu f-string içine koşullu ifade olarak koymuştu:
        #     {(...uzun HTML...) if not body else ""}
        # `body` doluyken ifade "" döndürüyor ve SATIR TAMAMEN BOŞ kalıyordu.
        # Markdown boş satırı HTML bloğunun SONU sayar; ardından gelen
        # girintili "<table ...>" satırı KOD BLOĞU sanılıp kaçışlanıyordu.
        # Sonuç: canlı sayfada 98 ham HTML etiketi metin olarak göründü.
        # Değişken olarak kurulunca satır asla boşalmaz.
        _bos_era = ""
        if not body:
            _bos_era = (
                "<div class='dq'><b>Dönem " + str(_era.get("era", "?")) +
                " başladı — " + str(_era.get("bas", "")) + ".</b> Sahadaki " +
                str(_era.get("ajan", "?")) + " ajanın kasası sıfırlandı ve "
                "sayaçlar yeniden başladı; henüz kapanmış bahis yok. Bu bir "
                "arıza değil, dönemin kendisidir — <b>veri yokluğu ile temiz "
                "sayfa farklı şeylerdir</b>. Önceki dönemin karnesi arşivde: "
                "İnceleme ve Ölçüm Defteri onu hâlâ görüyor.</div>")
        # ⚠️⚠️ YER TUTUCU ASLA KENDİ SATIRINDA DURMAZ ⚠️⚠️
        # Bir f-string yer tutucusu ("{_kontrol}" gibi) tek başına bir
        # satırda dururken BOŞ dönerse o satır TAMAMEN BOŞALIR. Markdown
        # boş satırı HTML bloğunun SONU sayar; ardından gelen girintili
        # "<table ...>" satırı 4+ boşlukla başladığı için KOD BLOĞU
        # sanılır ve KAÇIŞLANIR. Canlıda sonuç: 98 ham HTML etiketi
        # sayfada metin olarak göründü (kullanıcı bildirdi).
        # Kural: her yer tutucu, kendisinden sonraki etiketle AYNI
        # SATIRDA olmalı — "{_kontrol}<div ...>" gibi. Böylece ifade boş
        # dönse bile satır boşalmaz.
        st.markdown(f"""
        <div class="v2card">
          <div class="v2head"><h2>Ajan Güveni</h2>
            <div class="hint">fiyata göre üstünlük</div></div>
          <div class="v2body">
            {_kontrol}<div class="v2mb"><b>İsabet oranı yanıltır.</b> %75 isabet, oran
              1,24'te <b>kötüdür</b> — fiyat zaten %80,6 bekliyordu. %59 isabet,
              oran 1,84'te <b>iyidir</b>. Doğru ölçü isabet değil,
              <b>fiyatın beklediğinden ne kadar fazlası</b>.
              {(" " + swap) if swap else ""}</div>
            {_bos_era}<table class="v2"><thead><tr><th></th><th>Ajan</th>
              <th class="r opt dar">İsabet</th>
              <th class="r opt dar">Fiyat bekler</th>
              <th class="r">Fark</th><th class="r">Hüküm</th></tr></thead>
              <tbody>{''.join(body)}</tbody></table>
          </div></div>""", unsafe_allow_html=True)

    # ── ORTA: tahta ───────────────────────────────────────────
    # Başlamış maç tahtada SEÇİLEMEZ — kupona eklenemez ve "bugün ne var"
    # sorusunun cevabı değildir. Ama gizlenmez de: sonucu bekleyen pozisyon
    # olarak ayrıca söylenir (kapanış otomatik, 90 dk'da bir).
    _tum = load_board()
    board = [b for b in _tum if not b.get("gecti")]
    _bekleyen = [b for b in _tum if b.get("gecti")]
    if "v2_sel" not in st.session_state:
        st.session_state["v2_sel"] = []
    with mid:
        # ⚠️ Eskiden tek sayı vardı ("kodlanmamış") ve yanında SABİT bir
        # "%79" yazıyordu — veritabanı değişse de değişmeyen bir sayı.
        # Şimdi iki farklı durum ayrılıyor: lig ADI biliniyor ama kanonik
        # kodu yok (bilgi VAR, sadece kodlanmadı) ve hiçbir şey bilinmiyor.
        # Fetcher artık iddaa'nın söylediği adı saklıyor; bu ayrım o
        # düzeltmenin kullanıcıya ulaştığı yer.
        kodsuz = [b for b in board if b["lg"] == "ALL"]
        adli = [b for b in kodsuz if b.get("iddaa_lig")]
        korlar = len(kodsuz) - len(adli)
        if korlar:
            _uyari = (f"<div class='dq'><b>{korlar}/{len(board)}</b> maçın "
                      f"ligi bilinmiyor — ülke rozeti yerine <b>—</b> "
                      f"gösteriliyor; <b>uydurulmuyor</b>."
                      + (f" Ayrıca <b>{len(adli)}</b> maçın lig <b>adı</b> "
                         f"biliniyor ama kanonik kodu yok; ad gösteriliyor."
                         if adli else "") + "</div>")
        elif adli:
            _uyari = (f"<div class='v2mb'><b>{len(adli)}/{len(board)}</b> "
                      f"maçın ligi kanonik kodda değil ama <b>adı biliniyor</b> "
                      f"— iddaa'nın söylediği ad gösteriliyor.</div>")
        else:
            _uyari = ""
        if _bekleyen:
            from html import escape as _esc
            _uyari += (
                "<div class='v2mb'><b>" + str(len(_bekleyen)) + "</b> maç "
                "başladı ya da bitti — <b>sonucu işleniyor</b>, seçilemez. "
                "Kapanış otomatik (90 dk'da bir): " +
                " · ".join(_esc(str(b["h"])[:16]) + "–" +
                           _esc(str(b["a"])[:16]) + " (" + b["ko"] + ")"
                           for b in _bekleyen[:6]) +
                (" …" if len(_bekleyen) > 6 else "") + "</div>")
        st.markdown(f"""
        <div class="v2card"><div class="v2head"><h2>Bugünün Tahtası</h2>
          <div class="hint">işaretle → kupona ekle</div></div>
          <div class="v2body" style="padding-bottom:2px;">{_uyari}</div>
          </div>""", unsafe_allow_html=True)
        sel = []
        for b in board[:22]:
            c1, c2 = st.columns([4.3, 1.35], gap="small")
            with c1:
                _lg = (b["iddaa_lig"] or "") if b["lg"] == "ALL" else ""
                _sh = _sira_h.get(b["pid"])
                _rank = (f" {_sh['sira']}/{_sh['toplam']}" if _sh else "")
                _isb = ("  ·  " + _isabet(_ag_h.get(b["pid"]))
                        if b["pid"] in _ag_h else "")
                lbl = (f"{b['h']} — {b['a']}  ·  {b['ad']}{_rank}{_isb}"
                       f"  ·  {b['mk']} {b['pk']}  ·  {b['ko']}"
                       + (f"  ·  {_lg}" if _lg else ""))
                _sepette = any(x["id"] == b["id"] for x in _sepet())
                on = st.checkbox(lbl + ("   ✓ sepette" if _sepette else ""),
                                 key=f"v2_{b['id']}")
            with c2:
                st.markdown(
                    f"<div style='text-align:right;font-family:\"JetBrains Mono\",monospace;"
                    f"font-size:var(--t-okuma);color:var(--ink);padding-top:3px;"
                    f"white-space:nowrap;'>"
                    f"<span class='cc{' no' if b['lg']=='ALL' else ''}'>{b['code']}</span>"
                    f"{_num(b['o'])}</div>", unsafe_allow_html=True)
                if _sh:
                    _g = {"İYİ": "g1", "KÖTÜ": "g3"}.get(_sh["hukum"], "g2")
                    st.markdown(
                        "<div style='text-align:right;margin:-6px 0 2px;'>"
                        "<span class='gr " + _g + "'>" + _sh["hukum"] +
                        "</span></div>", unsafe_allow_html=True)
            if on:
                sel.append(b)

    # ── SAĞ: sepete gönder ─────────────────────────────────────
    with right:
        sp = _sepet()
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Seçtiklerin</h2>"
            "<div class='hint'>sepete gönder</div></div><div class='v2body'>",
            unsafe_allow_html=True)
        if sel:
            O = 1.0
            for b in sel:
                O *= b["o"]
            st.markdown(
                "<div class='ro'><span>İşaretli</span><b>" + str(len(sel)) +
                "</b></div><div class='ro'><span>Toplam oran</span><b>" +
                _num(O) + "</b></div>", unsafe_allow_html=True)
            if st.button("Sepete ekle  (" + str(len(sel)) + ")",
                         type="primary", use_container_width=True,
                         key="v2_sepete"):
                # ⚠️ Onay kutusu durumuna DOKUNMA: Streamlit, bir widget'ın
                # session_state'ini AYNI çalıştırmada değiştirmeyi yasaklar ve
                # istisna firlatir — ilk denemede iki secimden biri eklendi ve
                # sayfa hic gecmedi. Sepet zaten kimlige gore tekillestiriyor,
                # kutular isaretli kalsa da zarar yok.
                for b in sel:
                    sepete_ekle(b)
                _git("Sepet")
        else:
            st.markdown(
                "<div class='v2bos'>Tahtadan seçim işaretle.<br>"
                "Seçtiklerin sepete gider, orada tartılır.</div>",
                unsafe_allow_html=True)
        if sp:
            st.markdown(
                "<div class='dq' style='margin-top:var(--s3);'>Sepette "
                "<b>" + str(len(sp)) + " ayak</b> bekliyor. Tartmak ve "
                "oynamak için <b>Sepet</b> sayfasına geç.</div>",
                unsafe_allow_html=True)
        st.markdown("</div></div>", unsafe_allow_html=True)

    poz = load_pozisyon()
    if poz:
        sat = []
        for k in poz[:14]:
            # ⏳ = maçı başladı/bitti, sonucu işleniyor. DÜZ METİN işaret:
            # bu dize aşağıda [:92] ile kesiliyor; içine HTML koymak etiketi
            # yarıdan bölüp sayfaya ham HTML sızdırırdı.
            ayaklar = " + ".join(
                ("⏳" if x.get("basladi") else "") +
                str(x["h"])[:12] + " " + str(x["pk"])[:10] for x in k["ayak"])
            sat.append(
                "<tr><td><span class='ag'>" + _rozet(k["p"]) + k["ad"] +
                "</span><span class='sb'>" + _isabet(_ag_h.get(k["p"])) +
                " · " + ayaklar[:92] + "</span></td>"
                "<td class='r n opt'>" + str(k["n"]) + "</td>"
                "<td class='r n'>" + _num(k["co"]) + "</td>"
                "<td class='r n opt'>" + "{:.0f}".format(k["sk"]) + " ₺</td>"
                "<td class='r n'>" + "{:,.0f}".format(k["pr"]).replace(",", ".") +
                " ₺</td><td class='r n opt'>" + k["ko"] + "</td></tr>")
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Açık Kuponlar</h2>"
            "<div class='hint'>" + str(len(poz)) + " kupon · kupon düzeyi"
            "</div></div><div class='v2body'>"
            "<div class='v2mb'>Tahta tek tek <b>seçimleri</b> gösterir; "
            "burası <b>kuponu</b>: kaç ayak, toplam oran, tutarsa ne döner. "
            "İkisi farklı sorulara cevap verir. <b>⏳</b> o ayağın maçı "
            "oynandı, sonucu işleniyor demektir.</div>"
            "<table class='v2'><thead><tr><th>Ajan ve ayaklar</th>"
            "<th class='r opt'>Ayak</th><th class='r'>Oran</th>"
            "<th class='r opt'>Yatan</th><th class='r'>Döner</th>"
            "<th class='r opt'>Başlangıç</th></tr></thead><tbody>" +
            "".join(sat) + "</tbody></table></div></div>",
            unsafe_allow_html=True)

    st.markdown(
        "<div class='v2dip'>"
        "Marj katsayıları ölçüldü (31.08.2026): 1X2 %17,6 · A/Ü %17,4 · "
        "KG %16,4 · kombo %19,5–20,4 · Kâğıt ticaret, kişisel araştırma"
        "</div>", unsafe_allow_html=True)


def page_opus() -> None:
    """🧑‍💻 OPUS 5 — gerçekte oynananların defteri."""
    o = load_opus()
    h = load_havuz()
    _k = []
    if o.get("var"):
        _f = o["edge"] - h["edge"] if h.get("n") else 0.0
        _k = [{"ad": "Kupon", "deger": str(o["kupon"])},
              {"ad": "Havuzdan fark", "deger": _sgn(_f),
               "cls": ("ps" if _f >= 0 else "ng")}]
    _sayfa_basligi(
        "OPUS 5 Defteri",
        "Gerçekte oynananlar. Kâğıt ile saha arasındaki fark ancak "
        "burada ölçülebilir.", _k)
    left, right = st.columns([1.15, 1.0], gap="small")

    with left:
        if not o.get("var"):
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>OPUS 5 Defteri</h2>"
                "<div class='hint'>gerçekte oynananlar</div></div>"
                "<div class='v2body'><div class='dq'>Defter boş. Sağdan gerçekte "
                "oynadığın kuponu kaydet — kâğıt ile saha arasındaki fark ancak "
                "böyle ölçülebilir.</div></div></div>", unsafe_allow_html=True)
        else:
            fark = o["edge"] - h["edge"] if h.get("n") else 0.0
            # ⚠️ KANIT EŞİĞİ — burası eskiden eşiksizdi. n=19 ayakta
            # "saha kâğıdı geçiyor, bunu bulmak yol haritasının dört
            # fazından da değerli" yazıyordu; aynı anda Karar Masası n=17'lik
            # EUVOX'a doğru şekilde ÖLÇÜLEMEZ diyordu. Aynı üründe iki ayrı
            # standart. Yetersiz örneklemde hüküm YOK — sayılar gösterilir,
            # yorum gösterilmez.
            _on = int(o.get("n") or 0)
            if not _olculebilir(_on):
                yorum = _esik_notu(_on) + (
                    " Defter büyüdükçe bu satır kendiliğinden hükme döner — "
                    "aşağıdaki sayılar doğru, <b>yorumu erken</b>.")
            elif fark > 0.02:
                yorum = ("<b>Saha kâğıdı geçiyor.</b> Aradaki farkı yaratan şey "
                         "modelin göremediği bir bilgidir — onu bulmak yol "
                         "haritasının dört fazından da değerli.")
            elif abs(fark) <= 0.02:
                yorum = ("<b>Saha ile kâğıt aynı yerde.</b> Gerçek oyun, "
                         "ajanların ölçülen performansından ayrışmıyor.")
            else:
                yorum = ("<b>Kâğıt sahayı geçiyor.</b> Manuel seçim, ajanların "
                         "ham çıktısından daha kötü sonuç veriyor.")
            hn = "{:,}".format(h.get("n", 0)).replace(",", ".")
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>OPUS 5 Defteri</h2>"
                "<div class='hint'>gerçekte oynananlar</div></div>"
                "<div class='v2body'>"
                "<table class='v2'><thead><tr><th></th>"
                "<th class='r opt'>Ayak</th><th class='r opt'>İsabet</th>"
                "<th class='r opt'>Fiyat bekler</th><th class='r'>Fark</th>"
                "</tr></thead><tbody>"
                "<tr" + (" class='adv'" if o["edge"] > h.get("edge", 0) else "") +
                "><td><span class='ag'>OPUS 5 · sen</span>"
                "<span class='sb'>" + str(o["kupon"]) + " kupon · " +
                str(o["acik"]) + " açık</span></td>"
                "<td class='r n'>" + str(o["ayak"]) + "</td>"
                "<td class='r n'>" + _pct(o["hit"]) + "</td>"
                "<td class='r n'>" + _pct(o["exp"]) + "</td>"
                "<td class='r'><span class='" +
                ("dp" if o["edge"] >= 0 else "dm") + "'>" + _sgn(o["edge"]) +
                "</span></td></tr>"
                "<tr><td><span class='ag'>Kâğıt ajanlar · havuz</span>"
                "<span class='sb'>kıyas tabanı</span></td>"
                "<td class='r n'>" + hn + "</td>"
                "<td class='r n'>" + _pct(h.get("hit", 0)) + "</td>"
                "<td class='r n'>" + _pct(h.get("exp", 0)) + "</td>"
                "<td class='r'><span class='" +
                ("dp" if h.get("edge", 0) >= 0 else "dm") + "'>" +
                _sgn(h.get("edge", 0)) + "</span></td></tr>"
                "</tbody></table>"
                "<div class='v2mb' style='margin-top:12px;'>" + yorum +
                " Sahanın üstünlüğü havuzdan <b>" + _sgn(fark) +
                "</b> farklı.</div></div></div>", unsafe_allow_html=True)

            if o["n_kars"] >= 3:
                k, t, d = o["kombo"], o["tek"], o["fark"]
                if d > 0:
                    hkm = "Kombine <b>daha iyi</b> — ama örneklem küçük."
                else:
                    hkm = ("Kombine <b>daha kötü</b>. Marj analizi bunu "
                           "öngörüyordu: her ayak kendi marjını taşır ve "
                           "marjlar çarpılır.")
                st.markdown(
                    "<div class='v2card'><div class='v2head'>"
                    "<h2>Kombine mi, Tek Tek mi</h2>"
                    "<div class='hint'>karşı-olgusal · " + str(o["n_kars"]) +
                    " kupon</div></div><div class='v2body'>"
                    "<div class='ro'><span>Kombine oynandı</span><b class='" +
                    ("ps" if k >= 0 else "ng") + "'>" +
                    ("+" if k >= 0 else "−") + _num(abs(k) * 100, 1) + "%</b></div>"
                    "<div class='ro'><span>Aynı ayaklar tek tek</span><b class='" +
                    ("ps" if t >= 0 else "ng") + "'>" +
                    ("+" if t >= 0 else "−") + _num(abs(t) * 100, 1) + "%</b></div>"
                    "<div class='ro big'><span>Kombinenin katkısı</span><b class='" +
                    ("ps" if d >= 0 else "ng") + "'>" +
                    ("+" if d >= 0 else "−") + _num(abs(d) * 100, 1) + "p</b></div>"
                    "<div class='vd' style='margin-top:10px;'>" + hkm +
                    " Bu, kombine alışkanlığının <b>kendi verinle</b> ölçülmüş "
                    "fiyatıdır — varsayımla değil.</div></div></div>",
                    unsafe_allow_html=True)
            else:
                st.markdown(
                    "<div class='v2card'><div class='v2head'>"
                    "<h2>Kombine mi, Tek Tek mi</h2>"
                    "<div class='hint'>bekliyor</div></div><div class='v2body'>"
                    "<div class='dq'>Karşı-olgusal için en az 3 sonuçlanmış "
                    "kupon gerekiyor — şu an " + str(o["n_kars"]) +
                    ". Kaydettikçe ölçülecek.</div></div></div>",
                    unsafe_allow_html=True)

    with right:
        board = load_board()
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Gerçekte Ne Oynadın</h2>"
            "<div class='hint'>işaretle → kaydet</div></div>"
            "<div class='v2body' style='padding-bottom:4px;'>"
            "<div class='v2mb'>iddaa arşivi siliyor. Buraya girdiğin her kupon "
            "kalıcı olur ve <b>kâğıt ile saha arasındaki farkı</b> ölçmeyi "
            "mümkün kılar.</div></div></div>", unsafe_allow_html=True)
        secili = []
        for b in board[:18]:
            lbl = b["h"] + " — " + b["a"] + "  ·  " + str(b["pk"]) + \
                  "  ·  " + _num(b["o"])
            if st.checkbox(lbl, key="op_" + b["id"]):
                secili.append(b)
        stake = st.number_input("Bahis (₺)", min_value=5.0, max_value=5000.0,
                                value=50.0, step=5.0, key="op_stake")
        if secili:
            O = 1.0
            for b in secili:
                O *= b["o"]
            doner = "{:,.0f}".format(stake * O).replace(",", ".")
            st.markdown(
                "<div class='vd' style='margin:8px 0;'><b>" + str(len(secili)) +
                " ayak · toplam oran " + _num(O) + "</b> · " +
                "{:.0f}".format(stake) + " ₺ yatırırsan tutarsa " + doner +
                " ₺ döner.</div>", unsafe_allow_html=True)
        if st.button("✓ Gerçekte oynadım — kaydet", type="primary",
                     use_container_width=True, disabled=not secili):
            try:
                import manual_book as mb
                res = mb.play_custom([b["id"] for b in secili],
                                     stake=float(stake))
            except Exception as e:
                res = {"ok": False, "msg": "Hata: %s: %s" % (type(e).__name__, e)}
            if res.get("ok"):
                st.success(res["msg"])
                for b in secili:
                    st.session_state["op_" + b["id"]] = False
                load_opus.clear()
                st.rerun()
            else:
                st.error(res.get("msg", "kaydedilemedi"))


def _ajan_paneli(pid: str, lig: dict, sayfa: bool = False) -> None:
    """Ajan dosyası. 19.09'dan beri kendi sayfası var (Ajan Dosyası, sol
    panelde TAKIMLAR altında); sayfa=True o kip — Kapat düğmesi yok, büyük
    işlem bandı var. Takım tablosundaki bant özetin, bu sayfa ayrıntının
    yeri."""
    tum = lig["mavi"] + lig["kirmizi"] + lig.get("turuncu", [])
    a = next((x for x in tum if x["pid"] == pid), None)
    if not a:
        return
    d = load_ajan_detay(pid)
    eg = load_ajan_egri().get(pid, {})
    ust, kapat = st.columns([6, 1], gap="small")
    with ust:
        st.markdown(
            "<div class='v2ajan-bas'>"
            "<span class='ad'>" + _rozet(pid) + a["ad"] + "</span>"
            "<span class='alt'>dönem " +
            str(a["era"] or "—") + " · " + _isabet(a) + " · kasa " +
            "{:,.0f}".format(a["kasa"]).replace(",", ".") + " ₺</span></div>",
            unsafe_allow_html=True)
    if not sayfa:
        with kapat:
            if st.button("Kapat", key="v2_ajan_kapat", use_container_width=True):
                st.session_state["v2_ajan"] = None
                st.rerun()
    else:
        _is = load_islem_bandi().get(pid) or []
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>İşlem Bandı</h2>"
            "<div class='hint'>kronolojik · son " + str(min(len(_is), 120)) +
            " işlem</div></div><div class='v2body'>" +
            ("<div class='bant-buyuk'>" + _islem_bandi(_is, son=120, h=72, adim=14) +
             "</div><div class='bant-not'>" + _bant_ozet(_is, son=120) +
             " · çubuğun üzerine gel: maç, seçim, oran, kâr/zarar</div>"
             if _is else "<div class='dq'>Dönem içi işlem yok.</div>") +
            "</div></div>", unsafe_allow_html=True)

    sol, sag = st.columns([1.0, 1.0], gap="small")
    with sol:
        ic = ""
        if d["teshis"]:
            t = str(d["teshis"]["status"] or "")
            g = ("g3" if "TIKANIKLIK" in t else
                 "g1" if "🟢" in t else "g2")
            temiz = t
            for e in ("🔴 ", "🟠 ", "🟢 ", "⚪ ", "😴 ", "🧊 ", "⏸ ", "🔒 ",
                      "🏁 ", "🛑 ", "🚫 "):
                temiz = temiz.replace(e, "")
            ic += ("<div class='dq' style='margin-bottom:var(--s3);'>"
                   "<span class='gr " + g + "'>" + temiz + "</span> " +
                   str(d["teshis"]["detail"] or "")[:120] + "</div>")
        if eg.get("seri"):
            ic += _svg_egri({"nokta": [{"k": v} for v in eg["seri"]],
                             "son": eg["son"]}, 460, 120)
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Seyir ve Durum</h2>"
            "<div class='hint'>dönem içi</div></div><div class='v2body'>" +
            (ic or "<div class='dq'>Dönem içi veri yok.</div>") +
            "</div></div>", unsafe_allow_html=True)

    with sag:
        if d["acik"]:
            sat = "".join(
                "<tr><td><span class='ag'>" + str(x["h"])[:16] + " — " +
                str(x["a"])[:16] + "</span><span class='sb'>" +
                str(x["mk"]) + " · " + str(x["pk"]) + "</span></td>"
                "<td class='r n'>" + _num(float(x["o"] or 0)) + "</td>"
                "<td class='r n opt'>" + _tr_saat(x["ko"]) +
                "</td></tr>" for x in d["acik"])
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>Açık Pozisyon</h2>"
                "<div class='hint'>" + str(len(d["acik"])) + " bahis</div></div>"
                "<div class='v2body'><table class='v2'><thead><tr><th>Maç</th>"
                "<th class='r'>Oran</th><th class='r opt'>Başlangıç</th>"
                "</tr></thead><tbody>" + sat + "</tbody></table></div></div>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>Açık Pozisyon</h2>"
                "<div class='hint'>yok</div></div><div class='v2body'>"
                "<div class='dq'>Şu an açık bahis yok.</div></div></div>",
                unsafe_allow_html=True)

    # ── GEREKÇE VE SONUÇ — tam genişlik, tablo değil LİSTE.
    # Kullanıcı (19.09): "gerekçe ve sonuç daha net görünsün, sağa çek sola
    # çek tablo gibi oluyor". Eski hâl yarım genişlikte iki sütunlu tabloydu;
    # alt satırlar sarılmıyordu (.sb nowrap), gerekçe 88, sonuç 52 karakterde
    # KESİLİYORDU ve kart yatay kaydırmaya düşüyordu. Şimdi her bahis bir
    # blok: üstte sonuç rozeti · maç · seçim @ oran · skor · tarih; altında
    # gerekçe ve sonuç TAM metin, sarılarak, bir punto küçük.
    import html as _h
    if d["bet"]:
        blok = []
        for x in d["bet"]:
            kaz = x["s"] == "won"
            skor = str(x.get("res") or "").strip()
            blok.append(
                "<div class='gs'><div class='gs-ust'>"
                "<span class='gs-sonuc " + ("won" if kaz else "lost") + "'>" +
                ("KAZANDI" if kaz else "KAYBETTİ") + "</span>"
                "<b>" + _h.escape(str(x["h"])) + " — " + _h.escape(str(x["a"])) +
                "</b><span class='gs-sec'>" + _h.escape(str(x["mk"])) + " · " +
                _h.escape(str(x["pk"])) + " @ " + _num(float(x["o"] or 0)) +
                "</span>" +
                ("<span class='gs-sec'>skor " + _h.escape(skor) + "</span>"
                 if skor else "") +
                "<span class='gs-tarih'>" + _tr_saat(x.get("ko") or x.get("sat")) +
                (" · " + _h.escape(str(x["lg"])) if x.get("lg") else "") +
                "</span></div>"
                "<div class='gs-sat'><span class='gs-et'>Gerekçe</span>" +
                _h.escape(str(x["rsn"] or "—")) + "</div>" +
                ("<div class='gs-sat'><span class='gs-et'>Sonuç</span>" +
                 _h.escape(str(x["pm"])) + "</div>" if x.get("pm") else "") +
                "</div>")
        st.markdown(
            "<div class='v2card'><div class='v2head'>"
            "<h2>Gerekçe ve Sonuç</h2><div class='hint'>son " +
            str(len(d["bet"])) + " bahis · yeniden eskiye</div></div>"
            "<div class='v2body'><div class='gs-list'>" + "".join(blok) +
            "</div></div></div>", unsafe_allow_html=True)
    else:
        st.markdown(
            "<div class='v2card'><div class='v2head'>"
            "<h2>Gerekçe ve Sonuç</h2><div class='hint'>boş</div></div>"
            "<div class='v2body'><div class='dq'>Dönem içi kapanmış "
            "bahis yok.</div></div></div>", unsafe_allow_html=True)


def _gezinme_alt() -> None:
    """Önceki / sonraki sayfa — okuma sırasını takip eden gezinme.

    Sol panel 'nereye gidebilirim'i söyler; alttaki bu çift 'sırada ne
    var'ı. İkisi farklı sorulardır ve panelde ikisi de gerekir."""
    ad = list(PAGES)
    i = ad.index(st.session_state["v2_page"])
    onc = ad[i - 1] if i > 0 else None
    son = ad[i + 1] if i < len(ad) - 1 else None
    st.markdown("<div class='v2gez'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.4, 2.2, 1.4], gap="small")
    with c1:
        if onc and st.button("Önceki:  " + onc, key="v2_onc",
                             use_container_width=True):
            _git(onc)
    with c2:
        # Zincirde konum + SIRADAKİ SORU. "Sonraki: Sepet" bir menü
        # öğesidir; "Ne kuruyorum, kaça mal oluyor?" bir devir teslimdir.
        _sn = SORU.get(son, {}).get("soru", "") if son else ""
        st.markdown(
            "<div class='v2gez-orta'>" + str(i + 1) + " / " + str(len(ad)) +
            " · " + st.session_state["v2_page"] +
            ("<span class='sonraki-soru'>sırada: " + _sn + "</span>"
             if _sn else "") + "</div>",
            unsafe_allow_html=True)
    with c3:
        if son and st.button("Sonraki:  " + son, key="v2_son",
                             use_container_width=True):
            _git(son)


def _takim_tablo(rows, baslik, alt, renk, EG=None, BANT=None):
    EG = EG or {}
    BANT = BANT or {}
    if not rows:
        return ("<div class='v2card'><div class='v2head'><h2>" + baslik +
                "</h2><div class='hint'>" + alt + "</div></div>"
                "<div class='v2body'><div class='dq'>Bu takımda dönem içi "
                "kapanmış bahis yok.</div></div></div>")
    body = []
    for i, a in enumerate(rows, 1):
        g, txt = _hukum(a)      # Karar Masası ile AYNI kural (kanıt eşiği dahil)
        # ⚠️ n=1'lik bir farki yesil cip ile one cikarmak, gurultuyu
        # avantaj gibi sunmaktir. KAVSAK n=1 ile +36,8p gosteriyordu.
        # Vurgu icin hem anlamli fark hem asgari orneklem sart.
        yeter = a["n"] >= 10
        adv = " class='adv'" if (a["edge"] >= 0.005 and yeter) else ""
        uyari = ""
        if a["benched"]:
            uyari = " <span class='gr g3'>KADRO DIŞI</span>"
        elif a["ihtar"]:
            uyari = " <span class='gr g2'>" + str(a["ihtar"]) + " İHTAR</span>"
        kasa_cls = "dp" if a["yuzde"] >= 100 else "dm"
        _is = BANT.get(a["pid"]) or []
        if _is:
            adv = adv.replace("class='", "class='ust ") if adv else " class='ust'"
        body.append(
            "<tr" + adv + "><td class='rk'>" + str(i) + "</td>"
            "<td><span class='ag'>" + _rozet(a["pid"]) + a["ad"] + "</span>" + uyari +
            # İsabet alt satırda — "İsabet" sütunu telefonda gizleniyor.
            "<span class='sb'>" +
            (_isabet(a) + " · oran " + _num(a["odds"]) if a["n"] else "oynamadı") +
            "</span></td>"
            "<td class='opt' style='width:100px;'>" +
            _kivilcim(EG.get(a["pid"], {}).get("seri", [])) + "</td>"
            "<td class='r'>" + (
                ("<span class='ak'>" + str(a["acik_kupon"]) + "</span>"
                 "<span class='sb' style='text-align:right;'>" +
                 str(a["acik_ayak"]) + " ayak · " +
                 "{:,.0f}".format(a["riskte"]).replace(",", ".") + " ₺</span>")
                if a["acik_kupon"] else
                "<span class='sb' style='text-align:right;'>—</span>") + "</td>"
            "<td class='r n'>" + ("{:,.0f}".format(a["kasa"]).replace(",", ".")) + "</td>"
            "<td class='r opt'><span class='" + kasa_cls + "'>" +
            "{:.0f}".format(a["yuzde"]) + "%</span></td>"
            "<td class='r n opt'>" + (_pct(a["hit"]) if a["n"] else "—") + "</td>"
            "<td class='r n opt'>" + (_pct(a["exp"]) if a["n"] else "—") + "</td>"
            "<td class='r'>" + (
                "<span class='" + ("dp" if (a["edge"] >= 0.005 and yeter)
                                   else "dm") + "'>" +
                _sgn(a["edge"]) + "</span>" if a["n"] else "—") + "</td>"
            "<td class='r'><span class='gr " + g + "'>" + txt + "</span></td></tr>")
        # İŞLEM BANDI — ajanın hemen altında, borsa işlem şeridi gibi
        if _is:
            body.append(
                "<tr class='bant-satir'><td></td><td colspan='9'>"
                "<div class='bant-kap'>" + _islem_bandi(_is) +
                "<span class='bant-not'>" + _bant_ozet(_is) + "</span>"
                "</div></td></tr>")
    return ("<div class='v2card' style='border-top:3px solid " + renk + ";'>"
            "<div class='v2head'><h2>" + baslik + "</h2>"
            "<div class='hint'>" + alt + "</div></div><div class='v2body'>"
            "<table class='v2'><thead><tr><th></th><th>Ajan</th>"
            "<th class='opt'>Seyir</th><th class='r'>Açık</th>"
            "<th class='r'>Kasa</th><th class='r opt'>%</th>"
            "<th class='r opt'>İsabet</th>"
            "<th class='r opt'>Fiyat bekler</th><th class='r'>Fark</th>"
            "<th class='r'>Hüküm</th></tr></thead><tbody>" +
            "".join(body) + "</tbody></table></div></div>")


def _sepet() -> list:
    if "v2_sepet" not in st.session_state:
        st.session_state["v2_sepet"] = []
    return st.session_state["v2_sepet"]


def sepete_ekle(b: dict) -> None:
    sp = _sepet()
    if not any(x["id"] == b["id"] for x in sp):
        sp.append(b)


def page_sepet() -> None:
    """Sepet — seçtiklerini topla, tart, sonra oyna.

    Ayrı sayfa olmasının sebebi: seçmek ile OYNAMAK farklı kararlardır.
    Tahtada gezerken 'bunu beğendim' demek ucuzdur; kuponu kurup parayı
    yatırmak değildir. Sepet ikisinin arasına bir eşik koyar."""
    sp = _sepet()
    _ag_s = {a["pid"]: a for a in load_agents()}     # ajan isabeti
    O, p = 1.0, 1.0
    for b in sp:
        O *= b["o"]
        p *= (1.0 / b["o"]) / b["m"]
    ev = (p * O - 1.0) if sp else 0.0
    _sayfa_basligi(
        "Sepet",
        "Seçmek ile oynamak farklı kararlardır. Sepet ikisinin arasına "
        "bir eşik koyar: burada tartılır, sonra kaydedilir.",
        [{"ad": "Ayak", "deger": str(len(sp))},
         {"ad": "Toplam oran", "deger": (_num(O) if sp else "—")},
         {"ad": "Beklenen getiri",
          "deger": (("+" if ev >= 0 else "−") + _num(abs(ev) * 100, 1) + "%"
                    if sp else "—"),
          "cls": ("ps" if ev >= 0 else "ng")}])

    sol, sag = st.columns([1.35, 1.0], gap="medium")
    with sol:
        st.markdown("<div class='v2card'><div class='v2head'>"
                    "<h2>Sepetteki Seçimler</h2><div class='hint'>"
                    "çıkarmak için sil</div></div><div class='v2body'>",
                    unsafe_allow_html=True)
        if not sp:
            st.markdown(
                "<div class='v2bos'>Sepet boş.<br>Karar Masası'ndaki "
                "tahtadan seçim ekle.</div>", unsafe_allow_html=True)
        else:
            for b in list(sp):
                c1, c2 = st.columns([5, 1], gap="small")
                with c1:
                    st.markdown(
                        "<div class='v2sepet-satir'><div>"
                        "<div class='ad'>" + str(b["h"]) + " — " +
                        str(b["a"]) + "</div><div class='alt'>" +
                        str(b["ad"]) + " (" + _isabet(_ag_s.get(b.get("pid"))) +
                        ") · " + str(b["mk"]) + " · " + str(b["pk"]) +
                        (" · <b style='color:var(--ng,#b3261e);'>maç "
                         "başladı — çıkar</b>"
                         if _basladi_mi(b.get("ko_ham")) else "") +
                        "</div></div>"
                        "<div style='font-family:\"JetBrains Mono\",monospace;"
                        "font-size:var(--t-okuma);font-weight:500;'>" + _num(b["o"]) +
                        "</div></div>", unsafe_allow_html=True)
                with c2:
                    if st.button("Sil", key="v2_sil_" + b["id"],
                                 use_container_width=True):
                        st.session_state["v2_sepet"] = [
                            x for x in sp if x["id"] != b["id"]]
                        st.rerun()
        st.markdown("</div></div>", unsafe_allow_html=True)

    with sag:
        if sp:
            ayni = len({(b["h"], b["a"]) for b in sp}) < len(sp)
            not_ = ("<b>" + str(len(sp)) + " ayak · " + _pct(p) +
                    " tutma şansı.</b> Hiçbir şeyde yanılmadan önce <b>" +
                    _num(abs(ev) * 100, 1) + "%</b> geride başlıyorsun — "
                    "ayakların marjlarının çarpımı.")
            if ayni:
                not_ += (" <b>Uyarı:</b> aynı maçtan birden fazla ayak var; "
                         "bağımsız değiller, gerçek olasılık farklı.")
            if len(sp) >= 3:
                not_ += (" Üç ayakta maliyet, ölçülen en pahalı bölgeyi "
                         "(−%22) geçiyor.")
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>Tartı</h2>"
                "<div class='hint'>marj canlı</div></div><div class='v2body'>"
                "<div class='ro'><span>Toplam oran</span><b>" + _num(O) +
                "</b></div>"
                "<div class='ro'><span>Gerçek olasılık</span><b>" + _pct(p) +
                "</b></div>"
                "<div class='ro big'><span>Beklenen getiri</span><b class='" +
                ("ps" if ev >= 0 else "ng") + "'>" +
                ("+" if ev >= 0 else "−") + _num(abs(ev) * 100, 1) +
                "%</b></div>"
                "<div class='vd' style='margin-top:var(--s3);'>" + not_ +
                "</div></div></div>", unsafe_allow_html=True)
            st.markdown("<div class='v2card'><div class='v2head'>"
                        "<h2>Gerçekte Oyna</h2><div class='hint'>"
                        "OPUS 5 defterine yazılır</div></div>"
                        "<div class='v2body'>", unsafe_allow_html=True)
            stake = st.number_input("Bahis (₺)", min_value=5.0,
                                    max_value=5000.0, value=50.0, step=5.0,
                                    key="v2_sepet_stake")
            st.markdown(
                "<div class='dq' style='margin:var(--s2) 0;'>Tutarsa <b>" +
                "{:,.0f}".format(stake * O).replace(",", ".") +
                " ₺</b> döner. Bu kayıt kâğıt ile saha arasındaki farkı "
                "ölçmeyi mümkün kılar — iddaa arşivi siliyor.</div>",
                unsafe_allow_html=True)
            # Başlamış maç GERÇEK deftere yazılamaz: kaydedilecek oran maç
            # öncesinin oranı, saha artık o oranı vermiyor. Kâğıt ile saha
            # arasındaki farkı ölçen defter yanlış oranla kirlenirdi.
            _baslamis = [b for b in sp if _basladi_mi(b.get("ko_ham"))]
            if _baslamis:
                st.markdown(
                    "<div class='dq' style='margin:0 0 var(--s2);'><b>" +
                    str(len(_baslamis)) + " seçimin maçı başladı.</b> "
                    "Maç öncesi oranla deftere yazılamaz — soldan sil, "
                    "sonra oyna.</div>", unsafe_allow_html=True)
            if st.button("Oyna ve deftere yaz", type="primary",
                         use_container_width=True, key="v2_oyna",
                         disabled=bool(_baslamis)):
                try:
                    import manual_book as mb
                    r = mb.play_custom([b["id"] for b in sp],
                                       stake=float(stake))
                except Exception as e:
                    r = {"ok": False,
                         "msg": "Hata: %s: %s" % (type(e).__name__, e)}
                if r.get("ok"):
                    st.success(r["msg"])
                    st.session_state["v2_sepet"] = []
                    load_opus.clear()
                    st.rerun()
                else:
                    st.error(r.get("msg", "kaydedilemedi"))
            st.markdown("</div></div>", unsafe_allow_html=True)
        else:
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>Tartı</h2>"
                "<div class='hint'>bekliyor</div></div><div class='v2body'>"
                "<div class='v2bos'>Sepete seçim ekleyince<br>"
                "marj ve beklenen getiri burada hesaplanır.</div>"
                "</div></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# TAKIMLAR · PORTFÖY · ANALİZ — tek "Ajan Ligi" sayfası bölündü
# ══════════════════════════════════════════════════════════════
# Kullanıcı (19.09): "panel sistemine göre bazı sayfaları ayrıştırabilirsin,
# daha güzel bir navigasyon için". Eski Lig sayfası yedi ayrı şey taşıyordu
# (KPI · kasa eğrisi · alternatif maliyet · üç takım tablosu · ajan dosyası
# · arşiv · çakışma) ve her soruya aşağı kaydırarak ulaşılıyordu. Artık her
# soru kendi sayfasında, sol panelde kendi yerinde.

TAKIM_TANIM = {
    "mavi": {"ad": "Mavi Takım", "alt": "sinyal motoru", "renk": "#2563a8"},
    "kirmizi": {"ad": "Kırmızı Takım", "alt": "kombo pazarları · keşif",
                "renk": "#a82f22"},
    "turuncu": {"ad": "Turuncu Takım",
                "alt": "bağımsız skor modeli · keşif", "renk": "#d9730d"},
}
TAKIM_NOTU = {
    "turuncu": (
        "<div class='dq'><b>Turuncu takım keşif statüsünde.</b> Takımların "
        "geçmiş gollerinden iddaa'ya bakmadan skor dağılımı kurar (Dixon-Coles) "
        "ve fiyatı ondan çıkarır. Model ön kayıtlı sınavı <b>geçmedi</b>: "
        "2.996 maçta kapanış fiyatına bilgi eklemiyor, iddaa'dan ≥5 puan "
        "ayrıştığında gerçek sonuç piyasaya daha yakın. Sahada beş hipotez "
        "yarışıyor: ana pazar · dar kombine · geniş kombine · gol bandı · "
        "harman. <b>Karar kuralı</b> (ajan başına 60 bahiste, sonuç "
        "görülmeden yazıldı): CLV ort. &gt; 0 ve ROI &gt; −%8 → sürer · "
        "CLV ≤ 0 → emekli · arası → 120 bahise uzar, orada hâlâ arası → "
        "emekli. Hüküm Ölçüm Defteri'nde (TURUNCU_SAHA). Haftalık lig "
        "değerlendirmesine girmez; diğer takımları etkilemez.</div>"),
    "kirmizi": (
        "<div class='dq'>Kırmızı takımın sessizliği <b>arıza değil</b>: "
        "ölçüldü, iddaa kombo pazarlarında korelasyonu doğru fiyatlıyor "
        "(1X2_OU +%0,1 · 1X2_BTTS −%0,3 · OU_BTTS −%1,2) ve marj %19-20. "
        "Keşif modunda günün EN AZ KÖTÜ kombinelerini oynar; beklenen ROI "
        "negatiftir, amaç kanıttır. Ön kayıtlı karar ajan başına 60 "
        "bahiste.</div>"),
    "mavi": (
        "<div class='v2mb'><b>Mavi takım sistemin ana hattı.</b> Sinyal "
        "motoru ve fiyat bandı ajanları; JOKER rastgele seçim yapan kontrol "
        "çizgisidir — onu geçemeyen ajan bir şey bilmiyor demektir. Hacim "
        "19.09'da günde 10 kupona açıldı: kanıt için örneklem lazım.</div>"),
}


def _takim_ozet(rows: list, ham: list) -> dict:
    """Takımın dönem özeti: ajan · bahis · isabet · fark · net · açık."""
    pidler = {x["pid"] for x in rows}
    n = sum(x["n"] for x in rows)
    won = sum(x.get("won", 0) for x in rows)
    exp = (sum(x["exp"] * x["n"] for x in rows) / n) if n else 0.0
    net = sum(float(x["pnl"] or 0) for x in ham if x["p"] in pidler)
    ciro = sum(float(x["stake"] or 0) for x in ham if x["p"] in pidler)
    return {"ajan": len(rows), "n": n, "won": won,
            "hit": (won / n) if n else 0.0, "exp": exp,
            "fark": ((won / n) - exp) if n else 0.0, "net": net, "ciro": ciro,
            "acik": sum(x["acik_kupon"] for x in rows),
            "enIyi": max((x for x in rows if x["n"] >= 10),
                         key=lambda z: z["edge"], default=None)}


def _para(v: float) -> str:
    return ("+" if v >= 0 else "−") + "{:,.0f}".format(abs(v)).replace(",", ".") + " ₺"


def page_lig() -> None:
    """🏆 Lig Tablosu — üç takım yan yana, bütün ajanlar TEK sıralamada.
    Kullanıcının istediği rekabet burada görünür: takım rengi rozette."""
    d = load_lig()
    ham = load_egri_ham()
    bant = load_islem_bandi()
    ae = load_ajan_egri()
    tum = d["mavi"] + d["kirmizi"] + d.get("turuncu", [])
    _ak = sum(x["acik_kupon"] for x in tum)
    _rk = sum(x["riskte"] for x in tum)
    kpi = [{"ad": "Ajan", "deger": str(len(tum))},
           {"ad": "Açık kupon", "deger": str(_ak) + "  ·  " +
            "{:,.0f}".format(_rk).replace(",", ".") + " ₺"}]
    if ham:
        _t = sum(float(x["pnl"] or 0) for x in ham)
        kpi.append({"ad": "Net (dönem)", "deger": _para(_t),
                    "cls": ("ps" if _t >= 0 else "ng")})
    _sayfa_basligi(
        "Lig Tablosu",
        "Yürürlükteki dönem. Sıralama isabete göre değil, fiyata göre "
        "üstünlüğe göre — iki ölçü farklı sıralama verir.", kpi)

    # ── TAKIM KARTLARI — üçü yan yana, her biri kendi sayfasına açılır
    kol = st.columns(3, gap="small")
    for k_, (kod, t) in zip(kol, TAKIM_TANIM.items()):
        o = _takim_ozet(d.get(kod, []), ham)
        with k_:
            en = o["enIyi"]
            st.markdown(
                "<div class='tk-kart' style='border-top-color:" + t["renk"] + ";'>"
                "<div class='tk-ust'><b>" + t["ad"] + "</b><span>" + t["alt"] +
                "</span></div>"
                "<div class='tk-sayi'><div><span>Ajan</span><b>" + str(o["ajan"]) +
                "</b></div><div><span>Bahis</span><b>" + str(o["n"]) + "</b></div>"
                "<div><span>İsabet</span><b>" +
                (_pct(o["hit"]) if o["n"] else "—") + "</b></div>"
                "<div><span>Fark</span><b class='" +
                ("ps" if o["fark"] >= 0 else "ng") + "'>" +
                (_sgn(o["fark"]) if o["n"] else "—") + "</b></div>"
                "<div><span>Net</span><b class='" + ("ps" if o["net"] >= 0 else "ng") +
                "'>" + (_para(o["net"]) if o["ciro"] else "—") + "</b></div>"
                "<div><span>Açık</span><b>" + str(o["acik"]) + "</b></div></div>"
                "<div class='tk-alt'>" +
                ("önde: " + _rozet(en["pid"]) + en["ad"] + " · " + _sgn(en["edge"])
                 if en else "henüz 10 bahisli ajan yok") + "</div></div>",
                unsafe_allow_html=True)
            if st.button(t["ad"] + " sayfası", key="lig_ac_" + kod,
                         use_container_width=True):
                _git(t["ad"])

    st.markdown(
        "<div class='v2mb'><b>Tek sıralama, üç takım.</b> Rozet rengi takımı "
        "söyler (mavi · <span style='color:var(--neg)'>kırmızı</span> · "
        "<span style='color:var(--tu)'>turuncu</span>). Her ajanın altındaki "
        "bant son işlemleri: kazanç yukarı yeşil, kayıp aşağı kırmızı, boy "
        "tutarla orantılı; üzerine gelince maç ve sonuç görünür.</div>",
        unsafe_allow_html=True)
    sirali = sorted(tum, key=lambda z: (z["n"] == 0, -z["edge"]))
    st.markdown(_takim_tablo(sirali, "Tüm Ajanlar",
                             "yürürlükteki dönem · " + str(len(sirali)) + " ajan",
                             "var(--brand)", ae, bant), unsafe_allow_html=True)


def _takim_sayfasi(kod: str) -> None:
    t = TAKIM_TANIM[kod]
    d = load_lig()
    ham = load_egri_ham()
    rows = d.get(kod, [])
    o = _takim_ozet(rows, ham)
    kpi = [{"ad": "Ajan", "deger": str(o["ajan"])},
           {"ad": "Bahis", "deger": str(o["n"])},
           {"ad": "İsabet", "deger": (_pct(o["hit"]) + " · " + str(o["won"]) +
                                      "/" + str(o["n"])) if o["n"] else "—"},
           {"ad": "Açık", "deger": str(o["acik"])}]
    if o["ciro"]:
        kpi.append({"ad": "Net (dönem)", "deger": _para(o["net"]),
                    "cls": ("ps" if o["net"] >= 0 else "ng")})
    _sayfa_basligi(t["ad"], t["alt"] + " · yürürlükteki dönem", kpi)
    if TAKIM_NOTU.get(kod):
        st.markdown(TAKIM_NOTU[kod], unsafe_allow_html=True)
    st.markdown(_takim_tablo(rows, t["ad"], t["alt"] + " · " + str(len(rows)) +
                             " ajan", t["renk"], load_ajan_egri(),
                             load_islem_bandi()), unsafe_allow_html=True)
    if rows:
        st.markdown("<div class='v2suz'>ajan dosyasına git</div>",
                    unsafe_allow_html=True)
        kol = st.columns(min(len(rows), 5), gap="small")
        for i, a in enumerate(rows):
            with kol[i % len(kol)]:
                if st.button(a["ad"], key="tk_ajan_" + a["pid"],
                             use_container_width=True):
                    st.session_state["v2_ajan"] = a["pid"]
                    _git("Ajan Dosyası")


def page_mavi() -> None:
    _takim_sayfasi("mavi")


def page_kirmizi() -> None:
    _takim_sayfasi("kirmizi")


def page_turuncu() -> None:
    _takim_sayfasi("turuncu")


def page_ajan() -> None:
    """👤 Ajan Dosyası — seçilen ajanın seyri, işlem bandı, açık pozisyonu,
    gerekçesi ve sonucu. Eskiden Lig sayfasının dibindeydi."""
    d = load_lig()
    tum = d["mavi"] + d["kirmizi"] + d.get("turuncu", [])
    _sayfa_basligi("Ajan Dosyası", "Bir ajanın her işlemi, gerekçesi ve "
                   "sonucu — kronolojik.", [])
    if not tum:
        st.markdown("<div class='v2bos'>Sahada ajan yok.</div>",
                    unsafe_allow_html=True)
        return
    secenek = [x["ad"] for x in tum]
    simdi = st.session_state.get("v2_ajan")
    idx = next((i for i, x in enumerate(tum) if x["pid"] == simdi), 0)
    sec = st.selectbox("Ajan", secenek, index=idx, key="v2_ajan_sec_sf")
    pid = next(x["pid"] for x in tum if x["ad"] == sec)
    st.session_state["v2_ajan"] = pid
    _ajan_paneli(pid, d, sayfa=True)


def page_kasa() -> None:
    """💰 Kasa ve Getiri — para büyüyor mu, neye göre? Eskiden Lig'deydi."""
    ham = load_egri_ham()
    kpi = []
    if ham:
        _t = sum(float(x["pnl"] or 0) for x in ham)
        _c = sum(float(x["stake"] or 0) for x in ham)
        kpi = [{"ad": "Net", "deger": _para(_t), "cls": ("ps" if _t >= 0 else "ng")},
               {"ad": "Ciro", "deger": "{:,.0f}".format(_c).replace(",", ".") + " ₺"},
               {"ad": "ROI", "deger": ("+" if _t >= 0 else "−") +
                _num(abs(_t / _c) * 100, 1) + "%" if _c else "—",
                "cls": ("ps" if _t >= 0 else "ng")}]
    _sayfa_basligi("Kasa ve Getiri", "Yürürlükteki dönemin kasa eğrisi ve "
                   "para piyasası tabanına göre gerçek katkı.", kpi)
    # ── KASA EĞRİSİ · süzgeçli, zaman eksenli
    if ham:
        tum_ajan = sorted({str(x["p"]) for x in ham})
        tum_tur = sorted({str(x["ct"] or "?") for x in ham})
        f1, f2 = st.columns([1.0, 1.0], gap="small")
        with f1:
            sec_ajan = st.multiselect(
                "Ajan", tum_ajan, default=[], key="v2_eg_ajan",
                placeholder="tümü",
                help="Boş bırakırsan hepsi. Eğri süzgeçten SONRA yeniden "
                     "hesaplanır — önceden toplanmış seri süzülemez.")
        with f2:
            sec_tur = st.multiselect(
                "Oyun türü", tum_tur, default=[], key="v2_eg_tur",
                placeholder="tümü",
                help="Kupon türü: tek, kombine, sistem…")
        sz = [x for x in ham
              if (not sec_ajan or str(x["p"]) in sec_ajan)
              and (not sec_tur or str(x["ct"] or "?") in sec_tur)]
        kum, tepe, dus, nokta, ciro = 0.0, 0.0, 0.0, [], 0.0
        for x in sz:
            try:
                kum += float(x["pnl"] or 0)
                ciro += float(x["stake"] or 0)
            except Exception:
                continue
            tepe = max(tepe, kum)
            dus = min(dus, kum - tepe)
            nokta.append({"t": str(x["sa"])[:10], "k": kum})
        etiket = ("tümü" if not (sec_ajan or sec_tur)
                  else " · ".join(sec_ajan + sec_tur)[:60])
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Kasa Eğrisi</h2>"
            "<div class='hint'>" + etiket + " · " + str(len(sz)) +
            " kupon</div></div><div class='v2body'>" +
            _svg_zaman(nokta) +
            ("<div style='display:flex;gap:var(--s5);flex-wrap:wrap;"
             "margin-top:var(--s3);border-top:1px solid var(--line);"
             "padding-top:var(--s3);'>"
             "<div class='v2kpi'><span>Net</span><b class='" +
             ("ps" if kum >= 0 else "ng") + "'>" +
             ("+" if kum >= 0 else "−") +
             "{:,.0f}".format(abs(kum)).replace(",", ".") + " ₺</b></div>"
             "<div class='v2kpi'><span>Ciro</span><b>" +
             "{:,.0f}".format(ciro).replace(",", ".") + " ₺</b></div>"
             "<div class='v2kpi'><span>ROI</span><b class='" +
             ("ps" if kum >= 0 else "ng") + "'>" +
             (("+" if kum >= 0 else "−") + _num(abs(kum / ciro) * 100, 1) + "%"
              if ciro else "—") + "</b></div>"
             "<div class='v2kpi'><span>En büyük düşüş</span><b class='ng'>−" +
             "{:,.0f}".format(abs(dus)).replace(",", ".") + " ₺</b></div>"
             "<div class='v2kpi'><span>Tepe</span><b>" +
             "{:,.0f}".format(tepe).replace(",", ".") + " ₺</b></div></div>"
             if nokta else "") +
            "</div></div>", unsafe_allow_html=True)

    # ── ALTERNATİF MALİYET ────────────────────────────────────
    alt = load_alternatif()
    if alt and alt["gun"] >= 1:
        _iy = alt["fark"] >= 0
        st.markdown(
            "<div class='v2card' style='margin-bottom:var(--s5);'>"
            "<div class='v2head'><h2>Alternatif Maliyet</h2>"
            "<div class='hint'>dönem " + str(alt["gun"]) + " gün</div></div>"
            "<div class='v2body'>"
            "<div class='" + ("v2mb" if _iy else "dq") + "'>"
            "<b>Kâr eğrisi tek başına bir şey söylemez.</b> Aynı para "
            "para piyasasında dururken de büyüyordu. Bahis operasyonu "
            "ancak <b>o tabanı geçtiği kadar</b> değer üretir — belge "
            "§2.3: alternatif maliyet sıfır değildir, ve düşük yield "
            "senaryolarında bu kalem operasyonun kendisinden büyük "
            "olabilir.</div>"
            "<div class='ro'><span>Bahisle kazanılan</span><b class='" +
            ("ps" if alt["bahis"] >= 0 else "ng") + "'>" +
            ("+" if alt["bahis"] >= 0 else "−") +
            "{:,.0f}".format(abs(alt["bahis"])).replace(",", ".") +
            " ₺</b></div>"
            "<div class='ro'><span>Para piyasası (%" +
            _num(alt["oran"] * 100, 0) + " yıllık, " + str(alt["gun"]) +
            " gün)</span><b>+" +
            "{:,.0f}".format(alt["faiz"]).replace(",", ".") + " ₺</b></div>"
            "<div class='ro big'><span>Fark — gerçek katkı</span>"
            "<b class='" + ("ps" if _iy else "ng") + "'>" +
            ("+" if _iy else "−") +
            "{:,.0f}".format(abs(alt["fark"])).replace(",", ".") +
            " ₺</b></div>"
            "<div class='vd' style='margin-top:var(--s3);'>" +
            ("Operasyon tabanı geçiyor." if _iy else
             "<b>Operasyon tabanın altında.</b> Bu para faizde durunca "
             "daha çok kazanıyordu — kâğıt ticarette bu bir kayıp değil, "
             "bir <b>ölçü</b>: edge kurulmadan sermaye bağlamanın "
             "maliyeti bu.") +
            "</div></div></div>", unsafe_allow_html=True)



def page_cakisma() -> None:
    """🔀 Çakışma ve Arşiv — kaç bağımsız görüş var, kim emekli.
    Eskiden Lig sayfasının dibindeydi."""
    d = load_lig()
    _sayfa_basligi("Çakışma ve Arşiv", "Ajanlar gerçekten farklı şeyler mi oynuyor · emekli ajanların karnesi.", [])
    # ── AJAN ÇAKIŞMASI ────────────────────────────────────────
    _ckd = load_cakisma() or {}
    ck = _ckd.get("ciftler") or []
    if ck:
        sat = []
        for x in ck[:12]:
            o = x["oran"]
            g = "g3" if o >= 0.85 else ("g2" if o >= 0.6 else "g1")
            txt = ("AYNI" if o >= 0.85 else
                   ("BÜYÜK ÖLÇÜDE" if o >= 0.6 else "KISMEN"))
            sat.append(
                "<tr><td><span class='ag'>" + _rozet(x["a"]) +
                str(x["a"]).rsplit("_", 1)[0] + "</span>"
                "<span class='sb'>" + str(x["na"]) + " bahis</span></td>"
                "<td><span class='ag'>" + _rozet(x["b"]) +
                str(x["b"]).rsplit("_", 1)[0] + "</span>"
                "<span class='sb'>" + str(x["nb"]) + " bahis</span></td>"
                "<td class='r n'>" + str(x["ortak"]) + "</td>"
                "<td class='r n'>" + _num(o * 100, 0) + "%</td>"
                "<td class='r'><span class='gr " + g + "'>" + txt +
                "</span></td></tr>")
        _ayni = sum(1 for x in ck if x["oran"] >= 0.85)
        st.markdown(
            "<div class='v2card' style='margin-top:var(--s5);'>"
            "<div class='v2head'><h2>Ajan Çakışması</h2>"
            "<div class='hint'>kaç ajan gerçekten farklı</div></div>"
            "<div class='v2body'>"
            "<div class='" + ("dq" if _ayni else "v2mb") + "'>"
            "<b>Karar: elimizde kaç bağımsız görüş var?</b> On altı ajanın "
            "çoğu aynı seçimi yapıyorsa on altı görüş yok, <b>tek görüşün "
            "on altı kopyası</b> var. O zaman ortalama almak, çoğunluğa "
            "bakmak, 'ajanlar hemfikir' demek — hepsi yanıltıcı olur. "
            "Çeşitlilik bir tercih değil, <b>ölçümün ön koşuludur</b>." +
            ("" if not _ayni else " <b>Şu an " + str(_ayni) + " çift "
             "neredeyse aynı şeyi oynuyor.</b>") + "</div>"
            "<table class='v2'><thead><tr><th>Ajan</th><th>Ajan</th>"
            "<th class='r'>Ortak</th><th class='r'>Örtüşme</th>"
            "<th class='r'>Hüküm</th></tr></thead><tbody>" +
            "".join(sat) + "</tbody></table>"
            "<div class='sb' style='margin-top:9px;'>Örtüşme = ortak "
            "(maç, pazar, seçim) sayısı ÷ az oynayanın toplamı. Az oynayan "
            "bir ajanın tamamı diğerinin içindeyse bu %100'dür — bölen "
            "bilerek asimetrik, çünkü soru <i>&ldquo;bu ajan bağımsız bir şey "
            "söylüyor mu&rdquo;</i> sorusudur.</div>"
            "</div></div>", unsafe_allow_html=True)

    # ── ARŞİV — emekli ajanlar ────────────────────────────────
    # Kullanıcı: "Emekli ajanları arşiv gibi bir şeye alalım, listeyi
    # kalabalık gösteriyor." Doğru: emekli ajan yeni bahis üretmiyor,
    # sıralamada yer tutması "kime güvenirim" sorusunu bulandırır.
    # SİLİNMİYOR — karnesi burada okunabiliyor, karar geri alınabilir.
    _ar = d.get("arsiv") or []
    if _ar:
        with st.expander(f"Arşiv — emekli {len(_ar)} ajan  ·  "
                         f"dönem 3 tasfiyesi", expanded=False):
            st.markdown(
                "<div class='v2mb'>Bu ajanlar <b>yeni bahis üretmiyor</b>. "
                "Karneleri burada duruyor çünkü <b>silmek ölçümü yok "
                "etmektir</b> — bir kararı geri almak için de, neden "
                "verildiğini görmek için de bu satırlara ihtiyaç var. "
                "Emeklilik bayrağı kaldırılırsa ajan sahaya döner.</div>" +
                _takim_tablo(_ar, "Emekli Ajanlar",
                             "dönem 3'te sahada değil", "#8a94a0"),
                unsafe_allow_html=True)



def page_defter() -> None:
    """📓 Ölçüm Defteri — her bulgunun ön kayıtlı kurala karşı hükmü."""
    rows = load_defter()
    if rows:
        _g = sum(1 for r in rows if r["gecti"])
        _c = load_clv()
        _k = [{"ad": "Kural sağlayan", "deger": str(_g) + "/" + str(len(rows)),
               "cls": ("ps" if _g * 2 >= len(rows) else "ng")}]
        if _c.get("n", 0) >= 50:
            _k.append({"ad": "CLV",
                       "deger": ("+" if _c["ort"] >= 0 else "−") +
                       _num(abs(_c["ort"]) * 100, 2) + "%",
                       "cls": ("ps" if _c["t"] > 1.96 else "ng")})
        _sayfa_basligi(
            "Ölçüm Defteri",
            "Her bulgunun ön kayıtlı kurala karşı hükmü. Kural sonuç "
            "görülmeden yazıldı ki sonradan esnetilemesin.", _k)
    if not rows:
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Ölçüm Defteri</h2>"
            "<div class='hint'>henüz koşmadı</div></div><div class='v2body'>"
            "<div class='dq'>Defter henüz koşmadı. Worker her gün 04:20'de "
            "hafif ölçümleri, pazartesi 03:10'da tam takımı koşar. Elle: "
            "<code>python 02_VERI/olcum_defteri.py</code></div></div></div>",
            unsafe_allow_html=True)
        return
    gecen = sum(1 for r in rows if r["gecti"])
    body = []
    for r in rows:
        g = "g1" if r["gecti"] else "g3"
        txt = "KURAL SAĞLANDI" if r["gecti"] else "sağlanmadı"
        tr = ""
        if r["trend"] is not None and abs(r["trend"]) > 1e-9:
            cls = "dp" if r["trend"] > 0 else "dm"
            tr = ("<span class='" + cls + "' style='font-size:var(--t-kucuk);'>" +
                  ("+" if r["trend"] > 0 else "−") +
                  _num(abs(r["trend"]), 3) + "</span>")
        dg = ("<span class='gr g2'>🔔 " + str(r["degisim"]) + " KEZ DÖNDÜ</span>"
              if r["degisim"] else "")
        # 🔒 Kararı kesinleşmiş bulgu artık koşmaz, tarihi eski kalır —
        # SÖYLENMEZSE "ölçüm durmuş, bozuk" gibi görünür. Alt satır da
        # kesilmiş ölçüm dökümü yerine kararın kendisini gösterir.
        if r.get("kapandi"):
            dg += "<span class='gr g2'>🔒 KARAR KESİN</span>"
        _alt = (str(r["kapandi"])[:150] if r.get("kapandi")
                else str(r["detay"] or "")[:96])
        body.append(
            "<tr><td><span class='ag'>" + r["id"] + "</span>" + dg +
            "<span class='sb'>" + _alt + "</span></td>"
            "<td class='r n opt'>" + "{:,}".format(r["n"]).replace(",", ".") + "</td>"
            "<td class='r n'>" + _num(r["v"], 3) + " " + tr + "</td>"
            "<td class='r n opt'>" + str(r["kosu"]) + "</td>"
            "<td class='r'><span class='gr " + g + "'>" + txt + "</span></td></tr>")
    # ── KANIT KAPISI ──────────────────────────────────────────
    kn = load_kanit()
    if kn:
        _gecen = sum(1 for x in kn["satir"] if x["gecti"])
        _olculen = sum(1 for x in kn["satir"] if x["n"] > 0)
        ksat = []
        for x in kn["satir"]:
            if x["n"] == 0:
                ksat.append(
                    "<tr><td><span class='ag'>" + _rozet(x["pid"]) + x["ad"] +
                    "</span><span class='sb'>henüz bahis kurmadı</span></td>"
                    "<td class='r n'>0</td><td class='r n'>—</td>"
                    "<td class='r n'>—</td><td class='r n'>—</td>"
                    "<td class='r'><span class='gr g2'>BEKLİYOR</span>"
                    "</td></tr>")
                continue
            imk = x["ger"] is None or x["ger"] > 1
            g = "g1" if x["gecti"] else ("g2" if imk else "g3")
            txt = ("GEÇTİ" if x["gecti"] else
                   ("VERİ YETMEZ" if imk else "GEÇMEDİ"))
            ksat.append(
                "<tr><td><span class='ag'>" + _rozet(x["pid"]) + x["ad"] +
                "</span><span class='sb'>fiyat " + _pct(x["p0"]) +
                " bekliyor</span></td>"
                "<td class='r n'>" + str(x["n"]) + "</td>"
                "<td class='r n'>" + _pct(x["hit"]) + "</td>"
                "<td class='r n'>" + _pct(x["p0"]) + "</td>"
                "<td class='r n'>" +
                ("imkânsız" if imk else _pct(x["ger"])) + "</td>"
                "<td class='r'><span class='gr " + g + "'>" + txt +
                "</span></td></tr>")
        _c = kn["clv"]
        st.markdown(
            "<div class='v2card' style='margin-bottom:var(--s5);'>"
            "<div class='v2head'><h2>Kanıt Kapısı</h2>"
            "<div class='hint'>seçim yanlılığı düzeltilmiş</div></div>"
            "<div class='v2body'>"
            "<div class='" + ("dq" if not _gecen else "v2mb") + "'>"
            "<b>Karar: bir ajanın iyi görünmesi yeterli mi?</b> Hayır. "
            "Hiçbir ajanın gerçek üstünlüğü olmasa bile, yeterince ajan "
            "test edilirse <b>birkaçı tesadüfen mükemmel görünür</b>. "
            "O yüzden eşik, kaç ajan denendiğine göre yükselir "
            "(Šidák düzeltmesi). Ve korelasyonlu ajanlar tek ajan gibi "
            "davrandığı için sayılan şey <b>bağımsız</b> ajan sayısıdır."
            + ("" if not _olculen else
               (" Şu an ölçülen " + str(_olculen) + " ajandan <b>" +
                str(_gecen) + "</b> tanesi eşiği geçiyor.")) +
            "</div>"
            "<div class='v2kpi-satir' style='display:flex;flex-wrap:wrap;"
            "gap:var(--s3) var(--s5);margin-bottom:var(--s3);'>"
            "<div class='v2kpi'><span>Sahada ajan</span><b>" +
            str(kn["m"]) + "</b></div>"
            "<div class='v2kpi'><span>Ortalama örtüşme ρ</span><b>" +
            _num(kn["ro"] * 100, 0) + "%</b></div>"
            "<div class='v2kpi'><span>Etkin ajan</span><b class='" +
            ("ng" if kn["m_etkin"] < kn["m"] * 0.7 else "") + "'>" +
            _num(kn["m_etkin"], 1) + "</b></div>"
            "<div class='v2kpi'><span>Ajan güveni</span><b>" +
            _num((1 - kn["alpha"]) * 100, 2) + "%</b></div>"
            "</div>"
            "<table class='v2'><thead><tr><th>Ajan</th>"
            "<th class='r'>n</th><th class='r'>İsabet</th>"
            "<th class='r'>Fiyat bekler</th><th class='r'>Gereken</th>"
            "<th class='r'>Kapı</th></tr></thead><tbody>" +
            "".join(ksat) + "</tbody></table>"
            "<div class='sb' style='margin-top:10px;'>Eşik her ajanın "
            "<b>kendi fiyatına</b> göre: p₀ = ortalama(1/oran). Soru "
            "&ldquo;isabet yüksek mi&rdquo; değil, <b>fiyatın "
            "beklediğinden anlamlı yüksek mi</b>. Tek yönlü tam binom "
            "testi, " + str(kn["cift"]) + " ajan çifti üzerinden ölçülen "
            "ρ ile düzeltilmiş.</div>"
            "<div class='ro big' style='margin-top:var(--s4);'>"
            "<span>CLV kapısı</span><b class='" + _c.get("cls", "") + "'>" +
            _c.get("bolge", "—") + "</b></div>"
            "<div class='vd' style='margin-top:var(--s3);'>" +
            ("ortalama <b>" + ("+" if (_c.get("ort") or 0) >= 0 else "−") +
             _num(abs(_c.get("ort") or 0) * 100, 2) + "%</b> · n=" +
             "{:,}".format(_c.get("n", 0)).replace(",", ".") + " — "
             if _c.get("ort") is not None else "") +
            _c.get("not", "") +
            ("" if _c.get("yeterli") else
             " <b>Not: bu hüküm 200+ bahis ister; örneklem henüz orada "
             "değilse yön göstergesidir, karar değil.</b>") +
            "</div></div></div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='v2card'><div class='v2head'><h2>Ölçüm Defteri</h2>"
        "<div class='hint'>KAYIT — " + str(gecen) + "/" + str(len(rows)) +
        " kural sağlıyor</div></div><div class='v2body'>"
        "<div class='v2mb'><b>Kurallar sonuç görülmeden yazıldı</b> ki "
        "sonradan esnetilemesin. 'Sağlanmadı' bir arıza değil, bir "
        "<b>hükümdür</b> — konsept o kadar. Bir bulgunun çürümesi de "
        "güçlenmesi de karar gerektirir.</div>"
        "<div class='vd' style='margin-bottom:var(--s3);'>Buradaki her "
        "değer <b>ölçümün alındığı anın kaydıdır</b> — hüküm o sayıya "
        "karşı verildi. Aşağıdaki paneller <b>şu anı</b> hesaplar; iki "
        "sayı farklıysa arada yeni bahis kapanmış demektir, ikisi de "
        "doğrudur.</div>"
        "<table class='v2'><thead><tr><th>Ölçüm</th><th class='r opt'>n</th>"
        "<th class='r'>Değer</th><th class='r opt'>Koşu</th>"
        "<th class='r'>Hüküm</th></tr></thead><tbody>" +
        "".join(body) + "</tbody></table></div></div>", unsafe_allow_html=True)

    sol, sag = st.columns([1.0, 1.0], gap="small")

    # ── CLV: V1'in ayri sayfasi, artik olcum katmaninin icinde
    with sol:
        c = load_clv()
        if c.get("n", 0) < 50:
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>CLV</h2>"
                "<div class='hint'>kapanış çizgisi</div></div>"
                "<div class='v2body'><div class='dq'>Yeterli CLV kaydı yok."
                "</div></div></div>", unsafe_allow_html=True)
        else:
            iyi = c["t"] > 1.96
            sat = []
            for x in c["pazar"]:
                cls = "dp" if x["ort"] > 0.002 else "dm"
                sat.append("<tr><td><span class='ag'>" + x["ad"][:14] +
                           "</span></td><td class='r n opt'>" + str(x["n"]) +
                           "</td><td class='r'><span class='" + cls + "'>" +
                           ("+" if x["ort"] >= 0 else "−") +
                           _num(abs(x["ort"]) * 100, 2) + "%</span></td>"
                           "<td class='r n'>" + _pct(x["beat"]) + "</td></tr>")
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>CLV · Kapanış Çizgisi</h2>"
                "<div class='hint'>ŞU AN — canlı hesap</div></div>"
                "<div class='v2body'>"
                "<div class='v2mb'>Girdiğin fiyat kapanıştan iyiyse piyasadan "
                "<b>önce</b> doğru tarafı görmüşsün demektir — sonuçtan "
                "bağımsız. Ama tek başına marjı yenmez: %17,6'yı aşmak için "
                "+%17,6 CLV gerekir.</div>"
                # ⚠️ Denetim bulgusu O3: aynı sayfada CLV iki farklı sayı
                # gösteriyordu — yukarıdaki defter satırı +%0,60 (t=6,10),
                # buradaki panel +%0,63 (t=6,46). İkisi de doğruydu: biri
                # ölçümün ALINDIĞI ANIN kaydı, diğeri ŞU ANIN hesabı. Ama
                # sayfa bunu söylemiyordu; okuyan hangisinin geçerli
                # olduğunu bilemiyordu. Farkın kendisi bilgidir: bulgu
                # güçleniyor mu zayıflıyor mu, ancak ikisi yan yana
                # okununca görülür.
                "<div class='vd' style='margin-bottom:var(--s3);'>"
                "<b>Bu panel ŞU ANI hesaplar.</b> Yukarıdaki defter satırı "
                "ise ölçümün <b>alındığı anın kaydıdır</b> — kural o anki "
                "sayıya karşı verildi. İkisi arasındaki fark bulgunun "
                "yönüdür: güçleniyorsa canlı sayı defterdekini geçer."
                "</div>"
                "<div class='ro'><span>Ortalama CLV</span><b class='" +
                ("ps" if iyi else "ng") + "'>" +
                ("+" if c["ort"] >= 0 else "−") + _num(abs(c["ort"]) * 100, 2) +
                "%</b></div>"
                "<div class='ro'><span>t değeri</span><b class='" +
                ("ps" if iyi else "ng") + "'>" + _num(c["t"], 2) + "</b></div>"
                "<div class='ro'><span>Kapanışı geçen</span><b>" +
                _pct(c["beat"]) + "</b></div>"
                "<div class='ro'><span>Hiç oynamayan</span><b>" +
                _pct(c["sifir"]) + "</b></div>"
                "<table class='v2' style='margin-top:12px;'><thead><tr>"
                "<th>Pazar</th><th class='r opt'>n</th><th class='r'>CLV</th>"
                "<th class='r'>Geçen</th></tr></thead><tbody>" +
                "".join(sat) + "</tbody></table></div></div>",
                unsafe_allow_html=True)

    # ── MIHENK: arsivi OKU, yeniden uretme
    with sag:
        mh = load_mihenk()
        if not mh.get("var"):
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>Mihenk</h2>"
                "<div class='hint'>yönetici özeti</div></div>"
                "<div class='v2body'><div class='dq'>Henüz arşivlenmiş rapor "
                "yok. Üretim: <code>python 02_VERI/exec_report.py</code>"
                "</div></div></div>", unsafe_allow_html=True)
        else:
            p = mh["payload"]
            bul = p.get("findings") or p.get("bulgular") or []
            kap = p.get("gates") or []
            ic = ""
            if bul:
                ic += ("<div class='v2mb'><b>Bulgular</b><br>" +
                       "<br>".join("· " + str(b)[:150] for b in bul[:6]) +
                       "</div>")
            if kap:
                sat = []
                for gt in kap[:6]:
                    ad = str(gt.get("name") or gt.get("ad") or "?")[:30]
                    ok = bool(gt.get("ok") or gt.get("passed"))
                    sat.append("<tr><td><span class='ag'>" + ad + "</span></td>"
                               "<td class='r'><span class='gr " +
                               ("g1" if ok else "g3") + "'>" +
                               ("GEÇTİ" if ok else "geçmedi") +
                               "</span></td></tr>")
                ic += ("<table class='v2'><thead><tr><th>Gerçek para kapısı</th>"
                       "<th class='r'>Durum</th></tr></thead><tbody>" +
                       "".join(sat) + "</tbody></table>")
            if not ic:
                ic = ("<div class='dq'>Rapor #" + str(mh["no"]) +
                      " arşivde ama okunabilir bulgu alanı yok.</div>")
            gec = " · ".join("#" + str(g["no"]) for g in mh["gecmis"])
            st.markdown(
                "<div class='v2card'><div class='v2head'>"
                "<h2>Mihenk · Rapor #" + str(mh["no"]) + "</h2>"
                "<div class='hint'>" + mh["ts"] + "</div></div>"
                "<div class='v2body'>" + ic +
                "<div class='dq' style='margin:10px 0 0;'>Arşiv: " + gec +
                " · rapor <b>üretimi</b> exec_report.py'de kalır, burası "
                "okuma yüzeyidir. Bir işin iki yerde yapılması V1'in en "
                "büyük hatasıydı.</div></div></div>", unsafe_allow_html=True)


def page_sistem() -> None:
    """🩺 Sistem — sessizlik meşru mu, arıza mı?"""
    d = load_sistem()
    sy = d["sistem"]
    _durum = str(sy["status"]) if sy else "—"
    _bos = sum(1 for f in d["alan"] if f["pay"] < 0.5)
    _sayfa_basligi(
        "Sistem Sağlığı",
        "Bir ajanın oynamaması meşru PAS da olabilir tıkanıklık da — "
        "ikisini karıştırmak haftalar sürer.",
        [{"ad": "Veri hattı", "deger": _durum.split(" ")[-1][:14],
          "cls": ("ng" if "TIKANIKLIK" in _durum else "ps")},
         {"ad": "Zayıf alan", "deger": str(_bos) + " / " + str(len(d["alan"])),
          "cls": ("ng" if _bos else "ps")}])
    if sy:
        kirik = "TIKANIKLIK" in str(sy["status"])
        st.markdown(
            "<div class='" + ("dq" if kirik else "v2mb") + "'>"
            "<b>" + str(sy["status"]) + "</b> — " + str(sy["detail"] or "") +
            "<br><span style='font-size:var(--t-kucuk);opacity:.75;'>son teşhis " +
            str(sy["ts"])[:16] + "</span></div>", unsafe_allow_html=True)

    sek = _sekmeler("sistem", ["Teşhis", "Veri", "Risk", "Defter"])

    if sek == "Teşhis":
        st.markdown(
            "<div class='v2mb'><b>Karar:</b> bir ajan neden oynamıyor — "
            "<b>meşru PAS</b> mı (eşiği geçen aday yok) yoksa <b>tıkanıklık</b> "
            "mı (kod/veri kırık)? İkisini karıştırmak haftalar sürer. En üstteki "
            "SİSTEM satırı veri hattını bekler: fetch çökerse tüm ajanlar masum "
            "sessizlik gibi görünür.</div>", unsafe_allow_html=True)
    elif sek == "Veri":
        st.markdown(
            "<div class='v2mb'><b>Karar:</b> hangi analiz <b>yapılamıyor</b>? "
            "Boş sütun, yapılamayan analiz demektir. Doluluk tek başına yetmez: "
            "26.000 satırın %90'ı dolu ama hepsi iki yıl önceden ise sistem "
            "kördür. Üç soru ayrı sorulur — ne kadar var, ne kadarı dolu, ne "
            "kadarı taze.</div>", unsafe_allow_html=True)
    elif sek == "Defter":
        st.markdown(
            "<div class='v2mb'><b>Karar:</b> defter kendi kendini tutuyor "
            "mu? Bu sekme sunum değil <b>denetim</b>dir. 1 Eylül 2026'da "
            "üretimde şu bulundu: mutabakat kodu açık ayakları süzüp atıp "
            "kuponu erken <b>kazandı</b> yazıyordu — bir kupon 1 Eylül'de "
            "ödendi, iki maçı 2 ve 4 Eylül'de oynanacaktı. Kasaya var "
            "olmayan para girdi. Kök neden düzeltildi; <b>bu satırlar o "
            "hatanın sessizce geri dönmemesi için var.</b></div>",
            unsafe_allow_html=True)
    else:
        st.markdown(
            "<div class='v2mb'><b>Karar:</b> hangi ajan sözleşmesini "
            "zorluyor? Prop-firm mantığı: her ajanın kendi kasası, tabanı ve "
            "sözleşmesi var. Taban altına düşen koruma moduna girer, iki ihtar "
            "kadro dışı demektir. <b>Sistemin ajanı susturması arıza değil, "
            "sözleşmenin işlemesidir.</b></div>", unsafe_allow_html=True)

    if sek != "Teşhis":
        left, right = st.container(), st.container()
    else:
        left, right = st.columns([1.25, 1.0], gap="small")

    with left:
        body = []
        for a in d["ajan"]:
            t = str(a["status"] or "")
            if "TIKANIKLIK" in t:
                g = "g3"
            elif "🟠" in t or "MONTAJ" in t:
                g = "g2"
            elif "🟢" in t:
                g = "g1"
            else:
                g = "g2"
            pid = str(a["pid"])
            body.append(
                "<tr><td><span class='ag'>" + _rozet(pid) +
                pid.rsplit("_", 1)[0] + "</span>"
                "<span class='sb'>" + str(a["detail"] or "")[:88] + "</span></td>"
                "<td class='r'><span class='gr " + g + "'>" +
                t.replace("🔴 ", "").replace("🟠 ", "").replace("🟢 ", "")
                 .replace("⚪ ", "").replace("😴 ", "").replace("🧊 ", "")
                 .replace("⏸ ", "").replace("🔒 ", "").replace("🏁 ", "")
                 .replace("🛑 ", "").replace("🚫 ", "") + "</span></td></tr>")
        if sek != "Teşhis":
            body = []
        st.markdown(
            ("" if sek != "Teşhis" else
             "<div class='v2card'><div class='v2head'><h2>Ajan Teşhisi</h2>"
            "<div class='hint'>günlük · sorunlu üstte</div></div>"
            "<div class='v2body'>"
            "<div class='v2mb'>Bir ajanın oynamaması iki ayrı şey olabilir: "
            "<b>meşru PAS</b> (eşiği geçen aday yok) ya da <b>tıkanıklık</b> "
            "(kod/veri kırık). İkisini karıştırmak haftalar sürebilir — "
            "bu yüzden sebep her gün kayda geçer.</div>"
            "<table class='v2'><thead><tr><th>Ajan</th>"
            "<th class='r'>Durum</th></tr></thead><tbody>" +
            "".join(body) + "</tbody></table></div></div>"),
            unsafe_allow_html=True)

    with right:
        if sek != "Veri":
            st.markdown("", unsafe_allow_html=True)
        body = []
        for f in d["alan"]:
            p = f["pay"]
            if p >= 0.90:
                g, txt = "g1", "TAM"
            elif p >= 0.50:
                g, txt = "g2", "KISMÎ"
            elif p > 0:
                g, txt = "g3", "ZAYIF"
            else:
                g, txt = "g3", "BOŞ"
            bar = int(round(p * 100))
            body.append(
                "<tr><td><span class='ag'>" + f["ad"] + "</span>"
                "<span class='sb'>" + f["neden"] + "</span>"
                "<div style='height:3px;background:var(--line);margin-top:5px;'>"
                "<i style='display:block;height:3px;width:" + str(bar) + "%;"
                "background:" + ("var(--pos)" if p >= 0.5 else "var(--neg)") +
                ";'></i></div></td>"
                "<td class='r n'>" + "{:,}".format(f["n"]).replace(",", ".") +
                "</td>"
                "<td class='r'><span class='gr " + g + "'>" +
                "{:.0f}".format(p * 100) + "% " + txt + "</span></td></tr>")
        st.markdown(
            ("" if sek != "Veri" else
             "<div class='v2card'><div class='v2head'><h2>Veri Doluluğu</h2>"
            "<div class='hint'>yol haritası · faz 1</div></div>"
            "<div class='v2body'>"
            "<div class='v2mb'>Boş sütun, yapılamayan analiz demektir. "
            "<b>İlk yarı skoru</b> hiç yok — oysa iddaa'nın çıpa pazarları "
            "golün <b>ne zaman</b> atıldığını belirlemiyor; kitabın en az "
            "güvendiği yer orası (HT_FT marjı %25,8).</div>"
            "<table class='v2'><thead><tr><th>Alan</th><th class='r'>Dolu</th>"
            "<th class='r'>Oran</th></tr></thead><tbody>" +
            "".join(body) + "</tbody></table></div></div>"),
            unsafe_allow_html=True)

    vo = load_veri_ozet() if sek == "Veri" else {}
    if vo.get("toplam"):
        tsat = "".join(
            "<tr><td><span class='ag'>" + x["ad"] + "</span>"
            "<span class='sb'>" + x["tb"] + "</span></td>"
            "<td class='r n'>" + "{:,}".format(x["n"]).replace(",", ".") +
            "</td></tr>" for x in vo["tablolar"])
        ksat = "".join(
            "<tr><td><span class='ag'>" + str(k["k"] or "?") + "</span>"
            "<span class='sb'>" + str(k["ilk"]) + " → " + str(k["son"]) +
            "</span></td><td class='r n'>" +
            "{:,}".format(int(k["n"])).replace(",", ".") + "</td></tr>"
            for k in vo["kaynak"])
        s1, s2 = st.columns([1.0, 1.0], gap="small")
        with s1:
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>Veri Özeti</h2>"
                "<div class='hint'>sistemin hafızası</div></div>"
                "<div class='v2body'>"
                "<div class='ro'><span>Toplam maç</span><b>" +
                "{:,}".format(vo["toplam"]).replace(",", ".") + "</b></div>"
                "<div class='ro'><span>Sonuçlanmış</span><b>" +
                "{:,}".format(vo["sonuclanmis"]).replace(",", ".") + "</b></div>"
                "<div class='ro'><span>Yaklaşan</span><b>" +
                str(vo["yaklasan"]) + "</b></div>"
                "<div class='ro'><span>Son tazeleme</span><b style='font-size:var(--t-govde);'>" +
                str(vo["tazelik"] or "—") + "</b></div>"
                "<table class='v2' style='margin-top:var(--s3);'><thead><tr>"
                "<th>Tablo</th><th class='r'>Satır</th></tr></thead><tbody>" +
                tsat + "</tbody></table></div></div>", unsafe_allow_html=True)
        with s2:
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>Fiyat Kaynağı</h2>"
                "<div class='hint'>kapsam ve dönem</div></div>"
                "<div class='v2body'>"
                "<div class='v2mb'>Hangi fiyattan ölçtüğün, ne ölçtüğünü "
                "belirler. Pinnacle marjı ~%3, iddaa ~%17,6 — aynı modeli "
                "iki kaynakta sınamak <b>iki farklı sonuç</b> verir. "
                "Kaynakların <b>çakışmadığına</b> dikkat et.</div>"
                "<table class='v2'><thead><tr><th>Kaynak · dönem</th>"
                "<th class='r'>Maç</th></tr></thead><tbody>" + ksat +
                "</tbody></table></div></div>", unsafe_allow_html=True)

    rk = load_risk() if sek == "Risk" else []
    if rk:
        sat = []
        for x in rk:
            if x["p"] in ("PAPER_V1",):
                continue
            kc = "dp" if x["oran"] >= 1.0 else "dm"
            sat.append(
                "<tr><td><span class='ag'>" + _rozet(x["p"]) + x["ad"] +
                "</span><span class='sb'>dönem " + str(x["era"] or "—") +
                " · başlangıç " + "{:,.0f}".format(x["ib"]).replace(",", ".") +
                " ₺</span></td>"
                "<td class='r n'>" + "{:,.0f}".format(x["cb"]).replace(",", ".") +
                " ₺</td>"
                "<td class='r'><span class='" + kc + "'>" +
                "{:.0f}".format(x["oran"] * 100) + "%</span></td>"
                "<td class='r n opt'>" +
                ("−" + _num(abs(x["dusus"]) * 100, 0) + "%"
                 if x["dusus"] < 0 else "—") + "</td>"
                "<td class='r'><span class='gr " + x["sev"] + "'>" +
                x["dur"] + "</span></td></tr>")
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Risk ve Sözleşme</h2>"
            "<div class='hint'>prop-firm mantığı</div></div>"
            "<div class='v2body'>"
            "<div class='v2mb'>Her ajanın <b>kendi kasası ve kendi "
            "sözleşmesi</b> var. Taban altına düşen koruma moduna girer, "
            "iki ihtar kadro dışı demektir. Sistemin ajanı susturması "
            "bir arıza değil, sözleşmenin işlemesidir.</div>"
            "<table class='v2'><thead><tr><th>Ajan</th><th class='r'>Kasa</th>"
            "<th class='r'>%</th><th class='r opt'>Tepeden</th>"
            "<th class='r'>Durum</th></tr></thead><tbody>" +
            "".join(sat) + "</tbody></table></div></div>",
            unsafe_allow_html=True)

    dd = load_defter_denetim() if sek == "Defter" else []
    if dd:
        _kirik = sum(1 for x in dd
                     if x["esik"] is not None and x["n"] > x["esik"])
        sat = []
        for x in dd:
            if x["esik"] is None:                      # bilgi satiri
                g, txt = "g2", "BİLGİ"
            elif x["n"] > x["esik"]:
                g, txt = "g3", "BOZUK"
            else:
                g, txt = "g1", "TEMİZ"
            sat.append(
                "<tr><td><span class='ag'>" + x["ad"] + "</span>"
                "<span class='sb'>" + x["aciklama"] + "</span></td>"
                "<td class='r n'>" + str(x["n"]) + "</td>"
                "<td class='r'><span class='gr " + g + "'>" + txt +
                "</span></td></tr>")
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Defter Denetimi</h2>"
            "<div class='hint'>" +
            ("hepsi temiz" if not _kirik else str(_kirik) + " satır bozuk") +
            "</div></div><div class='v2body'>"
            "<div class='" + ("dq" if _kirik else "v2mb") + "'>"
            "Kâr eğrisi ancak defter tutarlıysa bir şey ifade eder. "
            "Buradaki her satır <b>her açılışta canlı veritabanından "
            "yeniden</b> okunur — sabit bir sonuç saklanmaz." +
            ("" if not _kirik else
             " <b>Şu an bozuk satır var; kasa rakamlarına güvenme.</b>") +
            "</div>"
            "<table class='v2'><thead><tr><th>Denetim</th>"
            "<th class='r'>Sayı</th><th class='r'>Durum</th></tr></thead>"
            "<tbody>" + "".join(sat) + "</tbody></table>"
            "<div class='sb' style='margin-top:10px;'>Bozuk satır varsa "
            "onarım: <code>python 02_VERI/fix_early_settled.py --dry</code> "
            "ile bak, <code>--dry</code>siz uygula. Kural sonuç-kördür: "
            "kaybeden ayağı olan kupon (ölü kombine) dokunulmadan kalır."
            "</div></div></div>", unsafe_allow_html=True)


def _mini(baslik, ipucu, basliklar, satirlar):
    if not satirlar:
        return ("<div class='v2card'><div class='v2head'><h2>" + baslik +
                "</h2><div class='hint'>" + ipucu + "</div></div>"
                "<div class='v2body'><div class='dq'>Yeterli örneklem yok."
                "</div></div></div>")
    th = "".join("<th class='r'>" + h + "</th>" if i else "<th>" + h + "</th>"
                 for i, h in enumerate(basliklar))
    tb = "".join("<tr>" + "".join(
        ("<td>" + c + "</td>") if i == 0 else ("<td class='r'>" + c + "</td>")
        for i, c in enumerate(r)) + "</tr>" for r in satirlar)
    return ("<div class='v2card'><div class='v2head'><h2>" + baslik + "</h2>"
            "<div class='hint'>" + ipucu + "</div></div><div class='v2body'>"
            "<table class='v2'><thead><tr>" + th + "</tr></thead><tbody>" +
            tb + "</tbody></table></div></div>")


def page_inceleme() -> None:
    """İnceleme — kazanan/kaybeden ayrıştırması, dört ayrı soruda.

    Tek sayfada dört tabloyu üst üste yığmak 'kompakt' değil OKUNMAZ
    yapar. Her sekme TEK bir karara hizmet eder ve hangisi olduğunu
    kendi yazar."""
    d = load_inceleme()
    if not d.get("n"):
        _sayfa_basligi("İnceleme", "Dönem içinde kapanmış bahis yok.", [])
        st.markdown("<div class='v2bos'>Veri birikince burası dolacak.</div>",
                    unsafe_allow_html=True)
        return
    g = d["genel"]
    _sayfa_basligi(
        "İnceleme",
        "Kayıp modelden mi, pazardan mı, veriden mi geliyor — üçü ayrılır.",
        [{"ad": "Kapanmış bahis", "deger": str(g["n"])},
         {"ad": "İsabet", "deger": _pct(g["hit"])},
         {"ad": "Getiri", "deger": ("+" if g["roi"] >= 0 else "−") +
          _num(abs(g["roi"]) * 100, 1) + "%",
          "cls": ("ps" if g["roi"] >= 0 else "ng")}])

    sek = _sekmeler("inceleme",
                    ["Model", "Trade", "Kayıp Anatomisi", "Gerekçe Defteri"])

    if sek == "Model":
        st.markdown(
            "<div class='v2mb'><b>Karar:</b> modelin ürettiği olasılığa "
            "güvenilir mi? Kalibrasyon <i>“model %X dediğinde gerçekten %X mi "
            "oluyor”</i>u, edge geçerliliği <i>“yüksek edge gerçekten daha iyi "
            "mi”</i>yi sorar. İkisi de hayır derse sorun modeldedir; evet derse "
            "kaybı başka yerde aramak gerekir.</div>", unsafe_allow_html=True)
        kr = []
        for k in d["kal"]:
            if k.get("n", 0) < 5:
                kr.append([k["ad"], str(k.get("n", 0)), "—", "—", "—"])
                continue
            f = k["fark"]
            kr.append([k["ad"], str(k["n"]), _pct(k["tah"]), _pct(k["ger"]),
                       "<span class='" + ("dp" if abs(f) <= 0.05 else "dm") +
                       "'>" + _sgn(f) + "</span>"])
        er = []
        for e in d["eb"]:
            er.append([e["ad"], str(e["n"]), _sgn(e["e"]),
                       "<span class='" + ("dp" if e["roi"] >= 0 else "dm") +
                       "'>" + ("+" if e["roi"] >= 0 else "−") +
                       _num(abs(e["roi"]) * 100, 1) + "%</span>"])
        # ⚠️ Kalibrasyon sapması YÖNLÜ mü, dağınık mı? Tablo tüm bantları
        # gösteriyordu ama hüküm yoktu. Üretimde bantların hepsi aynı yöne
        # sapıyordu (model %64,6 diyor, gerçek %69,2) — bu rastgele hata
        # değil SİSTEMATİK KAYMA'dır ve tek bir düzeltmeyle giderilebilir.
        # Dağınık sapma başka bir sorundur; ikisini ayırmak gerekir.
        _ge = [k for k in d["kal"] if k.get("n", 0) >= 20]
        _kal_h = ""
        if len(_ge) >= 3:
            _art = sum(1 for k in _ge if k["fark"] > 0.02)
            _eks = sum(1 for k in _ge if k["fark"] < -0.02)
            _ort = sum(k["fark"] * k["n"] for k in _ge) / sum(k["n"] for k in _ge)
            if _art >= len(_ge) - 1 and _art >= 3:
                _b, _c = "SİSTEMATİK — DÜŞÜK TAHMİN", "ng"
                _m = ("Ölçülen bantların neredeyse hepsinde gerçek, tahminden "
                      "<b>yüksek</b> çıkıyor (ağırlıklı ortalama <b>" +
                      _sgn(_ort) + "</b>). Bu rastgele hata değil, <b>tek "
                      "yönlü kayma</b> — model kendi olasılığını sistematik "
                      "olarak düşük söylüyor. Sistematik kayma tek bir "
                      "düzeltmeyle giderilebilir; dağınık hata giderilemez.")
            elif _eks >= len(_ge) - 1 and _eks >= 3:
                _b, _c = "SİSTEMATİK — YÜKSEK TAHMİN", "ng"
                _m = ("Ölçülen bantların neredeyse hepsinde gerçek, tahminden "
                      "<b>düşük</b> çıkıyor (ağırlıklı ortalama <b>" +
                      _sgn(_ort) + "</b>). Model kendine fazla güveniyor — "
                      "bu, sahte edge üretmenin en yaygın yoludur.")
            else:
                _b, _c = "DAĞINIK", ""
                _m = ("Sapmalar tek yöne gitmiyor (ağırlıklı ortalama <b>" +
                      _sgn(_ort) + "</b>). Tek bir kaydırmayla düzelmez; "
                      "sorun modelin <b>biçiminde</b>, kalibrasyonunda değil.")
            _kal_h = ("<div class='v2card' style='margin-top:var(--s3);'>"
                      "<div class='v2head'><h2>Hüküm — kalibrasyon</h2>"
                      "<div class='hint'>sapma yönlü mü</div></div>"
                      "<div class='v2body'><div class='ro big'>"
                      "<span>Sapma</span><b class='" + _c + "'>" + _b +
                      "</b></div><div class='vd' "
                      "style='margin-top:var(--s3);'>" + _m + "</div>"
                      "</div></div>")
        c1, c2 = st.columns([1, 1], gap="medium")
        with c1:
            st.markdown(_mini("Kalibrasyon",
                              "model %X dediğinde gerçekten %X mi oluyor",
                              ["Model bandı", "n", "Tahmin", "Gerçek", "Fark"],
                              kr) + _kal_h, unsafe_allow_html=True)
        with c2:
            st.markdown(_mini("Edge geçerliliği",
                              "yüksek edge gerçekten daha iyi mi",
                              ["Dilim", "n", "Ort. edge", "Getiri"], er),
                        unsafe_allow_html=True)

        # ── HÜKÜM ────────────────────────────────────────────────
        # ⚠️ Denetim bulgusu K1: bu tablo üretimde şunu gösteriyordu —
        #   Q1 (edge −5,5p) → +%1,2   ·   Q5 (edge +4,5p) → −%7,9
        # yani edge sıralaması TERS. Sayfa "kayıp modelden mi" diye
        # soruyordu, cevap tablonun içindeydi ve HİÇBİR hüküm etiketi
        # yoktu: renk yok, uyarı yok, k ölçümüyle bağ yok. Bir bulguyu
        # göstermek onu söylemek değildir.
        _eb = d["eb"]
        if len(_eb) >= 3:
            _ust, _alt = _eb[-1], _eb[0]
            _n = sum(int(x["n"] or 0) for x in _eb)
            _acik = _ust["roi"] - _alt["roi"]          # Q5 − Q1
            # sıralama tutarlılığı: ardışık dilimler arası artış sayısı
            _artan = sum(1 for i in range(len(_eb) - 1)
                         if _eb[i + 1]["roi"] > _eb[i]["roi"])
            _oran = _artan / (len(_eb) - 1)
            if not _olculebilir(_n, 200):
                _bas, _cls = "ÖLÇÜLEMEZ", ""
                _mtn = _esik_notu(_n, 200)
            elif _acik <= -0.03:
                _bas, _cls = "TERS ÇALIŞIYOR", "ng"
                _mtn = ("En <b>düşük</b> edge dilimi (" + _sgn(_alt["e"]) +
                        ") <b>" + ("+" if _alt["roi"] >= 0 else "−") +
                        _num(abs(_alt["roi"]) * 100, 1) + "%</b> getiriyor; "
                        "en <b>yüksek</b> dilim (" + _sgn(_ust["e"]) +
                        ") <b>" + ("+" if _ust["roi"] >= 0 else "−") +
                        _num(abs(_ust["roi"]) * 100, 1) + "%</b>. Aradaki "
                        "fark <b>" + _num(abs(_acik) * 100, 1) + " puan</b> ve "
                        "yön yanlış. Model gürültü üretmiyor — <b>ters yönde "
                        "bilgi taşıyor</b>. Bu haldeyken yüksek edge'e göre "
                        "seçim yapmak, sistematik olarak kötü tarafı seçmektir.")
            elif _acik >= 0.03 and _oran >= 0.6:
                _bas, _cls = "ÇALIŞIYOR", "ps"
                _mtn = ("Yüksek edge dilimi düşük dilimi <b>" +
                        _num(_acik * 100, 1) + " puan</b> geçiyor ve sıralama "
                        "tutarlı. Edge bilgi taşıyor.")
            else:
                _bas, _cls = "AYRIŞMIYOR", ""
                _mtn = ("Diliminler arasındaki fark <b>" +
                        _num(abs(_acik) * 100, 1) + " puan</b> — bu örneklemde "
                        "rastlantıdan ayrılamıyor. Edge ne işe yarıyor ne "
                        "zarar veriyor; <b>sıralama olarak kullanılamaz</b>.")
            st.markdown(
                "<div class='v2card' style='margin-top:var(--s4);'>"
                "<div class='v2head'><h2>Hüküm — edge sıralaması</h2>"
                "<div class='hint'>n=" +
                "{:,}".format(_n).replace(",", ".") + " kapanmış bahis</div>"
                "</div><div class='v2body'>"
                "<div class='ro big'><span>Edge sıralaması</span>"
                "<b class='" + _cls + "'>" + _bas + "</b></div>"
                "<div class='vd' style='margin-top:var(--s3);'>" + _mtn +
                "</div>"
                + (("<div class='vd' style='margin-top:var(--s3);'>"
                    "<b>Terslik her yerde mi, bir dilimde mi?</b> Pazar "
                    "bazında alt ve üst üçlük ayrı ölçüldü — <b>fark "
                    "pozitif olmalıydı</b> (yüksek edge daha iyi getirmeli). "
                    "Negatif olan her satır o pazarda edge'in ters "
                    "çalıştığını söyler."
                    "<table class='v2' style='margin-top:9px;'><thead><tr>"
                    "<th>Pazar</th><th class='r'>n</th>"
                    "<th class='r'>Alt üçlük</th><th class='r'>Üst üçlük</th>"
                    "<th class='r'>Fark</th></tr></thead><tbody>"
                    + "".join(
                        "<tr><td>" + str(x["ad"]) + "</td>"
                        "<td class='r n'>" + str(x["n"]) + "</td>"
                        "<td class='r n'>" + ("+" if x["alt"] >= 0 else "−") +
                        _num(abs(x["alt"]) * 100, 1) + "%</td>"
                        "<td class='r n'>" + ("+" if x["ust"] >= 0 else "−") +
                        _num(abs(x["ust"]) * 100, 1) + "%</td>"
                        "<td class='r'><span class='" +
                        ("dp" if x["fark"] >= 0 else "dm") + "'>" +
                        ("+" if x["fark"] >= 0 else "−") +
                        _num(abs(x["fark"]) * 100, 1) + "p</span></td></tr>"
                        for x in d.get("eb_kirilim", []))
                    + "</tbody></table></div>")
                   if d.get("eb_kirilim") else "") +
                "<div class='vd' style='margin-top:var(--s3);'>"
                "<b>Bunu başka ölçümler de söylüyor.</b> Beceri katsayısı "
                "<b>k</b> güven aralığı sıfırı içeriyorsa edge sıralaması "
                "bilgi taşımıyor demektir (Ölçüm Defteri › K_BECERİ), ve "
                "<b>rastgele kontrol ajanı JOKER</b> güven tablosunda kaçıncı "
                "sıradaysa o kadar ajan rastgeleden ayrışamıyor demektir "
                "(Karar Masası › Ajan Güveni). Bağımsız ölçümler aynı yeri "
                "gösteriyorsa bu bir rastlantı değil, <b>modelin şu anki "
                "halidir</b>.</div>"
                "</div></div>", unsafe_allow_html=True)

    elif sek == "Trade":
        st.markdown(
            "<div class='v2mb'><b>Karar:</b> doğru olasılıkla yanlış yerde mi "
            "oynuyoruz? Aynı model farklı pazarda ve farklı kupon türünde "
            "farklı sonuç verir — çünkü <b>marj her yerde aynı değil</b>. Bu "
            "tablolar nereden çıkılacağını söyler.</div>",
            unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 1, 1], gap="medium")
        for kol, (bas, anh, ip) in zip(
                (c1, c2, c3),
                (("Pazar", "pazar", "hangi pazarda iyiyiz"),
                 ("Kupon türü", "tur", "tek mi kombine mi"),
                 ("Lig", "lig", "nerede oynuyoruz"))):
            sat = []
            for x in d[anh]:
                sat.append([str(x["ad"])[:16], str(x["n"]), _pct(x["hit"]),
                            "<span class='" +
                            ("dp" if x["roi"] >= 0 else "dm") + "'>" +
                            ("+" if x["roi"] >= 0 else "−") +
                            _num(abs(x["roi"]) * 100, 1) + "%</span>"])
            with kol:
                st.markdown(_mini(bas, ip, ["", "n", "İsabet", "Getiri"], sat),
                            unsafe_allow_html=True)

    elif sek == "Kayıp Anatomisi":
        st.markdown(
            "<div class='v2mb'><b>Karar:</b> kombine kaybettiğinde hangi ayak "
            "düşürdü? Zayıf halka belliyse o ayağı kupondan çıkarmak "
            "<b>ölçülebilir</b> bir iyileştirmedir. Tarihsel evrende altı "
            "hücrenin altısında zayıf halka <b>sonuç (1X2) ayağıydı</b> — "
            "kaybın yarısı gol ayağı tuttuğu hâlde geliyordu.</div>",
            unsafe_allow_html=True)
        a = d["anat"]
        if a["n"] >= 1:
            top = a["n"]
            sat = [[ad, str(a[k]), _pct(a[k] / top)]
                   for k, ad in (("sonuc", "Sonuç ayağı düşürdü"),
                                 ("gol", "Gol/KG ayağı düşürdü"),
                                 ("iki", "İkisi birden"))]
            # ⚠️ Eskiden: zayif = "SONUÇ" if sonuc >= gol else "GOL/KG"
            # `>=` beraberliği SESSİZCE SONUÇ'a yazıyordu. Üretimde 4–4
            # eşitlikte "ZAYIF HALKA: SONUÇ (1X2)" hükmü çıktı — yazı-tura.
            # Eşik de 5'ti: Ölçüm Defteri n=17'yi ÖLÇÜLEMEZ sayarken burası
            # n=15'te kesin konuşuyordu. Artık ürünün TEK eşiği geçerli.
            ayristi = _ayrisiyor_mu(a["sonuc"], a["gol"], top)
            olculur = _olculebilir(top)
            if ayristi:
                zayif = ("SONUÇ (1X2)" if a["sonuc"] > a["gol"] else "GOL/KG")
                hkm_cls, ipucu = "ng", "zayıf halka"
                gerekce = ("Bu ayak kupondan çıkarılırsa kayıpların <b>" +
                           _pct(max(a["sonuc"], a["gol"]) / top) + "</b>'i "
                           "önlenebilirdi — diğer ayak zaten tutmuştu.")
            elif olculur:
                zayif = "AYRIŞMIYOR"
                hkm_cls, ipucu = "", "hüküm yok"
                gerekce = ("İki ayak <b>" + str(a["sonuc"]) + "–" +
                           str(a["gol"]) + "</b> ile ayrışmıyor. Bu veriyle "
                           "bir ayağı suçlamak <b>yazı-tura atmaktır</b>; "
                           "fark rastlantıdan ayrılamıyor.")
            else:
                zayif = "ÖLÇÜLEMEZ"
                hkm_cls, ipucu = "", "örneklem yetersiz"
                gerekce = _esik_notu(top)
            c1, c2 = st.columns([1, 1], gap="medium")
            with c1:
                st.markdown(
                    _mini("Hangi ayak düşürdü", str(top) + " kombine kaybı",
                          ["Ayak", "n", "Pay"], sat), unsafe_allow_html=True)
            with c2:
                st.markdown(
                    "<div class='v2card'><div class='v2head'><h2>Hüküm</h2>"
                    "<div class='hint'>" + ipucu + "</div></div>"
                    "<div class='v2body'><div class='ro big'>"
                    "<span>Zayıf halka</span><b class='" + hkm_cls + "'>" +
                    zayif + "</b></div>"
                    "<div class='vd' style='margin-top:var(--s3);'>" +
                    gerekce + "</div></div></div>", unsafe_allow_html=True)
        else:
            st.markdown(
                "<div class='v2bos'>Henüz kombine kaybı yok.</div>",
                unsafe_allow_html=True)

    else:
        st.markdown(
            "<div class='v2mb'><b>Karar yok — burası hafıza.</b> Her bahsin "
            "<b>neden</b> seçildiği ve sonra <b>ne kadar yaklaştığı</b>. Kupon "
            "sonucu ikilidir (tuttu/tutmadı) ama bilgi süreklidir: “bir gol "
            "eksik” ile “3-0 ıska” aynı şey değildir.</div>",
            unsafe_allow_html=True)
        if d["defter"]:
            sat = []
            for x in d["defter"]:
                sat.append(
                    ["<span class='ag'>" + _rozet(x["p"]) +
                     str(x["h"])[:15] + " — " + str(x["a"])[:15] + "</span>"
                     "<span class='sb'>" + str(x["rsn"] or "—")[:120] +
                     "</span>",
                     "<span class='" + ("dp" if x["won"] else "dm") + "'>" +
                     str(x["pk"])[:16] + "</span>",
                     "<span class='sb'>" + str(x["pm"] or "—")[:70] +
                     "</span>"])
            st.markdown(
                _mini("Gerekçe Defteri", "neden seçildi · ne kadar yaklaştı",
                      ["Maç ve gerekçe", "Seçim", "Sonra ne oldu"], sat),
                unsafe_allow_html=True)
        else:
            st.markdown("<div class='v2bos'>Gerekçe kaydı yok.</div>",
                        unsafe_allow_html=True)

# Menü etiketleri sade: aktif durumdaki amber şerit zaten yönlendiriyor,
# emoji sadece gürültü ekliyordu.
# ── BİLGİ MİMARİSİ — SOL PANEL (SaaS) · 19.09.2026 ─────────────
# Kullanıcı: "Sol SaaS paneli yap — kimliğine, görünümüne ve navigasyona
# uygun; eklemeleri oraya mantık dahilinde ekleyelim, feature set olarak
# görürüz. Ürün mantığına girmiyor böyle."
#
# Önceki ray ana akışta bir SÜTUNDU ve form düğmeleri gibi duruyordu.
# Artık Streamlit'in YERLEŞİK çok sayfalı gezinmesi (st.navigation):
#   · her sayfanın kendi ADRESİ var — tarayıcıda geri/ileri çalışır,
#     bir sayfa bağlantısı paylaşılabilir;
#   · oturum KORUNUR — sepet sayfa değişince kaybolmaz;
#   · bölümler ÖZELLİK SETİDİR: MASA · TAKIMLAR · PORTFÖY · ANALİZ · SİSTEM.
# Kenar çubuğu masaüstünde KAPATILAMAZ (eski ders: kullanıcı kapatıyor,
# gezinme ekrandan kayboluyordu); mobilde standart açılır çekmece.
# Hikâye ilkesi korundu: her sayfa bir SORUYA cevap verir, başlık o soruyu
# yazar, alttaki gezinme bir sonraki soruya devreder.
# ── SÜPER TOTO — ayrı ürün, ayrı veri (09_TOTO) ─────────────────
# Kullanıcı (19.09.2026): "SÜPER TOTO sayfası ve panelde ayrı bir yer…
# sakın karıştırma, BetAgents'la birbirini etkilemeyecekler." Sayfa
# gövdeleri 09_TOTO/toto_panel.py'de, veri yalnız toto_* tablolarında.
# Burada yalnız gezinme girişi var: Toto tarafında bir hata olursa YALNIZ
# o sayfa bir uyarı gösterir; BetAgents sayfaları etkilenmez.
_TOTO_DIZIN = str(THIS_DIR.parent / "09_TOTO")


_CANLI_DIZIN = str(THIS_DIR.parent / "10_CANLI")


def _toto_sayfa(ad: str, modul: str = "toto_panel", dizin: str | None = None):
    def _f():
        try:
            for _d in (dizin or _TOTO_DIZIN,):
                if _d not in sys.path:
                    sys.path.append(_d)           # SONA: ad çakışmasında BetAgents modülü kazanır
            import importlib
            getattr(importlib.import_module(modul), ad)(_sayfa_basligi)
        except Exception as _e:
            import html as _h
            st.markdown("<div class='v2bos'>Toto sayfası şu an çizilemedi — BetAgents etkilenmez. "
                        "Ayrıntı: " + _h.escape(f"{type(_e).__name__}: {_e}")[:240] + "</div>",
                        unsafe_allow_html=True)
    _f.__name__ = modul.split("_")[0] + "_" + ad
    return _f


SAYFA_TANIM = [
    ("VIBE", [
        ("Vibe Betting", _toto_sayfa("vibe", "vibe_panel"), ":material/auto_awesome:", "vibe",
         "Sor — veriye bakıp cevaplasın.")]),
    ("MASA", [
        ("Karar Masası", page_desk, ":material/space_dashboard:", "masa",
         "Kime güvenirim, bugün ne var?"),
        ("Sepet", page_sepet, ":material/shopping_basket:", "sepet",
         "Ne kuruyorum, kaça mal oluyor?")]),
    ("TAKIMLAR", [
        ("Lig Tablosu", page_lig, ":material/leaderboard:", "lig",
         "Kim önde, kim geride?"),
        ("Mavi Takım", page_mavi, ":material/shield:", "mavi",
         "Sinyal motoru sahada ne yapıyor?"),
        ("Kırmızı Takım", page_kirmizi, ":material/local_fire_department:",
         "kirmizi", "Kombine pazarında değer var mı?"),
        ("Turuncu Takım", page_turuncu, ":material/science:", "turuncu",
         "Bağımsız skor modeli sahada ne yapıyor?"),
        ("Ajan Dosyası", page_ajan, ":material/badge:", "ajan",
         "Bu ajan neyi, neden oynadı?")]),
    ("PORTFÖY", [
        ("Kasa ve Getiri", page_kasa, ":material/show_chart:", "kasa",
         "Para büyüyor mu, neye göre?"),
        ("OPUS 5", page_opus, ":material/account_balance_wallet:", "opus",
         "Gerçekte ne oynadım?")]),
    ("ANALİZ", [
        ("İnceleme", page_inceleme, ":material/troubleshoot:", "inceleme",
         "Neden kaybediyorum?"),
        ("Çakışma ve Arşiv", page_cakisma, ":material/join_inner:",
         "cakisma", "Kaç bağımsız görüş var?")]),
    ("SÜPER TOTO", [
        ("Toto · Bu Hafta", _toto_sayfa("bu_hafta"), ":material/sports_soccer:", "toto",
         "Bu hafta Toto'da ne oynayalım, neden?"),
        ("Toto · Ajan Pazarı", _toto_sayfa("ajan_pazari"), ":material/storefront:", "toto-pazar",
         "Hangi ajanın sesi ne kadar, neden?"),
        ("Toto · Geçmiş Test", _toto_sayfa("gecmis_test"), ":material/history:", "toto-test",
         "Bu sistemle geçmişte oynasaydık ne olurdu?"),
        ("Toto · Arşiv", _toto_sayfa("arsiv"), ":material/inventory_2:", "toto-arsiv",
         "Ne oynadık, ne oldu, ne öğrendik?")]),
    # CANLI — üçüncü ürün, kendi tabloları (cl_*) ve kendi toplayıcısı. Toto ve
    # BetAgents'ı yalnız OKUR; hata olursa yalnız bu sayfa uyarı gösterir.
    ("CANLI", [
        ("Canlı Maçlar", _toto_sayfa("canli_maclar", "canli_panel", _CANLI_DIZIN),
         ":material/sensors:", "canli", "Sahada ne oluyor, fiyat ne diyor, model ne diyor?")]),
    ("SİSTEM", [
        ("Ölçüm Defteri", page_defter, ":material/menu_book:", "defter",
         "Hangi bulgu hâlâ ayakta?"),
        ("Sağlık", page_sistem, ":material/monitor_heart:", "saglik",
         "Sistem ayakta mı, veri sağlam mı?")]),
]
# sayfa adı -> {bölüm, soru}; PAGES okuma sırasını taşır (alt gezinme)
SORU: dict = {}
PAGES: dict = {}
for _b, _ler in SAYFA_TANIM:
    for _x in _ler:
        SORU[_x[0]] = {"perde": _b, "soru": _x[4]}
        PAGES[_x[0]] = _x[1]
_SAYFA_NESNE: dict = {}
_MARKA_DIZIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "marka")


def _git(ad: str) -> None:
    """Programla sayfa değiştir — oturum (sepet) korunur."""
    st.session_state["v2_page"] = ad
    p = _SAYFA_NESNE.get(ad)
    if p is not None:
        st.switch_page(p)
    st.rerun()


def _sarmala(ad: str, fn):
    """Sayfa fonksiyonunu sar: kanonik adı oturuma yaz (başlık ve alt
    gezinme onu okur), sayfayı çiz, alt gezinmeyi ekle."""
    def _sayfa():
        st.session_state["v2_page"] = ad
        fn()
        _gezinme_alt()
    _sayfa.__name__ = "sayfa_" + "".join(c for c in ad.lower() if c.isalnum())
    return _sayfa


def _kenar_durum() -> None:
    """Kenar çubuğunun dibi — canlı durum. Eskiden üstte koyu bir şeritti;
    marka kenar çubuğunun başına (st.logo), durum dibine taşındı."""
    r = load_rail()
    st.sidebar.markdown(
        "<div class='kc-durum'>"
        "<div class='kc-baslik'>Canlı · <b>" + r["kaynak"] + "</b></div>"
        "<div class='kc-sat'><b>" + str(r["acik"]) + "</b> açık · <b>" +
        "{:,}".format(r["kapali"]).replace(",", ".") + "</b> kapanmış · <b>" +
        _isabet_toplam(kisa=True) + "</b> isabet</div></div>",
        unsafe_allow_html=True)


def _db_kapali(hata: Exception) -> None:
    """Veritabanı yanıt vermiyor — BEYAZ SAYFA DEĞİL, teşhis göster.

    ⚠️ 12 Eylül 2026: Railway proxy'sinin TCP portu açık cevap veriyordu
    ama PostgreSQL el sıkışması hiç dönmüyordu. Uygulama dakikalarca
    bekledi ve kullanıcı bembeyaz bir sayfa gördü — "çalışan sistemin
    içine ettik" hissinin kaynağı buydu. Oysa KOD sağlamdı; ulaşılamayan
    şey veritabanıydı. Bir ürün, bağımlılığı düştüğünde SUSMAMALI."""
    import re as _re
    _u = ""
    try:
        import db as _d
        _u = _re.sub(r":[^:@]+@", ":***@", _d.database_url())
    except Exception:
        pass
    st.markdown(
        "<div class='v2ust'><div class='marka'><div class='mark'>BA</div>"
        "<div><b>BetAgents</b><span>Desk · v2</span></div></div></div>"
        "<div class='v2card' style='max-width:780px;margin:var(--s6) auto;'>"
        "<div class='v2head'><h2>Veritabanına ulaşılamıyor</h2>"
        "<div class='hint'>uygulama ayakta · veri yok</div></div>"
        "<div class='v2body'>"
        "<div class='dq'><b>Kod çalışıyor, veritabanı cevap vermiyor.</b> "
        "Bu bir uygulama hatası değil — bağlantı kurulamadı. Sayfa "
        "beklemek yerine bunu söylüyor.</div>"
        "<div class='vd' style='margin-top:var(--s3);'>"
        "<b>Ne kontrol edilmeli</b><br>"
        "1 · Railway panelinde <b>Postgres servisi ayakta mı</b><br>"
        "2 · Bağlantı kotası dolmuş olabilir — servisi yeniden başlatmak "
        "boştaki bağlantıları serbest bırakır<br>"
        "3 · <code>DATABASE_URL</code> değişkeni değişti mi</div>"
        "<div class='sb' style='margin-top:var(--s3);'>Denenen: " +
        (_u or "—") + "<br>Hata: " + str(hata)[:160] + "</div>"
        "</div></div>", unsafe_allow_html=True)


def main() -> None:
    st.markdown(V2_CSS, unsafe_allow_html=True)
    # Veri katmanı ayakta mı — SAYFA ÇİZİLMEDEN önce tek ucuz sorgu.
    # Düşükse teşhis göster ve çık; her panelin ayrı ayrı zaman aşımına
    # uğramasını beklemek dakikalar sürüyordu.
    try:
        _conn().execute("SELECT 1").fetchall()
    except Exception as _e:
        _conn.clear()
        _db_kapali(_e)
        return
    if "v2_page" not in st.session_state:
        st.session_state["v2_page"] = "Karar Masası"
    try:
        st.logo(os.path.join(_MARKA_DIZIN, "logo.svg"), size="large",
                icon_image=os.path.join(_MARKA_DIZIN, "logo-ikon.svg"))
    except Exception:
        pass
    sp = _sepet()
    bolumler: dict = {}
    _SAYFA_NESNE.clear()
    for bolum, ogeler in SAYFA_TANIM:
        liste = []
        for ad, fn, ikon, url, _soru in ogeler:
            baslik = ad + ("  ·  " + str(len(sp)) if ad == "Sepet" and sp else "")
            pg = st.Page(_sarmala(ad, fn), title=baslik, icon=ikon,
                         url_path=url, default=(ad == "Karar Masası"))
            _SAYFA_NESNE[ad] = pg
            liste.append(pg)
        bolumler[bolum] = liste
    nav = st.navigation(bolumler, position="sidebar", expanded=True)
    _kenar_durum()
    nav.run()


if __name__ == "__main__":
    main()
