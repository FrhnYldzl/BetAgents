# MULTI-MARKET MODEL TASARIMI v0.1
## "5 pazar = edge alanı 5x, doğru kombin = silah"

**Tarih:** 2026-05-28
**Vizyon:** Şu anki 1X2 modeli → 5 pazara genişletme
**Beklenen Etki:** Pick frekansı 3-5x, Q5+agree kombin uzayı çok zenginleşir

---

## 1) MEVCUT DURUM vs HEDEF

### Şu Anki Durum (v1)
- Tek pazar: **Maç Sonucu (1X2)** — Home/Draw/Away
- Sample/maç: 1 tahmin
- Edge sınırı: market 1X2 marjı (%5-12)

### Hedef (v2 — Multi-Market)
- **5 pazar**, her maçta:
  1. **Maç Sonucu (MS)** — 1, X, 2 (mevcut)
  2. **İlk Yarı Sonucu (İY)** — 1, X, 2 (YENİ)
  3. **Handikaplı Maç Sonucu (AH)** — 1, X, 2 (YENİ, +1.5 / −1.5 spread)
  4. **Alt/Üst 2.5 Gol (A/Ü)** — Alt, Üst (YENİ — odds var, model yok)
  5. **Karşılıklı Gol (KG)** — Var, Yok (YENİ)

