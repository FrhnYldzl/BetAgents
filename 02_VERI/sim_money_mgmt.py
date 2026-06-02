"""
PARA YÖNETİMİ SİMÜLASYONU — hedef% ve süre (time-limit) analizi
================================================================
Soru: %20 hedef yerine DAHA FAZLA / SÜRE koysak sistem farklı mı davranırdı?

Monte Carlo: dönem dinamiğini (manage_period) modeller.
  - dönem başı B0, hedef = B0×(1+T), stop = B0×(1+S, S=-15%)
  - her gün ~4 K3 kupon, sabit stake (dönem-başı bankroll'un %'si)
  - dönem: hedef / stop / süre dolunca biter
DÜRÜST NOT: hedef/süre EDGE üretmez — sadece RİSK/YOL şekillendirir.
"""
import sys
import numpy as np
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RNG = np.random.default_rng(42)
B0 = 5000.0
STOP = -0.15
N_COUPONS = 4          # gün başına ~4 K3 kupon
STAKE_PCT = 0.018      # kupon başına dönem-başı bankroll'un %1.8'i
ODDS = 3.8             # tipik 3-ayak kombine oran
N_SIM = 20000


def run_period(T, D, q, rng):
    B = B0
    target = B0 * (1 + T)
    stopb = B0 * (1 + STOP)
    stake = STAKE_PCT * B0
    for day in range(1, D + 1):
        wins = rng.binomial(N_COUPONS, q)
        B += wins * stake * (ODDS - 1) - (N_COUPONS - wins) * stake
        if B >= target:
            return "target", day, B
        if B <= stopb:
            return "stop", day, B
    return "timeout", D, B


def analyze(T, D, ev_label, q):
    out = {"target": 0, "stop": 0, "timeout": 0}
    days = []
    finals = []
    for _ in range(N_SIM):
        res, day, B = run_period(T, D, q, RNG)
        out[res] += 1
        days.append(day)
        finals.append(B)
    n = N_SIM
    return {
        "p_target": 100 * out["target"] / n,
        "p_stop": 100 * out["stop"] / n,
        "p_timeout": 100 * out["timeout"] / n,
        "med_days": int(np.median(days)),
        "med_final": np.median(finals),
    }


def main():
    print("=" * 74)
    print(f"PARA YÖNETİMİ — hedef% ve süre analizi (B0={B0:.0f}, stop={STOP:.0%}, "
          f"{N_COUPONS} kupon/gün, stake %{STAKE_PCT*100:.1f}, oran {ODDS})")
    print(f"Monte Carlo: {N_SIM:,} dönem/senaryo")
    print("=" * 74)

    for ev_label, q in [("BAŞABAŞ (edge=0)", 1.0 / ODDS),
                        ("GERÇEKÇİ (edge≈-10%)", 0.90 / ODDS)]:
        print(f"\n### Senaryo: {ev_label}  (kupon kazanma olasılığı q={q:.3f})")
        print(f"{'Hedef':>7} {'Süre':>6} {'Hedef%':>8} {'Stop%':>7} {'Süre-doldu%':>12} {'medGün':>7} {'medSonuç':>10}")
        print("-" * 74)
        for T in [0.20, 0.35, 0.50]:
            for D in [30, 60, 9999]:
                r = analyze(T, D, ev_label, q)
                dlabel = "süresiz" if D == 9999 else f"{D}g"
                print(f"{T:>6.0%} {dlabel:>6} {r['p_target']:>7.1f}% {r['p_stop']:>6.1f}% "
                      f"{r['p_timeout']:>11.1f}% {r['med_days']:>7} {r['med_final']:>9.0f}")
        print("-" * 74)


if __name__ == "__main__":
    main()
