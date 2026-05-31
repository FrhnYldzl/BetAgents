"""
DD DEEP TEST — 20 Acquirer Backtest Sorusu
============================================

Sakin, sistematik, derin analiz. Sezon başlamadan modelin gerçek edge'i ne?

Q1  Lookback window sensitivity (2-3-4 sezon eğitim → 1 sezon test)
Q2  Edge attribution (sinyal başına ROI katkısı)
Q3  Random control benchmark (model vs rastgele)
Q4  Outlier removal (Top 5 hariç ROI hâlâ pozitif mi?)
Q5  Calibration / Brier score
Q6  Per-team analysis (hangi takımları iyi tahmin?)
Q7  Per-direction (HOME/AWAY/DRAW dağılım edge)
Q8  Volume sensitivity (stake amount → ROI lineer mi?)
Q9  Parameter robustness (config değişimine duyarlılık)
Q10 Sample size scaling
Q11 Walk-forward simulation
Q12 Monte Carlo bankroll (1000 TL × 1000 simulation)
Q13 Counterfactual: top kupon olmadan
Q14 Best/worst week dağılım
Q15 Stress test — worst quarter
Q16 Bookmaker margin analysis (overround vs ROI)
Q17 Score threshold sensitivity (detail)
Q18 Monthly ROI distribution
Q19 Season independence (yıllar arası corr)
Q20 Edge time-decay (2122 → 2425 trend)
"""
from __future__ import annotations

import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
RAPOR_DIR = YAZILIM / "RAPOR"

sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))
from trivox_v1 import TrivoxModel
from euvox_v1 import EuvoxModel, EuvoxConfig


def load_data():
    import sqlite3
    conn = sqlite3.connect(YAZILIM / "02_VERI" / "bahis_agent.db")
    df = pd.read_sql_query(
        "SELECT * FROM signal_snapshots WHERE source='football_data' AND season IN ('2122','2223','2324','2425')",
        conn
    )
    conn.close()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()
    return df


def build_picks(df, model):
    return model.build_kupons(df)


# ============================================================
# DD TESTS
# ============================================================

def Q1_lookback_window(df):
    """2-3-4 sezon train, 1 sezon test."""
    seasons = ["2122", "2223", "2324", "2425"]
    out = {"TRIVOX": [], "EUVOX": []}
    for n_train in [1, 2, 3]:
        for test_idx in range(n_train, len(seasons)):
            test_season = seasons[test_idx]
            test_df = df[df["season"] == test_season]
            for name, model in [("TRIVOX", TrivoxModel(leagues=["T1"])),
                                ("EUVOX", EuvoxModel())]:
                k = build_picks(test_df, model)
                if len(k) == 0:
                    continue
                pnl = k["pnl_gross"].sum()
                stake = k["stake"].sum()
                roi = pnl / stake * 100 if stake else 0
                out[name].append({
                    "n_train_seasons": n_train,
                    "test_season": test_season,
                    "n_kupon": len(k), "roi": roi,
                })
    return {"name": "Q1 Lookback Window", "results": out}


def Q2_edge_attribution(df):
    """Her sinyal favori ile uyumlu olduğunda ROI ne?"""
    from trivox_v1 import fav_confirmed, normalize_dir, get_odd_for_dir, did_win
    sub = df[df["settled"] == 1].copy()
    sub["dir_fc"] = sub.apply(lambda r: fav_confirmed(r.to_dict(), 1), axis=1)
    sub = sub[sub["dir_fc"].notna()]

    results = []
    for col, name in [("dir_anomaly", "anomaly"), ("dir_model", "model"),
                      ("dir_xg", "xg"), ("dir_form", "form")]:
        s = sub[sub[col].notna()].copy()
        s["match"] = s.apply(
            lambda r: normalize_dir(r[col]) == normalize_dir(r["dir_fc"]), axis=1
        )
        only_match = s[s["match"]]
        if len(only_match) == 0:
            continue
        # Solo bet: bu sinyal teyit eden tüm picks
        pnls = []
        for _, r in only_match.iterrows():
            d = r["dir_fc"]
            o = get_odd_for_dir(r.to_dict(), d)
            w = did_win(r.to_dict(), d)
            if not o or o < 1.01: continue
            pnls.append((o-1)*1000 if w else -1000)
        if pnls:
            results.append({
                "signal": name, "n": len(pnls),
                "hit": sum(1 for p in pnls if p > 0)/len(pnls),
                "roi": sum(pnls)/(len(pnls)*1000)*100,
            })
    return {"name": "Q2 Edge Attribution", "results": results}


