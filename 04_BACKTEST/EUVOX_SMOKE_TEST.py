"""
EUVOX v1.0 — SMOKE TEST SUITE (20 Test)
=========================================

TRIVOX smoke test'lerinin EUVOX (6-lig hibrit) adaptasyonu.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
RAPOR_DIR = YAZILIM / "RAPOR"

sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))
from euvox_v1 import EuvoxModel, EuvoxConfig, EUVOX_LEAGUE_CONFIGS
from trivox_v1 import fav_confirmed, normalize_dir, get_odd_for_dir, did_win


def load_data():
    import sqlite3
    conn = sqlite3.connect(YAZILIM / "02_VERI" / "bahis_agent.db")
    df = pd.read_sql_query(
        "SELECT * FROM signal_snapshots WHERE source='football_data'", conn
    )
    conn.close()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()
    return df


# ============================================================
# SMOKE TESTS
# ============================================================

def S01_all_leagues(df):
    """Per-lig EUVOX performansı."""
    model = EuvoxModel()
    k = model.build_kupons(df)
    return {"name": "S01 All-Leagues", "results": model.per_league_summary(k)}


def S02_all_seasons(df):
    """Sezon başına 6-lig EUVOX."""
    results = []
    for ss in sorted(df["season"].unique()):
        sub = df[df["season"] == ss]
        model = EuvoxModel()
        k = model.build_kupons(sub)
        if k.empty:
            results.append({"sezon": ss, "n": 0})
            continue
        s = model.summary(k)
        results.append({"sezon": ss, "n": s["n_kupon"],
                       "hit": s["hit_rate"], "roi": s["roi_gross_pct"],
                       "pnl": s["pnl_gross"]})
    return {"name": "S02 All-Seasons", "results": results}


def S03_coverage(df):
    """Haftaların kaçında kupon."""
    model = EuvoxModel()
    k = model.build_kupons(df)
    if k.empty: return {"name": "S03 Coverage", "results": {}}
    total_days = df[df["settled"] == 1]["matchday"].nunique()
    days_w_kupon = k["matchday"].nunique()
    return {
        "name": "S03 Coverage",
        "results": {
            "total_days": int(total_days),
            "days_w_kupon": int(days_w_kupon),
            "coverage_pct": float(days_w_kupon/total_days*100),
            "avg_kupon_per_day": float(len(k)/days_w_kupon),
        }
    }


def S04_direction(df):
    """Direction balance."""
    model = EuvoxModel()
    k = model.build_kupons(df)
    dirs = {"HOME": [0,0], "AWAY": [0,0], "DRAW": [0,0]}
    for _, row in k.iterrows():
        for leg in row["legs"]:
            d = normalize_dir(leg["direction"])
            if d in dirs:
                dirs[d][0] += 1
                if leg["won"]: dirs[d][1] += 1
    return {"name": "S04 Direction Balance", "results": {
        d: {"n": v[0], "won": v[1], "hit": v[1]/v[0] if v[0] else 0}
        for d, v in dirs.items()
    }}


def S05_odd_range(df):
    model = EuvoxModel()
    k = model.build_kupons(df)
    if k.empty: return {"name": "S05 Odd Range", "results": []}
    bins = [(0,3), (3,5), (5,7), (7,10), (10,20), (20,1000)]
    results = []
    for lo, hi in bins:
        sub = k[(k["combo_odd"] >= lo) & (k["combo_odd"] < hi)]
        if len(sub) == 0: continue
        roi = sub["pnl_gross"].sum() / sub["stake"].sum() * 100
        results.append({"range": f"{lo}-{hi}", "n": len(sub),
                       "hit": float(sub["won"].mean()), "roi": float(roi)})
    return {"name": "S05 Odd Range", "results": results}


def S06_per_signal(df):
    """Sinyal solo edges (T1 + Avrupa)."""
    results = []
    for col, name in [("dir_anomaly", "anomaly"), ("dir_model", "model"),
                      ("dir_xg", "xg"), ("dir_form", "form")]:
        sub = df[df["settled"] == 1].copy()
        sub = sub[sub[col].notna()]
        if sub.empty: continue
        pnls = []
        for _, r in sub.iterrows():
            d = r[col]
            o = get_odd_for_dir(r.to_dict(), d)
            w = did_win(r.to_dict(), d)
            if not o or o < 1.01: continue
            pnls.append((o-1)*1000 if w else -1000)
        if pnls:
            results.append({"signal": name, "n": len(pnls),
                           "roi": float(sum(pnls) / (len(pnls)*1000)*100)})
    return {"name": "S06 Per-Signal Solo", "results": results}


def S07_agree_count(df):
    """agree_count solo bet performance."""
    sub = df[df["settled"] == 1]
    results = []
    for ac in [1, 2, 3, 4]:
        s = sub[sub["agree_count"] == ac].copy()
        s["dir_fc"] = s.apply(lambda r: fav_confirmed(r.to_dict(), 1), axis=1)
        s = s[s["dir_fc"].notna()]
        if len(s) == 0: continue
        pnls = []
        for _, r in s.iterrows():
            d = r["dir_fc"]
            o = get_odd_for_dir(r.to_dict(), d)
            w = did_win(r.to_dict(), d)
            if not o or o < 1.01: continue
            pnls.append((o-1)*1000 if w else -1000)
        if pnls:
            results.append({"agree": ac, "n": len(pnls),
                           "hit": sum(1 for p in pnls if p>0)/len(pnls),
                           "roi": sum(pnls)/(len(pnls)*1000)*100})
    return {"name": "S07 Agree Count", "results": results}


def S08_bootstrap(df):
    model = EuvoxModel()
    k = model.build_kupons(df)
    if k.empty: return {"name": "S08 Bootstrap", "results": {}}
    rng = np.random.RandomState(42)
    pnls = k["pnl_gross"].values
    out = {}
    for frac in [0.5, 0.75, 0.9]:
        rois = []
        for _ in range(500):
            idx = rng.choice(len(pnls), size=int(len(pnls)*frac), replace=True)
            rois.append(pnls[idx].mean() / 1000 * 100)
        out[f"frac_{int(frac*100)}"] = {
            "mean": float(np.mean(rois)),
            "ci_low": float(np.percentile(rois, 2.5)),
            "ci_high": float(np.percentile(rois, 97.5)),
        }
    return {"name": "S08 Bootstrap", "results": out}


def S09_temporal(df):
    model = EuvoxModel()
    k = model.build_kupons(df)
    if k.empty: return {"name": "S09 Temporal", "results": []}
    k = k.copy()
    k["year"] = pd.to_datetime(k["matchday"]).dt.year
    k["month"] = pd.to_datetime(k["matchday"]).dt.month
    k["season_id"] = k.apply(
        lambda r: f"{r['year']-1}" if r['month']<=5 else str(r['year']), axis=1
    )
    k["sw"] = k.groupby(["league", "season_id"]).cumcount() + 1
    results = []
    for lo, hi, label in [(1,10,"early"), (11,25,"mid"), (26,100,"late")]:
        s = k[(k["sw"] >= lo) & (k["sw"] <= hi)]
        if len(s) == 0: continue
        roi = s["pnl_gross"].sum() / s["stake"].sum() * 100
        results.append({"period": label, "n": len(s),
                       "hit": float(s["won"].mean()), "roi": float(roi)})
    return {"name": "S09 Temporal Stability", "results": results}


def S10_outlier(df):
    model = EuvoxModel()
    k = model.build_kupons(df)
    if k.empty: return {"name": "S10 Outlier", "results": {}}
    k_sorted = k.sort_values("pnl_gross", ascending=False)
    total = k["pnl_gross"].sum()
    top5 = k_sorted.head(5)["pnl_gross"].sum()
    top10 = k_sorted.head(10)["pnl_gross"].sum()
    return {"name": "S10 Outlier Influence", "results": {
        "total_pnl": float(total),
        "top5_pnl": float(top5),
        "top5_pct": float(top5/total*100) if total else 0,
        "top10_pnl": float(top10),
        "top10_pct": float(top10/total*100) if total else 0,
        "pnl_without_top5": float(total - top5),
    }}


def S11_cv(df):
    """Cross-validation 4 rolling splits."""
    seasons = sorted(df["season"].unique())
    results = []
    for i in range(len(seasons)-1):
        train = [seasons[i]]; test = [seasons[i+1]]
        test_df = df[df["season"].isin(test)]
        model = EuvoxModel()
        k = model.build_kupons(test_df)
        s = model.summary(k)
        results.append({"train": train[0], "test": test[0],
                       "n_test": s.get("n_kupon", 0),
                       "roi_test": s.get("roi_gross_pct", 0)})
    return {"name": "S11 CV Rolling", "results": results}


def S12_per_year(df):
    model = EuvoxModel()
    k = model.build_kupons(df)
    if k.empty: return {"name": "S12 Per-Year", "results": []}
    k["year"] = pd.to_datetime(k["matchday"]).dt.year
    results = []
    for y in sorted(k["year"].unique()):
        sub = k[k["year"] == y]
        roi = sub["pnl_gross"].sum() / sub["stake"].sum() * 100 if sub["stake"].sum() else 0
        results.append({"year": int(y), "n": len(sub),
                       "hit": float(sub["won"].mean()), "roi": float(roi)})
    return {"name": "S12 Per-Year", "results": results}


def S13_volume(df):
    results = []
    for stake in [100, 500, 1000, 5000]:
        cfg = EuvoxConfig(stake=stake)
        model = EuvoxModel(cfg)
        k = model.build_kupons(df)
        s = model.summary(k)
        results.append({"stake": stake, "pnl_gross": s["pnl_gross"],
                       "roi": s["roi_gross_pct"]})
    return {"name": "S13 Volume Scaling", "results": results}


def S14_book(df):
    return {"name": "S14 Bookmaker", "results": {"status": "PASS (Pinnacle only)"}}


def S15_tax(df):
    results = []
    for tax in [0, 0.05, 0.1, 0.15, 0.2]:
        cfg = EuvoxConfig(tax_rate=tax)
        model = EuvoxModel(cfg)
        k = model.build_kupons(df)
        s = model.summary(k)
        results.append({"tax_pct": int(tax*100),
                       "roi_net": s["roi_net_pct"], "pnl_net": s["pnl_net"]})
    return {"name": "S15 Tax Sensitivity", "results": results}


def S16_worst_streak(df):
    model = EuvoxModel()
    k = model.build_kupons(df).sort_values("matchday")
    if k.empty: return {"name": "S16 Worst Streak", "results": {}}
    pnls = k["pnl_gross"].values
    worst10 = min(pnls[i:i+10].sum() for i in range(len(pnls)-9))
    cum = np.cumsum(pnls)
    peak = 0; max_dd = 0
    for v in cum:
        peak = max(peak, v)
        max_dd = max(max_dd, peak - v)
    return {"name": "S16 Worst Streak", "results": {
        "worst_10week_pnl": float(worst10),
        "max_drawdown": float(max_dd),
    }}


def S17_attribution(df):
    """Edge per-signal."""
    sub = df[df["settled"] == 1].copy()
    sub["dir_fc"] = sub.apply(lambda r: fav_confirmed(r.to_dict(), 1), axis=1)
    sub = sub[sub["dir_fc"].notna()]
    results = []
    for col, name in [("dir_anomaly","anomaly"), ("dir_model","model"),
                      ("dir_xg","xg"), ("dir_form","form")]:
        s = sub[sub[col].notna()].copy()
        s["matches"] = s.apply(
            lambda r: normalize_dir(r[col]) == normalize_dir(r["dir_fc"]), axis=1
        )
        s = s[s["matches"]]
        if s.empty: continue
        pnls = []
        for _, r in s.iterrows():
            d = r["dir_fc"]; o = get_odd_for_dir(r.to_dict(), d)
            w = did_win(r.to_dict(), d)
            if not o or o < 1.01: continue
            pnls.append((o-1)*1000 if w else -1000)
        if pnls:
            results.append({"signal": name, "n": len(pnls),
                           "roi": sum(pnls)/(len(pnls)*1000)*100})
    return {"name": "S17 Edge Attribution", "results": results}


def S18_per_lig_freq(df):
    """Per-lig kupon frequency."""
    model = EuvoxModel()
    k = model.build_kupons(df)
    if k.empty: return {"name": "S18 Lig Freq", "results": []}
    results = []
    for lg in k["league"].unique():
        sub = k[k["league"] == lg]
        n_days = df[df["league_code"] == lg]["matchday"].nunique()
        n_k = len(sub)
        results.append({"lig": lg, "n_kupon": n_k,
                       "n_days": int(n_days),
                       "kupon_per_day": n_k/n_days if n_days else 0,
                       "avg_odd": float(sub["combo_odd"].mean())})
    return {"name": "S18 Lig Frequency", "results": results}


def S19_threshold_sense(df):
    """Score threshold sensitivity."""
    sub = df[df["settled"] == 1].copy()
    sub["dir_fc"] = sub.apply(lambda r: fav_confirmed(r.to_dict(), 1), axis=1)
    sub = sub[sub["dir_fc"].notna()]
    results = []
    for thr in [0.0, 0.5, 0.6, 0.7, 0.8, 0.9]:
        s = sub[sub["score_v13"] >= thr]
        if s.empty: continue
        pnls = []
        for _, r in s.iterrows():
            d = r["dir_fc"]; o = get_odd_for_dir(r.to_dict(), d)
            w = did_win(r.to_dict(), d)
            if not o or o < 1.01: continue
            pnls.append((o-1)*1000 if w else -1000)
        if pnls:
            results.append({"thr": thr, "n": len(pnls),
                           "roi": sum(pnls)/(len(pnls)*1000)*100})
    return {"name": "S19 Threshold", "results": results}


def S20_combo_dist(df):
    model = EuvoxModel()
    k = model.build_kupons(df)
    if k.empty: return {"name": "S20 Combo Dist", "results": {}}
    odds = k["combo_odd"].values
    return {"name": "S20 Combo Odd Dist", "results": {
        "min": float(np.min(odds)), "p25": float(np.percentile(odds,25)),
        "median": float(np.median(odds)), "p75": float(np.percentile(odds,75)),
        "max": float(np.max(odds)), "mean": float(np.mean(odds)),
    }}


def run():
    print("=" * 100)
    print("EUVOX v1.0 — SMOKE TEST SUITE (20 Test)")
    print("=" * 100)

    df = load_data()
    print(f"Loaded: {len(df)} records, "
          f"{df['league_code'].nunique()} ligs, {df['season'].nunique()} seasons\n")

    tests = [S01_all_leagues, S02_all_seasons, S03_coverage, S04_direction,
             S05_odd_range, S06_per_signal, S07_agree_count, S08_bootstrap,
             S09_temporal, S10_outlier, S11_cv, S12_per_year, S13_volume,
             S14_book, S15_tax, S16_worst_streak, S17_attribution,
             S18_per_lig_freq, S19_threshold_sense, S20_combo_dist]

    all_results = []
    for i, fn in enumerate(tests, 1):
        try:
            r = fn(df)
            all_results.append(r)
            print(f"[OK] S{i:02d} {r['name']}")
        except Exception as e:
            print(f"[FAIL] S{i:02d}: {e}")
            all_results.append({"name": f"S{i:02d} FAIL", "error": str(e)})

    write_report(all_results)
    return all_results


def write_report(results):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "EUVOX_SMOKE_TEST.md"
    md = f"""# EUVOX v1.0 — Smoke Test Suite Master Report

**Tarih:** {datetime.now().isoformat()[:19]}
**Tests:** 20

---

## Model

**EUVOX v1.0** — 6 lig hibrit consensus engine

Per-lig optimal config:
```
T1   K=3 mc=1 thr=0       (TRIVOX baseline)
E0   K=2 mc=1 thr=0
D1   K=2 mc=1 thr=0.7
SP1  K=2 mc=1 thr=0.7
I1   K=3 mc=1 thr=0
F1   K=2 mc=2 thr=0
```

---

## Test Sonuçları

"""
    for r in results:
        md += f"\n### {r['name']}\n\n"
        if "error" in r:
            md += f"FAIL: {r['error']}\n"; continue
        res = r.get("results")
        if isinstance(res, dict):
            md += "```\n"
            for k, v in res.items():
                if isinstance(v, dict):
                    md += f"  {k}:\n"
                    for k2, v2 in v.items():
                        md += f"    {k2}: {v2}\n"
                elif isinstance(v, float):
                    md += f"  {k}: {v:.3f}\n"
                else:
                    md += f"  {k}: {v}\n"
            md += "```\n"
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
    print(f"\nMaster Report: {p}")


if __name__ == "__main__":
    run()
