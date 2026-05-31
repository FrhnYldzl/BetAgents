# 📚 BAHIS AGENT — MODEL CATALOG

**Son güncelleme:** 2026-05-28
**Toplam model:** 13 (10 aktif + 2 deprecated + 1 EUVOX deprecated)
**Aktif silah sayısı:** 10

---

## 🎯 ÜRETİM HAZIR (DUOVOX TAVSİYE EDİLEN)

### ⭐ DUOVOX v1.0 — **TAVSİYE EDİLEN ANA ÜRÜN**
- **Pazar:** 1X2
- **Lig:** E0 (Premier) + SP1 (La Liga)
- **Sample:** 1,807 — büyük ve güvenilir
- **Q5+a2 hit:** %62 (stabil)
- **Bonferroni p:** **0.0000** ⭐⭐⭐ (en güvenli kanıt)
- **Sezonsal std:** 3.5pp (en stabil)
- **Neden:** T1 xG eksik, I1/F1 zayıf. E0+SP1 hem sample büyük hem xG dolu.
- **Nasıl:** FAV_CONFIRMED + Q5 quintile + agree_count≥2

### TRIOVOX v1.0
- **Pazar:** 1X2
- **Lig:** E0 + SP1 + D1
- **Sample:** 2,529 (en büyük 1X2 portföyü)
- **Q5+a2 hit:** %60
- **Bonferroni p:** 0.0001 ⭐⭐⭐
- **Sezonsal std:** 3.3pp
- **D1 ekleyince ortalama hafif düştü ama sample +%40 büyüdü.**

### MONOVOX-E0 v1.0
- **Pazar:** 1X2
- **Lig:** E0 (Premier League tek-lig)
- **Sample:** 881
- **Q5+a2 hit:** %65
- **Bonferroni p:** 0.0017 ⭐⭐⭐

### TRIVOX v1.2
- **Pazar:** 1X2
- **Lig:** T1 (Türk Süper Lig)
- **Sample:** 905 (Q5+a2: 22)
- **Q5+a2 hit:** **%82** ⭐ (en yüksek!)
- **Edge:** +%16.69
- **Bonferroni p:** 0.0071 (%1 anlamlı, Bonferroni sınırda)
- **⚠ Caveat:** T1 xG verisi YOK, FotMob bekleniyor

### MONOVOX-SP1 v1.0
- **Pazar:** 1X2
- **Lig:** SP1 (La Liga tek-lig)
- **Sample:** 926, Q5+a2: 20
- **Q5+a2 hit:** %55
- **Bonferroni p:** 0.0081 (%1)

---

## 🔬 PROTOTİP — Multi-Market V2

### OU25-D1-Over (Bundesliga A/Ü Üst)
- Hit %61, edge +%3.09, sample 180

### OU25-E0-Under (Premier A/Ü Alt)
- Hit %43, edge **+%5.98** ⭐⭐ (yüksek odd 2.68)

### BTTS-D1-Var (Bundesliga KG Var)
- Hit %61, edge +%3.58, sample 515 (BÜYÜK!)

### BTTS-SP1-Var + BTTS-SP1-Yok (La Liga KG çift yön)
- Var: %58, edge +%6.25 ⭐
- Yok: %55, edge **+%6.73** ⭐⭐ (en yüksek KG edge)

### BTTS-I1-Yok (Serie A KG Yok)
- Hit %47, edge +%4.64 (Italian defansif futbol)

---

## 🪦 EMEKLİ (DEPRECATED)

### EUVOX v1.1 — emekliye 2026-05-27
- **Neden:** K=1 baseline −%0.8 ROI net. Komite madde 32 lottery hipotezi doğrulandı.
- **Yerine:** DUOVOX/TRIOVOX K=1

### TRIVOX K=3 (lottery) — emekliye 2026-05-26
- **Neden:** +%38.65 ROI ama n=109, hit %23. Outlier-dependent (4 maç toplam ROI'nin %80'i)
- **Yerine:** TRIVOX v1.2 K=1

---

## 🎓 MODEL FAMİLİLERİ

### VOX Ailesi (1X2 selective sniper)
**Ortak felsefe:** "Modelin EN GÜVENDIĞI anlarda büyük oyna, gerisinde pas."

Üyeler: TRIVOX, MONOVOX-E0, MONOVOX-SP1, DUOVOX, TRIOVOX

**Ortak filtre:** FAV_CONFIRMED + Q5 + agree_count≥2
**Sinyaller:** anomaly, model, xG, form, shots (v14), referee (v14), cards (v14)

### MARKET Ailesi (Multi-market DC Poisson türetimleri)
**Ortak felsefe:** "DC modelin goal Poisson dağılımından her pazarın olasılığı türetilir."

Üyeler: OU25-*, BTTS-*

**Ortak teknik:** `score_matrix(λ_h, λ_a, ρ)` → `prob_over_under()` / `prob_btts()`

---

## 🚀 SONRAKİ VERSİYONLAR (PLANLI)

### VALUE_CONFIRMED v2 (Kapı 1)
- **Hedef:** CLV-positive filtre
- **Değişim:** FAV_CONFIRMED → VALUE_CONFIRMED (closing-altı seçim)
- **Sebep:** Mevcut modeller hit rate yüksek ama CLV negatif

### Platt Kalibrasyon
- **Hedef:** OU25 ve BTTS modelleri için kalibrasyon
- **Sebep:** Şu an >+%20 edge bölgesinde overconfident, U-shape bias

### FotMob T1 xG
- **Hedef:** TRIVOX'un xG açığını kapatma
- **Sebep:** T1 xG %0, Q5+a2 sample artırma potansiyeli 2-3x

---

## 📊 MODEL × PAZAR MATRİSİ (10 Aktif Silah)

| Lig | 1X2 | A/Ü 2.5 | KG | İY | AH |
|---|---|---|---|---|---|
| T1 | TRIVOX | — | — | — | — |
| E0 | MONOVOX-E0, DUOVOX, TRIOVOX | OU25-E0-Under | — | — | — |
| SP1 | MONOVOX-SP1, DUOVOX, TRIOVOX | — | BTTS-SP1-Var/Yok | — | — |
| D1 | TRIOVOX | OU25-D1-Over | BTTS-D1-Var | — | — |
| I1 | — | — | BTTS-I1-Yok | — | — |
| F1 | — | — | — | — | — |

**Doluluk:** %30 (60 hücreden 18 dolu) — bol genişleme alanı

---

## 📋 LİFECYCLE STAGES

- **PROTOTYPE**: Hesaplandı, henüz canlı test edilmedi (yeni multi-market modeller)
- **VALIDATED**: Bonferroni veya benzeri istatistiksel onayı geçti
- **PRODUCTION**: Live shadow + paper trading başarılı, gerçek bahisle hazır
- **DEPRECATED**: Üretimden çıkarıldı (sebep belirtilmiş)
- **ARCHIVED**: Arşivlendi, kayıtlı kalır

**Şu an:** 5 VALIDATED, 5 PROTOTYPE, 2 DEPRECATED

---

## 📁 KAYIT YERLERİ

- `model_registry.json` — Programatik erişim, JSON
- `MODEL_CATALOG.md` — Bu dosya (insan-okur)
- `model_card_*.md` — Her model için detay (planlı)
- Kod: `03_MODELLER/selective/trivox_v1.py`, `euvox_v1.py`, vs.