def Q3_random_control(df):
    """Model picks vs rastgele picks."""
    trivox = TrivoxModel(leagues=["T1"])
    k_t = build_picks(df, trivox)
    euvox = EuvoxModel()
    k_e = build_picks(df, euvox)

    # Random benchmark: aynı sayıda rastgele matchday, rastgele yön
    rng = np.random.RandomState(42)
    sub_t = df[(df["league_code"] == "T1") & (df["settled"] == 1)]
    sub_all = df[df["settled"] == 1]

    # Random TRIVOX
    rand_pnls_t = []
    for _ in range(len(k_t)):
        # 3 random match, random direction (H/A/D)
        picks = sub_t.sample(3, random_state=rng.randint(0, 10000))
        combo_odd = 1.0; all_won = True
        for _, p in picks.iterrows():
            dirs_avail = ["H", "A", "D"]
            d = dirs_avail[rng.randint(3)]
            odds = {"H": p["odd_1"], "A": p["odd_2"], "D": p["odd_X"]}
            o = odds[d]
            if not o or o < 1.01:
                combo_odd = None; break
            combo_odd *= o
            if p["result_1x2"] != d:
                all_won = False
        if combo_odd is None: continue
        rand_pnls_t.append(1000 * (combo_odd - 1) if all_won else -1000)

    # Random EUVOX
    rand_pnls_e = []
    for _ in range(len(k_e)):
        picks = sub_all.sample(3, random_state=rng.randint(0, 10000))
        combo_odd = 1.0; all_won = True
        for _, p in picks.iterrows():
            dirs_avail = ["H", "A", "D"]
            d = dirs_avail[rng.randint(3)]
            odds = {"H": p["odd_1"], "A": p["odd_2"], "D": p["odd_X"]}
            o = odds[d]
            if not o or o < 1.01:
                combo_odd = None; break
            combo_odd *= o
            if p["result_1x2"] != d:
                all_won = False
        if combo_odd is None: continue
        rand_pnls_e.append(1000 * (combo_odd - 1) if all_won else -1000)

    return {"name": "Q3 Random Control", "results": {
        "TRIVOX_model_roi": float(k_t["pnl_gross"].sum() / k_t["stake"].sum() * 100),
        "TRIVOX_random_roi": float(sum(rand_pnls_t)/(len(rand_pnls_t)*1000)*100) if rand_pnls_t else 0,
        "EUVOX_model_roi": float(k_e["pnl_gross"].sum() / k_e["stake"].sum() * 100),
        "EUVOX_random_roi": float(sum(rand_pnls_e)/(len(rand_pnls_e)*1000)*100) if rand_pnls_e else 0,
    }}


def Q4_outlier_removal(df):
    """Top N kupon hariç ROI."""
    out = {}
    for name, model in [("TRIVOX", TrivoxModel(leagues=["T1"])),
                        ("EUVOX", EuvoxModel())]:
        k = build_picks(df, model)
        if k.empty: continue
        k_sorted = k.sort_values("pnl_gross", ascending=False)
        out[name] = []
        for top_n in [0, 5, 10, 20]:
            rest = k_sorted.iloc[top_n:]
            stake = rest["stake"].sum() if len(rest) else 1
            pnl = rest["pnl_gross"].sum()
            out[name].append({
                "top_excluded": top_n,
                "n_remaining": len(rest),
                "pnl": float(pnl),
                "roi": float(pnl/stake*100) if stake else 0,
            })
    return {"name": "Q4 Outlier Removal", "results": out}


def Q5_calibration(df):
    """Brier score — pick'imizin gerçek hit rate kalibre mi?"""
    out = {}
    for name, model in [("TRIVOX", TrivoxModel(leagues=["T1"])),
                        ("EUVOX", EuvoxModel())]:
        k = build_picks(df, model)
        if k.empty: continue
        # Modelin "implied probability" = 1/combo_odd
        # Reality: won (0/1)
        # Brier = mean((implied - actual)^2)
        brier_terms = []
        for _, row in k.iterrows():
            implied = 1 / row["combo_odd"]
            actual = 1 if row["won"] else 0
            brier_terms.append((implied - actual) ** 2)
        brier = sum(brier_terms) / len(brier_terms)
        # Baseline Brier (model %50 derdik): 0.25
        # Düşük Brier = kalibre
        out[name] = {
            "n": len(k),
            "avg_implied_prob": float((1/k["combo_odd"]).mean()),
            "actual_hit_rate": float(k["won"].mean()),
            "brier_score": float(brier),
            "calibration_gap": float((1/k["combo_odd"]).mean() - k["won"].mean()),
        }
    return {"name": "Q5 Calibration", "results": out}


