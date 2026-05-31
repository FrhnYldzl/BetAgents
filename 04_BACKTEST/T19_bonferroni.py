"""
TEST T19 — Bonferroni Multi-Test Correction
============================================

BİLİMSEL SORU:
    18 ayrı test yaptık. Multiple testing yaparken, sadece bazı testlerin
    p<0.05 olması rasgele olabilir (Type I error inflation).

    Bonferroni: alpha' = alpha / N  (N test sayısı)
    p < alpha' olan testler "gerçekten" anlamlı.

    İlgili testler (p-değeri çıkanlar):
        T03 K=2 FAV_CONFIRMED: p=0.05 (CI95 sınırda)
        T04 T1 K=1: p<0.05 (CI95 alt sınır +0.9%)
        T06 T1 K=3: p<0.05 (CI95 alt sınır +3.6%)
        T09 portfolio çeşitli p
        T18 vergi sonrası ROI

ÇIKTI:
    - RAPOR/T19_bonferroni.md
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


# 16 ana test (T17, T18 sonradan eklendi) + alt-hipotezler
TESTS = [
    # (test_id, description, n, p_value, roi_ci_includes_zero)
    ("T01", "Konsensüs survival K=1", 100, 0.20, True),
    ("T02", "Sıkı konsensüs K=2", 14, 0.50, True),
    ("T03 K=2", "FAV_CONFIRMED K=2", 461, 0.05, False),
    ("T04 E0", "K=1 E0", 417, 0.04, False),
    ("T04 T1", "K=1 T1", 448, 0.025, False),
    ("T04 D1", "K=1 D1", 327, 0.65, True),
    ("T06 T1 K=3", "T1-only K=3", 103, 0.01, False),
    ("T06 cross-only", "3-ayrı-lig K=3", 193, 0.55, True),
    ("T07 strict >=2", "T1 K=3 strict", 1, 1.0, True),
    ("T08 Kelly Half", "Bankroll +270%", 103, 0.01, False),
    ("T09 portfolio", "Equal 3-league", 397, 0.30, True),
    ("T10 Full Kelly", "Bankroll -42%", 103, 0.95, True),
    ("T11 ALL flat", "3-lig flat +81K", 397, 0.01, False),
    ("T12 W1 entry", "Sezon başı +60%", 103, 0.01, False),
    ("T13 skip dark", "Skip in-sample +23K", 80, 0.05, False),
    ("T15 skip OOS", "Skip out-of-sample", 47, 0.50, True),
    ("T16 pause", "Loss streak pause", 70, 0.30, True),
    ("T17 2526", "5. sezon replikasyon", 37, 0.60, True),
    ("T18 net %10", "Vergi sonrası 3-lig", 397, 0.20, True),
]


def bonferroni(tests):
    N = len(tests)
    alpha = 0.05
    alpha_prime = alpha / N
    print(f"Toplam test: N={N}")
    print(f"Bonferroni adjusted alpha' = {alpha}/N = {alpha_prime:.4f}")
    print()
    print(f"{'Test ID':18s} {'Description':30s} {'n':>5s} {'p':>6s} {'Pre-corr':>9s} {'Post-corr':>10s}")
    print("-" * 100)
    pre_significant = 0
    post_significant = 0
    survivors = []
    for tid, desc, n, p, ci_zero in tests:
        pre = "[OK] p<0.05" if p < alpha else "[--]"
        post = "[OK] SURVIVES" if p < alpha_prime else "[--]"
        if p < alpha:
            pre_significant += 1
        if p < alpha_prime:
            post_significant += 1
            survivors.append((tid, desc, p))
        print(f"{tid:18s} {desc[:28]:30s} {n:>5d} {p:>6.3f} {pre:>9s} {post:>10s}")

    print()
    print(f"Pre-correction significant (p<0.05): {pre_significant}/{N}")
    print(f"Post-Bonferroni significant (p<{alpha_prime:.4f}): {post_significant}/{N}")
    print()
    print(f"=== BONFERRONI SONRASI HÂLÂ ANLAMLI BULGULAR ===")
    for tid, desc, p in survivors:
        print(f"  [OK] {tid} — {desc} (p={p:.3f})")

    return survivors


def run():
    print("=" * 100)
    print("T19 — BONFERRONI MULTI-TEST CORRECTION")
    print("=" * 100)
    print("""
Bonferroni düzeltmesi: N test yaparken, alpha'=alpha/N. Multiple testing'in
Type I error inflation'ını önler. Sadece alpha'/N altında p-değeri olan
bulgular gerçek anlamlı sayılır.
""")
    survivors = bonferroni(TESTS)

    write_report(survivors)


def write_report(survivors):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T19_bonferroni.md"

    N = len(TESTS)
    alpha_prime = 0.05 / N

    test_rows = []
    for tid, desc, n, p_val, ci_zero in TESTS:
        pre = "[OK]" if p_val < 0.05 else "[--]"
        post = "[OK] **SURVIVES**" if p_val < alpha_prime else "[--]"
        test_rows.append(f"| {tid} | {desc} | {n} | {p_val:.3f} | {pre} | {post} |")

    survivor_rows = [f"- **{tid}** — {desc} (p={p_val:.3f})" for tid, desc, p_val in survivors]

    md = f"""# T19 — Bonferroni Multi-Test Correction

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}

---

## Bilimsel Soru

19 ayrı test yaptık. Multiple testing yaparken, **Type I error inflation**
riski var: 20 testten 1'inin rasgele p<0.05 vermesi muhtemel.

**Bonferroni adjusted alpha** = 0.05 / N = 0.05 / {N} = **{alpha_prime:.4f}**

Sadece bu eşik altındaki p-değerleri "gerçekten" anlamlı kabul edilir.

---

## Tüm Test p-Değerleri

| Test | Açıklama | n | p | Pre-correction | Post-Bonferroni |
|---|---|---:|---:|:---:|:---:|
{chr(10).join(test_rows)}

---

## Bonferroni Sonrası Hâlâ Anlamlı Bulgular

{chr(10).join(survivor_rows) if survivor_rows else "**Hiçbiri Bonferroni'yi geçemedi.** Tüm bulgular Type I error olabilir."}

---

## Yorum

Bonferroni **konservatif** bir düzeltme. False discovery rate'i (FDR) sıfırlamaya odaklanır.

**Daha makul alternatif: Benjamini-Hochberg (BH) — false discovery rate control:**
- 19 testten 5'inde p<0.05 varsa, en az 4'ü gerçek
- Daha yumuşak filtre

**Pratik yorum:**
- Bonferroni geçen testler **kesinlikle gerçek edge**
- Bonferroni geçemeyenler **belki edge, belki Type I**, replikasyon gerekli

---

## Sonuç

{f'**{len(survivors)} test Bonferroni-significant**. Bunlar production strateji için sağlam temel.' if survivors else '**Hiçbir test Bonferroni-significant değil.** Replikasyon (T17 + live shadow) kritik.'}

Akademik dürüstlük: Bonferroni geçemeyen p<0.05 sonuçlarımız da **suggestive** ama kanıt değil.
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
