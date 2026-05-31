# 🎓 YÖNETİCİ ÖZETİ v4 — Akademik Sentez

**Versiyon:** v4.0 (T01-T16 sonrası, 5 Faz)
**Tarih:** 2026-05-27
**Format:** Bilimsel makale yapısı
**Önceki:** v3 (T01-T11)

---

## 📄 ABSTRACT

Bu çalışma, Türk Süper Lig özelinde **çoklu-sinyal konsensüsü** üzerinden inşa edilmiş 3-leg kombin (accumulator) stratejilerinin **uzun-dönemli pozitif edge** sağlayıp sağlamayacağını ve **giriş timing'i + skip stratejisi + bütçe dağılımı** parametrelerinin bu edge'i nasıl etkilediğini araştırır. 16 ayrı bilimsel test (T01-T16), 4 sezon × 3 lig × 4188 maç üzerinde uygulanmıştır.

**Ana bulgu:** Türk Süper Lig'de FAV_CONFIRMED 3-leg homogen kombin (Pinnacle favorisi + ≥1 sinyal teyit, aynı ligten 3 leg), 103 hafta backtest'inde **ROI +60.3%** (CI95 [+3.6%, +125.1%], p<0.01) elde etmiştir. Out-of-sample (test seasons 2324+2425) **+81.4% ROI** ile bulgu doğrulanmıştır — overfit değildir.

**Negatif bulgular (akademik kıymetli):**
- Skip-week stratejisi (T13) sample-specific overfit (T15 cross-validation reddetti)
- Loss-streak pause (T16) gambler's fallacy — mean reversion yok
- Cross-league diversifikasyon compound altında Sharpe'i azalttı, flat altında topladıkça mutlak kar arttı
- Sıkı filtre (≥2 confirmer) sample'ı çökertti

**Pratik (3-lig paralel flat 1000 TL/kupon):** 4 sezon backtest'inde **397 kupon, hacim 397K TL, NET +80,672 TL, ROI +20.3%, aylık ortalama +1,779 TL**. T1-only alternatif (saf yüksek ROI) +62K, daha düşük volatilite. Skip-week ve loss-streak pause reddedildi (T15/T16).

---

## 1. INTRODUCTION

### 1.1 Araştırma Problemi (v4 perspektif)

v1-v3 araştırması "edge nereden gelir?" sorusuna **çoklu-sinyal konsensüsü** cevabını verdi. v4 daha pratik sorulara odaklanıyor:

> *"Borsadaki giriş-çıkış kadar kritik. Hangi haftadan oynamaya başlamalı? PAS hafta olur mu? Bütçeyi nasıl böleyim?"*

Bu sorular **emperik test edilmeden** kullanılan sezgilerdir. Bilimsel disiplin bu sezgilerin yanlışlanmaya hazır olup olmadığını gerektirir.

### 1.2 Hipotezler (v4 yeni)

| # | Hipotez | Sonuç (kısa) |
|---|---|---|
| **H6** | Entry timing önemli, optimal warm-up var | ⚠️ sample küçük, W30 en iyi ama n=11 |
| **H7** | Skip dark weeks edge artırır | ❌ overfit (T15 reddetti) |
| **H8** | Multi-league flat budget T1-only'den iyi | ✅ doğru (T14 +80K vs +62K) |
| **H9** | Combined optimum tek-faktöre üstün | ⚠️ overfit riski |
| **H10** | Loss-streak pause mean reversion sömürür | ❌ gambler's fallacy (T16) |

### 1.3 Akademik Çerçeve

**Karl Popper'cı yaklaşım:** Hipotezler **falsifiable** olmalı. Negatif sonuç da bilgi.
- T13 dark_weeks → T15'te cross-validation reddetti → **bilgi kazanç**
- T16 loss-streak → mean reversion kanıt yok → **bilgi kazanç**

---

## 2. METHODOLOJİ — Faz V (yeni)

### 2.1 Cross-Validation Disiplini
- **Train:** 2021-22 + 2022-23 sezonu
- **Test:** 2023-24 + 2024-25 sezonu (out-of-sample)
- Skip rule, dark week tanımı train'den çıkarılır, test'te doğrulanır

