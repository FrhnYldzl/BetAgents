"""
SELECTIVE EDGE v1.1 — Model Confidence Signal

DC modelinin tahminini iddaa fair_prob ile karşılaştırır:
    KL divergence + max_edge → confidence sinyali

Yaklaşım:
    1. DC modeli ile P_model(1X2, OU, BTTS) hesapla
    2. iddaa fair_prob (vig-stripped) ile karşılaştır
    3. İki dağılım birbirine yakınsa → bookmaker ve model anlaşıyor → güvenilir
    4. Büyük divergence varsa → model alternatif görüş veriyor → potential edge

Sinyal değeri:
    - low_divergence + high model_edge → "model confident edge var"
    - high_divergence olmadan da → model has insight bookmaker missing

model_confidence = clip(0, 1) of:
    0.4 × agreement_score + 0.6 × max_edge_score

agreement_score = 1 - JS_divergence_normalized (yüksekse anlaşma var)
max_edge_score  = max(p_model[s] - fair_prob[s]) clipped

TEAM MAPPING:
    iddaa home_team string → DCParams.teams adı.
    Fuzzy match (team_match.py kullan).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent.parent
sys.path.insert(0, str(YAZILIM / "03_MODELLER"))
sys.path.insert(0, str(YAZILIM / "02_VERI"))
sys.path.insert(0, str(THIS_DIR))

from base.dixon_coles import DCParams, score_matrix
from base.markets import prob_1x2, prob_over_under, prob_btts


MODELS_DIR = YAZILIM / "06_PRODUCTION" / "models"

# Lig-spesifik takım eşlemesi: hangi DC modeli kullanılacak
# iddaa team name → (league_code, dc_team_name)
# Bu mapping team_match.py geliştikçe genişler
LEAGUE_CANDIDATES = ["T1", "E0", "D1", "SP1", "I1", "F1"]  # Eğitilmiş modeller (EUVOX)


# Cache: lig başına params
_CACHE: dict[str, DCParams] = {}


def _load_dc(league: str) -> DCParams | None:
    if league in _CACHE:
        return _CACHE[league]
    p = MODELS_DIR / f"dc_params_{league}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    params = DCParams(teams=d["teams"], attack=d["attack"], defence=d["defence"],
                     home_adv=d["home_adv"], rho=d["rho"], xi=d["xi"])
    _CACHE[league] = params
    return params


def find_team_in_models(team_name: str) -> tuple[str, str] | None:
    """
    team_match.py'den fuzzy_find kullan. Hangi ligin DC modelinde
    bu takım var?
    """
    try:
        from team_match import best_team_match
    except ImportError:
        # fallback: direct lookup
        for lg in LEAGUE_CANDIDATES:
            params = _load_dc(lg)
            if params and team_name in params.teams:
                return lg, team_name
        return None

    best_score = 0.0
    best_match = None
    for lg in LEAGUE_CANDIDATES:
        params = _load_dc(lg)
        if not params:
            continue
        match, score = best_team_match(team_name, params.teams)
        if match and score > best_score:
            best_score = score
            best_match = (lg, match)
    return best_match if best_score > 0.65 else None


def model_predict(home: str, away: str) -> dict | None:
    """DC tahmini — hangi DC modelinde olduklarını otomatik bul."""
    h_match = find_team_in_models(home)
    a_match = find_team_in_models(away)
    if not h_match or not a_match or h_match[0] != a_match[0]:
        return None

    league = h_match[0]
    params = _load_dc(league)
    if not params:
        return None

    h_dc, a_dc = h_match[1], a_match[1]
    lam, mu = params.expected_goals(h_dc, a_dc)
    M = score_matrix(lam, mu, params.rho, max_goals=10)

    o = prob_1x2(M)
    ou25 = prob_over_under(M, 2.5)
    btts = prob_btts(M)

    return {
        "league": league,
        "matched_home": h_dc,
        "matched_away": a_dc,
        "p_1": o["1"], "p_X": o["X"], "p_2": o["2"],
        "p_over25": ou25["over"], "p_under25": ou25["under"],
        "p_btts_yes": btts["yes"], "p_btts_no": btts["no"],
        "lam_h": lam, "lam_a": mu,
    }


def js_divergence(p: list[float], q: list[float]) -> float:
    """Jensen-Shannon divergence (0=identical, 1=max divergent)."""
    if len(p) != len(q):
        return 1.0
    m = [(pi + qi) / 2 for pi, qi in zip(p, q)]
    def kl(a, b):
        return sum(ai * math.log(ai / bi) for ai, bi in zip(a, b)
                   if ai > 1e-10 and bi > 1e-10)
    return 0.5 * (kl(p, m) + kl(q, m)) / math.log(2)


def compute_model_confidence(iddaa_home: str, iddaa_away: str,
                              fair_probs_iddaa: dict) -> dict:
    """
    fair_probs_iddaa = {
        'p_1': .., 'p_X': .., 'p_2': ..,
        'p_over25': .., 'p_under25': ..,
        'p_btts_yes': .., 'p_btts_no': ..,
    }

    Returns:
        model_confidence: 0-1, sinyal gücü
        model_direction: en güçlü edge yönü
        kl_divergence : model vs market
        details       : breakdown
    """
    pred = model_predict(iddaa_home, iddaa_away)
    if not pred:
        return {"signal": 0.0, "model_available": False, "reason": "team_not_in_dc"}

    # 1X2 divergence
    p_m_1x2 = [pred["p_1"], pred["p_X"], pred["p_2"]]
    p_i_1x2 = [fair_probs_iddaa.get("p_1", 0),
               fair_probs_iddaa.get("p_X", 0),
               fair_probs_iddaa.get("p_2", 0)]

    edges = {}
    if sum(p_i_1x2) > 0.01:
        js_1x2 = js_divergence(p_m_1x2, p_i_1x2)
        edges["1X2_1"] = pred["p_1"] - p_i_1x2[0]
        edges["1X2_X"] = pred["p_X"] - p_i_1x2[1]
        edges["1X2_2"] = pred["p_2"] - p_i_1x2[2]
    else:
        js_1x2 = None

    # OU 2.5
    if fair_probs_iddaa.get("p_over25"):
        p_m_ou = [pred["p_over25"], pred["p_under25"]]
        p_i_ou = [fair_probs_iddaa["p_over25"], fair_probs_iddaa["p_under25"]]
        js_ou = js_divergence(p_m_ou, p_i_ou)
        edges["OU_Over"] = pred["p_over25"] - p_i_ou[0]
        edges["OU_Under"] = pred["p_under25"] - p_i_ou[1]
    else:
        js_ou = None

    # BTTS
    if fair_probs_iddaa.get("p_btts_yes"):
        p_m_bt = [pred["p_btts_yes"], pred["p_btts_no"]]
        p_i_bt = [fair_probs_iddaa["p_btts_yes"], fair_probs_iddaa["p_btts_no"]]
        js_btts = js_divergence(p_m_bt, p_i_bt)
        edges["BTTS_Yes"] = pred["p_btts_yes"] - p_i_bt[0]
        edges["BTTS_No"] = pred["p_btts_no"] - p_i_bt[1]
    else:
        js_btts = None

    # Max edge
    if edges:
        max_edge_key = max(edges, key=lambda k: edges[k])
        max_edge = edges[max_edge_key]
    else:
        max_edge_key = None
        max_edge = 0

    # Sinyal: agreement (low JS) + nonzero edge
    js_values = [v for v in (js_1x2, js_ou, js_btts) if v is not None]
    js_mean = sum(js_values) / len(js_values) if js_values else 1.0
    agreement_score = max(0.0, 1.0 - js_mean / 0.3)  # JS<0.05 → ~0.83 agreement
    max_edge_score = max(0.0, min(1.0, max_edge / 0.10))  # 10pp edge → 1.0

    signal = 0.4 * agreement_score + 0.6 * max_edge_score

    return {
        "signal": signal,
        "model_available": True,
        "league": pred["league"],
        "matched_home": pred["matched_home"],
        "matched_away": pred["matched_away"],
        "agreement_score": agreement_score,
        "max_edge": max_edge,
        "max_edge_key": max_edge_key,
        "edges": edges,
        "js_divergence": {"1X2": js_1x2, "OU": js_ou, "BTTS": js_btts, "mean": js_mean},
        "lam_h": pred["lam_h"], "lam_a": pred["lam_a"],
    }


if __name__ == "__main__":
    # Demo: iddaa odds tablosundan bir maç al, fair_probs çıkar, DC karşılaştır
    import database as db
    from odds_anomaly import get_match_odds, _read_1x2, _read_ou, _read_btts
    conn = db.connect()
    rows = conn.execute(
        "SELECT DISTINCT iddaa_match_id, home_team, away_team "
        "FROM iddaa_odds LIMIT 20"
    ).fetchall()
    found = 0
    for r in rows:
        mkts = get_match_odds(conn, r["iddaa_match_id"])
        one = _read_1x2(mkts)
        ou = _read_ou(mkts, "2.5")
        bt = _read_btts(mkts)
        if not one:
            continue
        fp = {"p_1": one[0], "p_X": one[1], "p_2": one[2]}
        if ou:
            fp["p_over25"] = ou[1]; fp["p_under25"] = ou[0]
        if bt:
            fp["p_btts_yes"] = bt[0]; fp["p_btts_no"] = bt[1]
        result = compute_model_confidence(r["home_team"], r["away_team"], fp)
        if result.get("model_available"):
            found += 1
            print(f"\n{r['home_team']} vs {r['away_team']}")
            print(f"  League: {result['league']}  matched: {result['matched_home']} / {result['matched_away']}")
            print(f"  Signal: {result['signal']:.3f}  Agreement: {result['agreement_score']:.2f}  MaxEdge: {result['max_edge']:+.3f} ({result['max_edge_key']})")
    print(f"\n[OK] {found} mac DC modeline eslesti (20 mac taranıp)")
    conn.close()
