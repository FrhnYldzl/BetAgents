"""
HABER KATMANI — maç bağlamını topla, JOURNAL'a yaz
====================================================
Kullanıcı (15.11.2026): *"Denetçi katmanının içine haber akışı katmanı
ekle — o maç artık net kupona da girecek ya, olasılığı etkileyen oyuncu
vs. gibi konular eklenir, journal zenginleşir, karar katmanı
güçlenir. İleride ölçekli bu dataları çekeriz."*

⚠️ HABER OLASILIĞA DOKUNMAZ — tasarım kararı, eksiklik değil
Sakatlık/kadro haberi çıktığında fiyat ÇOKTAN hareket etmiş olabilir.
Haberi olasılığa katmak, aynı bilgiyi iki kez saymak olur ve kuponun
şansını yanlış yükseltir. Bu projede aynı sınıftan hata üç kez yapıldı:
  · paper_bets.edge = marjın kendisiydi, kenar sanıldı
  · ham 1/oran olasılık sanıldı (3 ayakta 17 puan şişme)
  · kasa'nın ham-tabanlı kenarı marjsız tabana eklendi (çift sayım)

Doğru sıra: TOPLA → ÖLÇ → BAĞLA.
  1. aşama (bu modül): haberi `mac_haber` tablosuna yaz. Karar YOK.
  2. aşama: haber çıkan maçlar gerçekten farklı mı davranıyor — fiyatın
     ötesinde bilgi taşıyor mu? Ölç.
  3. aşama: ölçüm olumluysa karar katmanına bağla.

Bu modül YALNIZ 1. aşamadır.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import db  # noqa: E402

# ⚠️ Model adı DOĞRULANDI (15.11.2026): "gemini-2.0-flash" HTTP 404
# veriyor — bu anahtarın erişebildiği modeller arasında yok. Mevcut
# listeden seçildi. Model adı varsayılmaz, /models ucundan okunur.
MODEL = "gemini-2.5-flash"
UC = ("https://generativelanguage.googleapis.com/v1beta/models/"
      "{model}:generateContent")
# Dış API'ye ardışık hızlı istek ATILMAZ. Bu projede API-Football hesabı
# tam bu yüzden askıya alındı (bkz. dis-api-hiz-siniri notu).
ASGARI_ARALIK_SN = 2.0
_SON = 0.0
DURDURULDU = False
SON_HATA = ""


def _anahtar() -> str:
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if k:
        return k
    for aday in (THIS_DIR.parent / ".env", THIS_DIR / ".env"):
        try:
            for s in open(aday, encoding="utf-8-sig"):
                if s.strip().startswith("GEMINI_API_KEY="):
                    return s.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            continue
    return ""


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def kur(conn=None) -> None:
    kapat = conn is None
    conn = conn or db.connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mac_haber (
                mac_id     TEXT,
                ts         TEXT,
                kaynak     TEXT,
                ozet       TEXT,
                etki       TEXT,
                ham        TEXT,
                PRIMARY KEY (mac_id, ts)
            )""")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_mh_mac "
                     "ON mac_haber (mac_id)")
        conn.commit()
    finally:
        if kapat:
            conn.close()


