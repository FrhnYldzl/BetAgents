"""
TOTO · KADRO — eksik oyuncular (API-Football) ve KADRO ajanı
=============================================================
Kaynak: api-sports.io `injuries?date=YYYY-MM-DD` — o gün oynanacak maçların
eksik/şüpheli oyuncuları (takım, oyuncu, tür, sebep). Tek sorgu o günün TÜM
maçlarını kapsar; maç başına sorgu YOK (ücretsiz planda günde 100 istek var,
BetAgents'ın yerel betikleri de aynı anahtarı kullanıyor).

⚠️ Ücretsiz plan yalnız dün–bugün–yarın penceresine izin veriyor. Toto listesi
bir haftaya yayıldığı için ajan, penceredeki maçlarda görüş bildirir, diğerlerinde
SUSAR (yanlış bilgi yerine sessizlik). Kapanış günü yapılan son analizde o günün
ve ertesi günün maçları kapsanır. Plan yükseltilirse pencere kendiliğinden genişler.

Ajanın görüşü: piyasa/Elo önselini, iki takımın eksik ağırlığı farkı kadar kaydırır.
Piyasa sakatlıkları ZATEN fiyatlıyor; bu yüzden ajan çoğu zaman piyasayı tekrar eder
ve pazarda cüzdanı büyümez. Katkısı, fiyatın oluşmadığı ya da haberin geç yayıldığı
maçlarda ortaya çıkar — pazar bunu kendiliğinden ölçer.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

import numpy as np

from esle import benzer
from toto_ortak import CACHE, MILLI_EN

HOST = "v3.football.api-sports.io"
ONBELLEK_SN = 6 * 3600
KAPPA = 0.05                  # eksik oyuncu başına logit kayması (önsel; pazar ağırlığı ölçer)
TAKIM_TAVAN = 6.0             # bir takımın ağırlığı en çok 6 sayılır — listeler uzun süreli
MAKS_KAYMA = 0.25             # sakatlık haberi tek başına maçı çevirmez; piyasa zaten fiyatlıyor
TUR_AGIRLIK = {"missing fixture": 1.0, "questionable": 0.45}
SEBEP_AGIRLIK = {"red card": 1.0, "suspended": 1.0, "coach decision": 0.5, "national team": 0.6}


def _anahtar() -> tuple[str, str]:
    import os
    k = os.environ.get("API_FOOTBALL_KEY", "").strip()
    h = os.environ.get("API_FOOTBALL_HOST", "").strip() or HOST
    if not k:                                   # yerelde .env (üretimde Railway değişkeni)
        try:
            for satir in open(CACHE.parent.parent / ".env", encoding="utf-8"):
                if satir.strip().startswith("API_FOOTBALL_KEY="):
                    k = satir.split("=", 1)[1].strip()
        except Exception:
            pass
    return k, h


def _onbellek_yol(ad: str):
    CACHE.mkdir(exist_ok=True)
    return CACHE / f"af_{ad}.json"


_SON_HATA: str = ""          # API'nin son söylediği sorun (panelde dürüstçe gösterilir)


def _cagir(yol: str, onbellek_ad: str, taze_sn: int = ONBELLEK_SN):
    global _SON_HATA
    p = _onbellek_yol(onbellek_ad)
    try:
        if p.exists() and time.time() - p.stat().st_mtime < taze_sn:
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    k, h = _anahtar()
    if not k:
        return None
    r = urllib.request.Request(f"https://{h}/{yol}", headers={"x-rapidapi-key": k, "x-rapidapi-host": h})
    try:
        with urllib.request.urlopen(r, timeout=30) as x:
            d = json.loads(x.read())
    except Exception as e:
        _SON_HATA = f"{type(e).__name__}"
        return None
    if d.get("errors"):
        # Anahtar var ama API çalışmıyor (kota bitti / hesap askıda / plan dışı
        # tarih). Bunu YUTARSAK panel "hazır" der, ajan sessizce susar ve biz
        # veri geldiğini sanırız. Hatayı sakla, gun_ozeti() söylesin.
        h_metin = d["errors"] if isinstance(d["errors"], str) else "; ".join(
            f"{a}: {b}" for a, b in (d["errors"] or {}).items())
        _SON_HATA = str(h_metin)[:160]
        d = {"response": [], "errors": d["errors"]}
    else:
        _SON_HATA = ""
    try:
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return d


def pencere_ici(gun: str) -> bool:
    """Ücretsiz plan penceresi: dün, bugün, yarın."""
    try:
        g = datetime.fromisoformat(str(gun)[:10]).date()
    except Exception:
        return False
    bugun = datetime.now(timezone(timedelta(hours=3))).date()
    return abs((g - bugun).days) <= 1


def gun_eksikleri(gun: str) -> dict | None:
    """{takım adı: [ {oyuncu, tur, sebep, agirlik} ]} — o günün tüm maçları için."""
    if not pencere_ici(gun):
        return None
    d = _cagir(f"injuries?date={gun[:10]}", f"sakatlik_{gun[:10]}")
    if not d or d.get("errors"):
        return None
    out: dict[str, list] = {}
    for x in d.get("response") or []:
        t = ((x.get("team") or {}).get("name") or "").strip()
        p = x.get("player") or {}
        tur = str(p.get("type") or "").strip().lower()
        sebep = str(p.get("reason") or "").strip().lower()
        a = TUR_AGIRLIK.get(tur, 0.5) * SEBEP_AGIRLIK.get(sebep, 1.0)
        out.setdefault(t, []).append({"oyuncu": p.get("name"), "tur": p.get("type"), "sebep": p.get("reason"),
                                      "agirlik": round(a, 2)})
    return out


def gun_fiksturleri(gun: str) -> list | None:
    """O günün maçları: (fikstür id, ev adı, dep adı) — API'nin KENDİ adlarıyla.
    Sakatlıkları takım adına göre eşlerken bu adlar kullanılır: API milli takımları
    yerel adla tutuyor (Türkiye, Czechia) ve bulanık eşleme kulüplere takılabiliyor
    ("Türkiyemspor"). Fikstürden geçmek bu riski kapatır."""
    if not pencere_ici(gun):
        return None
    d = _cagir(f"fixtures?date={gun[:10]}", f"fikstur_{gun[:10]}", 12 * 3600)
    if not d or d.get("errors"):
        return None
    out = []
    for x in d.get("response") or []:
        t = x.get("teams") or {}
        out.append({"id": (x.get("fixture") or {}).get("id"),
                    "ev": ((t.get("home") or {}).get("name") or "").strip(),
                    "dep": ((t.get("away") or {}).get("name") or "").strip(),
                    "lig": ((x.get("league") or {}).get("name") or "")})
    return out


def _adlar(mac: dict, milli: bool) -> tuple[list[str], list[str]]:
    """Aranacak adlar: Toto'nun Türkçe adı + (milli ise) İngilizce karşılığı."""
    ev = [mac["ev"]]
    dep = [mac["dep"]]
    if milli:
        for liste, ad in ((ev, mac["ev"]), (dep, mac["dep"])):
            en = MILLI_EN.get(ad.strip())
            if en:
                liste.append(en)
    return ev, dep


