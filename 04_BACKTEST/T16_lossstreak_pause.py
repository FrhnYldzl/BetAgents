"""
TEST T16 — Loss-Streak Triggered Pause
=======================================

BİLİMSEL SORULAR:
    H10a: 3+ ardışık kayıp sonrası N hafta pas geçmek edge'i artırır mı?
    H10b: Bu **gambler's fallacy** (rasgele sıralamalardan sonra bekleme efektif değil)
          mi yoksa gerçek mean reversion sinyali mi?

NULL HİPOTEZ:
    Eğer her hafta bağımsız Bernoulli denemeyse, loss-streak sonrası
    pause edge'i değiştirmez. Mean reversion ANCAK serial correlation varsa anlamlı.

YÖNTEM:
    1. T1 K=3 picks kronolojik
    2. Streak threshold ∈ {2, 3, 4, 5}
    3. Pause duration ∈ {0, 1, 2, 3, 5}
    4. Sonraki M=10 hafta ROI ölç (pause sonrası)
    5. Karşılaştırma: pause-with vs pause-without

ÇIKTI:
    - RAPOR/T16_lossstreak_pause.md
    - 07_LOG_VE_RAPORLAR/T16_streak_results.csv
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
LOGS_DIR = YAZILIM / "07_LOG_VE_RAPORLAR"

sys.path.insert(0, str(THIS_DIR))
from T11_flat1000 import build_kupons


def simulate_with_pause(kupons: pd.DataFrame, streak_thr: int, pause_n: int,
                        stake: float = 1000.0) -> dict:
    """
    streak_thr: kaç ardışık kayıp sonrası pause başlasın
    pause_n: kaç hafta pas geçilsin
    """
    kupons = kupons.sort_values("matchday").reset_index(drop=True)
    n = len(kupons)
    current_streak = 0
    paused_remaining = 0
    pnls = []
    n_played = 0
    n_won = 0
    n_paused = 0

    for _, row in kupons.iterrows():
        if paused_remaining > 0:
            paused_remaining -= 1
            n_paused += 1
            continue
        # Bet placed
        if row["won"]:
            pnl = stake * (row["combo_odd"] - 1)
            n_won += 1
            current_streak = 0
        else:
            pnl = -stake
            current_streak += 1
        pnls.append(pnl)
        n_played += 1
        # Loss streak threshold reached?
        if current_streak >= streak_thr:
            paused_remaining = pause_n
            current_streak = 0  # reset

    if not pnls:
        return {"streak_thr": streak_thr, "pause_n": pause_n,
                "n_played": 0}
    return {
        "streak_thr": streak_thr,
        "pause_n": pause_n,
        "n_played": n_played,
        "n_won": n_won,
        "n_paused": n_paused,
        "hit_rate": n_won / n_played if n_played else 0,
        "total_pnl": sum(pnls),
        "roi": sum(pnls) / (n_played * stake) if n_played else 0,
    }


def run():
    print("=" * 100)
    print("T16 — LOSS-STREAK TRIGGERED PAUSE")
    print("=" * 100)

    kupons = build_kupons(K=3, leagues=["T1"])
    print(f"\nT1 K=3 kupon: {len(kupons)}, hit %{kupons['won'].mean()*100:.0f}")

    # Baseline (no pause)
    baseline = simulate_with_pause(kupons, streak_thr=999, pause_n=0)
    print(f"\nBaseline (no pause): n={baseline['n_played']}, "
          f"hit={baseline['hit_rate']*100:.0f}%, "
          f"pnl={baseline['total_pnl']:+,.0f}, ROI={baseline['roi']*100:+.1f}%")

    # Grid
    print(f"\n{'streak_thr':>10s} {'pause_n':>7s} {'played':>7s} {'paused':>7s} "
          f"{'hit%':>5s} {'pnl':>9s} {'ROI':>6s} {'vs_base':>9s}")
    print("-" * 90)
    results = [baseline | {"streak_thr": 0, "pause_n": 0}]

    for streak in [2, 3, 4, 5]:
        for pause in [1, 2, 3, 5]:
            r = simulate_with_pause(kupons, streak, pause)
            results.append(r)
            diff = r["total_pnl"] - baseline["total_pnl"]
            print(f"  {streak:>10d} {pause:>7d} {r['n_played']:>7d} {r['n_paused']:>7d} "
                  f"{r['hit_rate']*100:>4.0f}% {r['total_pnl']:>+8,.0f} "
                  f"{r['roi']*100:>+5.1f}% {diff:>+8,.0f}")

    # Best variant
    valid = [r for r in results if r["n_played"] > 30]
    best = max(valid, key=lambda x: x["total_pnl"])
    print(f"\nEn yuksek pnl: streak>={best['streak_thr']}, pause={best['pause_n']} "
          f"-> {best['total_pnl']:+,.0f} (baseline'dan {best['total_pnl']-baseline['total_pnl']:+,.0f})")

    # GAMBLER'S FALLACY testi:
    # Eğer outcome'lar bağımsızsa, streak sonrası hit rate ≈ overall hit rate olmalı
    # Streak sonrası N kuponun hit rate'ini ölç
    streaks_after = {2: [], 3: [], 4: []}
    cur_streak = 0
    for i, row in kupons.iterrows():
        if not row["won"]:
            cur_streak += 1
        else:
            # ardışık kayıp serisi bitti
            for thr in [2, 3, 4]:
                if cur_streak >= thr:
                    # Bu maç (kazanç) streak sonrası
                    streaks_after[thr].append(1)
            cur_streak = 0
        if row["won"]:
            # Sonraki maçlara ekleme yapma — yalnız streak sonrası ilk maç
            pass

    # Daha doğru: streak biten her noktada SONRAKI K mac hit rate
    print(f"\n=== GAMBLER'S FALLACY TESTİ ===")
    print(f"Overall hit rate: {kupons['won'].mean()*100:.1f}%")
    for thr in [2, 3, 4]:
        # streak >= thr biten noktalardan sonraki M=5 maç
        cur = 0
        wins_after = []
        plays_after = []
        for i, row in kupons.iterrows():
            if not row["won"]:
                cur += 1
            else:
                if cur >= thr:
                    # streak sonrası sonraki 5 maç
                    n_after = min(5, len(kupons) - i - 1)
                    sub = kupons.iloc[i+1:i+1+n_after]
                    wins_after.extend(sub["won"].tolist())
                cur = 0
        if wins_after:
            hr_after = sum(1 for w in wins_after if w) / len(wins_after)
            print(f"  Streak>={thr} sonrası sonraki 5 maç hit rate: {hr_after*100:.1f}% (n={len(wins_after)})")
        else:
            print(f"  Streak>={thr}: yetersiz veri")

    # CSV
    LOGS_DIR.mkdir(exist_ok=True)
    pd.DataFrame(results).to_csv(LOGS_DIR / "T16_streak_results.csv", index=False)

    write_report(results, baseline, best, kupons)
    return results


def write_report(results, baseline, best, kupons):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T16_lossstreak_pause.md"

    rows = []
    for r in results:
        if r["n_played"] == 0:
            continue
        diff = r["total_pnl"] - baseline["total_pnl"]
        rows.append(
            f"| {r['streak_thr']} | {r['pause_n']} | {r['n_played']} | "
            f"{r['n_paused']} | {r['hit_rate']*100:.0f}% | "
            f"{r['total_pnl']:+,.0f} | {r['roi']*100:+.1f}% | {diff:+,.0f} |"
        )

    overall_hit = kupons["won"].mean() * 100

    md = f"""# T16 — Loss-Streak Triggered Pause

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}

