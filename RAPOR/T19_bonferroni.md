# T19 — Bonferroni Multi-Test Correction

**Versiyon:** v1.0
**Tarih:** 2026-05-27T22:08:40

---

## Bilimsel Soru

19 ayrı test yaptık. Multiple testing yaparken, **Type I error inflation**
riski var: 20 testten 1'inin rasgele p<0.05 vermesi muhtemel.

**Bonferroni adjusted alpha** = 0.05 / N = 0.05 / 19 = **0.0026**

Sadece bu eşik altındaki p-değerleri "gerçekten" anlamlı kabul edilir.

---

## Tüm Test p-Değerleri

| Test | Açıklama | n | p | Pre-correction | Post-Bonferroni |
|---|---|---:|---:|:---:|:---:|
| T01 | Konsensüs survival K=1 | 100 | 0.200 | [--] | [--] |
| T02 | Sıkı konsensüs K=2 | 14 | 0.500 | [--] | [--] |
| T03 K=2 | FAV_CONFIRMED K=2 | 461 | 0.050 | [--] | [--] |
| T04 E0 | K=1 E0 | 417 | 0.040 | [OK] | [--] |
| T04 T1 | K=1 T1 | 448 | 0.025 | [OK] | [--] |
| T04 D1 | K=1 D1 | 327 | 0.650 | [--] | [--] |
| T06 T1 K=3 | T1-only K=3 | 103 | 0.010 | [OK] | [--] |
| T06 cross-only | 3-ayrı-lig K=3 | 193 | 0.550 | [--] | [--] |
| T07 strict >=2 | T1 K=3 strict | 1 | 1.000 | [--] | [--] |
| T08 Kelly Half | Bankroll +270% | 103 | 0.010 | [OK] | [--] |
| T09 portfolio | Equal 3-league | 397 | 0.300 | [--] | [--] |
| T10 Full Kelly | Bankroll -42% | 103 | 0.950 | [--] | [--] |
| T11 ALL flat | 3-lig flat +81K | 397 | 0.010 | [OK] | [--] |
| T12 W1 entry | Sezon başı +60% | 103 | 0.010 | [OK] | [--] |
| T13 skip dark | Skip in-sample +23K | 80 | 0.050 | [--] | [--] |
| T15 skip OOS | Skip out-of-sample | 47 | 0.500 | [--] | [--] |
| T16 pause | Loss streak pause | 70 | 0.300 | [--] | [--] |
| T17 2526 | 5. sezon replikasyon | 37 | 0.600 | [--] | [--] |
| T18 net %10 | Vergi sonrası 3-lig | 397 | 0.200 | [--] | [--] |

---

## Bonferroni Sonrası Hâlâ Anlamlı Bulgular

**Hiçbiri Bonferroni'yi geçemedi.** Tüm bulgular Type I error olabilir.

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

**Hiçbir test Bonferroni-significant değil.** Replikasyon (T17 + live shadow) kritik.

Akademik dürüstlük: Bonferroni geçemeyen p<0.05 sonuçlarımız da **suggestive** ama kanıt değil.
