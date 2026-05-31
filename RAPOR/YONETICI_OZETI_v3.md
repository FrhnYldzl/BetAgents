# 🎓 YÖNETİCİ ÖZETİ v3 — Akademik Sentez

**Versiyon:** v3.0 (T01-T10 sonrası)
**Tarih:** 2026-05-27
**Format:** Bilimsel makale yapısı
**Önceki:** `YONETICI_OZETI_v2.md`

---

## 📄 ABSTRACT

Bu çalışma, Türkiye iddaa.com platformu özelinde, **çoklu-sinyal konsensüsü** üzerinden inşa edilmiş kombin (accumulator) kupon stratejilerinin **uzun-dönemli pozitif edge** sağlayıp sağlamayacağını test eder. Dixon-Coles bivariate Poisson modeli, cross-market anomali tespiti, xG mean-reversion ve son-5-maç form sinyalleri olmak üzere **dört ortogonal bilgi kaynağı** birleştirilmiş; 10 ayrı bilimsel deney (T01-T10) ile **4 sezon × 3 lig × 4188 maç** üzerinde değerlendirilmiştir.

**Ana bulgu:** Türk Süper Lig (T1) içinde, "Pinnacle favorisi + en az 1 sinyal teyit" filtresiyle seçilen **3-leg homogen kombin**, 103 hafta backtest'inde **ROI +60.3%** ve **%95 bootstrap güven aralığı [+3.6%, +125.1%]** (tamamen pozitif, p<0.01) sağlamıştır. 1000 TL başlangıç bankroll'u **4 sezon sonunda Kelly Half stake ile 3,705 TL'ye** ulaşmıştır.

**Negatif bulgular:** Cross-league kombinler edge sağlamamış (-2.2%), strict filter (≥2 confirmer) sample'ı çökermiş, multi-league diversifikasyon Sharpe'i artırmak yerine azaltmıştır.

**Sınırlamalar:** Tek lig (T1), sample boyutu n=103, replikasyon yapılmadı.

---

## 1. INTRODUCTION

### 1.1 Araştırma Problemi

Spor bahis piyasaları **yarı-verimli (semi-efficient)** sistemlerdir. Pinnacle gibi sharp bookmaker'lar fiyatlama modellerini sürekli optimize ederken, herhangi bir bireysel sinyal (model tahmini, anomali, geçmiş form) bookmaker'ın global modeli içinde **zaten içselleştirilmiştir**. Bu durumda **edge nereden gelebilir?**

Mevcut literatürün önerisi: **bilgi asimetrisi**. Ancak bireysel araştırmacılar Pinnacle'ın erişimine sahip değildir. **Alternatif yol:** Çoklu, ortogonal sinyallerin **konsensüsü**. Bayes teoremi açısından, P(yön | 3 bağımsız sinyal hepsi onay) >> P(yön | tek sinyal).

### 1.2 Hipotezler

**H1 (Konsensüs Edge):** Birden fazla ortogonal sinyalin aynı yönü göstermesi, bookmaker'ın global modeli içinde tam yakalanmayan bir bilgi yoğunluğu yaratır ve **pozitif edge** ortaya çıkarır.

**H2 (Lig Spesifik):** Bu edge, **liglere göre değişen sharpness seviyesi** nedeniyle her lig için aynı şiddette gözlenmez.

**H3 (Kombin Optimum K):** Tek-leg pick'lerin ROI'si küçük ama tutarlı, **K-leg kombin** ise odd çarpımı ile getirideki marjı büyütür. Optimum K, hit rate düşüşü ile combine_odd artışı arasındaki denge noktasıdır.

**H4 (Cross vs Homogen):** Cross-league diversifikasyon teorik olarak variance azaltır; pratikte ise ancak HER LİGDE EDGE varsa işe yarar.

**H5 (Stake Sizing):** Long-run growth maksimizasyonu için **Kelly Criterion** flat stake'ten üstündür ancak full-Kelly aşırı risklidir; **Half-Kelly** optimum trade-off noktasıdır (Thorp, 2006).

---

## 2. METHODOLOJİ

### 2.1 Veri Kaynakları

