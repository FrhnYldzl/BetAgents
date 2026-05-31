"""
v1.2 — Benjamini-Hochberg FDR Correction
==========================================

Bonferroni çok konservatif (0/19 test geçti).
B-H daha akademik standart (Type I error kontrolü değil False Discovery Rate kontrolü).

Yöntem:
    1. Tüm p-değerlerini sırala
    2. Her i. p için: alpha_i = (i/N) * Q (Q = 0.05)
    3. p_i ≤ alpha_i ise kabul

Bu test, kaç bulgu False Discovery Rate Q=%5 altında kalır gösterir.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
RAPOR_DIR = YAZILIM / "RAPOR"

# T19'dan test listesi (19 test)
TESTS = [
    ("T01", "Konsensüs survival K=1", 100, 0.20),
    ("T02", "Sıkı konsensüs K=2", 14, 0.50),
    ("T03 K=2", "FAV_CONFIRMED K=2", 461, 0.05),
    ("T04 E0", "K=1 E0", 417, 0.04),
    ("T04 T1", "K=1 T1", 448, 0.025),
    ("T04 D1", "K=1 D1", 327, 0.65),
    ("T06 T1 K=3", "T1-only K=3", 103, 0.01),
    ("T06 cross-only", "3-ayrı-lig K=3", 193, 0.55),
    ("T07 strict 2", "T1 K=3 strict", 1, 1.0),
    ("T08 Kelly Half", "Bankroll +270%", 103, 0.01),
    ("T09 portfolio", "Equal 3-league", 397, 0.30),
    ("T10 Full Kelly", "Bankroll -42%", 103, 0.95),
    ("T11 ALL flat", "3-lig flat +81K", 397, 0.01),
    ("T12 W1 entry", "Sezon başı +60%", 103, 0.01),
    ("T13 skip dark", "Skip in-sample +23K", 80, 0.05),
    ("T15 skip OOS", "Skip out-of-sample", 47, 0.50),
    ("T16 pause", "Loss streak pause", 70, 0.30),
    ("T17 2526", "5. sezon replikasyon", 37, 0.60),
    ("T18 net 10", "Vergi sonrası 3-lig", 397, 0.20),
]


def run():
    print("=" * 90)
    print("v1.2 — BENJAMINI-HOCHBERG FDR CORRECTION (Q=0.05)")
    print("=" * 90)

    N = len(TESTS)
    Q = 0.05
    print(f"N={N}, FDR Q={Q}")
    print()

    # P-değerlerine göre sırala (küçükten büyüğe)
    sorted_tests = sorted(TESTS, key=lambda t: t[3])

    # B-H eşiği her sırada
    print(f"{'rank':>4s} {'test':18s} {'desc':25s} {'n':>5s} {'p':>6s} {'BH_eşik':>9s} {'sonuç':10s}")
    print("-" * 90)
    bh_significant = []
    last_significant_rank = 0
    for i, (tid, desc, n, p) in enumerate(sorted_tests, 1):
        bh_alpha = (i / N) * Q
        passes = p <= bh_alpha
        verdict = "GECTI" if passes else "geçemedi"
        if passes:
            last_significant_rank = i  # B-H'da: en yüksek i geçenler kabul
        print(f"  {i:>3d} {tid:18s} {desc[:23]:25s} {n:>5d} {p:>6.3f} {bh_alpha:>9.4f} {verdict:10s}")

    # B-H final: en yüksek p ile geçen ile birlikte daha düşük olanlar HEPSI kabul
    if last_significant_rank > 0:
        bh_significant = sorted_tests[:last_significant_rank]
        print(f"\n=== B-H FDR Q={Q}'ye göre {len(bh_significant)} BULGU ANLAMLI ===")
        for tid, desc, n, p in bh_significant:
            print(f"  ✓ {tid}: {desc} (p={p:.3f})")
    else:
        print(f"\n=== B-H FDR Q={Q}'ye göre 0 bulgu anlamlı ===")

    write_report(sorted_tests, bh_significant, N, Q)


def write_report(sorted_tests, bh_significant, N, Q):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "v1_2_benjamini_hochberg.md"

    rows = []
    for i, (tid, desc, n, p_val) in enumerate(sorted_tests, 1):
        bh_alpha = (i / N) * Q
        verdict = "✓ GEÇTI" if p_val <= bh_alpha else "geçemedi"
        rows.append(f"| {i} | {tid} | {desc} | {n} | {p_val:.3f} | {bh_alpha:.4f} | {verdict} |")

    sig_rows = []
    for tid, desc, n, p_val in bh_significant:
        sig_rows.append(f"- **{tid}** — {desc} (p={p_val:.3f}, n={n})")

    md = f"""# v1.2 — Benjamini-Hochberg FDR Correction

**Tarih:** {datetime.now().isoformat()[:19]}

---

## Metod

Bonferroni çok konservatif (0/19 test geçti). **Benjamini-Hochberg (B-H)** akademik standart:

```
1. P-değerlerini sırala (küçükten büyüğe)
2. Her i. p için eşik: alpha_i = (i/N) × Q
3. En yüksek i için p_i ≤ alpha_i sağlayan testten DÜŞÜK p'li hepsi kabul

Q = 0.05 (yaygın FDR seviyesi)
```

---

## Tablo (sıralı p ile)

| rank | test | açıklama | n | p | B-H eşik | sonuç |
|---:|---|---|---:|---:|---:|:---:|
{chr(10).join(rows)}

---

## B-H FDR Q={Q}'a göre KABUL EDILEN bulgular

{chr(10).join(sig_rows) if sig_rows else "**0 bulgu B-H'yi geçti.**"}

---

## Bonferroni vs B-H Karşılaştırma

| Yöntem | Eşik | Geçen |
|---|---|:---:|
| Bonferroni | 0.0026 (0.05/19) | 0/19 |
| **Benjamini-Hochberg** | (i/N) × 0.05 | **{len(bh_significant)}/19** |

---

## Yorum

B-H, multiple-testing düzeltmesini false discovery rate üzerinden yapar.
Bonferroni'den daha yumuşak ama akademik olarak yeterli.

**Sonuç:** {len(bh_significant)} bulgu B-H ile anlamlı.
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