def _fikstur_bul(mac: dict, milli: bool):
    """Toto maçını API fikstürüne bağla → (ev_api_adi, dep_api_adi, fikstur_id)."""
    fk = gun_fiksturleri(mac["tarih"])
    if not fk:
        return None
    ev_adlar, dep_adlar = _adlar(mac, milli)
    en, skor = None, 0.0
    for f in fk:
        s = max(benzer(a, f["ev"]) for a in ev_adlar) + max(benzer(b, f["dep"]) for b in dep_adlar)
        if s > skor:
            en, skor = f, s
    return (en["ev"], en["dep"], en["id"]) if en is not None and skor >= 1.6 else None


def _takim_bul(eksikler: dict, ad: str) -> list | None:
    """Sakatlık listesinde takımı TAM adla bul (fikstürden gelen ad)."""
    if ad in eksikler:
        return eksikler[ad]
    en_iyi, skor = None, 0.0
    for t, v in eksikler.items():
        s = benzer(ad, t)
        if s > skor:
            en_iyi, skor = v, s
    return en_iyi if skor >= 0.95 else None


def kadro_gorusu(mac: dict, onsel, milli: bool) -> tuple[list | None, dict]:
    """(p, not) — veri yoksa (None, {})."""
    eksikler = gun_eksikleri(mac["tarih"])
    if not eksikler or onsel is None:
        return None, {}
    f = _fikstur_bul(mac, milli)
    if f is None:                                   # maçı API fikstüründe bulamadıysak SUS
        return None, {}
    ev = _takim_bul(eksikler, f[0])
    dep = _takim_bul(eksikler, f[1])
    if ev is None and dep is None:
        return None, {}
    ag_ev = sum(x["agirlik"] for x in (ev or []))
    ag_dep = sum(x["agirlik"] for x in (dep or []))
    # Tavan: kadro listeleri uzun süreli sakatları da taşıyor; ham sayı maçı çevirmez.
    s = KAPPA * (min(ag_dep, TAKIM_TAVAN) - min(ag_ev, TAKIM_TAVAN))
    s = float(np.clip(s, -MAKS_KAYMA, MAKS_KAYMA))  # rakip daha eksikse ev lehine kayar
    p = np.asarray(onsel, float).copy()
    p[0] *= float(np.exp(+s))
    p[2] *= float(np.exp(-s))
    p = p / p.sum()
    not_ = {"ev_eksik": len(ev or []), "dep_eksik": len(dep or []),
            "ev_agirlik": round(ag_ev, 1), "dep_agirlik": round(ag_dep, 1),
            "ev_liste": [x["oyuncu"] for x in (ev or [])][:6],
            "dep_liste": [x["oyuncu"] for x in (dep or [])][:6],
            "kayma": round(s, 3), "api_ev": f[0], "api_dep": f[1], "fikstur": f[2]}
    return p.tolist(), not_


def gun_ozeti() -> str:
    """Panelde görünen durum. Anahtarın VARLIĞI yetmez — API çalışıyor mu, o önemli."""
    k, _ = _anahtar()
    if not k:
        return "API-Football anahtarı yok"
    if _SON_HATA:
        return f"API yanıt vermiyor — {_SON_HATA}"
    return "hazır"