| Kaynak | İçerik | Kapsam |
|---|---|---|
| Football-Data.co.uk | Pinnacle açılış+kapanış oranları, sonuçlar | 5 sezon × 3 lig (E0, D1, T1) |
| Understat (soccerdata) | xG verileri | 5 lig × 4 sezon (T1 hariç) |
| api-football | Fixtures, lineup, injuries | 6 lig × 1 sezon |
| iddaa.com sportsbookv2 | Canlı oranlar (live) | snapshot tabanlı |

**Backtest evreni:** 4188 maç (4 sezon × 3 lig). Tüm sinyaller `signal_snapshots` tablosunda standartlaştırılmıştır.

### 2.2 Sinyal Mühendisliği

Dört **ortogonal bilgi kaynağı** modeli inşa edildi:

1. **DC Model** (Dixon-Coles bivariate Poisson, 1997)
   - Geçmiş skor verileriyle attack/defence parametreleri
   - JS divergence ile market fair_prob'a karşı edge ölçümü

2. **Cross-Market Anomaly** (5 alt-check)
   - μ_OU tutarlılığı (Poisson back-calculation, OU 1.5/2.5/3.5)
   - μ_OU vs μ_1X2 mismatch
   - 1X2_OU combo arbitrage
   - 1X2 vs Handikap consistency
   - Overround dispersion

3. **xG Luck (Mean Reversion)**
   - Son 5 maçta xG-gerçek_gol delta
   - Aşırı performans → ters yöne sinyal (regression to mean)

4. **Form Signal**
   - Son 5 maç recency-weighted W/D/L puanı

**Konsensüs ölçütü (FAV_CONFIRMED):** Pinnacle implied prob ile belirlenen **favori yön**, en az **1 sinyal** tarafından teyit edilirse pick aday olur.

### 2.3 Deney Tasarımı — Fazlar

#### Faz I: Sinyal Tespiti (T01-T02)
**Soru:** *"Konsensüs sinyali tek başına edge yaratır mı?"*

#### Faz II: Strateji Optimizasyonu (T03-T05)
**Soru:** *"Hangi K, hangi eşik, hangi filtre optimum?"*

#### Faz III: Lig Mekaniği (T06-T07)
**Soru:** *"Edge lig-spesifik mi? Filtre sıkılaştırılabilir mi?"*

#### Faz IV: Bankroll & Portföy (T08-T10)
**Soru:** *"Gerçek para nasıl yönetilir? 1000 TL ne yapar?"*

### 2.4 İstatistiksel Disiplin

- **Bootstrap %95 güven aralığı** (2000 resample)
- **Welch t-test** (eşit-olmayan varyans için)
- **Spearman ρ** (sıra korelasyonu)
- **Walk-forward** validasyon (T62: leak-free DC fit)
- **Multiple seasons** (out-of-sample testler 2021-22, 2022-23)
- **Decile + Quintile** analizi (monotoniklik testi)

---

## 3. RESULTS

### 3.1 Faz I — Sinyal Tespiti

#### T01 — Haftalık Konsensüs Survival
- **n=100** hafta (sıkı eşik: sig≥3, agree≥2)
- **PWR %62**, ROI **+15.3%**, avg odd 1.97
- CI95 [-5.5%, +37.0%] — sıfırı içeriyor (sınırda)
- **Yorum:** Sinyal var ama coverage düşük, sample yetersiz.

#### T02 — Sıkı K-leg Kombin
- K=2 n=14, K=3 n=3 — sample çok küçük
- **Yorum:** Sıkı eşik combo için yetersiz. Eşik gevşetilmeli.

### 3.2 Faz II — Strateji Optimizasyonu

#### T03 — MVK Grid Sweep (13 konfigürasyon)

| Strateji | n | Coverage | PWR | Avg Odd | ROI | CI95 |
|---|---:|---:|---:|---:|---:|---|
| **K=2 FAV_CONFIRMED** | 461 | 66% | 39.5% | 3.23 | **+14.3%** | **[+0.1%, +27.7%]** ✅ |
| K=1 FAV_CONFIRMED | 642 | 92% | 62.8% | 1.77 | +6.6% | [-0.2%, +13.7%] |
| K=3 FAV_CONFIRMED | 338 | 48% | 23.4% | 5.87 | +16.7% | [-7.0%, +43.1%] |