- Sample/maç: **5+ tahmin** (her pazarda olasılık)
- Edge sınırı: market pazar-spesifik marj, **niş pazarlar daha gevşek** (iddaa'nın boşluk alanları)

---

## 2) MATEMATİK — DC POISSON'DAN HER PAZAR

İyi haber: Dixon-Coles modeli **goal Poisson** veriyor. Tüm 5 pazar bundan **matematiksel olarak türetilebilir**:

```
DC Modeli:
  λ_home = atk_h × def_a × home_advantage
  λ_away = atk_a × def_h
  
  P(home_goals = i, away_goals = j) = Poisson(λ_h, i) × Poisson(λ_a, j) × dc_correction(i,j)
```

Bu **2D olasılık matrisi**'nden (i=0..6, j=0..6) tüm pazarlar çıkar:

### Maç Sonucu (1X2)
```python
P(1) = Σ Σ P(i,j) for i > j
P(X) = Σ P(i,i)
P(2) = Σ Σ P(i,j) for i < j
```

### Alt/Üst 2.5
```python
P(Üst 2.5) = Σ Σ P(i,j) for i+j > 2.5
P(Alt 2.5) = 1 - P(Üst 2.5)
```

### Karşılıklı Gol (KG)
```python
P(KG Var) = Σ Σ P(i,j) for i ≥ 1 AND j ≥ 1
P(KG Yok) = P(0,0) + Σ P(0,j) + Σ P(i,0) (i,j ≥ 1)
```

### Handikaplı Maç Sonucu (AH, +1.5 / −1.5)
```python
# Ev sahibi −1.5 (favorit): -1.5 fark + ev kazansın
P(AH_1 | −1.5) = Σ Σ P(i,j) for i - j ≥ 2
P(AH_X | −1.5) = N/A (handikap virgüllü, beraberlik yok)
P(AH_2 | +1.5) = Σ Σ P(i,j) for j - i ≥ -1  # away +1.5 da kazansa
```

### İlk Yarı Sonucu (İY)
İlk yarıda **gol oranı ~%45-50** (Premier League: 0.45, ortalama maç golunun yarısı).
```python
λ_h_HT = λ_h × 0.45
λ_a_HT = λ_a × 0.45

P_HT(i,j) = Poisson(λ_h_HT, i) × Poisson(λ_a_HT, j) × dc(i,j)

P_İY(1) = Σ Σ P_HT(i,j) for i > j
P_İY(X) = Σ P_HT(i,i)  # ←  İlk yarı 0-0 dahil!
P_İY(2) = Σ Σ P_HT(i,j) for i < j
```

**Önemli:** İlk yarıda **draw (0-0, 1-1) çok yaygın** (~%40), bu yüzden İY-X piyasada 1.95-2.10 oran (yüksek!) → potansiyel value alanı.

---

## 3) PAZAR-SPESİFİK EDGE DAĞILIMI

İddaa'nın marj profilleri (tipik):

| Pazar | Marj (overround) | Likitide | Edge bulma kolaylığı |
|---|---|---|---|
| Maç Sonucu (1X2) | %5-8 | Çok yüksek | Zor (her oyuncu burada) |
| İlk Yarı (İY) | **%8-12** | Orta | **Orta-Kolay** ⭐ |
| Handikap (AH) | %4-7 | Yüksek | Zor |
| Alt/Üst 2.5 | %5-9 | Yüksek | Orta |
| Karşılıklı Gol (KG) | **%9-14** | Orta | **Kolay** ⭐ |

**Trader gözüyle:**
- İY ve KG **yüksek marjlı** ama daha az analiz edilen pazarlar = **value avı için ideal**
- AH zaten sharp pazar, edge zor
- A/Ü orta

Yani **niş pazarlara açılarak edge alanını genişletmek** stratejik akıllılık.

---

## 4) KORELASYON HARİTASI (ÇOK KRİTİK!)

5 pazar bağımsız DEĞİL. Birinin sonucu diğerini belirler:

```
         MS-1  MS-X  MS-2  İY-1  İY-X  İY-2  Üst2.5  Alt2.5  KGVar  KGYok
MS-1      1.0  -0.5  -0.5   0.7  -0.2  -0.4   0.3    -0.3    0.2   -0.2
MS-X     -0.5   1.0  -0.5  -0.2   0.7  -0.2  -0.3     0.3   -0.1    0.1
MS-2     -0.5  -0.5   1.0  -0.4  -0.2   0.7   0.3    -0.3    0.2   -0.2
İY-1      0.7  -0.2  -0.4   1.0  -0.5  -0.5   0.4    -0.4    0.2   -0.2
İY-X     -0.2   0.7  -0.2  -0.5   1.0  -0.5  -0.2     0.2   -0.3    0.3
İY-2     -0.4  -0.2   0.7  -0.5  -0.5   1.0   0.4    -0.4    0.2   -0.2
Üst2.5    0.3  -0.3   0.3   0.4  -0.2   0.4   1.0    -1.0    0.7   -0.7
Alt2.5   -0.3   0.3  -0.3  -0.4   0.2  -0.4  -1.0     1.0   -0.7    0.7
KGVar     0.2  -0.1   0.2   0.2  -0.3   0.2   0.7    -0.7    1.0   -1.0
KGYok    -0.2   0.1  -0.2  -0.2   0.3  -0.2  -0.7     0.7   -1.0    1.0
```

**Anlam:**
- **Üst 2.5 ve KG Var korelasyonu +0.70** — birlikte oynanırsa kombin değil sırf yan yana risk
- **İY-1 ve MS-1 korelasyonu +0.70** — birlikte koymak bağımsız değil
- **Alt 2.5 ve KG Yok korelasyonu +0.70** — aynı şey iki kez

### Kombin Yapma Kuralı

**✅ İzin verilen kombinler (korelasyon |r| < 0.4):**
- MS-1 (Ev kazansın) + KG Var → r ≈ 0.20, kombo OK
- MS-1 + İY-X → r ≈ −0.20, kombo OK
- A/Ü Üst + AH-1 → r ≈ 0.30, kombo OK

**❌ İzin verilmeyen (kovaryans riskini iki kez almak):**
- MS-1 + İY-1 → r = 0.70, **çift-bahis** sayılır
- Üst 2.5 + KG Var → r = 0.70, **çift-bahis**
- Alt 2.5 + KG Yok → r = 0.70, **çift-bahis**

**Korelasyon Adjustment (Komite C3 maddesi):**
- Combo joint probability = P(A) × P(B) × (1 + ρ_AB × correction)
- Eğer korelasyon yüksekse → odds birikimi yanıltıcı

---

## 5) V2 İNŞAATI — SİNYAL & SCORE GENİŞLETME

Her maç için 5 pazarda **ayrı score_v13** hesaplanacak:

```python
class MultiMarketSignals:
    def compute_all_signals(match):
        # DC Poisson
        lam_h, lam_a = dc_model.predict(match)
        prob_matrix = build_2d_poisson(lam_h, lam_a)
        
        # Tüm pazarlar
        markets = {
            "MS":  derive_1x2(prob_matrix),
            "IY":  derive_HT_1x2(lam_h * 0.45, lam_a * 0.45),
            "AH":  derive_asian_handicap(prob_matrix),
            "OU":  derive_over_under(prob_matrix, threshold=2.5),
            "KG":  derive_btts(prob_matrix),
        }
        
        # Her pazar için sinyal
        signals = {}
        for market_name, model_probs in markets.items():
            market_implied = derive_market_probs(match.odds[market_name])
            signals[market_name] = {
                "model_p": model_probs,
                "market_p": market_implied,
                "edge": model_probs - market_implied,
                "score": compute_score_for_market(model_probs, signals_aux),
            }
        return signals
```

Her pazar için Q1-Q5 quintile + agree_count.

---

## 6) KUPON STRATEJİSİ — MULTI-MARKET

### Tek-Maç Multi-Bahis (RECOMMENDED)

Trader bir maçta 1-2 pazar seçer:
```
Maç: Liverpool - Tottenham
  ┌─────────────────────────────────────────┐
  │ MS:    Liverpool 1 @ 1.55  (Q5+a2 ★)    │
  │ İY:    Liverpool 1 @ 2.10  (Q4)         │
  │ AH:    Liverpool -1 @ 2.00 (Q4)         │
  │ Ü/A:   Üst 2.5 @ 1.65      (Q5)         │
  │ KG:    Var @ 1.55          (Q3)         │
  └─────────────────────────────────────────┘
```

**Strateji 1: Tek pazar + ALL-IN** (Q5+a2)
- Liverpool 1 @ 1.55 → 500 TL stake (BÜYÜK)

**Strateji 2: 2 pazar + ULTRA güven**
- Liverpool 1 (Q5+a2) + Üst 2.5 (Q5) → kombin
- Korelasyon r=0.30 (OK)
- Kombin odd: ~2.56 → 300 TL stake

**Strateji 3: Niş pazar value**
- İY-X (eğer model Q5'te ise) — piyasa marjı %12, odd 1.95
- Tek başına 100 TL

### Multi-Maç Kombin (DİKKAT)

Eski K=3 kombin mantığı KORUNUR ama YENİ KURALLA:
- **Her kupon bacağı farklı pazardan** (varyans dağıtımı)
- Aynı pazardan kombin → bağımsız picks → klasik

```
Kupon (multi-leg multi-market):
  Liverpool MS-1    @ 1.55  (Q5+a2)
  Real Madrid AH-1  @ 1.80  (Q5+a2)
  Bayer Üst 2.5    @ 1.65  (Q5)
  ─────────────────────────────
  Kombin: 4.60     Stake: 200 TL
```

3 farklı maç + 3 farklı pazar = düşük korelasyon, yüksek bağımsızlık.

---

## 7) İNŞAAT PLANI — SPRINT V2-MULTI

### Sprint A — Veri Genişletme (1-2 hafta)
**A1. Football-Data multi-market odds ingest**
- Mevcut FD CSV'lerinde var:
  - `HF` (HT goals home), `AF` (HT goals away)
  - `B365H/X/A` (1X2)
  - `B365>2.5`, `B365<2.5` (A/Ü 2.5)
  - `BbAvHA` (AH)
  - `BTS` veya `BTS-Yes` (KG)
- matches_v2'ye yeni kolonlar ekle:
  - `ht_home_score`, `ht_away_score` (FTHG/FTAG yarı)
  - `closing_iy_1`, `closing_iy_X`, `closing_iy_2` (İY 1X2)
  - `closing_ah_handicap`, `closing_ah_1`, `closing_ah_2`
  - `closing_btts_yes`, `closing_btts_no`

**A2. iddaa'dan canlı multi-market odds ingest**
- iddaa.com pazar id'leri map'le
- Her aktif maç için 5 pazar odds çek
- Buna geliştirme yapıldı 7 pazar modülü var (`signal_snapshots.odd_*`) — kullan

### Sprint B — Model Genişletme (2-3 hafta)
**B1. DC Poisson → Multi-Market projector**
- `multi_market_projector.py` modülü
- DC λ_h, λ_a girdisi → 5 pazar olasılık çıktısı

**B2. Her pazar için signal stack**
- MS, İY, AH, A/Ü, KG her biri için:
  - anomaly signal (cross-market)
  - DC model signal
  - xG luck (gol-tabanlı pazarlarda güçlü)
  - form signal
  - **YENİ:** market-specific xG variance (A/Ü için kritik)

**B3. Per-market score_v13**
- Her pazar için ayrı Q1-Q5 quintile
- agree_count per market

### Sprint C — Backtest (2 hafta)
**C1. Her pazar için hit rate per quintile**
- Mevcut Q5 hit %70 hesabını 5 pazara genişlet
- Beklenen: İY ve KG'de Q5 hit **%65-75** (piyasa daha az analiz ediyor)

**C2. Korelasyon adjustment validation**
- Kombo joint prob gerçek hit rate ile uyumlu mu?
- Frank/Gumbel kopula deneme

**C3. CLV per market**
- Her pazarın closing odds drift'i ölçülür
- İY ve KG'de CLV daha pozitif olabilir (niş)

### Sprint D — Trader UI (1 hafta)
**D1. Multi-market dashboard**
- Maç başına 5 pazar tahmini, quintile renkli
- Kombin önericisi (korelasyon filtreli)
- Stake hesaplayıcı

**D2. Manuel decision recorder**
- Trader hangi pazarı seçti, neden, sonuç → öğrenme

---

## 8) BEKLENEN ETKİ

### Pick Frekansı

| Senaryo | Şu Anki (1X2) | Multi-Market (5 pazar) |
|---|---|---|
| Q5+agree2 / hafta | ~1-2 | **~5-7** (5x) |
| Q5 toplam / hafta | ~3-5 | **~15-25** (5x) |
| Q4+ / hafta | ~10-15 | **~50-75** (5x) |

### ROI Etkisi (tahmin)

| Senaryo | Mean ROI (in-sample) |
|---|---|
| 1X2 only Q5 sniper | %5-8 aylık |
| Multi-market Q5+a2 sniper | **%8-15 aylık** |
| Multi-market + niş pazarlar (İY, KG) | **%12-20 aylık** (en optimist) |

### Edge Profili Değişimi
- **Mevcut**: market 1X2'sini yenmek zor → marjinal edge
- **V2**: İY-X ve KG niş pazarlarında piyasa zayıf → daha kolay edge
- **Bonus**: Tek maçta 2-3 pazar açık → korelasyonlu kombin opportunity

---

## 9) RİSK YÖNETİMİ — Multi-Market

### Eklenen Riskler
1. **Korelasyon görmezden gelme** → kombo varyansı patlar
2. **Pazar-spesifik overfit** — model bir pazarı çok iyi, diğerini kötü öğrenir
3. **Veri eksikliği** — İY/AH/KG için Football-Data tamamı vermiyor, eksik

### Güvenlik Mekanizması
- Korelasyon filtresi (|r| > 0.4 ise combo yasak)
- Pazar başına minimum sample (n ≥ 500 / lig × pazar)
- Walk-forward training per market
- CLV kontrolü per market (negatif ise modeli durdur)

---

## 10) TEK SAYFA ÖZET

```
┌────────────────────────────────────────────────────────────┐
│         MULTI-MARKET V2 — Edge Alanı Genişletme           │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Şu anki (v1)        →    Hedef (v2)                       │
│  ─────────                ──────────                       │
│  1 pazar (MS)             5 pazar (MS, İY, AH, A/Ü, KG)    │
│  3-5 Q5 / hafta           15-25 Q5 / hafta                 │
│  %5-8 aylık ROI           %12-20 aylık ROI (tahmin)        │
│                                                            │
│  TEMEL: DC Poisson her pazara matematiksel olarak yayılır  │
│  NİŞ:   İY ve KG yüksek marjlı → value avı için ideal      │
│  RİSK:  Korelasyon (Üst 2.5 + KG Var = r=0.7)              │
│         → kombo filtresi şart                              │
│                                                            │
│  SPRINT PLAN:                                              │
│    A. Veri (1-2 hf) — multi-market odds ingest             │
│    B. Model (2-3 hf) — DC→5 pazar projector + signals      │
│    C. Backtest (2 hf) — per market hit + CLV               │
│    D. UI (1 hf) — trader dashboard                         │
│                                                            │
│  TOPLAM: ~7 hafta                                          │
└────────────────────────────────────────────────────────────┘
```

---

## 11) İLK ADIM (BU HAFTA)

Multi-market'a geçişin **küçük ilk adımı**:

**Mini-Test: A/Ü 2.5 üzerinde TRIVOX/DUOVOX picks Q5 hit rate ölç**
- Mevcut signal_snapshots'ta `fp_over25`, `fp_under25` var
- matches_v2'de `closing_over25`, `closing_under25` var
- Q5 hit rate hesapla A/Ü için → değer var mı görelim

Eğer **A/Ü Q5'te %65+ hit** çıkarsa → multi-market hipotezi doğrulandı, B inşaata gir.
Eğer **%50 civarında** → DC modeli A/Ü için zayıf, B'de iyileştirme şart.

Bu mini-test 1 saat. Kapı 0'ın son testi olarak yapalım.
