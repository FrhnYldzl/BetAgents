"""
🔴 KIRMIZI TAKIM MOTORU — kombo korelasyon değeri
==================================================
TEK MOTOR, ÜÇ PAZAR. Her Kırmızı ajan aynı matematiği farklı bir kombo
pazarında uygular:
    🎰 ÇARPAN  → 1X2_OU    ("1 ve Üst")
    🔺 SİMETRİ → OU_BTTS   ("Alt ve Yok")   ⭐ en güçlü korelasyon
    ✖️ KAVŞAK  → 1X2_BTTS  ("0 ve Var")

MANTIK: adil oran = (bileşen oranlarının çarpımı) ÷ korelasyon katsayısı.
Katsayı maç profiline koşulludur (combo_tables.py). iddaa'nın verdiği
kombine oranı adil oranı MIN_EDGE kadar aşıyorsa değer vardır.

İZOLASYON: aday kaynağı YALNIZ `market_odds` tablosudur. matches_v2'ye
dokunmaz, sinyal motorunu çağırmaz. MAVİ TAKIM bu hesaptan hiçbir şey
okumaz; Kırmızı ajanlar KONSEY oylamasında yoktur.

    python multiplier_agent.py            # tüm pazarlar
    python multiplier_agent.py OU_BTTS    # tek pazar
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db
from combo_tables import MARKETS, band

MIN_EDGE = 0.08
MIN_ODDS = 2.50
MAX_ODDS = 40.0


def _now() -> str:
    return datetime.utcnow().isoformat()


def _load_latest() -> tuple[dict, dict]:
    """market_odds'tan her (maç, pazar, seçim) için EN SON fiyat."""
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT iddaa_event_id, league_code, kickoff_utc, home_team, away_team, "
            "market, selection, odd, lead_h FROM market_odds "
            "WHERE kickoff_utc > ? ORDER BY ts", (_now(),)).fetchall()
    except Exception:
        conn.rollback()
        conn.close()
        return {}, {}
    conn.close()
    latest, meta = {}, {}
    for r in rows:
        ev = str(r[0])
        latest[(ev, r[5], r[6])] = float(r[7] or 0)
        meta[ev] = {"lg": r[1], "ko": r[2], "home": r[3], "away": r[4], "lead": r[8]}
    return latest, meta


def _norm_probs(latest: dict, ev: str, market: str) -> dict | None:
    """Bir pazarın marjsızlaştırılmış olasılıkları."""
    if market == "1X2":
        o1 = latest.get((ev, "1X2", "1"))
        ox = latest.get((ev, "1X2", "0")) or latest.get((ev, "1X2", "X"))
        o2 = latest.get((ev, "1X2", "2"))
        if not all((o1, ox, o2)):
            return None
        s = 1/o1 + 1/ox + 1/o2
        return {"1": (1/o1)/s, "0": (1/ox)/s, "2": (1/o2)/s,
                "_odds": {"1": o1, "0": ox, "2": o2}}
    if market == "OU2.5":
        ou = latest.get((ev, "OU2.5", "Üst"))
        al = latest.get((ev, "OU2.5", "Alt"))
        if not all((ou, al)):
            return None
        s = 1/ou + 1/al
        return {"U": (1/ou)/s, "A": (1/al)/s, "_odds": {"U": ou, "A": al}}
    if market == "BTTS":
        v = latest.get((ev, "BTTS", "Var"))
        y = latest.get((ev, "BTTS", "Yok"))
        if not all((v, y)):
            return None
        s = 1/v + 1/y
        return {"V": (1/v)/s, "Y": (1/y)/s, "_odds": {"V": v, "Y": y}}
    return None


def candidates(combo_market: str = "1X2_OU", min_edge: float = MIN_EDGE,
               min_odds: float = MIN_ODDS, max_odds: float = MAX_ODDS) -> list[dict]:
    cfg = MARKETS.get(combo_market)
    if not cfg:
        return []
    latest, meta = _load_latest()
    if not latest:
        return []
    (mk_a, edges_a) = cfg["band_a"]
    (mk_b, edges_b) = cfg["band_b"]
    out: list[dict] = []
    for ev, m in meta.items():
        pa = _norm_probs(latest, ev, mk_a)
        pb = _norm_probs(latest, ev, mk_b)
        if not pa or not pb:
            continue
        # bant: a için ilk kod (1X2'de "1", OU'da "U"), b için ilk kod
        key_a = "1" if mk_a == "1X2" else "U"
        key_b = "U" if mk_b == "OU2.5" else "V"
        ba = band(pa[key_a], edges_a)
        bb = band(pb[key_b], edges_b)
        for ca in cfg["a_sel"]:
            for cb in cfg["b_sel"]:
                c = cfg["table"].get((ba, bb, ca, cb))
                if not c:
                    continue
                sel = cfg["label"](ca, cb)
                combo = latest.get((ev, combo_market, sel))
                if not combo:
                    continue
                oa = pa["_odds"].get(ca)
                ob = pb["_odds"].get(cb)
                if not oa or not ob:
                    continue
                naive = oa * ob
                fair = naive / c
                edge = combo / fair - 1
                if edge < min_edge or not (min_odds <= combo <= max_odds):
                    continue
                out.append({
                    "event_id": ev, "league": m["lg"], "kickoff": m["ko"],
                    "home": m["home"], "away": m["away"],
                    "market": combo_market, "pick": sel, "odds": combo,
                    "fair": round(fair, 2), "naive": round(naive, 2),
                    "corr": c, "edge": round(edge * 100, 1), "lead": m["lead"],
                })
    out.sort(key=lambda x: -x["edge"])
    return out


def report(market: str | None = None, min_edge: float = MIN_EDGE) -> None:
    mks = [market] if market else list(MARKETS)
    for mk in mks:
        cs = candidates(mk, min_edge)
        print(f"\n🔴 {mk} — aday (edge ≥ %{min_edge*100:.0f}): {len(cs)}")
        for c in cs[:10]:
            print(f"   {str(c['home'])[:15]:15s}-{str(c['away'])[:15]:15s} "
                  f"{c['pick']:11s} @{c['odds']:6.2f} adil {c['fair']:6.2f} "
                  f"(kor {c['corr']:.2f}) → %{c['edge']:+.1f}")


if __name__ == "__main__":
    report(sys.argv[1] if len(sys.argv) > 1 else None)