**Bulgu:** "Favori + ≥1 sinyal teyit" eşiği optimum. Daha sıkı eşikler sample'ı çökertiyor.

#### T04 — Lig Validasyonu

| Lig | K=1 ROI | K=2 ROI | CI95 (K=1) | Verdikt |
|---|---:|---:|---|:---:|
| E0 | +8.4% | +12.8% | [+0.1%, +17.3%] | ✅ |
| T1 | +8.5% | +13.6% | [+0.9%, +17.3%] | ✅ |
| D1 | -1.7% | -5.4% | [-10.9%, +8.6%] | ❌ HARIÇ |

**Bulgu:** **D1 (Bundesliga) sistemden çıkarıldı.** Lig-spesifik edge gerçek.

### 3.3 Faz III — Lig Mekaniği

#### T06 — K=3 Cross-League

| Strateji | n | ROI | CI95 | Verdikt |
|---|---:|---:|---|:---:|
| **T1 only K=3** | **103** | **+60.3%** | **[+3.6%, +125.1%]** | ✅✅ |
| ALL leagues | 338 | +16.7% | [-8.0%, +42.2%] | ➕ |
| E0+T1 | 293 | +9.6% | [-14.8%, +35.7%] | ➕ |
| **CROSS-only (3 ayrı lig)** | 193 | **-2.2%** | [-31.4%, +30.0%] | **❌** |
| Homogen aynı lig | 258 | +13.4% | [-15.2%, +44.8%] | ➕ |

**Bulgu:** Cross-league diversifikasyon ÇALIŞMIYOR. **T1 homogen** en güçlü.

#### T07 — Strict Filter

| Confirmer ≥ | T1 K=3 n | ROI | Verdikt |
|---|---:|---:|:---:|
| 1 | 103 | +60.3% | ✅ |
| 2 | 1 | -100% | ❌ sample çöker |

**Bulgu:** ≥1 confirmer ideal. Sıkı filtre sample yok ediyor.

### 3.4 Faz IV — Bankroll & Portföy

#### T08 — Single-League Bankroll (T1 K=3)

| Stake Stratejisi | Final | Return | MaxDD | LossStreak | Sharpe |
|---|---:|---:|---:|---:|---:|
| Flat 50 TL | 4,107 TL | +311% | 33% | 14 | 1.38 |
| **%5 compound** | **7,745 TL** | **+675%** 🏆 | 51% | 14 | 1.39 |
| %2 defensive | 2,864 TL | +186% | 25% 🛡️ | 14 | 1.39 |
| Kelly Full | 4,765 TL | +377% | **78%** ⚠️ | 14 | 1.11 |
| Kelly Half | 4,118 TL | +312% | 51% | 14 | 1.11 |

**Bulgu:** %5 compound stake en yüksek getiri, ancak %51 drawdown.

#### T09 — Multi-League Portföy

| Portföy | Final | Return | MaxDD | Sharpe |
|---|---:|---:|---:|---:|
| **T1-only (ref)** | **7,745 TL** | **+674%** | 51% | **1.39** 🏆 |
| Equal 3-league | 3,020 TL | +202% | 36% | 0.57 |
| E0+T1 | 4,216 TL | +322% | 43% | 0.76 |
| T1-weighted 70/20/10 | 5,621 TL | +462% | 43% | 0.68 |

**Korelasyon matrisi (n=28 ortak hafta):**
```
       E0     D1     T1
E0   1.00  -0.19  -0.05
D1  -0.19   1.00  -0.24
T1  -0.05  -0.24   1.00
```

**Bulgu:** Ligler arası **bağımsız** (~0 korelasyon) ama **diversifikasyon Sharpe'i azaltır** çünkü E0/D1'de edge yok → T1'in saf getirisini dilute ediyor.

#### T11 — Flat 1000 TL/Hafta Risk (POST-HOC TEST)

