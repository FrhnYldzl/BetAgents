# v2 — YATIRIM KOMİTESİNE BAĞIMSIZ CEVAP & SPRINT PLANI

**Tarih:** 2026-05-28
**Konu:** Yatırım Komitesi Raporu (28 Mayıs 2026, Conditional Hold) — bağımsız değerlendirme + somut sprint planı
**Karar:** Kullanıcı **Seçenek A** (Kapı 0 öncelikli, kanıt restorasyonu) seçti

---

## BÖLÜM 1 — KOMİTENİN BULGULARINI 4 KATEGORİYE AYIRMA

### 1.1 ✅ Bizim Zaten Yaptığımız / Doğruladığımız (komite haklı + işlendi)

| Komite Bulgusu | Bizim Durum |
|---|---|
| **A1** Bonferroni 0/19 | T19'da bulduk; B-H ile 4 anlamlı bulgu eklendi |
| **A3** CLV ölçümü yok | **Bugün ölçtük** (Sprint 2.1): TRIVOX −3.08%, EUVOX −1.67% — **komitenin tezi bağımsız olarak doğrulandı** |
| **A4** T17 −%13.6 prelim | DD raporlarında zaten var |
| **A9** Bootstrap CI çok geniş | Sample sorunu — Quick Wins ile 5,800 → 19,198 maça çıktık (3.3x) |
| **B1** T1 xG yok | A1 (FotMob) task'ında planlı |
| **B2** Pinnacle opening yok | S1 (OddsPortal) task'ında planlı |
| **D6** Beklenti yönetimi | v1.2 → v2 pivot bu raporla zaten gerçekleşti |

### 1.2 🎯 Hedeflediğimiz (v2 planında zaten var, henüz tamamlanmadı)

| Komite Bulgusu | v2 Plan Karşılığı |
|---|---|
| **A8** PSI/drift kod yok | Sprint 2.5'te live monitoring planlı |
| **B4** İY/MS, AH, Korner pazarları | v3 (faz sonrası) — şu an kapsam dışı |
| **B6** Hakem/lineup yarım | A4 (match stats — referee ✓) + A2 (lineup, injuries) |
| **C2** Risk manager yarım | v2 plan'da "dynamic Kelly + stop-loss enforce" madde |
| **E5** Veri lineage zayıf | matches_v2 schema bu sorunu çözmek için kuruldu |

### 1.3 🚨 KAÇIRDIĞIMIZ — Komitenin Yakaladığı Yeni Kritik Bulgular

Bunlar bizim hiç düşünmediğimiz veya doğrulamadığımız noktalar — **Kapı 0'a alındı**:

