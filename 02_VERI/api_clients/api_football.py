"""
api-football.com istemcisi (v3.football.api-sports.io).

Free tier: 100 request/gün — her çağrı diske cache'lenir.
Cache anahtar: endpoint + query params, TTL'siz (manuel sil).

Doc: https://www.api-football.com/documentation-v3

Önemli endpoint'ler:
    GET /leagues            — lig listesi (lig ID'leri öğren)
    GET /fixtures?league=&season=&from=&to=
                            — maç listesi (date filter)
    GET /odds?fixture=      — bir fixture için tüm bookmaker oranları
    GET /predictions?fixture=
                            — api-football'un kendi tahmini (bonus referans)
    GET /injuries?fixture=  — sakatlık
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
import urllib.parse
import urllib.request

THIS_DIR = Path(__file__).resolve().parent
YAZILIM_DIR = THIS_DIR.parent.parent  # YAZILIM/
CACHE_DIR = THIS_DIR / "_cache_api_football"
CACHE_DIR.mkdir(exist_ok=True, parents=True)

# .env'den oku
def _load_env() -> dict[str, str]:
    env_path = YAZILIM_DIR / ".env"
    out = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    out.setdefault("API_FOOTBALL_KEY", os.environ.get("API_FOOTBALL_KEY", ""))
    out.setdefault("API_FOOTBALL_HOST", os.environ.get(
        "API_FOOTBALL_HOST", "v3.football.api-sports.io"
    ))
    return out


ENV = _load_env()


# ============================================================
# LEAGUE ID HARITASI (api-football'un kendi ID'leri)
# ============================================================
# https://www.api-football.com/documentation-v3#section/Authentication adresinden
# /leagues çağrısı ile çıkarıldı (yaygın kullanılanlar):

LEAGUE_IDS = {
    "T1": 203,    # Türkiye Süper Lig
    "E0": 39,     # Premier League
    "D1": 78,     # Bundesliga
    "I1": 135,    # Serie A
    "SP1": 140,   # La Liga
    "F1": 61,     # Ligue 1
    "Champions": 2,   # UEFA Champions League
    "Europa": 3,      # UEFA Europa League
}

# Geri eşleme
LEAGUE_NAME_TR = {
    "T1": "Türkiye Süper Lig",
    "E0": "Premier League",
    "D1": "Bundesliga",
    "I1": "Serie A",
    "SP1": "La Liga",
    "F1": "Ligue 1",
    "Champions": "UEFA Champions League",
    "Europa": "UEFA Europa League",
}


# ============================================================
# CACHE
# ============================================================

def _cache_key(endpoint: str, params: dict) -> str:
    """Endpoint + sorted params -> sha1."""
    payload = endpoint + json.dumps(params, sort_keys=True)
    return hashlib.sha1(payload.encode()).hexdigest()


def _cache_get(endpoint: str, params: dict) -> dict | None:
    key = _cache_key(endpoint, params)
    p = CACHE_DIR / f"{key}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _cache_set(endpoint: str, params: dict, data: dict) -> None:
    key = _cache_key(endpoint, params)
    p = CACHE_DIR / f"{key}.json"
    payload = {
        "_endpoint": endpoint,
        "_params": params,
        "_cached_at": datetime.now().isoformat(),
        "data": data,
    }
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# ============================================================
# API CHARGE
# ============================================================

class APIFootballError(Exception):
    pass


def call(endpoint: str, params: dict | None = None, use_cache: bool = True) -> dict:
    """
    api-football.com'a istek at. Cache varsa onu dön, yoksa fetch + cache.

    Args:
        endpoint: "fixtures", "odds", "predictions", "leagues", ...
        params  : query params dict
        use_cache: True ise cache'den oku, yoksa fetch

    Returns:
        Parse edilmiş JSON response (`data` field içeren dict).
    """
    if params is None:
        params = {}

    if use_cache:
        cached = _cache_get(endpoint, params)
        if cached is not None:
            return cached["data"]

    key = ENV.get("API_FOOTBALL_KEY", "")
    host = ENV.get("API_FOOTBALL_HOST", "v3.football.api-sports.io")
    if not key:
        raise APIFootballError("API_FOOTBALL_KEY .env dosyasında yok")

    qs = urllib.parse.urlencode(params)
    url = f"https://{host}/{endpoint}"
    if qs:
        url += "?" + qs

    req = urllib.request.Request(url, headers={
        "x-rapidapi-host": host,
        "x-rapidapi-key": key,
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        raise APIFootballError(f"Network fail: {e}") from e

    try:
        data = json.loads(body)
    except Exception as e:
        raise APIFootballError(f"Bad JSON: {body[:200]}") from e

    # API hata field'ı
    if data.get("errors") and isinstance(data["errors"], dict) and data["errors"]:
        # bazen [] döner; sadece dict olduğunda hata
        raise APIFootballError(f"API errors: {data['errors']}")

    _cache_set(endpoint, params, data)
    return data


# ============================================================
# YÜKSEK SEVİYE FONKSİYONLAR
# ============================================================

def get_fixtures_by_date_range(
    league_code: str,
    season: int,
    date_from: str,
    date_to: str,
    use_cache: bool = True,
) -> list[dict]:
    """
    Belli tarih aralığındaki maçları döndür.

    Args:
        league_code: "T1", "E0", vb. (LEAGUE_IDS keys)
        season:      başlangıç yılı (2025-26 sezon = 2025)
        date_from:   "YYYY-MM-DD"
        date_to:     "YYYY-MM-DD"

    Returns:
        Normalize edilmiş fixture listesi:
        [
          {
            "fixture_id": int,
            "kickoff": str (ISO),
            "status": str,       # NS, FT, ...
            "home": str,
            "away": str,
            "home_score": int | None,
            "away_score": int | None,
            "venue": str,
            "league": str,       # api-football lig adı
            "league_code": str,
          }
        ]
    """
    lid = LEAGUE_IDS.get(league_code)
    if lid is None:
        raise ValueError(f"Bilinmeyen lig kodu: {league_code}")
    raw = call("fixtures", {
        "league": lid,
        "season": season,
        "from": date_from,
        "to": date_to,
    }, use_cache=use_cache)

    out = []
    for item in raw.get("response", []) or []:
        f = item.get("fixture", {})
        t = item.get("teams", {})
        g = item.get("goals", {})
        v = f.get("venue", {})
        out.append({
            "fixture_id": f.get("id"),
            "kickoff": f.get("date"),
            "status": f.get("status", {}).get("short"),
            "home": t.get("home", {}).get("name"),
            "away": t.get("away", {}).get("name"),
            "home_score": g.get("home"),
            "away_score": g.get("away"),
            "venue": v.get("name") if isinstance(v, dict) else None,
            "league": item.get("league", {}).get("name"),
            "league_code": league_code,
        })
    return out


def get_odds_for_fixture(
    fixture_id: int,
    bookmaker: int | None = None,
    use_cache: bool = True,
) -> dict:
    """
    Bir fixture için bookmaker oranlarını döndür.

    Args:
        fixture_id : api-football fixture ID
        bookmaker  : opsiyonel — Pinnacle=4, Bet365=8, ... None = hepsi.

    Returns:
        Ham response (response listesi içinde bookmaker'lar)
    """
    params: dict[str, Any] = {"fixture": fixture_id}
    if bookmaker is not None:
        params["bookmaker"] = bookmaker
    return call("odds", params, use_cache=use_cache)


def parse_odds_response(raw: dict) -> dict[str, dict[str, float]]:
    """
    Ham /odds response'ı pazara göre özetler.

    Returns:
        {
          "1X2":         {"1": 1.50, "X": 4.20, "2": 6.50},      # ortalama
          "Over_Under":  {"2.5_over": 1.80, "2.5_under": 2.00},
          "BTTS":        {"yes": 1.65, "no": 2.20},
        }

    Birden fazla bookmaker varsa ortalama alır.
    """
    out: dict[str, dict[str, list[float]]] = {
        "1X2": {"1": [], "X": [], "2": []},
        "Over_Under": {},
        "BTTS": {"yes": [], "no": []},
    }

    for bm in raw.get("response", []) or []:
        for bm_entry in bm.get("bookmakers", []) or []:
            for bet in bm_entry.get("bets", []) or []:
                name = (bet.get("name") or "").strip()
                values = bet.get("values", []) or []

                if name == "Match Winner":
                    for v in values:
                        val = v.get("value", "")
                        try:
                            odd = float(v.get("odd"))
                        except (TypeError, ValueError):
                            continue
                        if val == "Home":
                            out["1X2"]["1"].append(odd)
                        elif val == "Draw":
                            out["1X2"]["X"].append(odd)
                        elif val == "Away":
                            out["1X2"]["2"].append(odd)

                elif name == "Goals Over/Under":
                    for v in values:
                        val = (v.get("value") or "").strip()
                        try:
                            odd = float(v.get("odd"))
                        except (TypeError, ValueError):
                            continue
                        # value: "Over 2.5" / "Under 2.5"
                        parts = val.split()
                        if len(parts) == 2:
                            side, thr = parts
                            key = f"{thr}_{side.lower()}"
                            out["Over_Under"].setdefault(key, []).append(odd)

                elif name == "Both Teams Score":
                    for v in values:
                        val = (v.get("value") or "").strip().lower()
                        try:
                            odd = float(v.get("odd"))
                        except (TypeError, ValueError):
                            continue
                        if val == "yes":
                            out["BTTS"]["yes"].append(odd)
                        elif val == "no":
                            out["BTTS"]["no"].append(odd)

    # Ortalamaları al
    summary: dict[str, dict[str, float]] = {}
    for market, vals in out.items():
        summary[market] = {}
        for k, v in vals.items():
            if v:
                summary[market][k] = round(sum(v) / len(v), 3)
    return summary


# ============================================================
# CLI / DEBUG
# ============================================================

if __name__ == "__main__":
    import sys
    from datetime import timedelta

    # Test: bugün + 7 gün için Süper Lig + Premier League fixtures
    today = datetime.now().date()
    end = today + timedelta(days=10)
    print(f"Fixtures: {today} -> {end}")

    for code in ["T1", "E0"]:
        season = 2025  # 2025-26 sezonu
        try:
            f = get_fixtures_by_date_range(
                code, season,
                today.isoformat(), end.isoformat()
            )
            print(f"\n[{code}] {LEAGUE_NAME_TR[code]}: {len(f)} mac")
            for m in f[:5]:
                print(f"  {m['kickoff'][:16]}  {m['home']} vs {m['away']}  [{m['status']}]")
        except APIFootballError as e:
            print(f"  [{code}] HATA: {e}", file=sys.stderr)
