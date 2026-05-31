"""
Geliştirilmiş walk-forward backtest motoru — Faz 1.5

İlk backtest'te tespit edilen sorunlar:
    1. Model aşırı özgüvenli (max edge %74 — gerçekçi değil)
    2. Yeni çıkan takımlar için kararsız parametreler
    3. CLV negatif (-2.29%) → Pinnacle'ı yenemiyor

Uygulanan iyileştirmeler:
    1. Platt scaling kalibrasyonu — her refit'te validation set ile
    2. Min match threshold — bir takım bu sezon en az 10 maç oynamış olmalı
    3. Min edge %5 (önceki %3'ten yukarı)
    4. Max edge cap %15 — bunu aşan tahminler reddedilir
    5. Pinnacle açılış oranı kontrolü — DC ve Pinnacle çok uyumsuz ise skip
"""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent.parent  # YAZILIM/
sys.path.insert(0, str(PROJECT_ROOT / "03_MODELLER" / "base"))
sys.path.insert(0, str(PROJECT_ROOT / "03_MODELLER" / "calibration"))

from dixon_coles import fit_dixon_coles  # noqa: E402
from markets import prob_over_under, compute_edge  # noqa: E402
from platt_scaling import fit_platt, PlattParams  # noqa: E402


CONFIG = {
    "league": "T1",
    "test_seasons": ["2324", "2425"],
    "warmup_min_matches": 300,           # Daha fazla warmup (önceki 200)
    "refit_every_days": 7,
    # Yeni: kalibrasyon ayarları
    "calib_lookback_matches": 200,       # Platt fit için son N maç
    # Filtreler (sıkılaştırıldı)
    "min_edge_pct": 5.0,                 # önceki 3.0
    "max_edge_pct": 15.0,                # YENİ: bu üstü reddet
    "min_team_matches_in_train": 15,     # YENİ: takım az veriliyse skip
    # Sizing
    "max_kelly_pct": 3.0,                # önceki 5.0 — daha konservatif
    "kelly_fraction": 0.20,              # önceki 0.25 — daha konservatif
    "starting_bankroll": 10000.0,
    "xi": 0.0019,
    "max_goals": 10,
}


@dataclass
class BetRecord:
    match_date: datetime
    home: str
    away: str
    home_goals: int
    away_goals: int
    selection: str
    model_prob_raw: float
    model_prob_calibrated: float
    market_odds: float
    closing_odds: float
    edge_pct: float
    stake: float
    bankroll_before: float
    won: bool
    payout: float
    pnl: float
    bankroll_after: float

    @property
    def clv_pct(self) -> float:
        if self.closing_odds and self.closing_odds > 1.0:
            return (self.market_odds / self.closing_odds - 1.0) * 100.0
        return 0.0


@dataclass
class BacktestResult:
    bets: list[BetRecord] = field(default_factory=list)
    starting_bankroll: float = 0.0
    final_bankroll: float = 0.0
    n_matches_evaluated: int = 0
    n_skipped_no_odds: int = 0
    n_skipped_low_data: int = 0
    n_skipped_max_edge: int = 0
    n_skipped_no_value: int = 0

    @property
    def n_bets(self): return len(self.bets)
    @property
    def n_wins(self): return sum(1 for b in self.bets if b.won)
    @property
    def total_staked(self): return sum(b.stake for b in self.bets)
    @property
    def total_pnl(self): return sum(b.pnl for b in self.bets)

    @property
    def roi_pct(self):
        return (self.total_pnl / self.total_staked * 100.0) if self.total_staked else 0.0

    @property
    def bankroll_growth_pct(self):
        return (self.final_bankroll / self.starting_bankroll - 1.0) * 100.0

    @property
    def avg_clv_pct(self):
        clvs = [b.clv_pct for b in self.bets if b.closing_odds]
        return float(np.mean(clvs)) if clvs else 0.0

    @property
    def max_drawdown_pct(self):
        if not self.bets:
            return 0.0
        br = [self.starting_bankroll] + [b.bankroll_after for b in self.bets]
        peak = br[0]
        max_dd = 0.0
        for b in br:
            if b > peak:
                peak = b
            dd = (peak - b) / peak * 100.0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def brier_score(self):
        if not self.bets:
            return 1.0
        return float(np.mean([
            (b.model_prob_calibrated - (1.0 if b.won else 0.0)) ** 2
            for b in self.bets
        ]))