def _sor(soru: str) -> dict | None:
    """Gemini'ye tek istek — hız sınırlı, hatada durur."""
    global _SON, DURDURULDU, SON_HATA
    if DURDURULDU:
        SON_HATA = "durduruldu (önceki hata)"
        return None
    k = _anahtar()
    if not k:
        SON_HATA = "GEMINI_API_KEY yok"
        return None
    import time as _t
    bekle = ASGARI_ARALIK_SN - (_t.time() - _SON)
    if bekle > 0:
        _t.sleep(bekle)
    _SON = _t.time()
    # ⚠️ GOOGLE ARAMA ZORUNLU. Düz LLM çağrısının internete erişimi yok;
    # gelecek haftaki bir maçın sakatlık haberini bilemez ve doğru olarak
    # "BİLGİ YOK" der (ölçüldü 15.11.2026). Haber katmanının anlamı
    # ARAMADAN gelir, modelin hafızasından değil.
    # maxOutputTokens yüksek: 2.5-flash düşünme belirteçleri harcıyor,
    # 400'de cevap yarıda kesiliyordu.
    govde = json.dumps({
        "contents": [{"parts": [{"text": soru}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 2000},
    }).encode("utf-8")
    r = urllib.request.Request(
        UC.format(model=MODEL) + f"?key={k}", data=govde,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=40) as x:
            return json.loads(x.read())
    except urllib.error.HTTPError as e:
        SON_HATA = f"HTTP {e.code}"
        if e.code in (429, 403):
            DURDURULDU = True
            SON_HATA = f"HTTP {e.code} — hız/erişim, çağrılar DURDURULDU"
        return None
    except Exception as e:
        SON_HATA = f"{type(e).__name__}: {str(e)[:80]}"
        return None


def _metin(d: dict) -> str:
    try:
        return d["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return ""


SORU = (
    "Futbol maçı: {ev} - {dep}{lig}, tarih {tarih}.\n"
    "Bu maçla ilgili BİLDİĞİN kadarıyla, sonucu etkileyebilecek somut "
    "bilgileri kısaca listele: önemli sakatlık/ceza, kadro dışı oyuncu, "
    "teknik direktör değişikliği, kritik motivasyon durumu (küme düşme, "
    "şampiyonluk, derbi), yoğun fikstür.\n"
    "KURALLAR:\n"
    "- Emin olmadığın hiçbir şeyi yazma. Bilgin yoksa yalnızca 'BİLGİ YOK' yaz.\n"
    "- Tahmin, yorum veya bahis önerisi YAZMA. Yalnız olgu.\n"
    "- En fazla 4 madde, her biri tek satır.\n"
    "- Son satıra şunu ekle: ETKI=yok|dusuk|orta|yuksek"
)


def mac_haberi(ev: str, dep: str, tarih: str = "", lig: str = "") -> dict:
    """Tek maç için bağlam. Karar ÜRETMEZ, olgu toplar."""
    d = _sor(SORU.format(ev=ev, dep=dep, tarih=tarih or "yakın tarih",
                         lig=f" ({lig})" if lig else ""))
    if not d:
        return {"ozet": "", "etki": "", "hata": SON_HATA}
    t = _metin(d)
    # ETKI etiketi metnin HERHANGİ bir yerinde aranır. Satır başı şartı
    # koyunca uzun cevaplarda sessizce kaçıyordu (ölçüldü: iki maçtan
    # birinde etiket okunamadı).
    import re as _re
    m = _re.search(r"ETKI\s*=\s*(yok|dusuk|düşük|orta|yuksek|yüksek)",
                   t, _re.I)
    etki = ""
    if m:
        etki = (m.group(1).lower().replace("ü", "u").replace("ş", "s"))
    return {"ozet": t, "etki": etki, "hata": ""}


def yaz(mac_id, ozet: str, etki: str, ham: str = "", conn=None) -> bool:
    if not ozet:
        return False
    kapat = conn is None
    conn = conn or db.connect()
    try:
        kur(conn)
        conn.execute(
            "INSERT INTO mac_haber (mac_id, ts, kaynak, ozet, etki, ham) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT (mac_id, ts) DO NOTHING",
            (str(mac_id), _ts(), MODEL, ozet[:2000], etki[:20], ham[:4000]))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        if kapat:
            conn.close()


def oku(mac_id, conn=None) -> list[dict]:
    kapat = conn is None
    conn = conn or db.connect()
    try:
        kur(conn)
        r = conn.execute(
            "SELECT ts, ozet, etki FROM mac_haber WHERE mac_id = ? "
            "ORDER BY ts DESC", (str(mac_id),)).fetchall()
        return [{"ts": a, "ozet": b, "etki": c} for a, b, c in r]
    except Exception:
        return []
    finally:
        if kapat:
            conn.close()


def kupon_haberleri(kupon: dict, conn=None, cek: bool = False) -> list[dict]:
    """Kuponun ayaklarına ait haberler — journal için.

    `cek=True` ise eksik olanlar Gemini'den çekilir. Varsayılan FALSE:
    denetim ve test akışları ağ çağrısı yapmasın.
    """
    out = []
    for a in (kupon.get("ayaklar") or []):
        mid = a.get("mac_id")
        mevcut = oku(mid, conn)
        if not mevcut and cek:
            m = a.get("_match") or {}
            h = mac_haberi(str(a.get("ev") or m.get("home_team") or ""),
                           str(a.get("dep") or m.get("away_team") or ""),
                           str(m.get("kickoff_utc") or "")[:10],
                           str(m.get("league_code") or ""))
            if h.get("ozet") and "BİLGİ YOK" not in h["ozet"].upper():
                yaz(mid, h["ozet"], h.get("etki", ""), conn=conn)
                mevcut = oku(mid, conn)
        for x in mevcut:
            out.append({**x, "mac_id": mid,
                        "ev": a.get("ev"), "dep": a.get("dep")})
    return out


def kendi_testi() -> list[str]:
    """Ağsız: şema, yazma/okuma ve 'olasılığa dokunmama' güvencesi."""
    import os as _os
    import sqlite3
    import tempfile
    hata = []
    yol = _os.path.join(tempfile.gettempdir(), f"haber_{_os.getpid()}.db")
    try:
        _os.unlink(yol)
    except OSError:
        pass
    try:
        c = sqlite3.connect(yol)
        kur(c)
        if yaz("m1", "", "", conn=c):
            hata.append("boş özet yazıldı")
        if not yaz("m1", "Kaleci sakat.", "orta", conn=c):
            hata.append("haber yazılamadı")
        r = oku("m1", c)
        if len(r) != 1 or r[0]["etki"] != "orta":
            hata.append(f"haber okunamadı: {r}")
        if oku("yok_boyle", c):
            hata.append("olmayan maç için haber döndü")
        # ⚠️ EN ÖNEMLİ GÜVENCE: bu modül olasılık alanı ÜRETMEZ.
        # Bir gün biri 'sans'/'olasilik' döndürmeye kalkarsa test kalır
        # ve "topla → ölç → bağla" sırası bilerek bozulmuş olur.
        yasak = {"sans", "olasilik", "prob", "kenar", "edge", "ev"}
        for ad in dir(sys.modules[__name__]):
            if ad.lower() in yasak:
                hata.append(f"haber modülü olasılık alanı üretiyor: {ad}")
        k = {"ayaklar": [{"mac_id": "m1", "ev": "A", "dep": "B"}]}
        hh = kupon_haberleri(k, conn=c, cek=False)
        if len(hh) != 1:
            hata.append(f"kupon haberi okunamadı: {len(hh)}")
        if any("sans" in x or "olasilik" in x for x in hh):
            hata.append("kupon haberi olasılık alanı taşıyor")
        c.close()
    except Exception as e:
        hata.append(f"{type(e).__name__}: {e}")
    finally:
        try:
            _os.unlink(yol)
        except OSError:
            pass
    return hata


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    h = kendi_testi()
    print("kendi testi:", "TEMİZ" if not h else f"{len(h)} sorun")
    for x in h:
        print("  ", x)
    print("anahtar:", "var" if _anahtar() else "YOK")