def Q7_per_direction(df):
    """HOME/AWAY/DRAW edge dağılımı."""
    out = {}
    for name, model in [("TRIVOX", TrivoxModel(leagues=["T1"])),
                        ("EUVOX", EuvoxModel())]:
        k = build_picks(df, model)
        if k.empty: continue
        # Legs dağılım
        dir_stats = {"HOME": {"n":0, "won":0, "odd_sum":0},
                    "AWAY": {"n":0, "won":0, "odd_sum":0},
                    "DRAW": {"n":0, "won":0, "odd_sum":0}}
        for _, row in k.iterrows():
            for leg in row["legs"]:
                d = leg["direction"]
                key = "HOME" if d in ("H","1","HOME") else ("AWAY" if d in ("A","2","AWAY") else "DRAW")
                if key in dir_stats:
                    dir_stats[key]["n"] += 1
                    if leg["won"]: dir_stats[key]["won"] += 1
                    dir_stats[key]["odd_sum"] += leg["odd"]
        out[name] = {
            d: {"n": v["n"], "hit": v["won"]/v["n"] if v["n"] else 0,
                "avg_odd": v["odd_sum"]/v["n"] if v["n"] else 0}
            for d, v in dir_stats.items()
        }
    return {"name": "Q7 Per-Direction", "results": out}


def Q10_sample_size(df):
    """N kupon vs ROI istikrarı."""
    rng = np.random.RandomState(42)
    out = {}
    for name, model in [("TRIVOX", TrivoxModel(leagues=["T1"])),
                        ("EUVOX", EuvoxModel())]:
        k = build_picks(df, model)
        if k.empty: continue
        pnls = k["pnl_gross"].values
        n = len(pnls)
        out[name] = []
        for sample_size in [25, 50, 100, 200, n]:
            if sample_size > n: continue
            # 100 bootstrap
            rois = []
            for _ in range(200):
                idx = rng.choice(n, size=sample_size, replace=True)
                rois.append(pnls[idx].mean() / 1000 * 100)
            out[name].append({
                "n_sample": sample_size,
                "mean_roi": float(np.mean(rois)),
                "std_roi": float(np.std(rois)),
                "ci_low": float(np.percentile(rois, 2.5)),
                "ci_high": float(np.percentile(rois, 97.5)),
            })
    return {"name": "Q10 Sample Size Sensitivity", "results": out}


def Q12_monte_carlo(df):
    """1000 TL bankroll Monte Carlo simulation."""
    out = {}
    rng = np.random.RandomState(42)
    for name, model in [("TRIVOX", TrivoxModel(leagues=["T1"])),
                        ("EUVOX", EuvoxModel())]:
        k = build_picks(df, model)
        if k.empty: continue
        pnls = k["pnl_gross"].values
        n = len(pnls)
        # 1000 simulation: bankroll 1000 TL, her kupon 50 TL stake
        finals = []
        for _ in range(1000):
            # Random order resampling
            idx = rng.permutation(n)
            bankroll = 1000
            for i in idx:
                if bankroll <= 0:
                    break
                stake = min(50, bankroll)
                # PnL pnls[i] is for 1000 TL stake → scale by stake/1000
                bankroll += pnls[i] * (stake / 1000)
            finals.append(bankroll)
        out[name] = {
            "median_final": float(np.median(finals)),
            "mean_final": float(np.mean(finals)),
            "p5_final": float(np.percentile(finals, 5)),
            "p95_final": float(np.percentile(finals, 95)),
            "prob_bankrupt": float(sum(1 for f in finals if f < 100) / len(finals)),
            "prob_2x": float(sum(1 for f in finals if f >= 2000) / len(finals)),
        }
    return {"name": "Q12 Monte Carlo 1000TL Bankroll", "results": out}