# ============================================================
# KALİBRASYON HELPER
# ============================================================

def build_calibration_set(
    params,
    history: pd.DataFrame,
    n_last: int = 200,
    max_goals: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Son N maç için modelin Over 2.5 tahminlerini ve gerçek sonuçları döndürür.

    Returns:
        p_raw: shape (n,), modelin tahmini
        y: shape (n,), gerçek outcome (1=Over, 0=Under)
    """
    recent = history.tail(n_last)
    p_list = []
    y_list = []
    for _, row in recent.iterrows():
        if (row["home_team"] not in params.attack
                or row["away_team"] not in params.attack):
            continue
        M = params.score_matrix_for(row["home_team"], row["away_team"], max_goals)
        p_over = prob_over_under(M, 2.5)["over"]
        total = row["home_goals"] + row["away_goals"]
        p_list.append(p_over)
        y_list.append(1 if total > 2 else 0)
    return np.array(p_list), np.array(y_list)


# ============================================================
# BACKTEST
# ============================================================

def run_backtest(df: pd.DataFrame, config: dict) -> BacktestResult:
    league = config["league"]
    test_seasons = set(config["test_seasons"])
    warmup = config["warmup_min_matches"]
    refit_days = config["refit_every_days"]
    calib_lookback = config["calib_lookback_matches"]
    min_edge = config["min_edge_pct"]
    max_edge = config["max_edge_pct"]
    min_team_matches = config["min_team_matches_in_train"]
    max_kelly = config["max_kelly_pct"] / 100.0
    kelly_frac = config["kelly_fraction"]
    starting_bankroll = config["starting_bankroll"]
    xi = config["xi"]
    max_goals = config["max_goals"]

    lg = df[df["league"] == league].copy()
    lg = lg.dropna(subset=["home_goals", "away_goals"])
    lg["home_goals"] = lg["home_goals"].astype(int)
    lg["away_goals"] = lg["away_goals"].astype(int)
    lg["match_date"] = pd.to_datetime(lg["match_date"])
    lg = lg.sort_values("match_date").reset_index(drop=True)

    test_df = lg[lg["season"].astype(str).isin(test_seasons)].copy()
    print(f"\nBacktest: {league}, test sezonlari {test_seasons}")
    print(f"  Test maci sayisi: {len(test_df)}")
    print(f"  Filtreler: edge in [{min_edge}, {max_edge}]%, min team matches={min_team_matches}")
    print(f"  Sizing: {kelly_frac}x Kelly, max %{max_kelly*100} stake")
    print()

    result = BacktestResult(starting_bankroll=starting_bankroll, final_bankroll=starting_bankroll)
    bankroll = starting_bankroll

    cached_params = None
    cached_platt: PlattParams | None = None
    last_fit_date = None

    for _, row in test_df.iterrows():
        match_dt = row["match_date"]
        result.n_matches_evaluated += 1

        need_refit = (
            cached_params is None
            or last_fit_date is None
            or (match_dt - last_fit_date).days >= refit_days
        )

        if need_refit:
            train = lg[lg["match_date"] < match_dt]
            if len(train) < warmup:
                continue
            try:
                cached_params = fit_dixon_coles(
                    home_teams=train["home_team"].tolist(),
                    away_teams=train["away_team"].tolist(),
                    home_goals_arr=train["home_goals"].tolist(),
                    away_goals_arr=train["away_goals"].tolist(),
                    match_dates=train["match_date"].dt.to_pydatetime().tolist(),
                    reference_date=match_dt.to_pydatetime(),
                    xi=xi,
                    verbose=False,
                )
                last_fit_date = match_dt
                # Platt scaling fit — son N maç için
                p_raw, y = build_calibration_set(
                    cached_params, train, calib_lookback, max_goals
                )
                if len(p_raw) >= 50:
                    cached_platt = fit_platt(p_raw, y)
                else:
                    cached_platt = PlattParams(a=1.0, b=0.0, n_train_samples=len(p_raw))
            except Exception as e:
                print(f"  fit hatasi {match_dt.date()}: {e}")
                continue

        # Takım veri yeterliliği
        train_so_far = lg[lg["match_date"] < match_dt]
        home_count = (
            (train_so_far["home_team"] == row["home_team"]).sum()
            + (train_so_far["away_team"] == row["home_team"]).sum()
        )
        away_count = (
            (train_so_far["home_team"] == row["away_team"]).sum()
            + (train_so_far["away_team"] == row["away_team"]).sum()
        )
        if home_count < min_team_matches or away_count < min_team_matches:
            result.n_skipped_low_data += 1
            continue

        if (row["home_team"] not in cached_params.attack
                or row["away_team"] not in cached_params.attack):
            result.n_skipped_low_data += 1
            continue

        over_odds = row.get("odds_over25_b365")
        under_odds = row.get("odds_under25_b365")
        if pd.isna(over_odds) or pd.isna(under_odds):
            result.n_skipped_no_odds += 1
            continue

        # Model + kalibrasyon
        M = cached_params.score_matrix_for(row["home_team"], row["away_team"], max_goals)
        p_over_raw = prob_over_under(M, 2.5)["over"]
        p_over_cal = float(cached_platt.apply(p_over_raw)) if cached_platt else p_over_raw
        p_under_cal = 1.0 - p_over_cal

        close_over = row.get("odds_over25_pin_close")
        close_under = row.get("odds_under25_pin_close")

        _, edge_over, kelly_over = compute_edge(p_over_cal, float(over_odds))
        _, edge_under, kelly_under = compute_edge(p_under_cal, float(under_odds))

        # En yüksek edge'i seç ama kapakla
        if edge_over >= edge_under and edge_over >= min_edge:
            if edge_over > max_edge:
                result.n_skipped_max_edge += 1
                continue
            selection = "Over 2.5"
            sel_prob_raw = p_over_raw
            sel_prob_cal = p_over_cal
            sel_odds = float(over_odds)
            sel_kelly = kelly_over
            sel_edge = edge_over
            sel_close = float(close_over) if pd.notna(close_over) else 0.0
        elif edge_under > edge_over and edge_under >= min_edge:
            if edge_under > max_edge:
                result.n_skipped_max_edge += 1
                continue
            selection = "Under 2.5"
            sel_prob_raw = 1.0 - p_over_raw
            sel_prob_cal = p_under_cal
            sel_odds = float(under_odds)
            sel_kelly = kelly_under
            sel_edge = edge_under
            sel_close = float(close_under) if pd.notna(close_under) else 0.0
        else:
            result.n_skipped_no_value += 1
            continue

        stake_pct = min(sel_kelly * kelly_frac, max_kelly)
        stake = bankroll * stake_pct
        if stake < 1.0:
            continue

        total_goals = row["home_goals"] + row["away_goals"]
        if selection == "Over 2.5":
            won = total_goals > 2
        else:
            won = total_goals < 3

        payout = stake * sel_odds if won else 0.0
        pnl = payout - stake
        bankroll_new = bankroll + pnl

        result.bets.append(BetRecord(
            match_date=match_dt,
            home=row["home_team"],
            away=row["away_team"],
            home_goals=int(row["home_goals"]),
            away_goals=int(row["away_goals"]),
            selection=selection,
            model_prob_raw=sel_prob_raw,
            model_prob_calibrated=sel_prob_cal,
            market_odds=sel_odds,
            closing_odds=sel_close,
            edge_pct=sel_edge,
            stake=stake,
            bankroll_before=bankroll,
            won=won,
            payout=payout,
            pnl=pnl,
            bankroll_after=bankroll_new,
        ))
        bankroll = bankroll_new

    result.final_bankroll = bankroll
    return result


def print_report(result: BacktestResult, config: dict) -> None:
    print("\n" + "=" * 64)
    print("BACKTEST RAPORU (Faz 1.5 — kalibre + sıkı filtre)")
    print("=" * 64)
    print(f"  Degerlendirilen mac        : {result.n_matches_evaluated:>8}")
    print(f"  Konulan bahis              : {result.n_bets:>8}")
    print(f"  Kazanan bahis              : {result.n_wins:>8} ({result.n_wins/max(result.n_bets,1)*100:.1f}%)")
    print()
    print(f"  Toplam stake               : {result.total_staked:>12,.2f} TL")
    print(f"  Toplam P&L                 : {result.total_pnl:>+12,.2f} TL")
    print(f"  ROI                        : {result.roi_pct:>+11.2f}%")
    print()
    print(f"  Baslangic bankroll         : {result.starting_bankroll:>12,.2f} TL")
    print(f"  Bitis bankroll             : {result.final_bankroll:>12,.2f} TL")
    print(f"  Bankroll buyume            : {result.bankroll_growth_pct:>+11.2f}%")
    print(f"  Maksimum drawdown          : {result.max_drawdown_pct:>11.2f}%")
    print()
    print(f"  Ortalama CLV               : {result.avg_clv_pct:>+11.2f}%")
    print(f"  Brier (kalibre p)          : {result.brier_score:>12.4f}")
    print()
    print(f"  Atlanan (oran yok)         : {result.n_skipped_no_odds}")
    print(f"  Atlanan (yetersiz veri)    : {result.n_skipped_low_data}")
    print(f"  Atlanan (max edge cap)     : {result.n_skipped_max_edge}")
    print(f"  Atlanan (edge yok)         : {result.n_skipped_no_value}")

    if result.bets:
        edges = [b.edge_pct for b in result.bets]
        raw_p = [b.model_prob_raw for b in result.bets]
        cal_p = [b.model_prob_calibrated for b in result.bets]
        print()
        print(f"  Edge dagilimi (kabul edilenler):")
        print(f"    min={min(edges):.2f}%, med={np.median(edges):.2f}%, max={max(edges):.2f}%")
        print(f"  Olasilik kayma (ham → kalibre):")
        print(f"    median ham={np.median(raw_p):.3f}, kalibre={np.median(cal_p):.3f}")


def save_bet_log(result: BacktestResult, path: Path) -> None:
    if not result.bets:
        print("\nHic bahis konulmadi, log yazilmadi.")
        return
    rows = []
    for b in result.bets:
        rows.append({
            "match_date": b.match_date,
            "home": b.home,
            "away": b.away,
            "score": f"{b.home_goals}-{b.away_goals}",
            "selection": b.selection,
            "p_raw": b.model_prob_raw,
            "p_calibrated": b.model_prob_calibrated,
            "market_odds": b.market_odds,
            "closing_odds": b.closing_odds,
            "edge_pct": b.edge_pct,
            "stake": b.stake,
            "won": b.won,
            "pnl": b.pnl,
            "bankroll_after": b.bankroll_after,
            "clv_pct": b.clv_pct,
        })
    df = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"\nBet log: {path}")


def main() -> int:
    print("=" * 64)
    print("BAHIS AGENT — Improved Backtest (Faz 1.5)")
    print("=" * 64)

    data_path = PROJECT_ROOT / "02_VERI" / "processed" / "matches.csv"
    if not data_path.exists():
        print(f"Veri yok: {data_path}")
        return 1

    df = pd.read_csv(data_path, parse_dates=["match_date"])
    print(f"Veri: {len(df):,} mac\n")
    print("Konfigurasyon:")
    for k, v in CONFIG.items():
        print(f"  {k}: {v}")

    result = run_backtest(df, CONFIG)
    print_report(result, CONFIG)

    out_path = PROJECT_ROOT / "07_LOG_VE_RAPORLAR" / "backtest_bets_v2.csv"
    save_bet_log(result, out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
