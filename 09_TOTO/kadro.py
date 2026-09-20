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


def _cagir(yol: str, onbellek_ad: str, taze_sn: int = ONBELLEK_SN):
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
    with urllib.request.urlopen(r, timeout=30) as x:
        d = json.loads(x.read())
    if d.get("errors"):
        d = {"response": [], "errors": d["errors"]}
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


def _takim_bul(eksikler: dict, ad: str, milli: bool) -> list | None:
    if milli:
        en = MILLI_EN.get(ad.strip())
        if en and en in eksikler:
            return eksikler[en]
        ad = en or ad
    en_iyi, skor = None, 0.0
    for t, v in eksikler.items():
        s = benzer(ad, t)
        if s > skor:
            en_iyi, skor = v, s
    return en_iyi if skor >= 0.8 else None


def kadro_gorusu(mac: dict, onsel, milli: bool) -> tuple[list | None, dict]:
    """(p, not) — veri yoksa (None, {})."""
    eksikler = gun_eksikleri(mac["tarih"])
    if not eksikler or onsel is None:
        return None, {}
    ev = _takim_bul(eksikler, mac["ev"], milli)
    dep = _takim_bul(eksikler, mac["dep"], milli)
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
            "kayma": round(s, 3)}
    return p.tolist(), not_


def gun_ozeti() -> str:
    k, _ = _anahtar()
    return "API-Football anahtarı yok" if not k else "hazır"
