# v2 — CLV PIPELINE ANALIZI: KRİTİK BULGU

**Tarih:** 2026-05-28
**Test:** Sprint 2.1 (CLV pipeline) + Sprint 2.2 (Historical picks CLV)
**Sample:** matches_v2 — 19,198 settled maç, 18,122 CLV ölçülmüş

---

## 1) ÖZET

Mevcut TRIVOX v1.0 ve EUVOX v1.1 modellerinin tarihsel picks'lerini **matches_v2** üzerinde tek tek ölçtüm. Sonuç:

| Model | n_pick | CLV mean | CLV > 0 | t-stat | p-value |
|---|---|---|---|---|---|
| **TRIVOX v1.0 (T1 only)** | 327 | **−3.08%** | %35 | −6.83 | <0.0001 |
| **EUVOX v1.1 (6 lig)** | 3,138 | **−1.67%** | %36 | −13.78 | <0.0001 |
| **TRIVOX v1.2 (min_conf=2)** | 3 | −6.97% | %0 | −2.51 | 0.012 |

**Negatif CLV anlamı:** Model picks'lerinin opening odd'u, Pinnacle closing odd'undan **yüksek** kapanıyor. Yani:
- Modelin seçtiği taraf, piyasa yetkin tarafından "yanlış" değerlendirilmiş kabul edilmiyor
- Aksine, çoğunluğun gittiği (favori) taraf seçiliyor → CLV negatif

---

## 2) BASELINE KARŞILAŞTIRMASI

**Tüm settled maçların ortalama CLV'si** (matches_v2):

| Lig | clv_home | clv_draw | clv_away |
|---|---|---|---|
| D1  | −2.61% | −2.20% | −3.40% |
| E0  | −2.42% | −1.42% | −2.62% |
| F1  | −3.05% | −1.98% | −3.27% |
| I1  | −3.26% | −1.34% | −4.39% |
| SP1 | −2.65% | −1.85% | −4.98% |
| **T1** | **−2.81%** | **−3.51%** | **−4.35%** |

**Yorum:** TRIVOX v1.0 picks ortalaması **−3.08%** ≈ T1 baseline (−2.81% to −4.35%). Yani model **piyasanın hareketinden öğrenmiyor**, sadece favori tarafı taklit ediyor.

EUVOX **−1.67%** baseline (~−3%) altında, yani marjinal pozitif edge var ama hala negatif.

---

## 3) WIN-RATE × CLV İLİŞKİSİ (POZİTİF BULGU)

| Model | CLV (won legs) | CLV (lost legs) | Δ |
|---|---|---|---|
| TRIVOX | −2.40% (n=194) | −4.09% (n=133) | **+1.69pp** |
| EUVOX  | −1.48% (n=1759) | −1.91% (n=1379) | +0.42pp |

✓ **Kazanan bacaklar daha pozitif CLV taşıyor** → CLV reel sinyaldir.
✗ Lakin tüm picks negatif baseline ortalamasında → modelin "doğru zamanda doğru taraf" üretme yeteneği zayıf.

---

## 4) NEDEN BU KADAR ÖNEMLİ?

CLV, **profesyonel bahis dünyasının altın standart** validasyon metriğidir çünkü:
- ROI = küçük sample'da gürültülü; CLV her pick için anında hesaplanabilir
- CLV pozitif → uzun vadede ROI pozitif (matematiksel ilişki)
- CLV negatif → "şanslı backtest" şüphesi

Önceki testlerimiz (T01-T20) ROI bazlıydı:
- TRIVOX +%51 ROI = **109 maç içinde 4 outlier maçtan kaynaklı** (DD Deep Test Q4 bulgusu)
- Bu nedenle CLV'nin negatif olması, ROI'nin "şans" olduğu hipotezini destekliyor

---

## 5) V2 MODEL TASARIM SONUCU

Bu bulgu, v2 model tasarımının yönünü kesin olarak belirledi:

### TRIVOX v2 (yeni hedef)
| Eski | Yeni |
|---|---|
| **FAV_CONFIRMED** — favori tarafı seç + 1+ sinyal teyit | **VALUE_CONFIRMED** — closing'in altında değerli yön + 2+ sinyal teyit |
| Score = harmonik ortalama | Score = CLV-weighted ortalama |
| min_confirmers=1 | min_confirmers=2 (Q19 Bonferroni Benjamini-H bulgusu) |
| Sample 109 → 327 | Sample 19K → ~600-1000 pick (5x) |

### EUVOX v2 (yeni hedef)
- 8 sinyal eklendi: + shots_diff, + corners_diff, + recent_xg_form
- **CLV filter pre-selection:** her pick için match-level CLV >0 olan adayların öncelikle seçimi
- Per-lig Half-Kelly cap (zaten v1.1'de vardı)

### Yeni Validasyon Eşiği
- **TRIVOX v2 mean CLV > 0** olmadan production'a alınmıyor
- **EUVOX v2 mean CLV > +0.5%** olmadan release edilmiyor

---

## 6) SIRADA NE VAR?

1. **Sprint 2.3 — TRIVOX v2 sinyal yeniden tasarımı**
   - Anomaly: cross-market drift detection
   - Model: DC + xG karma (Bayesian blend)
   - xG luck: T1 hariç (A1 bekleyecek)
   - Form: rolling 5
   - **YENİ: CLV-historical signal** (geçmiş 30 günde aynı takımın CLV ortalaması)
   - **YENİ: Sharp-money signal** (kapanışta keskin hareketler)

2. **Sprint 2.4 — Walk-forward CLV training**
   - 2017-2022: train
   - 2022-2024: validation (CLV optimize)
   - 2024-2026: holdout test (CLV ölçümü)

3. **Sprint 2.5 — Yeni picks_log_v2 doldur ve canlı CLV monitor**

---

## 7) DD CEVABI — "Bu Model Gerçekten Para Kazandırır mı?"

Önceki cevap: "Backtest +%51 ROI, T1 → 6 lig portföy +%18 ROI"
**Yeni cevap (CLV ile):** Mevcut v1 modelleri **istatistiksel olarak edge'siz**. ROI sonucu küçük sample'da şanslı outliers'dan kaynaklı.

**Çözüm yolu net:** v2 model CLV-optimized retraining. Yeni 19K sample 5x büyük, p-value Bonferroni eşiğini geçecek kadar power'a sahip.

DD'ye verilecek dürüst mesaj:
> "v1 prototip seviyesinde, edge gerçek değil. v2 tasarımı CLV-positive olmaya yönelik kuruldu. 19K sample + 8 sinyal + walk-forward CLV optimization ile production'a girecek."

---

## 8) DOSYALAR

| Dosya | Açıklama |
|---|---|
| `02_VERI/matches_v2_compute_clv.py` | Sprint 2.1 — CLV kolonlar ekle ve doldur |
| `04_BACKTEST/historical_picks_clv.py` | Sprint 2.2 — TRIVOX/EUVOX historical picks CLV |
| `02_VERI/matches_v2.clv_avg_1x2` | Her maç için tüm 1X2 ortalama CLV |
| `02_VERI/matches_v2.has_clv` | CLV hesaplanabildi mi flag |
