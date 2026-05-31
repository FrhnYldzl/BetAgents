# KAPI 0 — TEST 1: K=1 BASELINE — DERİN ANALİZ

**Tarih:** 2026-05-28
**Komite Tezi (Madde 32 + 60):** "K=1 negatif, K=3 pozitif → edge LOTTERY, gerçek değil"
**Sample:** signal_snapshots (eski 10,657 satır × FAV_CONFIRMED filter)

---

## 1) SONUÇ MATRİSİ

### TRIVOX (T1-only, FAV_CONFIRMED, min_conf=1)

| K | n | hit% | avg_odd | ROI_gross | **ROI_net (vergi sonrası)** | CLV mean |
|---|---|---|---|---|---|---|
| **1** | **489** | **61%** | **1.84** | **+6.5%** | **+2.0%** | **−2.94%** |
| 2 | 256 | 34% | 3.63 | +9.4% | +1.8% | −2.69% |
| 3 | 109 | 23% | 7.64 | +51.5% | +38.7% | −3.08% |

### EUVOX (6-lig, FAV_CONFIRMED, min_conf=1)

| K | n | hit% | avg_odd | ROI_gross | **ROI_net (vergi sonrası)** | CLV mean |
|---|---|---|---|---|---|---|
| **1** | **2,812** | **59%** | **1.84** | **+3.7%** | **−0.8%** | **−2.03%** |
| 2 | 1,727 | 33% | 3.43 | +4.0% | −3.1% | −1.67% |
| 3 | 1,046 | 18% | 6.69 | +6.6% | −2.2% | −1.67% |

---

## 2) KARARLAR (komite tezi karşısında)

### TRIVOX → **KISMI RED** (komite tezini)

✅ **K=1 baseline POZİTİF** (n=489, ROI_net **+%2.0**, ROI_gross **+%6.5**)
- Komitenin "lottery hipotezi" TRIVOX için **reddedildi**
- 489 pick → istatistiksel anlamlı sample
- Binomial test: observed hit %61.1, breakeven %54.3, **Z ≈ 3.02, p ≈ 0.0025**
- **Bonferroni eşiği** (α/19 = 0.0026) ile **kıl payı geçer**
- Bu, komitenin "Bonferroni 0/19" iddiasına da **kontra-kanıt** olur

⚠️ Ama **K=3 ROI %38** **K=1'in 19 katı** → kombin varyans büyütme etkisi VAR
- Yani: edge var ama K=3'ün abartılı ROI'si **outlier-dependent**
- Production strateji K=1 ya da K=2 olmalı, K=3 değil

❌ **CLV tüm K seviyelerinde negatif** (−2.69% to −3.08%)
- ROI pozitif ama CLV negatif → "modelin edge'i piyasayı yenmekten gelmiyor"
- T1 baseline CLV ~ −2.81% to −4.35%, picks CLV ≈ baseline → **piyasayla aynı**
- Bu çelişki = "modelin edge'i sezonsal sample variance veya outliers"

### EUVOX → **TAM ONAY** (komite tezi doğrulandı)

❌ **K=1 baseline NEGATİF** (n=2812, ROI_net **−%0.8**)
- Komitenin "edge yok" tezi EUVOX için **doğrulandı**
- Tüm K seviyelerinde ROI_net negatif (vergi sonrası)
- Sample 2,812 büyük → bu bir gürültü değil, **gerçek sonuç**

❌ **CLV de negatif** (−1.67% to −2.03%)
- ROI ve CLV her ikisi negatif → **EUVOX gerçek edge'siz**

**Karar:** EUVOX v1.1 production'a alınmamalı. v2 retrain gerekli.

---

## 3) İSTATİSTİKSEL DERİNLİK

### TRIVOX K=1 Binomial Test
```
H0: p = 1/avg_odd = 1/1.84 = 0.5435 (piyasayla aynı)
H1: p > 0.5435 (edge var)
Observed: 299/489 = 0.6114
Z = (0.6114 - 0.5435) / sqrt(0.5435 × 0.4565 / 489) = 3.02
p-value (one-tailed) ≈ 0.00126
p-value (two-tailed) ≈ 0.0025
```
**Bonferroni eşiği α/19 = 0.0026** → TRIVOX K=1 **kıl payı geçer**.
**B-H (FDR) ile** kesin geçer.

