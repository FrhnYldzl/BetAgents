"""
TRIVOX v1.0 — Final Production Model
=====================================

ADı: TRIVOX (Tri-Voice Consensus Engine)
SEMBOL: "3 bağımsız ses aynı şeyi söylediğinde, bu duyulması gereken sestir"

MİMARİ:
    Input: signal_snapshots tablosu (her maç için 4 sinyal + odds + outcome)
    Output: kupon önerisi (K=3 leg combo)

PARAMETRELER:
    league_whitelist: ["T1"] (PRIMARY) veya ["T1", "E0", "D1"] (3-LIG)
    K: 3 (combo legs)
    min_confirmers: 1 (≥1 sinyal favori yönü teyit etmeli)
    mode: homogenous (aynı ligten 3 leg)
    stake: 1000 TL flat
    skip_rules: NONE (T15 overfit kanıtladı)
    pause_rules: NONE (T16 gambler's fallacy)

SİNYAL KAYNAKLARI:
    1. Cross-market anomaly (5 alt-check)
    2. Dixon-Coles model confidence
    3. xG luck (mean reversion)
    4. Recent form (rolling 5)

FAV_CONFIRMED FİLTRESİ:
    favori_yön(Pinnacle implied) + en az 1 sinyal aynı yönü teyit ediyor

SELECTION:
    score_v13 en yüksek 3 maç (matchday × league içinde)

KARAR VERİTABANI:
    - Suggestive evidence (p<0.05 pre-correction, n=103)
    - Bonferroni-significant değil → replikasyon kritik
    - Vergi sonrası T1 net ROI +38%

USE:
    >>> from trivox_v1 import TrivoxModel
    >>> model = TrivoxModel(leagues=["T1"])
    >>> result = model.weekly_kupon("2025-05-18")
    >>> print(result)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent.parent


@dataclass
class TrivoxConfig:
    """TRIVOX model konfigürasyonu (varsayılan = T1-only K=3)."""
    name: str = "TRIVOX v1.0"
    leagues: list = field(default_factory=lambda: ["T1"])  # default: T1 only
    K: int = 3
    min_confirmers: int = 1
    mode: str = "homogenous"
    stake: float = 1000.0
    skip_rules: list = field(default_factory=list)  # boş = skip yok
    pause_rules: list = field(default_factory=list)  # boş = pause yok
    tax_rate: float = 0.10
    tax_mode: str = "net_profit"

    def signature(self) -> str:
        """Modelin unique signature'ı (config'i değişince değişir)."""
        return (f"{self.name}/L{'+'.join(sorted(self.leagues))}"
                f"/K{self.K}/MC{self.min_confirmers}"
                f"/{self.mode}")


# ============================================================
# CORE MODEL
# ============================================================

def normalize_dir(d):
    if d in ("HOME", "H", "1"): return "HOME"
    if d in ("AWAY", "A", "2"): return "AWAY"
    if d in ("DRAW", "D", "X"): return "DRAW"
    return d


def fav_confirmed(row: dict, min_confirmers: int = 1) -> str | None:
    """Favori yön + en az N sinyal teyit ediyor mu?"""
    fav = row.get("dir_favorite")
    if not fav:
        return None
    fav_n = normalize_dir(fav)
    sigs = [row.get("dir_anomaly"), row.get("dir_model"),
            row.get("dir_xg"), row.get("dir_form")]
    agreeing = [s for s in sigs if s and normalize_dir(s) == fav_n]
    return fav if len(agreeing) >= min_confirmers else None


def get_odd_for_dir(row: dict, direction: str) -> float | None:
    if direction in ("HOME", "H", "1"): return row.get("odd_1")
    if direction in ("AWAY", "A", "2"): return row.get("odd_2")
    if direction in ("DRAW", "D", "X"): return row.get("odd_X")
    return None


def did_win(row: dict, direction: str) -> bool:
    ftr = row.get("result_1x2")
    if direction in ("HOME", "H", "1"): return ftr == "H"
    if direction in ("AWAY", "A", "2"): return ftr == "A"
    if direction in ("DRAW", "D", "X"): return ftr == "D"
    return False


class TrivoxModel:
    """TRIVOX v1.0 — Consensus kupon engine."""

    def __init__(self, config: TrivoxConfig | None = None, **kwargs):
        if config is None:
            config = TrivoxConfig(**kwargs)
        self.config = config

    def build_kupons(self, df: pd.DataFrame, settled_only: bool = True) -> pd.DataFrame:
        """Bir veri seti üzerinde TRIVOX kuponları üret."""
        df = df.copy()
        if settled_only:
            df = df[df["settled"] == 1]
        df = df[df["league_code"].isin(self.config.leagues)]
        if "matchday" not in df.columns:
            df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()

        # FAV_CONFIRMED
        df["dir_fav_confirmed"] = df.apply(
            lambda r: fav_confirmed(r.to_dict(), self.config.min_confirmers),
            axis=1
        )
        df = df[df["dir_fav_confirmed"].notna()]
        df = df.sort_values("score_v13", ascending=False)

        kupons = []
        K = self.config.K
        for (md, lg), group in df.groupby(["matchday", "league_code"]):
            topK = group.head(K)
            if len(topK) < K:
                continue
            combo_odd = 1.0
            all_won = True
            legs = []
            for _, leg in topK.iterrows():
                d = leg["dir_fav_confirmed"]
                o = get_odd_for_dir(leg.to_dict(), d)
                w = did_win(leg.to_dict(), d)
                if not o or o < 1.01:
                    combo_odd = None
                    break
                combo_odd *= o
                if not w:
                    all_won = False
                legs.append({
                    "home": leg["home_team"], "away": leg["away_team"],
                    "direction": d, "odd": o, "won": w,
                    "result": leg.get("result_1x2"),
                    "score": leg.get("score_v13"),
                })
            if combo_odd is None:
                continue
            kupons.append({
                "matchday": md, "league": lg,
                "combo_odd": combo_odd,
                "won": all_won,
                "stake": self.config.stake,
                "pnl_gross": self.config.stake * (combo_odd - 1) if all_won else -self.config.stake,
                "pnl_net": (
                    self.config.stake * (combo_odd - 1) * (1 - self.config.tax_rate)
                    if all_won else -self.config.stake
                ),
                "legs": legs,
                "K": K,
            })
        return pd.DataFrame(kupons)

    def summary(self, kupons: pd.DataFrame) -> dict:
        """Backtest özeti."""
        if kupons.empty:
            return {"n": 0}
        n = len(kupons); n_won = kupons["won"].sum()
        stake_tot = kupons["stake"].sum()
        pnl_gross = kupons["pnl_gross"].sum()
        pnl_net = kupons["pnl_net"].sum()
        return {
            "name": self.config.name,
            "signature": self.config.signature(),
            "n_kupon": int(n),
            "n_won": int(n_won),
            "hit_rate": float(n_won / n),
            "avg_combo_odd": float(kupons["combo_odd"].mean()),
            "total_stake": float(stake_tot),
            "pnl_gross": float(pnl_gross),
            "pnl_net": float(pnl_net),
            "roi_gross_pct": float(pnl_gross / stake_tot * 100) if stake_tot else 0,
            "roi_net_pct": float(pnl_net / stake_tot * 100) if stake_tot else 0,
            "best_kupon_pnl": float(kupons["pnl_gross"].max()),
            "worst_kupon_pnl": float(kupons["pnl_gross"].min()),
        }

    def __repr__(self):
        return f"TrivoxModel({self.config.signature()})"


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

    print(f"Loaded: {len(df)} match records\n")

    # PRIMARY config — T1 only
    print("=" * 80)
    print("CONFIG A — T1 only K=3 (PRIMARY)")
    print("=" * 80)
    model = TrivoxModel(leagues=["T1"])
    print(f"Model: {model}")
    kupons = model.build_kupons(df)
    summary = model.summary(kupons)
    for k, v in summary.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.2f}")
        else:
            print(f"  {k}: {v}")

    # SECONDARY — 3-lig
    print("\n" + "=" * 80)
    print("CONFIG B — 3-LIG paralel K=3 (alternative)")
    print("=" * 80)
    model_3lig = TrivoxModel(leagues=["T1", "E0", "D1"])
    print(f"Model: {model_3lig}")
    kupons_3lig = model_3lig.build_kupons(df)
    summary_3lig = model_3lig.summary(kupons_3lig)
    for k, v in summary_3lig.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.2f}")
        else:
            print(f"  {k}: {v}")