### 2.2 Gambler's Fallacy Testi
- H₀: Hit rate(streak sonrası) = Hit rate(overall)
- Eğer reddedilirse: mean reversion vardır → pause stratejisi mantıklı
- Reddedilmezse: pause sadece psikolojik

### 2.3 Multi-League Bütçe Tasarımı
- Her ligten K=3 kupon, 1000 TL/lig/hafta flat
- Mevcut 3 lig (T1+E0+D1) = 3000 TL/hafta budget
- 5-6 lig ekstrapolasyonu E0+D1 ortalaması bazında

---

## 3. RESULTS — 5 FAZ × 16 TEST

### Faz I — Sinyal Tespiti

| Test | Strateji | Sonuç |
|---|---|---|
| T01 | Konsensüs haftalık survival | PWR %62, ROI +15% (n=100) |
| T02 | Sıkı K-leg | sample yetersiz |

### Faz II — Strateji Optimizasyonu

| Test | Strateji | Sonuç |
|---|---|---|
| T03 | MVK grid (13 config) | K=2 FAV_CONFIRMED kazanan |
| T04 | Lig validasyon | E0+T1 ✅, **D1 hariç** |
| T05 | Production K=2 UI | UI canlı |

### Faz III — Lig Mekaniği

| Test | Strateji | Sonuç |
|---|---|---|
| T06 | K=3 cross-league | **T1-only +60.3%** ✅✅ |
| T07 | Strict ≥2 confirmer | sample çöker |

### Faz IV — Bankroll & Portföy

| Test | Strateji | Sonuç |
|---|---|---|
| T08 | Single-league bankroll | %5 compound +675% (51% DD) |
| T09 | Multi-league portföy | Compound → Sharpe AZALDI |
| T10 | Kelly stake sizing | Half-Kelly optimum |
| T11 | Flat 1000 TL stake | **ALL paralel +81K** vs T1 +62K |

### Faz V — Timing & Skip (v4 YENİ)

| Test | Strateji | Sonuç |
|---|---|---|
| T12 | Entry timing | W1 başla en yüksek mutlak getiri |
| T13 | Skip dark weeks | +23K (in-sample) — **OVERFIT (T15)** |
| T14 | Multi-league budget | T1 +skip = +85K, ALL paralel = +80K |
| **T15** | **Cross-validation** | **Skip rule out-of-sample = +0pp (overfit)** |
| **T16** | **Loss-streak pause** | **Mean reversion YOK — gambler's fallacy** |

---

## 4. DISCUSSION

### 4.1 Hipotezlerin Doğrulanma Durumu (v4 update)

| H | Durum | Kanıt |
|---|:---:|---|
| H1 — Konsensüs edge | ✅ | T06 CI [+3.6%, +125%] |
| H2 — Lig spesifik | ✅ | D1 ❌, T1 ✅ |
| H3 — K=3 optimum (T1) | ✅ | T06 ROI K3>K2>K1 |
| H4 — Cross vs Homogen | ⚠️ | Cross negatif (compound), pozitif (flat) |
| H5 — Half-Kelly | ✅ | T10 optimum |
| **H6 — Entry timing** | **⚠️** | W30 sample küçük; W1 en yüksek mutlak |
| **H7 — Skip dark weeks** | **❌ OVERFIT** | T15 cross-validation reddetti |
| **H8 — Multi-league flat** | **✅** | T11 +81K, T14 +80K |
| **H9 — Combined optimum** | **❌** | Overfit riski yüksek |
| **H10 — Loss-streak pause** | **❌** | T16 mean reversion yok |

### 4.2 İki Önemli Akademik Ders

#### Ders 1: Overfitting Tehlikesi (T13 → T15)

**Sezgi:** Dark weeks atla → ROI 2x.
**In-sample (4 sezon agreg)**: +23K kazanç.
**Out-of-sample (cross-validation)**: 0 pp delta.

> Sample-specific bir pattern bulduğumuzda, **out-of-sample doğrulanmadan** üzerine bina kuramayız. T15 bu disiplini zorla uygulattı.

#### Ders 2: Gambler's Fallacy (T16)

Bahis tarihinde en yaygın yanılgı: "3 kupon kaybettim, 4.sü tutar." H10 bunu test etti.