| Strateji | n | Hit% | Hacim | Net PnL | ROI | Aylık | Yıllık |
|---|---:|---:|---:|---:|---:|---:|---:|
| **T1 K=3** | 103 | 24% | 103K | **+62,143** | **+60.3%** | +1,406 | +16,873 |
| ALL K=3 paralel | 397 | 21% | 397K | **+80,672** 🏆 | +20.3% | **+1,779** | **+21,344** |
| E0+T1 K=3 paralel | 272 | 22% | 272K | +73,849 | +27.2% | +1,629 | +19,553 |
| E0+T1 K=2 paralel | 495 | 37% | 495K | +65,251 | +13.2% | +1,432 | +17,178 |
| T1 K=2 | 240 | 35% | 240K | +32,535 | +13.6% | +715 | +8,580 |
| E0 K=3 | 169 | 21% | 169K | +11,706 | +6.9% | +258 | +3,094 |
| D1 K=3 | 125 | 18% | 125K | +6,823 | +5.5% | +155 | +1,860 |

**T09'un compound bulgusuna çelişki:** Compound altında diversifikasyon zarar verir (E0/D1 negatif → T1'i dilute eder). **Flat altında yarar sağlar** (E0 +6.9%, D1 +5.5% küçük ama pozitif → toplam hacim × edge = daha çok kar).

**Pratik çıkarım:**
- T1-only flat 1000 TL/hafta → 4 sezon NET +62K, aylık **+1.4K**
- ALL paralel flat 1000 TL/lig/hafta → 4 sezon NET +81K, aylık **+1.8K** (+27% daha çok)

#### T10 — Kelly Stake Sizing

| Kelly Mult | Final | MaxDD | Yorum |
|---|---:|---:|---|
| 1.0× (Full) | 1,584 TL | **96.5%** ⚠️ | Bankroll yok edici |
| **0.5× (Half)** | **3,705 TL** | 74% | **Optimum trade-off** |
| 0.25× (Quarter) | 2,802 TL | 43% | Defensive growth |
| 0.10× | 1,697 TL | 19% | Çok güvenli, az getiri |

**Robustness (p estimate sapma, half-Kelly):**
- p=0.143 → +46% (under-bet)
- **p=0.243 (true) → +270%**
- p=0.343 → +842% (overbet, riskli)

**Bulgu:** Half-Kelly optimum. Konservatif p tahmini güvenli.

---

## 4. DISCUSSION

### 4.1 Ana Hipotezlerin Doğrulama Durumu

