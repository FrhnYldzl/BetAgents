"""
SELECTIVE EDGE v1.2 — Top-3 Match Selector (PURE DATA, NO TIPSTERS)

v1.2 değişimi (kullanıcı kararı 27.05.2026):
    Tipster sinyali score formülünden ÇIKARILDI.
    Sebepleri:
        - Tipster picks bir maç için her zaman mevcut olmayabilir
        - Küçük sample'ta tutma oranı tutarlılığı zayıf (Wilson CI çok geniş)
        - İnsan görüşü pure-data analizinin saflığını bozar

    Şimdi 4 sinyal — hepsi PURE iddaa API data + DC matematiği:
        score = 0.40 * odds_anomaly       (cross-market tutarsızlık)
              + 0.30 * model_confidence   (DC modeli ↔ market diverjans)
              + 0.15 * sharp_money        (line movement)
              + 0.15 * inverse_variance   (pazar tutarlılığı)

    Yetersiz veri durumlari (signal=None → ağırlık normalize):
        DC modelinde takım yok    → model_confidence = None
        Tek snapshot              → sharp_money = None

NOT: tipster_consensus.py ve scraper'ı silinmedi — gerçeğine ihtiyaç olursa
geri eklenebilir. UI tarafında "ek bilgi" olarak gösterilebilir ama SKOR'A
KATILMAZ.
"""
from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent.parent
sys.path.insert(0, str(YAZILIM / "02_VERI"))
sys.path.insert(0, str(THIS_DIR))

import database as db
from odds_anomaly import get_match_odds, _read_1x2, _read_ou, _read_btts
from model_confidence import compute_model_confidence
from line_movement import compute_movement


# ============================================================
# PURE-DATA AGIRLIKLARI
# ============================================================
WEIGHTS = {
    "odds_anomaly":     0.40,   # cross-market tutarsızlık (iddaa API)
    "model_confidence": 0.30,   # DC modeli divergence (matematik)
    "sharp_money":      0.15,   # line movement (iddaa API)
    "inverse_variance": 0.15,   # consistency (iddaa API)
}


def get_all_match_signals(snapshot_id: str | None = None,
                          verbose: bool = False) -> list[dict]:
    """Tum maçlar için 4 pure-data sinyali topla + normalize selection_score üret."""
    conn = db.connect()
    try:
        if snapshot_id is None:
            row = conn.execute(
                "SELECT snapshot_id FROM iddaa_odds ORDER BY snapshot_id DESC LIMIT 1"
            ).fetchone()
            if not row:
                return []
            snapshot_id = row[0]

        match_meta = {r["iddaa_match_id"]: dict(r) for r in conn.execute("""
            SELECT iddaa_match_id, MAX(home_team) as home_team,
                   MAX(away_team) as away_team, MAX(kickoff_iso) as kickoff_iso
            FROM iddaa_odds WHERE snapshot_id=? GROUP BY iddaa_match_id
        """, (snapshot_id,)).fetchall()}

        anomalies = {r["iddaa_match_id"]: dict(r) for r in conn.execute(
            "SELECT * FROM odds_anomaly_signals WHERE snapshot_id=?",
            (snapshot_id,)
        ).fetchall()}

        results = []
        for mid, meta in match_meta.items():
            home, away = meta["home_team"], meta["away_team"]
            anom = anomalies.get(mid, {})

            # === Sinyal 1: odds_anomaly (cross-market) ===
            s_anomaly = anom.get("anomaly_strength")
            s_consistency = anom.get("consistency_score") or 0
            signal_direction = anom.get("structural_signal")

            # === Sinyal 2: model_confidence (DC) ===
            mkts = get_match_odds(conn, mid, snapshot_id)
            one = _read_1x2(mkts)
            ou = _read_ou(mkts, "2.5")
            bt = _read_btts(mkts)
            fp = {}
            if one:
                fp["p_1"] = one[0]; fp["p_X"] = one[1]; fp["p_2"] = one[2]
            if ou:
                fp["p_under25"] = ou[0]; fp["p_over25"] = ou[1]
            if bt:
                fp["p_btts_yes"] = bt[0]; fp["p_btts_no"] = bt[1]
            try:
                model_res = compute_model_confidence(home, away, fp)
            except Exception as e:
                if verbose:
                    print(f"  [model err] {home}-{away}: {e}")
                model_res = {"signal": 0.0, "model_available": False}
            s_model = model_res["signal"] if model_res.get("model_available") else None

            # === Sinyal 3: sharp money (line movement) ===
            try:
                lm = compute_movement(mid)
                s_sharp = lm.get("signal") if lm.get("available") else None
                sharp_direction = lm.get("direction") if lm.get("available") else None
            except Exception:
                s_sharp = None
                sharp_direction = None

            # === Sinyal 4: inverse_variance ===
            s_inv_var = s_consistency

            # Selection score: mevcut sinyaller ağırlık-normalize
            parts = []
            if s_anomaly is not None:
                parts.append((WEIGHTS["odds_anomaly"], s_anomaly))
            if s_model is not None:
                parts.append((WEIGHTS["model_confidence"], s_model))
            if s_sharp is not None:
                parts.append((WEIGHTS["sharp_money"], s_sharp))
            if s_inv_var is not None:
                parts.append((WEIGHTS["inverse_variance"], s_inv_var))

            if not parts:
                selection_score = 0
            else:
                w_total = sum(w for w, _ in parts)
                selection_score = sum(w * v for w, v in parts) / w_total

            results.append({
                "iddaa_match_id": mid,
                "home": home, "away": away,
                "kickoff_iso": meta.get("kickoff_iso"),
                "signal_direction": signal_direction,
                "sharp_direction": sharp_direction,
                "model_direction": model_res.get("max_edge_key"),
                "s_odds_anomaly": s_anomaly,
                "s_model_confidence": s_model,
                "s_sharp_money": s_sharp,
                "s_inverse_variance": s_inv_var,
                "consistency_score": s_consistency,
                "selection_score": selection_score,
                # Yan bilgi
                "model_league": model_res.get("league") if model_res.get("model_available") else None,
                "model_lam_h": model_res.get("lam_h"),
                "model_lam_a": model_res.get("lam_a"),
                "model_max_edge": model_res.get("max_edge"),
                # Compat: tipster fields removed but kept as 0 for UI backward compat
                "s_tipster_consensus": 0,
                "consensus_direction": None,
                "tipster_match_count": 0,
            })

        return results
    finally:
        conn.close()