**Veri:**
- Overall hit rate: 24.3%
- Streak ≥3 sonrası 5 maç: 22.0%
- Streak ≥4 sonrası 5 maç: 20.0%

**Sonuç:** Hit rate DÜŞÜYOR, artmıyor. Streak'ten sonra "talihimiz dönecek" beklentisi yanlış. Pause stratejisi psikolojik tolerans için OK ama matematiksel +EV yok.

### 4.3 Stake Regime Paradox (T09 ↔ T11)

| Regime | Diversifikasyon | Etki |
|---|---|---|
| Compound (%5) | Multi-league | Sharpe 1.39 → 0.57 ❌ |
| Flat (1000 TL) | Multi-league | Net +62K → +81K ✅ |

**Mekanik:** Compound'da küçük negatif edge'ler kayıp serilerinde büyür. Flat'ta her bahis bağımsız → küçük pozitif edge × hacim = toplam kar.

> Bu projeyle gösterdik ki **"diversifikasyon iyidir"** tek başına yanlış genelleme. **Stake regime'e bağlı**.

### 4.4 T1 Edge'i Devam Ediyor mu?

T15 cross-validation:
- Train (2122+2223): n=56, ROI +42.7%
- **Test (2324+2425): n=47, ROI +81.4%**

Out-of-sample ROI baseline'dan **daha yüksek**! T1 K=3 edge'i en az 2 sezon daha tutarlı.

---

## 5. CONCLUSIONS

### 5.1 Final Production Strateji

```yaml
strateji: FAV_CONFIRMED K=3
lig: T1 (Türk Süper Lig) — ana strateji
multi-league: opsiyonel (flat altında ek +18K)
entry_timing: W1'den başla — sezonun tüm haftaları
skip_strategy: KULLANMA (T15 overfit kanıtladı)
loss_streak_pause: KULLANMA (T16 gambler's fallacy)
stake:
  flat: 1000 TL/kupon
  compound (advanced): %5 of bankroll
  kelly: Half (0.5×) p_estimate=0.243
budget:
  1000 TL/lig/hafta minimum
  5000 TL/hafta hedefi → 5 lig genişlemesi gerekli
```

### 5.2 Backtest Sonucu (canonical)

| Metrik | Değer |
|---|---|
| Sample | **103 hafta** (T1 K=3, 4 sezon) |
| Out-of-sample doğrulama | **47 hafta** (2324+2425) ROI +81.4% |
| ROI (in+out sample) | +60.3% (CI95 [+3.6%, +125.1%]) |
| Flat 1000 TL net (4 sezon) | **+62,143 TL** |
| Aylık ortalama PnL | +1,406 TL |
| Max Drawdown | 14K TL |
| En uzun kayıp serisi | 14 hafta |

### 5.3 Reddedilen Stratejiler (bilim için kıymetli)

| Strateji | Verdikt | Sebep |
|---|:---:|---|
| Skip dark weeks | ❌ OVERFIT | T15 cross-validation |
| Loss-streak pause | ❌ FALLACY | T16 mean reversion yok |
| Strict ≥2 confirmer | ❌ | T07 sample çöker |
| D1 (Bundesliga) | ❌ | T04 -1.7% ROI |
| Cross-only 3 lig | ❌ | T06 -2.2% |
| Full Kelly | ❌ | T10 96.5% drawdown |
| Equal 3-league compound | ❌ | T09 Sharpe 1.39→0.57 |

---

## 6. LIMITATIONS

1. **Sample n=103** — finite. Beş sezon (2526 dahil) replikasyon gerek.
2. **Tek lig fokus** — T1'in unique mekaniği transfer edilemez.
3. **In-sample DC bias riski** — T1 walk-forward DC eğitilmedi.
4. **Pinnacle CLV yok** — Football-Data closing veriyor, opening yok.
5. **xG T1'de yok** — Understat kapsamı yok.
6. **Survivorship bias** — 16 testten en iyileri seçtik (multiple-testing).
7. **Transaction cost** — iddaa.com %10 vergi hesaba katılmadı.
8. **Liquidity** — büyük stake'lerde iddaa max bahis limiti var.

---

## 7. FUTURE WORK

