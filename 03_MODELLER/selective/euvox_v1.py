"""
EUVOX v1.0 — European Voice Consensus Engine
==============================================

Türkiye ligi (TRIVOX'tan) + 5 Avrupa ligi için per-lig optimal config'li model.

Per-lig optimal config (E11 tuning):
    T1   K=3 mc=1 thr=0      → ROI +51.5%   (TRIVOX, en güçlü)
    E0   K=2 mc=1 thr=0      → ROI +16.1%
    D1   K=2 mc=1 thr=0.7    → ROI +11.3%
    SP1  K=2 mc=1 thr=0.7    → ROI +13.0%
    I1   K=3 mc=1 thr=0      → ROI +12.2%
    F1   K=2 mc=2 thr=0      → ROI +14.9%

KULLANIM:
    >>> from euvox_v1 import EuvoxModel
    >>> model = EuvoxModel()
    >>> kupons = model.weekly_picks("2025-05-18")
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent.parent

sys.path.insert(0, str(THIS_DIR))
from trivox_v1 import (
    fav_confirmed, normalize_dir, get_odd_for_dir, did_win,
    TrivoxConfig, TrivoxModel,
)


# Per-lig optimal config (v1.1 — fuzzy xG sonrası retune)
EUVOX_LEAGUE_CONFIGS = {
    "T1":  {"K": 3, "min_confirmers": 1, "score_thr": 0.0},   # ROI +51.5%
    "E0":  {"K": 2, "min_confirmers": 1, "score_thr": 0.0},   # ROI +11.7%
    "D1":  {"K": 3, "min_confirmers": 1, "score_thr": 0.7},   # ROI +21.5% (xG 2x)
    "SP1": {"K": 2, "min_confirmers": 1, "score_thr": 0.0},   # ROI +8.4%
    "I1":  {"K": 2, "min_confirmers": 2, "score_thr": 0.7},   # ROI +31.9% (xG 2.6x)
    "F1":  {"K": 2, "min_confirmers": 2, "score_thr": 0.0},   # ROI +25.8%
}


@dataclass
class EuvoxConfig:
    name: str = "EUVOX v1.0"
    leagues: list = field(default_factory=lambda: list(EUVOX_LEAGUE_CONFIGS.keys()))
    stake: float = 1000.0
    tax_rate: float = 0.10
    league_configs: dict = field(default_factory=lambda: dict(EUVOX_LEAGUE_CONFIGS))

    def signature(self) -> str:
        return f"{self.name}/L{'+'.join(sorted(self.leagues))}"


class EuvoxModel:
    """EUVOX v1.0 — 6-lig hibrit consensus engine."""

    def __init__(self, config: EuvoxConfig | None = None):
        self.config = config or EuvoxConfig()

    def build_kupons(self, df: pd.DataFrame, settled_only: bool = True) -> pd.DataFrame:
        """Per-lig konfige göre kuponlar üret."""
        df = df.copy()
        if settled_only:
            df = df[df["settled"] == 1]
        if "matchday" not in df.columns:
            df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()

        all_kupons = []
        for lg in self.config.leagues:
            if lg not in self.config.league_configs:
                continue
            cfg = self.config.league_configs[lg]
            K = cfg["K"]; mc = cfg["min_confirmers"]; thr = cfg["score_thr"]

            sub = df[df["league_code"] == lg].copy()
            sub["dir_fc"] = sub.apply(
                lambda r: fav_confirmed(r.to_dict(), mc), axis=1
            )
            sub = sub[sub["dir_fc"].notna()]
            if thr > 0:
                sub = sub[sub["score_v13"] >= thr]
            sub = sub.sort_values("score_v13", ascending=False)

            for md, group in sub.groupby("matchday"):
                topK = group.head(K)
                if len(topK) < K:
                    continue
                combo_odd = 1.0
                all_won = True
                legs = []
                for _, leg in topK.iterrows():
                    d = leg["dir_fc"]
                    o = get_odd_for_dir(leg.to_dict(), d)
                    w = did_win(leg.to_dict(), d)
                    if not o or o < 1.01:
                        combo_odd = None; break
                    combo_odd *= o
                    if not w: all_won = False
                    legs.append({
                        "home": leg["home_team"], "away": leg["away_team"],
                        "direction": d, "odd": o, "won": w,
                        "result": leg.get("result_1x2"),
                        "score": leg.get("score_v13"),
                    })
                if combo_odd is None: continue
                pnl_gross = self.config.stake * (combo_odd - 1) if all_won else -self.config.stake
                pnl_net = (
                    self.config.stake * (combo_odd - 1) * (1 - self.config.tax_rate)
                    if all_won else -self.config.stake
                )
                all_kupons.append({
                    "matchday": md, "league": lg, "K": K,
                    "config": f"K{K}/mc{mc}/thr{thr}",
                    "combo_odd": combo_odd, "won": all_won,
                    "stake": self.config.stake,
                    "pnl_gross": pnl_gross, "pnl_net": pnl_net,
                    "legs": legs,
                })
        return pd.DataFrame(all_kupons)

    def summary(self, kupons: pd.DataFrame) -> dict:
        if kupons.empty:
            return {"n": 0}
        n = len(kupons); n_won = int(kupons["won"].sum())
        stake_tot = float(kupons["stake"].sum())
        pnl_gross = float(kupons["pnl_gross"].sum())
        pnl_net = float(kupons["pnl_net"].sum())
        return {
            "name": self.config.name,
            "signature": self.config.signature(),
            "n_kupon": n, "n_won": n_won,
            "hit_rate": n_won / n,
            "avg_combo_odd": float(kupons["combo_odd"].mean()),
            "total_stake": stake_tot,
            "pnl_gross": pnl_gross, "pnl_net": pnl_net,
            "roi_gross_pct": pnl_gross / stake_tot * 100 if stake_tot else 0,
            "roi_net_pct": pnl_net / stake_tot * 100 if stake_tot else 0,
            "best_pnl": float(kupons["pnl_gross"].max()),
            "worst_pnl": float(kupons["pnl_gross"].min()),
        }

    def per_league_summary(self, kupons: pd.DataFrame) -> list[dict]:
        if kupons.empty: return []
        out = []
        for lg in kupons["league"].unique():
            sub = kupons[kupons["league"] == lg]
            n = len(sub)
            stake = sub["stake"].sum()
            pnl = sub["pnl_gross"].sum()
            out.append({
                "league": lg, "n": n,
                "hit_rate": float(sub["won"].mean()),
                "avg_odd": float(sub["combo_odd"].mean()),
                "pnl_gross": float(pnl),
                "roi_pct": float(pnl / stake * 100) if stake else 0,
                "config": sub["config"].iloc[0],
            })
        return sorted(out, key=lambda x: x["pnl_gross"], reverse=True)


# ============================================================
# DEMO
# ============================================================

if __name__ == "__main__":
    import sqlite3
    db_path = YAZILIM / "02_VERI" / "bahis_agent.db"
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT * FROM signal_snapshots WHERE source='football_data'", conn
    )
    conn.close()

    model = EuvoxModel()
    print(f"Model: {model.config.signature()}\n")
    kupons = model.build_kupons(df)
    summary = model.summary(kupons)
    print("=== EUVOX v1.0 — Genel Performans ===")
    for k, v in summary.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.2f}")
        else:
            print(f"  {k}: {v}")

    print("\n=== Per-Lig Performans ===")
    print(f"{'Lig':5s} {'config':25s} {'n':>4s} {'hit%':>5s} {'odd':>5s} {'pnl':>10s} {'ROI':>6s}")
    for r in model.per_league_summary(kupons):
        print(f"  {r['league']:4s} {r['config']:23s} {r['n']:>4d} "
              f"{r['hit_rate']*100:>4.0f}% {r['avg_odd']:>5.2f} "
              f"{r['pnl_gross']:>+9,.0f} {r['roi_pct']:>+5.1f}%")
