"""
SWAT · KAYNAK — ilk yarı skorunu dışarıdan getir
=================================================
Sağlayıcıdan BAĞIMSIZ tasarlandı: `cek_fikstur()` hangi sağlayıcı
yapılandırılmışsa onu kullanır. Bugün API-Football, yarın SoccersAPI
olabilir; SWAT'ın geri kalanı değişmez.

⚠️ MALİYET DENGESİ — tasarımı belirleyen şey bu
API-Football'da iki ayrı uç var ve fiyatları ÇOK farklı:

    /fixtures?league=X&season=Y   → BİR çağrıda bütün sezon.
                                     İçinde score.halftime ZATEN var.
    /fixtures/statistics?fixture= → MAÇ BAŞINA bir çağrı.
                                     Şut/korner/topla oynama burada.

Ücretsiz katman günde 100 istek. Yani:
  · İlk yarı skoru pratikte BEDAVA (lig-sezon başına 1 çağrı).
  · Maç istatistiği pahalı (10.000 maç = 10.000 çağrı = 100 gün).

Bu yüzden SWAT'ın 1. aşaması YALNIZ ilk/ikinci yarı pazarlarıdır.
Şut-korner istatistikleri ikinci aşama ve ayrı bir bütçe kararı.

⚠️ EŞLEŞTİRME
Sağlayıcının maçı ile bizim maçımız ortak kimlik taşımıyor
(matches_v2.external_id_af %0 dolu). Eşleştirme tarih + takım adı
benzerliğiyle yapılır ve EŞİĞİ GEÇMEYEN maç ATLANIR — yanlış eşleşmiş
bir ilk yarı skoru, eksik skordan çok daha kötüdür: bahis kapanır,
sayı üretir, ama yanlış.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parent
for _p in (str(KOK), str(KOK.parent / "02_VERI"), str(KOK.parent / "10_CANLI")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

AF_HOST = "v3.football.api-sports.io"
# Ad benzerliği eşiği. canli_kaynak'ta aynı iş için 0,72 kullanılıyor;
# burada DAHA YÜKSEK, çünkü orada hata canlı ekranı bozar, burada ajanın
# karnesini kalıcı olarak yanlış yazar.
ESIK = 0.80

KALAN: int | None = None     # sağlayıcının kendi günlük sayacı
SON_HATA: str = ""


def _anahtar() -> str:
    """API-Football anahtarı — ortam değişkeni, yoksa .env."""
    import os
    k = os.environ.get("API_FOOTBALL_KEY", "").strip()
    if k:
        return k
    for aday in (KOK.parent / ".env", KOK.parent.parent / ".env"):
        try:
            for satir in open(aday, encoding="utf-8"):
                if satir.strip().startswith("API_FOOTBALL_KEY="):
                    return satir.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            continue
    return ""


def _iste(yol: str, par: dict) -> dict | None:
    """Tek istek. Kota sayacını başlıktan OKUR, tahmin etmez."""
    global KALAN, SON_HATA
    k = _anahtar()
    if not k:
        SON_HATA = "API_FOOTBALL_KEY yok (.env ya da ortam değişkeni)"
        return None
    q = "&".join(f"{a}={b}" for a, b in par.items())
    r = urllib.request.Request(f"https://{AF_HOST}/{yol}?{q}",
                               headers={"x-apisports-key": k})
    try:
        with urllib.request.urlopen(r, timeout=30) as x:
            kal = x.headers.get("x-ratelimit-requests-remaining")
            if kal is not None:
                try:
                    KALAN = int(kal)
                except ValueError:
                    pass
            d = json.loads(x.read())
    except urllib.error.HTTPError as e:
        SON_HATA = f"HTTP {e.code}"
        return None
    except Exception as e:
        SON_HATA = f"{type(e).__name__}: {str(e)[:90]}"
        return None
    # ⚠️ API-Football hatayı 200 ile döndürür; `errors` boş değilse
    # yanıt BOŞ gelir ve sessizce "veri yok" sanılır. Askıya alınmış
    # hesap tam olarak böyle görünüyor.
    hata = d.get("errors")
    if hata:
        SON_HATA = str(hata)[:160]
        return None
    SON_HATA = ""
    return d


def hesap_durumu() -> dict:
    """Hesap açık mı, kota ne? Bu çağrı kotadan DÜŞMEZ."""
    d = _iste("status", {})
    if d is None:
        return {"acik": False, "hata": SON_HATA}
    r = d.get("response") or {}
    return {"acik": True,
            "hesap": (r.get("account") or {}).get("email"),
            "plan": (r.get("subscription") or {}).get("plan"),
            "aktif": (r.get("subscription") or {}).get("active"),
            "kullanilan": (r.get("requests") or {}).get("current"),
            "gunluk": (r.get("requests") or {}).get("limit_day")}


def _say(v):
    try:
        return None if v is None else int(v)
    except (TypeError, ValueError):
        return None


def cek_fikstur(lig_id: int, sezon: int, gelecek: bool = True) -> list[dict]:
    """Bir lig-sezonun bütün maçları — TEK çağrı. İlk yarı skoru dahil.

    `gelecek=True` ise OYNANMAMIŞ maçlar da yazılır (skorsuz).

    ⚠️ Neden gelecek maçlar da gerekiyor: SWAT'ın hangi maçta oynayacağına
    karar vermesi için maçın KAPSANAN bir ligde olduğunu önceden bilmesi
    lazım. Lig kodumuz bunu söyleyemiyor (matches_v2.league_code %94
    'ALL' ya da boş). Bu yüzden SWAT'ın evreni "lig kodu şu" değil,
    "çektiğimiz lig-sezonlarda yer alan maç" olarak tanımlandı — açık,
    denetlenebilir ve bozuk lig koduna hiç bağlı değil.

    Oynanmamış maç skorsuz yazılır; sonuçlandırma zaten ilk yarı skoru
    dolu değilse bahsi kapatmaz, yani erken kapanma riski yok.
    """
    d = _iste("fixtures", {"league": lig_id, "season": sezon})
    if not d:
        return []
    out = []
    for f in (d.get("response") or []):
        fx, lg = f.get("fixture") or {}, f.get("league") or {}
        tm, sc = f.get("teams") or {}, f.get("score") or {}
        iy = sc.get("halftime") or {}
        ms = sc.get("fulltime") or {}
        durum = ((fx.get("status") or {}).get("short") or "").upper()
        bitti = durum in ("FT", "AET", "PEN")
        if not bitti:
            if not gelecek:
                continue
            # Devam eden maçın ilk yarısı doğru olsa bile maç sonu yok;
            # yarım skor yazmak doluluk ölçümünü yanıltır. Skorsuz yaz.
            iy, ms = {}, {}
        out.append({
            "kaynak": "api_football",
            "kaynak_id": str(fx.get("id")),
            "lig": str(lg.get("id")),
            "lig_ad": lg.get("name"),
            "sezon": str(lg.get("season")),
            "ev": (tm.get("home") or {}).get("name"),
            "dep": (tm.get("away") or {}).get("name"),
            "baslangic": fx.get("date"),
            "iy_ev": _say(iy.get("home")), "iy_dep": _say(iy.get("away")),
            "ms_ev": _say(ms.get("home")), "ms_dep": _say(ms.get("away")),
        })
    return out


# ----------------------------------------------------------------------
# EŞLEŞTİRME — sağlayıcının maçı ↔ bizim matches_v2 satırımız
# ----------------------------------------------------------------------
def _benzer(a: str, b: str) -> float:
    """Takım adı benzerliği. canli_kaynak'taki ölçüyü kullanır (tek
    kaynak); o içe aktarılamazsa yerel yedeğe düşer."""
    try:
        import canli_kaynak as CK
        return CK.benzer(a, b)
    except Exception:
        import difflib
        import unicodedata

        def n(s):
            s = unicodedata.normalize("NFKD", str(s or "").lower())
            return "".join(c for c in s if c.isalnum() or c == " ").strip()
        return difflib.SequenceMatcher(None, n(a), n(b)).ratio()


def esle(kaynak_maclar: list[dict], conn=None) -> list[dict]:
    """Sağlayıcı maçlarını matches_v2 ile eşleştir — tarih + ad benzerliği.

    ⚠️ Eşik altı ATLANIR. Yanlış eşleşen ilk yarı skoru, eksik skordan
    kötüdür: bahis kapanır, sayı üretir, ama yanlış — ve bunu hiçbir şey
    göstermez.
    """
    import db
    if not kaynak_maclar:
        return []
    kapat = conn is None
    conn = conn or db.connect()
    try:
        bizim = {}
        for r in conn.execute(
                "SELECT match_id, external_id_iddaa, home_team, away_team, "
                "       kickoff_utc FROM matches_v2 "
                "WHERE home_team IS NOT NULL").fetchall():
            m = dict(r) if not isinstance(r, (tuple, list)) else {
                "match_id": r[0], "external_id_iddaa": r[1],
                "home_team": r[2], "away_team": r[3], "kickoff_utc": r[4]}
            gun = str(m.get("kickoff_utc") or "")[:10]
            bizim.setdefault(gun, []).append(m)
    finally:
        if kapat:
            conn.close()

    out, atlanan = [], 0
    for k in kaynak_maclar:
        gun = str(k.get("baslangic") or "")[:10]
        adaylar = bizim.get(gun, [])
        en, skor = None, 0.0
        for m in adaylar:
            s = (_benzer(k["ev"], m["home_team"])
                 + _benzer(k["dep"], m["away_team"])) / 2.0
            if s > skor:
                en, skor = m, s
        if en is None or skor < ESIK:
            atlanan += 1
            continue
        out.append({**k, "mac_id": str(en["match_id"]),
                    "iddaa_id": str(en.get("external_id_iddaa") or ""),
                    "eslesme": round(skor, 3)})
    if atlanan:
        print(f"[swat] eşleşmeyen maç: {atlanan}/{len(kaynak_maclar)} "
              f"(eşik {ESIK})")
    return out


def kendi_testi() -> list[str]:
    """Ağsız: eşleştirme eşiği ve yanıt ayrıştırma."""
    hata = []
    # 1) Benzerlik ölçüsü makul mü
    if _benzer("Galatasaray", "Galatasaray SK") < 0.7:
        hata.append("aynı takım benzer sayılmadı")
    if _benzer("Galatasaray", "Fenerbahce") > 0.6:
        hata.append("farklı takımlar benzer sayıldı")
    # 2) Eşleştirme: aynı gün + benzer ad eşleşmeli, farklı gün ASLA
    import sqlite3
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE matches_v2 (match_id TEXT, external_id_iddaa TEXT,"
              " home_team TEXT, away_team TEXT, kickoff_utc TEXT)")
    c.execute("INSERT INTO matches_v2 VALUES ('7','99','Galatasaray',"
              "'Besiktas','2026-11-02T18:00:00')")
    c.row_factory = None
    k = [{"ev": "Galatasaray SK", "dep": "Besiktas JK",
          "baslangic": "2026-11-02T18:00:00+00:00", "iy_ev": 1, "iy_dep": 0},
         {"ev": "Galatasaray SK", "dep": "Besiktas JK",
          "baslangic": "2026-11-09T18:00:00+00:00", "iy_ev": 2, "iy_dep": 2}]
    r = esle(k, c)
    if len(r) != 1:
        hata.append(f"1 maç eşleşmeliydi, {len(r)}")
    elif r[0]["mac_id"] != "7":
        hata.append("yanlış maça eşleşti")
    # 3) Alakasız takım eşleşmemeli
    r2 = esle([{"ev": "Real Madrid", "dep": "Barcelona",
                "baslangic": "2026-11-02T18:00:00+00:00"}], c)
    if r2:
        hata.append("alakasız takım eşleşti — yanlış skor yazılırdı")
    c.close()
    return hata


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    h = kendi_testi()
    print("kendi testi:", "TEMİZ" if not h else f"{len(h)} sorun")
    for x in h:
        print("  ", x)
    print("\nhesap durumu:", hesap_durumu())