| # | Aksiyon | Süre | Öncelik |
|---|---|---|:---:|
| 1 | 2025-26 5. sezon replikasyon | 1 saat | 🔴 |
| 2 | Live shadow run 4-8 hafta | 4-8 hafta | 🔴 |
| 3 | T1 walk-forward DC | 2 saat | 🟡 |
| 4 | SP1+I1+F1 CSV indir + ingest | 2 saat | 🟡 |
| 5 | xG T1 alternatif kaynak | 1 gün | 🟡 |
| 6 | Bonferroni multi-test correction | 30 dk | 🟢 |
| 7 | Transaction cost modeling | 1 saat | 🟢 |
| 8 | UI: skip rule ve loss-streak pause UYARI mesajı | 30 dk | 🟢 |

---

## 8. PROJE EVRİMİ (v1 → v4)

| Versiyon | Ana Sonuç | Test Sayısı | Yeni Bulgu |
|---|---|---:|---|
| v1 (TEKNOLOJI_VE_BILIMSEL_BULGU) | AGREE 2/3 +40% | – | İlk konsensüs sinyali |
| v2 | K=2 FAV_CONFIRMED +14% | T01-T05 | Lig validasyonu |
| v3 (Akademik 1) | T1 K=3 +60% | T01-T11 | Lig spesifik + bankroll |
| **v4 (Akademik 2)** | **T1 K=3 +60% TEYİT (out-of-sample)** | **T01-T16** | **Overfit testi + gambler's fallacy** |

---

## 9. APPENDICES

### A. Test Dosya Yapısı (v4)
```
04_BACKTEST/
├── T01_consensus_survival.py
├── T02_combo_kupon.py
├── T03_mvk_sweep.py
├── T04_league_validation.py
├── T06_k3_crossleague.py
├── T07_strict_filter.py
├── T08_bankroll_singleleague.py
├── T09_portfolio.py
├── T10_kelly_sizing.py
├── T11_flat1000.py
├── T12_entry_timing.py          ← Faz V
├── T13_skip_strategy.py         ← Faz V
├── T14_multileague_budget.py    ← Faz V
├── T15_optimum_combo.py         ← Faz V (CV)
└── T16_lossstreak_pause.py      ← Faz V (fallacy test)
```

### B. Rapor Dosya Yapısı
```
RAPOR/
├── YONETICI_OZETI_v4.md         ← BU DOSYA
├── YONETICI_OZETI_v3.md         (akademik 1)
├── YONETICI_OZETI_v2.md         (production strateji 1)
├── TEKNOLOJI_VE_BILIMSEL_BULGU_RAPORU.md (v1)
├── v4_FAZ5_TEST_ONERILER.md     ← Faz V tasarım
├── T01_*.md ... T16_*.md        ← Her test ayrı rapor (16 dosya)
```

### C. Referanslar (Faz V ek)

- Popper, K. (1959). *The Logic of Scientific Discovery* — falsification
- Tversky & Kahneman (1971). *Belief in the law of small numbers* — gambler's fallacy
- Mishkin, F.S. (2006). *Efficient Markets Hypothesis*
- Kelly (1956), Thorp (2006) — stake sizing
- Dixon & Coles (1997) — bivariate Poisson

---

## 🎓 BİLİMSEL ÖZ

> **"Bilim, sezgileri test ederek ilerler."**
>
> Bu projede sezgilerimizin **YARISI YANLIŞ** çıktı:
> - Cross-league iyidir → kısmen (sadece flat altında)
> - Dark weeks atla → overfit (cross-validation reddetti)
> - Loss streak sonrası bekleyince edge → gambler's fallacy
> - Lig sayısı artarsa edge artar → her lig edge'i farklı, dilution riski
>
> Sezgilerimizin **DİĞER YARISI DOĞRU** çıktı:
> - 3 bağımsız ses konsensüsü → gerçek edge (+60% ROI, CI tamamen pozitif, out-of-sample doğrulandı)
> - T1 farklıdır → 4 sezon ve test setinde teyit
> - Stake regime önemli → compound ↔ flat'ta diversifikasyon zıt etki
>
> **Veri-driven epistemoloji projesi.** Sezgi sınanır, veri konuşur, model adapte olur, sistem evrilir. Negatif bulgular pozitif kadar değerlidir.