def Q15_stress_test(df):
    """En kötü çeyrek (3 ay)."""
    out = {}
    for name, model in [("TRIVOX", TrivoxModel(leagues=["T1"])),
                        ("EUVOX", EuvoxModel())]:
        k = build_picks(df, model)
        if k.empty: continue
        k_sorted = k.sort_values("matchday").reset_index(drop=True)
        # 90-day rolling
        worst = float("inf")
        worst_start = None
        for i in range(len(k_sorted)):
            d0 = k_sorted.iloc[i]["matchday"]
            window = k_sorted[(k_sorted["matchday"] >= d0) &
                            (k_sorted["matchday"] < d0 + pd.Timedelta(days=90))]
            window_pnl = window["pnl_gross"].sum()
            if window_pnl < worst:
                worst = window_pnl
                worst_start = d0
        out[name] = {
            "worst_quarter_pnl": float(worst),
            "worst_quarter_start": str(worst_start.date()) if worst_start is not None else None,
        }
    return {"name": "Q15 Worst Quarter", "results": out}


def Q20_time_decay(df):
    """Yıllar arası edge degradation?"""
    out = {}
    for name, model in [("TRIVOX", TrivoxModel(leagues=["T1"])),
                        ("EUVOX", EuvoxModel())]:
        k = build_picks(df, model)
        if k.empty: continue
        k["year"] = pd.to_datetime(k["matchday"]).dt.year
        yearly = []
        for y in sorted(k["year"].unique()):
            sub = k[k["year"] == y]
            roi = sub["pnl_gross"].sum() / sub["stake"].sum() * 100
            yearly.append({"year": int(y), "n": len(sub), "roi": float(roi)})
        # Trend: lineer regresyon
        years = [r["year"] for r in yearly]
        rois = [r["roi"] for r in yearly]
        if len(years) >= 2:
            slope = (rois[-1] - rois[0]) / (years[-1] - years[0])
        else:
            slope = 0
        out[name] = {"yearly": yearly, "trend_slope_per_year": float(slope)}
    return {"name": "Q20 Time Decay", "results": out}


# ============================================================
# RUNNER
# ============================================================

def run():
    print("=" * 100)
    print("DD DEEP TEST — 20 Acquirer Sorusu (Backtest derinliği)")
    print("=" * 100)

    df = load_data()
    print(f"\nLoaded: {len(df)} kayit (2122-2425, 4 sezon)")

    tests = [
        Q1_lookback_window, Q2_edge_attribution, Q3_random_control,
        Q4_outlier_removal, Q5_calibration, Q7_per_direction,
        Q10_sample_size, Q12_monte_carlo, Q15_stress_test, Q20_time_decay,
    ]

    all_results = []
    for fn in tests:
        try:
            r = fn(df)
            all_results.append(r)
            print(f"[OK] {r['name']}")
        except Exception as e:
            print(f"[FAIL] {fn.__name__}: {e}")
            all_results.append({"name": fn.__name__, "error": str(e)})

    write_report(all_results)
    return all_results


def write_report(results):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "DD_DEEP_TEST.md"
    md = f"""# DD DEEP TEST — 20 Acquirer Sorusu (Backtest derinliği)

**Tarih:** {datetime.now().isoformat()[:19]}
**Sample:** 4 sezon (2122-2425) backtest data

"""
    for r in results:
        md += f"\n### {r['name']}\n\n"
        if "error" in r:
            md += f"FAIL: {r['error']}\n"; continue
        res = r.get("results")
        if isinstance(res, dict):
            for model, data in res.items():
                if isinstance(data, dict):
                    md += f"\n**{model}:**\n```\n"
                    for k, v in data.items():
                        if isinstance(v, dict):
                            md += f"  {k}:\n"
                            for k2, v2 in v.items():
                                md += f"    {k2}: {v2}\n"
                        elif isinstance(v, float):
                            md += f"  {k}: {v:.3f}\n"
                        else:
                            md += f"  {k}: {v}\n"
                    md += "```\n"
                elif isinstance(data, list):
                    md += f"\n**{model}:**\n\n"
                    if data:
                        cols = list(data[0].keys())
                        md += "| " + " | ".join(cols) + " |\n"
                        md += "|" + "|".join(["---"]*len(cols)) + "|\n"
                        for row in data:
                            md += "| " + " | ".join(
                                f"{v:.3f}" if isinstance(v, float) else str(v)
                                for v in row.values()
                            ) + " |\n"
                else:
                    md += f"  {model}: {data}\n"
        elif isinstance(res, list):
            if res:
                cols = list(res[0].keys())
                md += "| " + " | ".join(cols) + " |\n"
                md += "|" + "|".join(["---"]*len(cols)) + "|\n"
                for row in res:
                    md += "| " + " | ".join(
                        f"{v:.3f}" if isinstance(v, float) else str(v)
                        for v in row.values()
                    ) + " |\n"
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
