"""
Walk-forward backtest motoru.

Stratejimiz (FAZ 1):
    - Süper Lig (T1) odaklı
    - Alt/Üst 2.5 pazarı
    - Her yeni hafta için modeli o tarihe kadar olan verilerle yeniden fit et
    - Edge > %3 olan bahisler için 0.25x Kelly stake
    - iddaa simülasyonu: Bet365 B365>2.5 ve B365<2.5 oranlarını kullan
    - CLV referansı: Pinnacle kapanış (PC>2.5, PC<2.5)

Hipotezimiz:
    Dixon-Coles modeli, Bet365 marjını (~%5-7) yenebilecek kadar
    doğru Alt/Üst 2.5 olasılık tahmini yapar mı?

Çıktı:
    Backtest raporu — ROI, CLV ortalaması, calibration, drawdown
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Windows konsol encoding
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Modülleri import et
THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent.parent  # YAZILIM/
sys.path.insert(0, str(PROJECT_ROOT / "03_MODELLER" / "base"))

from dixon_coles import fit_dixon_coles  # noqa: E402
from markets import prob_over_under, compute_edge  # noqa: E402


# ============================================================
# YAPILANDIRMA
# ============================================================

CONFIG = {
    "league": "T1",                  # Süper Lig
    "test_seasons": ["2324", "2425"], # Test edilecek sezonlar
    "warmup_min_matches": 200,        # Model fit için minimum maç
    "refit_every_days": 7,            # Modeli haftada 1 yeniden fit et
    "min_edge_pct": 3.0,              # Edge eşiği
    "max_kelly_pct": 5.0,             # Tek bahis cap
    "kelly_fraction": 0.25,           # Quarter Kelly
    "starting_bankroll": 10000.0,
    "xi": 0.0019,                     # Zaman bozulması
    "max_goals": 10,
}


# ============================================================
# BAHIS KAYDI
# ============================================================

@dataclass
class BetRecord:
    match_date: datetime
    home: str
    away: str
    home_goals: int
    away_goals: int
    selection: str            # "Over 2.5" veya "Under 2.5"
    model_prob: float
    market_odds: float        # bahisi koyduğumuz oran (B365)
    closing_odds: float       # Pinnacle kapanış
    edge_pct: float
    stake: float
    bankroll_before: float
    won: bool
    payout: float
    pnl: float
    bankroll_after: float

    @property
    def clv_pct(self) -> float:
        """Closing Line Value: (aldigimiz oran / kapanis oran) - 1"""
        if self.closing_odds and self.closing_odds > 1.0:
            return (self.market_odds / self.closing_odds - 1.0) * 100.0
        return 0.0


@dataclass
class BacktestResult:
    bets: list[BetRecord] = field(default_factory=list)
    starting_bankroll: float = 0.0
    final_bankroll: float = 0.0
    n_matches_evaluated: int = 0

    @property
    def n_bets(self) -> int:
        return len(self.bets)

    @property
    def n_wins(self) -> int:
        return sum(1 for b in self.bets if b.won)

    @property
    def total_staked(self) -> float:
        return sum(b.stake for b in self.bets)

    @property
    def total_pnl(self) -> float:
        return sum(b.pnl for b in self.bets)

    @property
    def roi_pct(self) -> float:
        if self.total_staked == 0:
            return 0.0
        return (self.total_pnl / self.total_staked) * 100.0

    @property
    def bankroll_growth_pct(self) -> float:
        if self.starting_bankroll == 0:
            return 0.0
        return (self.final_bankroll / self.starting_bankroll - 1.0) * 100.0

    @property
    def avg_clv_pct(self) -> float:
        if not self.bets:
            return 0.0
        clvs = [b.clv_pct for b in self.bets if b.closing_odds]
        return float(np.mean(clvs)) if clvs else 0.0

    @property
    def max_drawdown_pct(self) -> float:
        if not self.bets:
            return 0.0
        bankrolls = [self.starting_bankroll] + [b.bankroll_after for b in self.bets]
        peak = bankrolls[0]
        max_dd = 0.0
        for b in bankrolls:
            if b > peak:
                peak = b
            dd = (peak - b) / peak * 100.0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def brier_score(self) -> float:
        """
        Brier score: ortalama (p - outcome)^2.
        İki sınıf (over/under) — düşük daha iyi. < 0.25 = bilgi var.
        """
        if not self.bets:
            return 1.0
        return float(np.mean([
            (b.model_prob - (1.0 if b.won else 0.0)) ** 2
            for b in self.bets
        ]))


# ============================================================
# ANA BACKTEST
# ============================================================

def run_backtest(df: pd.DataFrame, config: dict) -> BacktestResult:
    """
    Walk-forward backtest yürütücüsü.

    Args:
        df: tüm maçların normalize edilmiş veri seti
        config: yapılandırma sözlüğü

    Returns:
        BacktestResult
    """
    league = config["league"]
    test_seasons = set(config["test_seasons"])
    warmup = config["warmup_min_matches"]
    refit_days = config["refit_every_days"]
    min_edge = config["min_edge_pct"]
    max_kelly = config["max_kelly_pct"] / 100.0
    kelly_frac = config["kelly_fraction"]
    starting_bankroll = config["starting_bankroll"]
    xi = config["xi"]
    max_goals = config["max_goals"]

    # Lig filtre + sırala
    lg = df[df["league"] == league].copy()
    lg = lg.dropna(subset=["home_goals", "away_goals"])
    lg["home_goals"] = lg["home_goals"].astype(int)
    lg["away_goals"] = lg["away_goals"].astype(int)
    lg["match_date"] = pd.to_datetime(lg["match_date"])
    lg = lg.sort_values("match_date").reset_index(drop=True)

    # Test maçları: sadece bahis koyacağımız sezonlar
    test_mask = lg["season"].astype(str).isin(test_seasons)
    test_df = lg[test_mask].copy()

    result = BacktestResult(starting_bankroll=starting_bankroll)
    result.final_bankroll = starting_bankroll

    last_fit_date: datetime | None = None
    cached_params = None

    print(f"\nBacktest baslatildi: {league}, test sezonlari {test_seasons}")
    print(f"  Test maci sayisi: {len(test_df)}")
    print(f"  Baslangic bankroll: {starting_bankroll:,.0f} TL")
    print()

    bankroll = starting_bankroll
    eval_count = 0
    skipped_no_odds = 0

    for idx, row in test_df.iterrows():
        match_dt = row["match_date"]
        eval_count += 1

        # Modeli yeniden fit et (haftalık)
        need_refit = (
            cached_params is None
            or last_fit_date is None
            or (match_dt - last_fit_date).days >= refit_days
        )

        if need_refit:
            # Bu tarihten önceki TÜM maçları kullan
            train = lg[lg["match_date"] < match_dt]
            if len(train) < warmup:
                continue  # yeterli veri yok, atla
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
            except Exception as e:
                print(f"  fit hatasi {match_dt.date()}: {e}")
                continue

        # Takım daha önce görülmemişse skip (örn. yeni çıkan)
        if (
            row["home_team"] not in cached_params.attack
            or row["away_team"] not in cached_params.attack
        ):
            continue

        # iddaa oranları (Bet365 = piyasa simülasyonu)
        over_odds = row.get("odds_over25_b365")
        under_odds = row.get("odds_under25_b365")
        if pd.isna(over_odds) or pd.isna(under_odds):
            skipped_no_odds += 1
            continue

        # Modeli kullan
        M = cached_params.score_matrix_for(row["home_team"], row["away_team"], max_goals)
        p_over = prob_over_under(M, 2.5)["over"]
        p_under = 1.0 - p_over

        # Pinnacle closing (CLV için)
        close_over = row.get("odds_over25_pin_close")
        close_under = row.get("odds_under25_pin_close")

        # Hangi seçim daha çok value?
        _, edge_over, kelly_over = compute_edge(p_over, float(over_odds))
        _, edge_under, kelly_under = compute_edge(p_under, float(under_odds))

        # En yüksek edge'i seç (eğer eşiği geçiyorsa)
        if edge_over >= min_edge and edge_over >= edge_under:
            selection = "Over 2.5"
            sel_prob = p_over
            sel_odds = float(over_odds)
            sel_kelly = kelly_over
            sel_edge = edge_over
            sel_closing = float(close_over) if pd.notna(close_over) else 0.0
        elif edge_under >= min_edge and edge_under > edge_over:
            selection = "Under 2.5"
            sel_prob = p_under
            sel_odds = float(under_odds)
            sel_kelly = kelly_under
            sel_edge = edge_under
            sel_closing = float(close_under) if pd.notna(close_under) else 0.0
        else:
            continue  # value yok

        # Stake hesabı (0.25x Kelly, cap %5)
        stake_pct = min(sel_kelly * kelly_frac, max_kelly)
        stake = bankroll * stake_pct
        if stake < 1.0:
            continue

        # Sonucu değerlendir
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
            model_prob=sel_prob,
            market_odds=sel_odds,
            closing_odds=sel_closing,
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
    result.n_matches_evaluated = eval_count
    return result


# ============================================================
# RAPOR
# ============================================================

def print_report(result: BacktestResult) -> None:
    print("\n" + "=" * 64)
    print("BACKTEST RAPORU")
    print("=" * 64)
    print(f"  Degerlendirilen mac sayisi : {result.n_matches_evaluated:>8}")
    print(f"  Konulan bahis sayisi       : {result.n_bets:>8}")
    print(f"  Kazanan bahis              : {result.n_wins:>8} ({result.n_wins/max(result.n_bets,1)*100:.1f}%)")
    print()
    print(f"  Toplam stake               : {result.total_staked:>12,.2f} TL")
    print(f"  Toplam P&L                 : {result.total_pnl:>+12,.2f} TL")
    print(f"  ROI (P&L / stake)          : {result.roi_pct:>+11.2f}%")
    print()
    print(f"  Baslangic bankroll         : {result.starting_bankroll:>12,.2f} TL")
    print(f"  Bitis bankroll             : {result.final_bankroll:>12,.2f} TL")
    print(f"  Bankroll buyume            : {result.bankroll_growth_pct:>+11.2f}%")
    print(f"  Maksimum drawdown          : {result.max_drawdown_pct:>11.2f}%")
    print()
    print(f"  Ortalama CLV               : {result.avg_clv_pct:>+11.2f}%")
    print(f"  Brier score                : {result.brier_score:>12.4f}")

    # Edge dağılımı
    if result.bets:
        edges = [b.edge_pct for b in result.bets]
        print()
        print(f"  Edge dagilimi: min={min(edges):.1f}%, med={np.median(edges):.1f}%, max={max(edges):.1f}%")

    # Yorum
    print()
    print("--- Yorumlama ---")
    if result.n_bets < 30:
        print("  UYARI: Cok az bahis, istatistiksel olarak anlamsiz.")
    elif result.roi_pct > 3:
        print("  Pozitif ROI gozlemlendi — ama 200+ bet'e kadar 'sans' olabilir.")
    elif result.roi_pct > 0:
        print("  Marjinal pozitif — CLV'ye bakmak gerek.")
    else:
        print("  Negatif ROI — modelin Alt/Ust 2.5 pazarinda edge'i yok gibi.")

    if result.avg_clv_pct > 2:
        print("  CLV +%2 ustu — KUVVETLI bir sinyal, model gercek edge bulmus olabilir.")
    elif result.avg_clv_pct > 0:
        print("  CLV pozitif ama marjinal.")
    else:
        print("  CLV negatif — Pinnacle'i yenemiyor, edge yok.")


def save_bet_log(result: BacktestResult, path: Path) -> None:
    rows = []
    for b in result.bets:
        rows.append({
            "match_date": b.match_date,
            "home": b.home,
            "away": b.away,
            "score": f"{b.home_goals}-{b.away_goals}",
            "selection": b.selection,
            "model_prob": b.model_prob,
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
    print(f"\nBet log kaydedildi: {path}")


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    print("=" * 64)
    print("BAHIS AGENT — Walk-Forward Backtest")
    print("=" * 64)

    data_path = PROJECT_ROOT / "02_VERI" / "processed" / "matches.csv"
    if not data_path.exists():
        print(f"Veri yok: {data_path}")
        return 1

    df = pd.read_csv(data_path, parse_dates=["match_date"])
    print(f"Veri yuklendi: {len(df):,} mac")
    print(f"Konfigurasyon:")
    for k, v in CONFIG.items():
        print(f"  {k}: {v}")

    result = run_backtest(df, CONFIG)
    print_report(result)

    # Bet log'u kaydet
    out_path = PROJECT_ROOT / "07_LOG_VE_RAPORLAR" / "backtest_bets.csv"
    save_bet_log(result, out_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
