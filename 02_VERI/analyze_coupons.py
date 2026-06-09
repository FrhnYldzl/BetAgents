"""
KUPON ANALİZİ — DATA · MODEL · TRADE çerçevesi
==============================================
paper_coupons + paper_bets üzerinden kazanan/kaybeden analizi.
Her metrik üç eksenden birine işaret eder:

  DATA  — örneklem, void oranı, kapanış-oran kapsamı, lig dağılımı
  MODEL — kalibrasyon (model_prob vs gerçekleşen), edge-monotonluğu, CLV
  TRADE — ROI, bankroll, stake disiplini, tek vs kombine, MBS

Küçük örneklemde (sezon arası / ilk haftalar) win/loss GÜRÜLTÜDÜR;
CLV ve kalibrasyon daha hızlı sinyal verir. Rapor bunu vurgular.

Kullanım:
    python analyze_coupons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db


def _rows(conn, q, params=()):
    return [dict(r) for r in conn.execute(q, params).fetchall()]


def _rate(won, total):
    return (won / total) if total else None


def analyze(portfolio_id: str = "PAPER_V1") -> dict:
    conn = db.connect()
    try:
        coupons = _rows(conn, "SELECT * FROM paper_coupons WHERE portfolio_id=?", (portfolio_id,))
        bets    = _rows(conn, "SELECT * FROM paper_bets WHERE portfolio_id=?", (portfolio_id,))
        port    = _rows(conn, "SELECT * FROM paper_portfolio WHERE portfolio_id=?", (portfolio_id,))
    finally:
        conn.close()
    port = port[0] if port else {}

    SETTLED = ("won", "lost", "void")

    # ---- KUPON SEVİYESİ ----
    c_set = [c for c in coupons if (c.get("status") in SETTLED)]
    c_dec = [c for c in c_set if c.get("status") in ("won", "lost")]   # void hariç (karar)
    won_c = [c for c in c_dec if c.get("status") == "won"]
    staked = sum((c.get("stake") or 0) for c in c_dec)
    ret    = sum((c.get("actual_return") or 0) for c in c_dec)
    pnl    = sum((c.get("pnl") or 0) for c in c_set)

    overview = {
        "coupons_total":   len(coupons),
        "coupons_open":    sum(1 for c in coupons if c.get("status") == "open"),
        "coupons_settled": len(c_set),
        "coupons_void":    sum(1 for c in c_set if c.get("status") == "void"),
        "coupons_decided": len(c_dec),
        "coupons_won":     len(won_c),
        "hit_rate":        _rate(len(won_c), len(c_dec)),
        "staked":          round(staked, 1),
        "returned":        round(ret, 1),
        "pnl":             round(pnl, 1),
        "roi":             (round((ret - staked) / staked * 100, 1) if staked else None),
        "bankroll_init":   port.get("initial_bankroll"),
        "bankroll_cur":    port.get("current_bankroll"),
    }

    # ---- KUPON TÜRÜ / AYAK SAYISI KIRILIMI ----
    def _grp_coupons(key_fn):
        g = {}
        for c in c_dec:
            k = key_fn(c)
            g.setdefault(k, {"n": 0, "won": 0, "staked": 0.0, "ret": 0.0})
            g[k]["n"] += 1
            g[k]["won"] += 1 if c.get("status") == "won" else 0
            g[k]["staked"] += (c.get("stake") or 0)
            g[k]["ret"] += (c.get("actual_return") or 0)
        out = {}
        for k, v in g.items():
            out[k] = {
                "n": v["n"], "won": v["won"], "hit_rate": _rate(v["won"], v["n"]),
                "roi": (round((v["ret"] - v["staked"]) / v["staked"] * 100, 1) if v["staked"] else None),
            }
        return out

    by_type = _grp_coupons(lambda c: c.get("coupon_type") or "?")
    by_legs = _grp_coupons(lambda c: f"{c.get('num_legs') or '?'} ayak")

    # ---- BAHİS SEVİYESİ ----
    b_dec = [b for b in bets if b.get("status") in ("won", "lost")]

    def _grp_bets(key_fn):
        g = {}
        for b in b_dec:
            k = key_fn(b)
            g.setdefault(k, {"n": 0, "won": 0})
            g[k]["n"] += 1
            g[k]["won"] += 1 if b.get("status") == "won" else 0
        return {k: {"n": v["n"], "won": v["won"], "hit_rate": _rate(v["won"], v["n"])}
                for k, v in g.items()}

    by_market = _grp_bets(lambda b: b.get("market") or "?")
    by_league = _grp_bets(lambda b: b.get("league") or "?")

    # ---- KALİBRASYON: model_prob vs gerçekleşen (MODEL) ----
    calib_buckets = [(0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 1.01)]
    calibration = []
    for lo, hi in calib_buckets:
        sub = [b for b in b_dec if (b.get("model_prob") or 0) >= lo and (b.get("model_prob") or 0) < hi]
        n = len(sub)
        if not n:
            calibration.append({"band": f"%{int(lo*100)}-{int(hi*100)}", "n": 0,
                                "pred": None, "actual": None, "gap": None})
            continue
        pred = sum((b.get("model_prob") or 0) for b in sub) / n
        actual = sum(1 for b in sub if b.get("status") == "won") / n
        calibration.append({"band": f"%{int(lo*100)}-{int(hi*100)}", "n": n,
                            "pred": round(pred, 3), "actual": round(actual, 3),
                            "gap": round(actual - pred, 3)})

    # ---- EDGE MONOTONLUĞU: yüksek edge → yüksek hit? (MODEL) ----
    edge_buckets = [(-1, 0.0), (0.0, 0.05), (0.05, 0.12), (0.12, 1)]
    edge_perf = []
    for lo, hi in edge_buckets:
        sub = [b for b in b_dec if (b.get("edge") or 0) >= lo and (b.get("edge") or 0) < hi]
        n = len(sub)
        edge_perf.append({
            "band": f"{lo:+.2f}..{hi:+.2f}" if lo > -1 else f"<{hi:+.2f}",
            "n": n,
            "hit_rate": (_rate(sum(1 for b in sub if b.get("status") == "won"), n) if n else None),
        })

    # ---- CLV (MODEL/TRADE truth meter) ----
    clv_vals = [b.get("clv") for b in bets if b.get("clv") is not None]
    clv = None
    if clv_vals:
        n = len(clv_vals)
        clv = {
            "n": n,
            "mean": round(sum(clv_vals) / n, 4),
            "beat_rate": round(sum(1 for v in clv_vals if v > 0) / n, 3),
        }

    # ---- DATA KALİTE sinyalleri ----
    void_rate = _rate(sum(1 for c in c_set if c.get("status") == "void"), len(c_set))
    closing_cov = _rate(sum(1 for b in b_dec if b.get("closing_odds") is not None), len(b_dec))

    return {
        "overview": overview,
        "by_type": by_type,
        "by_legs": by_legs,
        "by_market": by_market,
        "by_league": by_league,
        "calibration": calibration,
        "edge_perf": edge_perf,
        "clv": clv,
        "data_quality": {
            "void_rate": void_rate,
            "closing_coverage": closing_cov,
            "settled_bets": len(b_dec),
        },
    }


def _pct(x):
    return f"%{x*100:.0f}" if x is not None else "—"


def print_report(a: dict) -> None:
    o = a["overview"]
    print("=" * 64)
    print("KUPON ANALİZİ — DATA · MODEL · TRADE")
    print("=" * 64)
    print(f"Kupon: toplam {o['coupons_total']} | açık {o['coupons_open']} | "
          f"settle {o['coupons_settled']} (void {o['coupons_void']})")
    print(f"Karar verilen (void hariç): {o['coupons_decided']} | kazanan {o['coupons_won']} | "
          f"isabet {_pct(o['hit_rate'])}")
    print(f"TRADE: staked {o['staked']} | dönüş {o['returned']} | "
          f"PnL {o['pnl']:+.1f} | ROI {o['roi'] if o['roi'] is not None else '—'}%")
    print(f"Bankroll: {o['bankroll_init']} -> {o['bankroll_cur']}")

    n_dec = o["coupons_decided"]
    print(f"\n[ÖRNEKLEM UYARISI] Karar verilen kupon = {n_dec}. "
          f"{'<30 → win/loss GÜRÜLTÜ, yorum erken.' if n_dec < 30 else 'orta örneklem.'}")

    print("\n--- KUPON TÜRÜ (void hariç) ---")
    for k, v in sorted(a["by_type"].items()):
        print(f"  {k:14s} n={v['n']:3d} isabet {_pct(v['hit_rate'])} ROI {v['roi'] if v['roi'] is not None else '—'}%")
    print("--- AYAK SAYISI ---")
    for k, v in sorted(a["by_legs"].items()):
        print(f"  {k:10s} n={v['n']:3d} isabet {_pct(v['hit_rate'])} ROI {v['roi'] if v['roi'] is not None else '—'}%")

    print("\n--- PAZAR (bahis) ---")
    for k, v in sorted(a["by_market"].items()):
        print(f"  {k:8s} n={v['n']:3d} isabet {_pct(v['hit_rate'])}")
    print("--- LİG (bahis) ---")
    for k, v in sorted(a["by_league"].items()):
        print(f"  {k:8s} n={v['n']:3d} isabet {_pct(v['hit_rate'])}")

    print("\n--- KALİBRASYON (MODEL: tahmin vs gerçek) ---")
    for c in a["calibration"]:
        if c["n"]:
            print(f"  {c['band']:8s} n={c['n']:3d} tahmin {_pct(c['pred'])} "
                  f"gerçek {_pct(c['actual'])} fark {c['gap']*100:+.0f}p")
        else:
            print(f"  {c['band']:8s} n=  0  (veri yok)")

    print("--- EDGE MONOTONLUĞU (yüksek edge→yüksek isabet?) ---")
    for e in a["edge_perf"]:
        print(f"  edge {e['band']:14s} n={e['n']:3d} isabet {_pct(e['hit_rate'])}")

    print("\n--- CLV (truth meter) ---")
    if a["clv"]:
        print(f"  n={a['clv']['n']} | ort CLV {a['clv']['mean']*100:+.2f}% | beat-rate {_pct(a['clv']['beat_rate'])}")
    else:
        print("  CLV verisi yok (maçlar başlayınca/ kapanış geldiğinde dolar)")

    dq = a["data_quality"]
    print("\n--- DATA KALİTE ---")
    print(f"  void oranı {_pct(dq['void_rate'])} | kapanış kapsamı {_pct(dq['closing_coverage'])} | "
          f"settle bahis {dq['settled_bets']}")


if __name__ == "__main__":
    print_report(analyze())