### EUVOX K=1 Binomial Test
```
H0: p = 1/1.84 = 0.5435
Observed: 1666/2812 = 0.5925
Z = (0.5925 - 0.5435) / sqrt(0.5435 × 0.4565 / 2812) = 5.22
p-value < 0.0001 — istatistiksel anlamlı POZİTİF gross edge
```
**Ama vergi sonrası negatif** (−%0.8). Yani:
- Brüt edge var (1.84 oranı yenmiş)
- Türkiye %10 stopaj vergisi edge'i yiyor
- Vergi olmasa EUVOX K=1 marginal pozitif

---

## 4) KOMİTEYE BAĞIMSIZ CEVAP

| Komite İddiası | T01 Bulgusu | Verdict |
|---|---|---|
| "K=3 lottery, K=1 negatif olur" | TRIVOX K=1 = **+%2 ROI** | ❌ TRIVOX için RED |
| "K=3 lottery, K=1 negatif olur" | EUVOX K=1 = **−%0.8 ROI** | ✅ EUVOX için ONAY |
| "Bonferroni 0/19" | TRIVOX K=1 p=0.0025 ≈ α/19 | ❌ Sınırda RED |
| "Edge gerçek değil, in-sample bias" | TRIVOX K=1 489 sample, hit %61 | ⚠️ Devam ediyor |
| "CLV negatif → edge sahte" | Hem TRIVOX hem EUVOX CLV negatif | ✅ ONAY |

---

## 5) BU SONUÇ V2 PLANINI NASIL ETKİLER?

### TRIVOX V2 (yeniden inşa, ama umut var)
- ✅ K=1 baseline pozitif → **edge gerçek** (ama küçük: +%2 net)
- ❌ CLV negatif → mevcut **filtre yanlış** (FAV_CONFIRMED → VALUE_CONFIRMED)
- 🎯 Hedef: V2 ile K=1 ROI'yi **+%5'e çıkar**, K=1 CLV'yi **>0'a getir**

### EUVOX V2 (radikal yeniden tasarım gerekli)
- ❌ K=1 baseline negatif → mevcut mimari **edge'siz**
- Yeni yaklaşım: per-lig **ayrı edge** ölç (T1+E0 vs SP1+I1+F1)
- Eğer per-lig K=1 hala negatif → EUVOX **emekliye**, sadece TRIVOX kalır

### Beklenmeyen Bulgu — K=1 ile K=3 arasındaki ROI farkı
```
TRIVOX: K=1 +%2  → K=3 +%38.7  (19x kat)
EUVOX:  K=1 −%0.8 → K=3 −%2.2  (negatif kalıyor)
```
- TRIVOX'ta K=3 outliers (top 5 maç) tüm ROI'yi taşıyor
- EUVOX'ta kombin büyütme yok çünkü edge zaten yok
- Bu, **K=3 stratejisinin TRIVOX için bile riskli** olduğunu gösteriyor
- V2'de **K=1 veya K=2** önerilmeli, K=3 değil

---

## 6) SIRADA — KAPI 0 KALAN TESTLER

| Test | Önem | Durum |
|---|---|---|
| T01 K=1 baseline | KRİTİK | ✅ TAMAM |
| T02 T1 walk-forward DC | KRİTİK | ⏳ SIRADAKİ |
| T03 xG/form timing leakage audit | KRİTİK | beklemede |
| T04 Platt 3-fold split | KRİTİK | beklemede |
| T05 External holdout 2024-25 | ORTA | beklemede |
| T06 Sezon-sınır validasyonu | DÜŞÜK | beklemede |
| T07 Refit frekansı sensitivity | DÜŞÜK | beklemede |

---

## 7) ÖZET — TEK SAYFA

**TRIVOX**: K=1 +%2 ROI, p≈0.0025 (Bonferroni sınırda). Edge gerçek ama **küçük** ve **CLV-negatif**.
→ V2 retrain meşru, hedef: edge'i %5'e çıkar + CLV pozitif yap.

**EUVOX**: K=1 −%0.8 ROI net. Edge yok (vergi sonrası).
→ V2 retrain'i radikal olmalı veya emekliye.

**Komiteye cevap**: "Lottery hipotezi TRIVOX için reddedildi, EUVOX için doğrulandı. Bonferroni 0/19 iddiası TRIVOX K=1 ile sınırda kontra-kanıt buldu."

**Sonraki adım**: T02 — T1 walk-forward DC. Eğer +%2 ROI in-sample biased ise → herşey çöker. Eğer ayakta kalırsa → V2 başlar.