def select_top_n(n: int = 3, min_selection_score: float = 0.0,
                 snapshot_id: str | None = None) -> list[dict]:
    matches = get_all_match_signals(snapshot_id)
    matches.sort(key=lambda m: m["selection_score"], reverse=True)
    return [m for m in matches if m["selection_score"] >= min_selection_score][:n]


def report(top_n: int = 20):
    matches = get_all_match_signals()
    matches.sort(key=lambda m: m["selection_score"], reverse=True)

    print("=" * 110)
    print(f"SELECTIVE EDGE v1.2 (PURE DATA) — TOP {top_n} MAC")
    print("=" * 110)
    print(f"Agirliklar: anomaly=0.40, model=0.30, sharp=0.15, inv_var=0.15  (tipster CIKARILDI)")
    print("-" * 110)
    header = f"{'Match':45s} {'Score':>5s} {'Anom':>5s} {'Model':>5s} {'Sharp':>5s} {'InvV':>5s} {'Yon':14s}"
    print(header)
    print("-" * 110)
    for m in matches[:top_n]:
        label = f"{m['home']} vs {m['away']}"[:43]
        def fmt(v):
            return f"{v:.2f}" if v is not None else "  -"
        print(
            f"{label:45s} {m['selection_score']:>5.2f} "
            f"{fmt(m['s_odds_anomaly']):>5s} "
            f"{fmt(m['s_model_confidence']):>5s} "
            f"{fmt(m['s_sharp_money']):>5s} "
            f"{fmt(m['s_inverse_variance']):>5s} "
            f"{(m['signal_direction'] or '-')[:13]:14s}"
        )

    print("\n" + "=" * 110)
    print("TOP 3 BREAKDOWN:")
    print("=" * 110)
    top3 = matches[:3]
    for i, m in enumerate(top3):
        print(f"\n  [{i+1}] {m['home']} vs {m['away']}  (score: {m['selection_score']:.3f})")
        print(f"      Anomaly       : {m['s_odds_anomaly']}  -> {m['signal_direction']}")
        if m['s_model_confidence'] is not None:
            print(f"      Model conf.   : {m['s_model_confidence']:.2f} ({m['model_league']})  "
                  f"lam_h={m['model_lam_h']:.2f} lam_a={m['model_lam_a']:.2f}  "
                  f"edge={m['model_max_edge']:+.3f}")
        else:
            print(f"      Model conf.   : N/A (DC modeli bu lig icin yok)")
        if m['s_sharp_money'] is not None:
            print(f"      Sharp money   : {m['s_sharp_money']:.2f} -> {m['sharp_direction']}")
        else:
            print(f"      Sharp money   : N/A (tek snapshot)")
        print(f"      Inv. variance : {m['s_inverse_variance']:.2f}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "report":
        report(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    elif cmd == "top3":
        for m in select_top_n(3):
            print(f"{m['home']} vs {m['away']}: score={m['selection_score']:.3f}")
    else:
        print("Komutlar: report [N] | top3")