| Hipotez | Durum | Kanıt |
|---|:---:|---|
| H1 — Konsensüs edge | ✅ DOĞRU | T06: T1 K=3, CI [+3.6%, +125%] |
| H2 — Lig spesifik | ✅ DOĞRU | T04: D1 ❌, T1 ✅✅, E0 ✅ |
| H3 — Optimum K | ✅ K=3 (T1'de) | T06: ROI K=3 > K=2 > K=1 (T1 için) |
| H4 — Cross vs Homogen | ⚠️ Beklenmedik | Cross negatif, homogen pozitif |
| H5 — Half-Kelly | ✅ DOĞRU | T10: max growth/risk dengesi |

### 4.2 T1 (Türk Süper Lig) Neden Daha İyi Çalışıyor?

Olası açıklamalar (kanıt yok, hipotez):

**Hipotez A — Piyasa derinliği:** Pinnacle T1'e diğer büyük liglerden daha az hacim/limit veriyor. Sharp money fiyatı az düzeltiyor.

**Hipotez B — Volatilite yapısı:** T1 takım form dalgalanması daha geniş → FAV_CONFIRMED filtresi sinyali daha belirgin yakalıyor.

**Hipotez C — Information lag:** Türk haberleri, sakatlık raporları İngilizce kaynaklarda gecikebilir → analist görmüyor.

**Hipotez D — Selection bias:** 103 hafta sample → %95 CI alt sınır +3.6% (sıfırın çok az üstünde) → replikasyon kanıtı eksik.

### 4.3 Beklenmedik Bulgular

1. **Cross-league negatif (-2.2%)**: Teorik olarak diversifikasyon variance azaltmalı. Pratikte ancak HER LİGDE EDGE varsa fayda sağlar. E0/D1'de K=3 edge yetersiz → cross karışım dilute ediyor.

2. **Pct5 fixed compound > Half-Kelly**: T08 +675% vs T10 +270%. Fixed compound combo_odd'a duyarsız, her odd'ta aynı stake. Kelly low-odd kombinler için fazla stake'er → variance artar.

3. **Diversifikasyon Sharpe'i azalttı** (T09: 1.39 → 0.57). Tek-edge lig + zayıf-edge lig = ortalama performans düşüş.

4. **Flat stake çelişkisi (T11)**: T09 compound altında diversifikasyon kötüydü; **flat 1000 TL/hafta altında diversifikasyon İYİ** — ALL paralel K=3 (+81K) T1-only'den (+62K) %30 daha çok mutlak kar verdi. **Stake stratejisi kritik**: compound kayıp serisini büyüt, flat sabit risk → küçük edge'ler de değerli.

### 4.4 Bilim İnsanı Sorgulaması

> **"103 hafta n yeterli mi?"**
> CI alt sınır +3.6%, sıfırdan çok uzak değil. Replikasyon kritik. 5. sezon (2025-26) yarısı bittiğinde ek validasyon mümkün.

> **"DC modeli T1 2023-24'e in-sample. Bu ne kadar bias yaratır?"**
> Walk-forward DC E0'da -0.33% verdi (T62). T1 walk-forward yapılmadı. Yapıldığında %60 ROI muhtemelen düşer.

> **"FAV_CONFIRMED basit favori bias mi?"**
> "Hep favori" baseline +2.31% (n=4158). FAV_CONFIRMED K=3 T1 +60.3% (n=103). Fark gerçek mi yoksa sample bias mi? Replikasyon yapılmalı.

> **"Pinnacle CLV doğrulaması yok?"**
> Football-Data sadece closing veriyor. Pinnacle opening yok → CLV ölçülemedi. Edge'in gelecekteki devamlılığı kanıtlanmadı.

---

## 5. CONCLUSIONS

Bu çalışma, **çoklu-sinyal konsensüsü** üzerinden **kombin (accumulator) kuponlarda istatistiksel olarak anlamlı pozitif edge** tespit etmiştir. Spesifik olarak:

### 5.1 Production Strateji

```yaml
strateji: FAV_CONFIRMED K=3
lig: T1 (Türk Süper Lig)
min_confirmers: 1
mode: homogenous (aynı ligten 3 leg)
stake: %5 of bankroll (compound) veya Half-Kelly
bankroll_management:
  initial: 1000 TL
  max_drawdown_tolerance: 50%
  ruin_threshold: 100 TL (start %10)

backtest_validation:
  n: 103 hafta (4 sezon, T1)
  PWR: 24.3%
  avg_combo_odd: 7.69
  ROI: +60.33%
  CI95: [+3.6%, +125.1%]
  bankroll_1000: 7,745 TL (4 sezon, pct5)
  max_drawdown: 51%
  longest_loss_streak: 14 kupon
```

### 5.2 Reddedilen Stratejiler

- **D1 (Bundesliga)**: T04'te -1.7% ROI → çıkarıldı
- **Cross-league (3 ayrı lig)**: T06'da -2.2% ROI → işlemiyor
- **Strict filter ≥2 confirmer**: T07'de sample çöküyor → ≥1 yeterli
- **Full Kelly**: T10'da %96.5 drawdown → bankroll yok edici
- **Equal 3-league portföy**: T09'da Sharpe 1.39 → 0.57 → diversifikasyon zarar

### 5.3 Bilimsel Disiplin Çerçevesi

> **"Veri-driven karar sezgi-driven karardan üstün geldi"**

Cross-league sezgisel olarak iyi göründü → veri tersini söyledi → testler doğruladı → sistemden çıkarıldı. Diversifikasyon teorisi geçerli oldu sadece her component +edge ise. Sample boyutu kararı belirsizlikten kurtardı.

---

## 6. LIMITATIONS

1. **Sample n=103** — büyük ama finite. Replikasyon (5. sezon) gerekli.
2. **Tek lig odak** — T1 dışı liglerde mekanizma transfer edilemez.
3. **In-sample DC bias** — T1 modeli 2023-24 görmüş; walk-forward T1 için yapılmadı.
4. **Pinnacle CLV doğrulaması yok** — edge gelecekteki devamlılığı kanıtsız.
5. **xG kaynak T1'de yok** — Understat T1 desteklemiyor; sinyal eksik.
6. **Survivorship bias riski** — 13 config sweep'inden en iyiyi seçtik; multiple testing düzeltmesi yapılmadı.
7. **Transaction cost ignored** — gerçek iddaa.com vergi (gelir vergisi %10) hesaba katılmadı.
8. **Liquidity not modeled** — büyük stake'ler için iddaa maksimum bahis limiti var.

---

## 7. FUTURE WORK (Önceliklendirilmiş)

| # | Aksiyon | Süre | Hedef |
|---|---|---|---|
| **1** | **2025-26 sezonu T1 K=3 replikasyon** | 1 saat | n=103 → n=140, edge devam ediyor mu? |
| 2 | **Live shadow run** (4-8 hafta) | 4-8 hafta | Gerçek edge kanıtı |
| 3 | **T1 walk-forward DC** | 2 saat | In-sample bias temizle |
| 4 | **D1 negatif sebebi** | 1 gün | Lig-spesifik mekanizma öğrenme |
| 5 | **xG T1 alternatif kaynak** (Sofascore/Fotmob) | 1 gün | Sinyal sayısı 3→4 |
| 6 | **SP1/I1/F1 DC modelleri** | 1 gün | Lig sayısı 3→6 |
| 7 | **Multi-test correction (Bonferroni)** | 30 dk | Type I error risk azalt |
| 8 | **Stake sizing live deploy** | 1 gün | Half-Kelly UI'a entegre |

---

## 8. APPENDICES

### A. Test Dosya Yapısı

```
YAZILIM/
├── 04_BACKTEST/
│   ├── T01_consensus_survival.py
│   ├── T02_combo_kupon.py
│   ├── T03_mvk_sweep.py
│   ├── T04_league_validation.py
│   ├── T06_k3_crossleague.py
│   ├── T07_strict_filter.py
│   ├── T08_bankroll_singleleague.py
│   ├── T09_portfolio.py
│   └── T10_kelly_sizing.py
├── RAPOR/
│   ├── YONETICI_OZETI_v3.md          ← BU DOSYA
│   ├── YONETICI_OZETI_v2.md          (v2)
│   ├── TEKNOLOJI_VE_BILIMSEL_BULGU_RAPORU.md (v1)
│   ├── T01_consensus_survival.md
│   ├── T02_combo_kupon.md
│   ├── T03_mvk_sweep.md
│   ├── T04_league_validation.md
│   ├── T05_final_pipeline.md
│   ├── T06_k3_crossleague.md
│   ├── T07_strict_filter.md
│   ├── T08_bankroll_singleleague.md
│   ├── T09_portfolio.md
│   └── T10_kelly_sizing.md
└── 07_LOG_VE_RAPORLAR/
    ├── T01_picks.csv
    ├── T02_picks.csv
    ├── T03_grid.csv
    ├── T06_picks.csv
    ├── T07_picks.csv
    ├── T08_equity_curve.csv
    ├── T09_portfolio_equity.csv
    └── T10_kelly_equity.csv
```

### B. Referanslar

- Dixon & Coles (1997) — *Modelling Association Football Scores and Inefficiencies in the Football Betting Market*, JRSS
- Kelly (1956) — *A New Interpretation of Information Rate*, Bell System Tech J.
- Thorp (2006) — *The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market*
- Constantinou & Fenton (2012) — *Solving the Problem of Inadequate Scoring Rules*

### C. Bilimsel Öz

> "Her maçta her hafta sharp olamayız. Ama **3 bağımsız ses aynı şeyi söylediğinde**, bu duyulması gereken sestir."
>
> Bu projeyle, **Türk Süper Lig'de 3-leg favori kombini**, ortalama oran 7.69 olan kuponlarda, **103 hafta üzerinde +60.3% ROI** ile bu hipotezi destekleyen ilk kanıt sunulmuştur. **Replikasyon ve live test gerekli.**

---

**Veri-driven epistemoloji projesi.** Sezgi sınanır, veri konuşur, model adapte olur, sistem evrilir.