| # | Komite Bulgusu | Kritiklik | Bizim Plan |
|---|---|---|---|
| **A2** | T1 walk-forward DC eksik (sadece E0 için yapılmış, −%0.33) | 🔴 BLOKLAYICI | Kapı 0 — Test 2 |
| **A5** | Refit-every=7 gün → soft-leakage (stale parameter Δ-ROI ölçülmemiş) | 🟠 ORTA | Kapı 0 — Test 7 |
| **A6** | Platt kalibrasyon tek-fold (DC + Platt aynı veri üstünde) | 🔴 KRİTİK | Kapı 0 — Test 4 |
| **A7** | xG-luck/form timing leakage şüphesi (xg_cache test fold'un xG'sini içerebiliyor) | 🔴 BLOKLAYICI | Kapı 0 — Test 3 |
| **A10** | Sezon-sınır validasyonu yok (holdout sezon boundary izlemiyor) | 🟡 ORTA | Kapı 0 — Test 6 |
| **B3** | SP1/I1/F1 için Platt yok (production'da eksik) | 🟠 ORTA | Kapı 1 — V2 retrain |
| **C3** | Korelasyon adjustment yok (combo independent assumption) | 🔴 KRİTİK | Kapı 1 — Combo redesign |
| **C5** | Selector `except Exception → signal=0` (phantom skip) | 🟡 DETAY | Kapı 3 — Pre-production |
| **C6** | DB connection resource leak (context manager yok) | 🟢 DÜŞÜK | Kapı 3 — Pre-production |
| **K=1 baseline yok** | (madde 32 + madde 60) "K=3 lottery mu, gerçek edge mi?" | 🔴 BLOKLAYICI | Kapı 0 — Test 1 |

**Toplam:** 10 yeni nokta; 4'ü BLOKLAYICI (K=1, A2, A7, A6/C3).

### 1.4 ❌ Komitenin Yanlış / Eksik / Kapsam Dışı Analizleri

Bağımsız değerlendirmemiz — komitenin bu noktaları **adil değil veya eksik**:

| Komite Bulgusu | Bağımsız İtirazımız |
|---|---|
| **5,800 maç** "sample yetersizliği" | Eski veri. Bugün **19,198 maç** (3.3x büyüme), Bonferroni power problemi büyük oranda çözülmüş olabilir |
| **4 sezon** | Eski. **9 sezon** (2017-18 → 2025-26) artık aktif |
| **Bonferroni 0/19** vurgusu | B-H (FDR) ile **4 anlamlı bulgu** var; komite bunu görmemiş veya değersiz bulmuş — modern istatistik pratiğinde BH > Bonferroni |
| **C7** "Otomatik bahis yok" | Bilinçli karar (7258 sayılı kanun). "Eksiklik" değil **risk azaltıcı tasarım** |
| **C8** "CI/CD yok" | Prototip aşaması için adil değil; pre-production gerekli ama şimdi değil |
| **D1-D6** Ticari katmandaki tüm eleştiriler | Kullanıcı tarafından kapsam dışı bırakıldı ("lisanslama/MOAT ticari, sen veri ve modele odaklan") |
| **Kanıtlanmış edge 3/10** | Won-legs CLV (−2.4%) > Lost-legs CLV (−4.1%), **+1.69pp delta** → CLV reel sinyal taşıyor; sadece filtre yanlış. Komite bu nüansı atlamış |
| **Plan-uygulama makası 6-10x slip** | FAZ1_MVP_PLAN eski plan; v2 plan'ı uyguluyoruz ve Sprint 1 PASS edildi |
| **EUVOX'u TRIVOX'la aynı kefede** | EUVOX 6-lig portföy + per-lig adaptive, CLV −1.67% (baseline −3% altı = marjinal edge işareti). Komite EUVOX'u "T20 reddedildi" tonuyla geçiştirmiş |

---

## BÖLÜM 2 — V2 CLV-POZİTİF MODEL SPRINT PLANI

### Genel Mimari (4 Kapı + 1 Faz)

```
┌──────────────────────────────────────────────────────────────┐
│ KAPI 0 — KANIT RESTORASYONU      (1-2 hafta, kod, $0 risk)   │
│   7 deterministik test → "edge gerçek mi?" sorusuna net cevap │
└──────────────────────────────────────────────────────────────┘
                            ↓ (geçerse)
┌──────────────────────────────────────────────────────────────┐
│ KAPI 1 — V2 SİNYAL & MİMARİ TASARIM   (2-3 hafta)            │
│   FAV → VALUE pivot, 8 sinyal, CLV-historical, korelasyon    │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ KAPI 2 — V2 EĞİTİM, BACKTEST & VALİDASYON  (2 hafta)         │
│   3-fold split, walk-forward CLV opt, BH-corrected            │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ KAPI 3 — PRE-PRODUCTION KALİTE     (1 hafta)                 │
│   Unit test ≥40, exception fix, resource fix, risk enforce   │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ KAPI 4 — PAPER TRADING (LIVE SHADOW)   (6 ay)                │
│   Haftalık CLV/ROI ölçümü, kapı kararları (3/6/12 ay)        │
└──────────────────────────────────────────────────────────────┘
```

---

### KAPI 0 — KANIT RESTORASYONU (öncelik: BLOKLAYICI)

**Amaç:** Para konuşulmadan önce "mevcut edge gerçek mi?" sorusunu deterministik testlerle cevapla.
**Süre:** 1-2 hafta
**Risk:** Sıfır (sadece kod, mevcut data)
**Çıkış kapısı:** 7/7 test ya geçer (v2'ye devam) veya 1+ kritik test başarısız (model emekliye, başka yöne pivot)

| Test | Süre | Bloklayıcı? | Açıklama |
|---|---|---|---|
| **T01 K=1 baseline** | yarım gün | 🔴 EVET | K=1 ROI ölç (tek-bahis). Eğer K=1 ≤ 0 ve K=3 > 0 → edge **kombin varyansından** (lottery), gerçek edge yok |
| **T02 T1 walk-forward DC** | 1 gün | 🔴 EVET | T1 için `walk_forward_dc.py` çalıştır. In-sample bias düzeltmesi sonrası T1 +%60 ROI nereye düşüyor? |
| **T03 xG/form timing leakage audit** | 1 gün | 🔴 EVET | Deterministik test: her sinyalin maç anından **önce** yazıldığını ispatla. xg_cache, fav_confirmed window |
| **T04 Platt 3-fold split** | yarım gün | 🔴 EVET | DC fit (t-1 sezon) + Platt fit (sezon ilk yarı) + test (sezon ikinci yarı). Brier yeniden ölç |
| **T05 External holdout** | 1 gün | 🟠 ORTA | 2024-25 sezonu **hiç** train'de olmasın. DC: 2017-2024, Platt: 2024 ilk yarı, test: 2024-26 ikinci yarı |
| **T06 Sezon-sınır validasyonu** | yarım gün | 🟡 DÜŞÜK | "Son 600 maç" holdout sezon boundary'sini izliyor mu? |
| **T07 Refit frekansı sensitivity** | 1 gün | 🟡 DÜŞÜK | refit_every = {1, 7, 14, 30} gün → ROI Δ ölç. Soft-leakage gerçek etkisi var mı? |

**Kapı 0 Çıkış Kuralı:**
- **GEÇTI** = T01-T04 hepsi yeşil (K=1 > 0, T1 walk-forward ROI ≥ %15, leakage yok, kalibrasyon Brier ≤ %2 sapma)
- **DURDUR** = T01 K=1 ≤ 0 (edge yok, model emekliye) VEYA T03 leakage tespit edildi (verinin yeniden inşası gerekli)
- **REVİZE** = T02 walk-forward ROI < %15 ama > 0 (in-sample bias var, v2'de düzelt)

---

### KAPI 1 — V2 SİNYAL & MİMARİ TASARIM (öncelik: BÜYÜK YENİDEN İNŞA)

**Amaç:** Mevcut FAV_CONFIRMED filter (negatif CLV) → VALUE_CONFIRMED filter (pozitif CLV hedefli)
**Süre:** 2-3 hafta
**Önkoşul:** Kapı 0 ≥ T01+T02 geçti

#### 1.1 — TRIVOX v2 Tasarım (T1-only)

| Eski (v1.0) | Yeni (v2) | Gerekçe |
|---|---|---|
| FAV_CONFIRMED (favori taraf + 1 sinyal) | **VALUE_CONFIRMED** (closing-altı taraf + 2 sinyal) | CLV negatif → favori değil değer aranmalı |
| 4 sinyal: anomaly, model, xG, form | **6 sinyal**: + sharp_money, + clv_historical | Kapı 1.2'de yeni 2 sinyal |
| min_confirmers = 1 | **min_confirmers = 2** | Komite madde A1 (Bonferroni) + B-H |
| Score = harmonik | **Score = CLV-weighted** | Walk-forward CLV optimize ile |
| K = 3 sabit | **K seçimi adaptif** (K=1 baseline pozitifse K=2 dene) | Komite madde 9 (3-leg lottery riski) |
| Stake = 1000 TL flat | Stake = **0.125 Half-Kelly** | Komite madde E1 |
| Sample 109 | **Sample ~500-800 pick** (19K maçta) | 5x büyüme |

#### 1.2 — Yeni 2 Sinyal Tasarımı

**Sinyal 5: sharp_money**
- Closing odd ile opening odd arasındaki yön değişimi
- Eğer closing < opening (favori daha düştü) ve birden fazla bookmaker'da düşüş varsa → sharp money sinyali
- Yön: closing düşen taraf

**Sinyal 6: clv_historical**
- Takımın son 30 günde maçlarındaki ortalama CLV
- Eğer takımın geçmiş CLV'si pozitif → public misevaluation potansiyeli
- Yön: takımın CLV'si pozitif olan tarafı destekle

#### 1.3 — EUVOX v2 Tasarım (6-lig)

| Eski (v1.1) | Yeni (v2) |
|---|---|
| 4 sinyal | **8 sinyal** (TRIVOX v2'nin 6 sinyali + shots_diff + corners_diff) |
| Per-lig harmonik mean | Per-lig **adaptive scoring + Half-Kelly cap** (zaten v1.1'de vardı) |
| min_conf = 1 | min_conf = 2 |
| Korelasyon adjustment yok | **Frank/Gumbel kopula** ile combo joint prob (Komite C3) |

#### 1.4 — Selector Refactor (Komite C5)

- `except Exception → signal=0` patterns değiştirilecek → `try/except: log + raise`
- Phantom skip durumları audit log'a yazılacak
- Backtest ve production aynı behavior

---

### KAPI 2 — EĞİTİM, BACKTEST & VALİDASYON (öncelik: BÜYÜK)

**Amaç:** Yeni 19K sample üzerinde walk-forward CLV-optimized model retrain + dürüst test
**Süre:** 2 hafta
**Önkoşul:** Kapı 1 tamamlandı

#### 2.1 — Walk-Forward Setup

```
TRAIN:        2017-08 ───────────────────────► 2022-06   (5 sezon)
VAL (Platt):                            2022-07 ───► 2024-06   (2 sezon)
HOLDOUT TEST:                                          2024-07 ───► 2026-05 (2 sezon)
```

#### 2.2 — Validation Metrikleri

| Metrik | Eski (v1) | v2 Hedef | Kabul Eşiği |
|---|---|---|---|
| **CLV mean (picks)** | −3.08% (TRIVOX) | > 0% | ≥ +0.3% |
| **Brier score** | optimistic | gerçek | ≤ %2 sapma val vs test |
| **ROI (holdout)** | %60 (in-sample) | %15-25 | ≥ %5 net |
| **Hit rate** | %24 | gerçek | breakeven ≥ %15 marj |
| **Sample size** | 109 | ≥ 500 | yeterli power |
| **BH-FDR significance** | 4/19 | ≥ 5/test | α=0.10 |

#### 2.3 — Stress Test (Komite Madde 54)

- Capacity stress: bankroll 50K, 100K, 200K, 500K seviyelerinde iddaa limit-yeme simülasyonu
- Drawdown stress: −%15 / −%20 / −%30 senaryolarında dynamic Kelly tepkisi
- Variance bombing: top-5 outlier maç çıkartıldıktan sonra ROI

---

### KAPI 3 — PRE-PRODUCTION KALİTE (öncelik: ORTA)

**Amaç:** Komitenin C kategorisi eksikliklerini kapat
**Süre:** 1 hafta

| Görev | Komite Madde | Süre |
|---|---|---|
| Unit test ≥40 (DC, Platt, selector, combo, risk_manager) | C1 | 3 gün |
| Selector exception handling fix | C5 | yarım gün |
| Resource leak fix (context managers) | C6 | yarım gün |
| Dynamic Kelly + stop-loss enforce | C2, E1 | 1 gün |
| PSI/drift detection kod | A8 | 1 gün |
| Operational dashboard (basic) | C8 | 1 gün |

---

### KAPI 4 — PAPER TRADING (LIVE SHADOW RUN)

**Amaç:** Gerçek iddaa ekranından sinyal al, fiziksel bahis koymadan kayıt tut
**Süre:** 6 ay
**Önkoşul:** Kapı 3 tamamlandı + Kapı 2 CLV > 0 ispatlanmış

**Karar Kapıları:**

| Ay | Karar Kuralı |
|---|---|
| **3. ay** | realized ROI < −%15 → **DURDUR** (model bozulması teyit) |
| **6. ay** | realized ROI < %0 → **REVİZE veya DURDUR** |
| **12. ay** | realized ROI > %5 ve CLV > %0 → **scale × 2** (canlı pilot) ; aksi → **emekliye ayır** |

---

## BÖLÜM 3 — KOMİTENİN 8 PİLOT ŞARTI VS BİZİM DURUMUMUZ

| # | Komite Şartı | Şu Anki Durum | Hangi Kapıda? |
|---|---|---|---|
| 1 | T1 walk-forward, 2024-25 holdout, ROI ≥ %20 | Yapılmadı | **Kapı 0 — T02 + T05** |
| 2 | Capacity stress (50/100/200K) | Yapılmadı | **Kapı 2 — Stress test** |
| 3 | External audit (2 hafta PhD) | Yapılmadı | (Kapı 2 sonrası, opsiyonel) |
| 4 | 6 ay paper trading + CLV > 0 + ROI > %3 | **CLV şu an negatif** | **Kapı 4** |
| 5 | Dynamic Kelly + stop-loss enforce | Yarım | **Kapı 3** |
| 6 | Unit test ≥ 40 yeşil | 0 | **Kapı 3** |
| 7 | Pinnacle opening / CLV ölçüm | **Bugün ölçüldü (B365 proxy)** | ✅ Sprint 2.1 |
| 8 | K=1 baseline negatif değil | **Bilinmiyor** | **Kapı 0 — T01 (EN KRİTİK)** |

---

## BÖLÜM 4 — TAKVİM

```
HAFTA 1-2 ────► KAPI 0 (7 test)                  [şimdi başlıyor]
HAFTA 3-5 ────► KAPI 1 (V2 sinyal + mimari)
HAFTA 6-7 ────► KAPI 2 (eğitim + validasyon)
HAFTA 8   ────► KAPI 3 (pre-production)
HAFTA 9+  ────► KAPI 4 (paper trading 6 ay)
```

**Karar noktaları:**
- Kapı 0 sonu (~Hafta 2): T01 (K=1) sonucuna göre devam ya da emekliye
- Kapı 2 sonu (~Hafta 7): CLV > 0 ispatlandı mı?
- Kapı 4 ay 3/6/12: paper trading kararları

---

## ŞU AN BAŞLIYORUM: KAPI 0 — TEST 1 (K=1 BASELINE)

**En kritik test, en hızlı sonuç.**
- Komite madde 32 ve madde 60'ın özünde olan soru: "K=3 ROI pozitif ama K=1 negatif mi? Eğer öyleyse edge lottery."
- Eğer K=1 ≤ 0 → tüm v2 inşaatı durur, model emekliye.
- Eğer K=1 > 0 → v2 retrain'i meşru, devam.

Çalıştırma: TRIVOX K=1 ve EUVOX K=1 için, mevcut signal_snapshots üzerinde ROI ölç + matches_v2 üzerinden CLV ölç.