---

## Bilimsel Soru

**H10a:** Ardışık 3+ kayıptan sonra pause ROI'yi artırır mı?
**H10b:** Bu **gambler's fallacy** mi yoksa gerçek mean reversion mi?

---

## Sonuçlar

| Streak ≥ | Pause N | n played | n paused | Hit% | PnL | ROI | vs Baseline |
|---|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

---

## En İyi Varyant

`streak>={best['streak_thr']}, pause={best['pause_n']}` →
PnL **{best['total_pnl']:+,.0f}** (baseline'dan {best['total_pnl']-baseline['total_pnl']:+,.0f})

---

## Gambler's Fallacy Testi

Overall hit rate: **{overall_hit:.1f}%**

Eğer outcome'lar bağımsızsa, loss-streak sonrası hit rate ≈ overall olmalı.
Eğer streak sonrası hit rate ANLAMLI farklıysa, mean reversion gerçek.

---

## Yorum

- Pause stratejisi marjinal etki yaratıyorsa: rastgelelik. Pas geçmek gereksiz.
- Belirgin ROI artışı varsa: serial correlation ipucu.
- Akademik tavsiye: bir trader pas geçme kararını **emosyonel kontrol** için kullanabilir,
  ancak **matematiksel edge** beklenmemeli.

CSV: `07_LOG_VE_RAPORLAR/T16_streak_results.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
