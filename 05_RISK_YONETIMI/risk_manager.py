"""
SPRINT 2.4 — Transaction Cost & Risk Yönetimi

Bookmaker marjı (vig/overround) net edge'den düşülür. Stake clamp,
daily/weekly loss limit, drawdown stop.

Akademik referans:
    - Levitt (2004): bookmaker pricing
    - Constantinou (2014): bias-adjusted edge
    - Thorp (2000): fractional Kelly criterion
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


# ============================================================
# VIG / OVERROUND
# ============================================================

def overround(odds_dict: dict[str, float]) -> float:
    """
    Bookmaker overround (vig) = sum(1/odds) - 1.
    Tipik iddaa 1X2 için ~%6-10.
    """
    if not odds_dict:
        return 0.0
    s = sum(1.0 / o for o in odds_dict.values() if o and o > 1.0)
    return max(s - 1.0, 0.0)


def remove_vig(odds_dict: dict[str, float]) -> dict[str, float]:
    """
    Vig'i çıkararak true probability tahmini (basic normalization).
    Returns: olasılık dict (toplamı 1).
    """
    if not odds_dict:
        return {}
    raw = {k: 1.0 / v for k, v in odds_dict.items() if v and v > 1.0}
    total = sum(raw.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in raw.items()}


def vig_adjusted_edge(model_prob: float, market_odd: float,
                       vig: float) -> float:
    """
    Vig'i düşürülmüş edge.
    Raw edge: (p * odds - 1)
    Vig-adjusted: bookmaker'ın marjını da iden net.

    Yorum: bookmaker'ın overround'unun "model edge'ini eritmediği" eşik.
    """
    raw_edge = model_prob * market_odd - 1
    # Vig'in yarısını bookmaker eli olarak düş (konservatif)
    net = raw_edge - (vig / 2.0)
    return net


# ============================================================
# STAKE LİMİTLERİ
# ============================================================

@dataclass
class RiskLimits:
    """Risk yönetimi sınırları."""
    max_stake_pct: float = 2.0       # Tek bahis max %2 bankroll
    max_daily_loss_pct: float = 5.0  # Günlük max %5 kayıp
    max_weekly_loss_pct: float = 10.0
    max_drawdown_pct: float = 20.0   # Peak'ten %20 düşüş = durdur
    min_net_edge_pct: float = 3.0    # Vig sonrası min %3 edge
    kelly_fraction: float = 0.20     # 0.20× Kelly
    min_match_count_combo: int = 2   # iddaa MBS=3, ama tek bahis de OK
    max_combo_legs: int = 5          # 5+ leg = aşırı varyans


# ============================================================
# STAKE HESAPLAMA (Kelly + clamp + vig)
# ============================================================

def calc_recommended_stake(
    model_prob: float, market_odd: float, bankroll: float,
    vig: float, limits: RiskLimits,
) -> dict:
    """
    Önerilen stake hesabı + filtreler.

    Returns:
        {
            "stake": float,           # önerilen stake (₺)
            "edge_raw_pct": float,    # ham edge
            "edge_net_pct": float,    # vig-düşülmüş net edge
            "kelly_full_pct": float,  # tam Kelly fraction
            "approved": bool,         # filtreden geçti mi?
            "rejection_reason": str | None,
        }
    """
    raw_edge = (model_prob * market_odd - 1) * 100
    net_edge = vig_adjusted_edge(model_prob, market_odd, vig) * 100

    out = {
        "stake": 0.0,
        "edge_raw_pct": raw_edge,
        "edge_net_pct": net_edge,
        "kelly_full_pct": 0.0,
        "approved": False,
        "rejection_reason": None,
    }

    # Filtre 1: oran geçersiz
    if market_odd <= 1.0 or model_prob <= 0 or model_prob >= 1:
        out["rejection_reason"] = "Geçersiz oran/olasılık"
        return out

    # Filtre 2: net edge yetersiz
    if net_edge < limits.min_net_edge_pct:
        out["rejection_reason"] = f"Net edge %{net_edge:.2f} < eşik %{limits.min_net_edge_pct}"
        return out

    # Kelly
    b = market_odd - 1
    f_star = (model_prob * market_odd - 1) / b
    out["kelly_full_pct"] = f_star * 100

    if f_star <= 0:
        out["rejection_reason"] = "Kelly negatif (model favorit değil)"
        return out

    # Fractional Kelly + max stake clamp
    stake_pct = min(f_star * limits.kelly_fraction, limits.max_stake_pct / 100)
    stake = bankroll * stake_pct

    out["stake"] = stake
    out["approved"] = True
    return out


# ============================================================
# GÜNLÜK / HAFTALIK LOSS LIMIT
# ============================================================

@dataclass
class SessionTracker:
    """Bahis seansının takibi (günlük/haftalık kayıp limiti için)."""
    starting_bankroll: float
    current_bankroll: float = field(init=False)
    peak_bankroll: float = field(init=False)
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    today: date = field(default_factory=date.today)
    bets_today: int = 0

    def __post_init__(self):
        self.current_bankroll = self.starting_bankroll
        self.peak_bankroll = self.starting_bankroll

    def record_bet(self, pnl: float, when: date | None = None):
        when = when or date.today()
        if when != self.today:
            self.daily_pnl = 0.0
            self.today = when
            self.bets_today = 0
        self.daily_pnl += pnl
        self.weekly_pnl += pnl  # haftalık simplistic
        self.current_bankroll += pnl
        if self.current_bankroll > self.peak_bankroll:
            self.peak_bankroll = self.current_bankroll
        self.bets_today += 1

    @property
    def drawdown_pct(self) -> float:
        if self.peak_bankroll <= 0:
            return 0.0
        return (self.peak_bankroll - self.current_bankroll) / self.peak_bankroll * 100

    def can_bet(self, stake: float, limits: RiskLimits) -> tuple[bool, str | None]:
        """Risk limitlerini kontrol et."""
        if stake > self.current_bankroll * (limits.max_stake_pct / 100):
            return False, f"Stake %{stake/self.current_bankroll*100:.1f} > limit %{limits.max_stake_pct}"

        worst_case_today = self.daily_pnl - stake
        if abs(worst_case_today) > self.starting_bankroll * (limits.max_daily_loss_pct / 100) and worst_case_today < 0:
            return False, f"Günlük kayıp limiti aşılır (max %{limits.max_daily_loss_pct})"

        if self.drawdown_pct + (stake / self.peak_bankroll * 100) > limits.max_drawdown_pct:
            return False, f"Drawdown limiti aşılır (max %{limits.max_drawdown_pct})"

        return True, None


# ============================================================
# KOMBO STAKE
# ============================================================

def combo_stake(legs: list[dict], bankroll: float, vig_avg: float,
                 limits: RiskLimits) -> dict:
    """
    Kombo (parlay) için stake. Her leg'in marjı çarpıldığı için
    toplam vig daha büyük olabilir.

    legs: [{"p": float, "odds": float}, ...]
    """
    if not legs or len(legs) < 1:
        return {"approved": False, "stake": 0,
                "rejection_reason": "Boş kombo"}

    if len(legs) > limits.max_combo_legs:
        return {"approved": False, "stake": 0,
                "rejection_reason": f"{len(legs)} leg > limit {limits.max_combo_legs}"}

    prob = 1.0
    odds = 1.0
    for leg in legs:
        prob *= leg["p"]
        odds *= leg["odds"]

    # Kombo vig ~ 1 - (1 - leg_vig)^n
    combo_vig = 1.0 - (1.0 - vig_avg) ** len(legs)

    return {
        **calc_recommended_stake(prob, odds, bankroll, combo_vig, limits),
        "combined_prob": prob,
        "combined_odds": odds,
        "n_legs": len(legs),
        "combo_vig_pct": combo_vig * 100,
    }


# ============================================================
# CLI Test
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SPRINT 2.4 — Risk Manager Demo")
    print("=" * 60)

    # Tipik iddaa 1X2 oranları
    iddaa_odds_1x2 = {"1": 1.85, "X": 3.50, "2": 4.20}
    vig = overround(iddaa_odds_1x2)
    print(f"\n1X2 oranları: {iddaa_odds_1x2}")
    print(f"Overround (vig): %{vig*100:.2f}")
    print(f"Vig-removed olasılıklar: {remove_vig(iddaa_odds_1x2)}")

    print(f"\n--- Bahis önerisi simülasyonu ---")
    limits = RiskLimits()
    cases = [
        # (model_p, market_odd, açıklama)
        (0.60, 1.85, "Model %60 ev kazanır (oran 1.85)"),
        (0.55, 1.85, "Model %55 ev kazanır (zayıf edge)"),
        (0.30, 4.50, "Model %30 (outsider, yüksek oran)"),
        (0.50, 1.95, "Tam fair odds"),
        (0.70, 1.85, "Çok güçlü ev favori"),
    ]
    for p, odd, desc in cases:
        rec = calc_recommended_stake(p, odd, 10000, vig, limits)
        status = "✅" if rec["approved"] else "❌"
        print(f"\n{status} {desc}")
        print(f"   Raw edge: %{rec['edge_raw_pct']:+.2f}  Net edge: %{rec['edge_net_pct']:+.2f}")
        if rec["approved"]:
            print(f"   Önerilen stake: {rec['stake']:.0f} ₺ "
                  f"(Kelly tam %{rec['kelly_full_pct']:.1f}, "
                  f"fractional {limits.kelly_fraction}x)")
        else:
            print(f"   Reddetme: {rec['rejection_reason']}")

    print(f"\n--- Combo (3 leg parlay) ---")
    legs = [
        {"p": 0.60, "odds": 1.85},
        {"p": 0.55, "odds": 1.95},
        {"p": 0.65, "odds": 1.70},
    ]
    cr = combo_stake(legs, 10000, vig, limits)
    print(f"Kombine: prob {cr['combined_prob']:.4f}, odds {cr['combined_odds']:.2f}")
    print(f"Kombo vig: %{cr['combo_vig_pct']:.2f}")
    print(f"Raw edge: %{cr['edge_raw_pct']:+.2f}, Net: %{cr['edge_net_pct']:+.2f}")
    if cr["approved"]:
        print(f"Önerilen stake: {cr['stake']:.0f} ₺")
    else:
        print(f"Red: {cr['rejection_reason']}")
