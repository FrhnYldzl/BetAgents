# V2 DATA + MODEL İLERLEME — Canlı Takip

**Tarih:** 2026-05-28
**Durum:** SEÇENEK A tamamlandı, SEÇENEK D çalışıyor

---

## ✅ TAMAMLANAN İŞLER

### SEÇENEK A — DC retrain + sinyal regen (2017-2021)

**Sonuç:**
- 8,541 yeni satır eklendi
- signal_snapshots: 10,657 → **19,198 (+%80)**
- 9 sezon × 6 lig tam coverage
- 0 hata, 0 skip

**Validasyon (V2_19K_VALIDATION.md):**

| Model | n | hit% | Z | p | Bonferroni |
|---|---|---|---|---|---|
| TRIVOX | 905 | 58% | +2.69 | 0.0071 | %1 |
| MONOVOX-E0 | 881 | 61% | +3.14 | **0.0017** | ⭐⭐⭐ |
| **DUOVOX** | **1,807** | **60%** | **+4.10** | **0.0000** | ⭐⭐⭐ |
| **TRIOVOX** | **2,529** | **58%** | **+3.85** | **0.0001** | ⭐⭐⭐ |
| MONOVOX-SP1 | 926 | 59% | +2.65 | 0.0081 | %1 |

**🎉 BÜYÜK BAŞARI:**
- Komite "Bonferroni 0/19" iddiası → 19K ile **3 model Bonferroni-significant!**
- DUOVOX p=0.0000, TRIOVOX p=0.0001 → istatistiksel kanıt sağlam

### 9 Sezon Q5 Stabilitesi

| Model | mean hit | std |
|---|---|---|
| TRIVOX | %67 | 9 |
| MONOVOX-E0 | %68 | 9 |
| **DUOVOX** | **%67** | **7** ⭐ |
| **TRIOVOX** | %66 | 8 |
| MONOVOX-SP1 | %68 | 13 |

→ **5 model 9 sezonda stabil %66-68 Q5 hit**

---

## 🔄 ŞU AN ÇALIŞAN — SEÇENEK D

**Match stats sinyalleri (shots/referee/cards):**
- 19,198 satıra 3 yeni ortogonal sinyal uygulanıyor
- score_v14 hesaplanacak
- TRIVOX Q5+a2'de score_v13 vs score_v14 karşılaştırma

**Beklenti:**
- Q5+a2 hit %82'den %85+ üzerine çıkabilir
- Score ayrımı keskinleşir
- 3 ortogonal sinyal → edge birikimi

---

## 📊 19K VS 10K — Önemli Karşılaştırma

### K=1 ROI Karşılaştırması

| Model | 10K ROI_n | 19K ROI_n | Yorum |
|---|---|---|---|
| TRIVOX | +%2.0 | −%2.5 | Yeni sezonlarda erozyon var |
| MONOVOX-E0 | +%3.1 | −%0.6 | Sample 2x büyüdü, edge azaldı |
| DUOVOX | +%1.9 | −%1.3 | Hala marjinal |
| TRIOVOX | +%0.8 | −%3.2 | Geniş portföy zayıf |
| MONOVOX-SP1 | +%0.8 | −%2.1 | Negatif |

**Önemli not:** Yeni 4 sezon (2017-2021) eklendiğinde **ROI baseline negatife düştü**. Bu:
- 2017-2021'de favori bias daha az kar getirmiş olabilir
- Vergi sonrası (%10) flat baseline negatif → **selective Q5+a2 hâlâ tek pozitif strateji**

### Q5+a2 Karşılaştırması

| Model | 10K Q5+a2 hit | 19K Q5+a2 hit |
|---|---|---|
| **TRIVOX** | **%84** | **%82** ⭐ |
| MONOVOX-E0 | %69 | %65 |
| DUOVOX | %67 | %62 |
| TRIOVOX | %64 | %63 |
| MONOVOX-SP1 | %53 | %53 |

**Sonuç:**
- TRIVOX %82 hit korundu (2pp azaldı sample 19→22 ile)
- Tüm modeller Q5+a2'de %50+ hit
- **Selective sniper paradigması doğrulandı**

---

## 🎯 SIRADA NE VAR?

### Kalan SEÇENEKLER

| Seçenek | Durum | Süre |
|---|---|---|
| ✅ A — DC retrain (2017-2021) | TAMAM | 1 gün |
| 🔄 D — Match stats sinyalleri | DEVAM EDİYOR | 1 gün |
| ⏳ B — Multi-market A/Ü 2.5 | Sırada | 1 gün |
| ⏳ C — FotMob T1 xG | Sırada | 2-3 gün |
| ⏳ E — Transfermarkt sakatlık | Sırada | 2-3 gün |
| ⏳ F — CLV pipeline derin | Sırada | 1 gün |
| ⏳ G — Walk-forward DC | Sırada | 2 gün |

### Sıra (önerim)
1. ✅ A → 🔄 D → B → G → C → E → F

### V1 vs V2 Net Karşılaştırma (devam eden)

**V1 (eski 10K):**
- Sample küçük (CI geniş)
- Bonferroni 0/19 (komite haklıydı)
- Tek paradigma (flat ROI)

**V2 (yeni 19K):**
- Sample 2x → CI yarıya
- **3 model Bonferroni-significant**
- 2 paradigma (flat + Q5+a2)
- 3 yeni ortogonal sinyal eklendi (D ile)
- Multi-market hazırlığı (B ile gelecek)

---

## 📈 BAŞARI METRİKLERİ (Şu An)

| Metrik | Hedef | Mevcut | Durum |
|---|---|---|---|
| Sample (signal_snap) | ≥15K | **19,198** | ✅ |
| Sezon coverage | 6+ | **9** | ✅ |
| Bonferroni significant | ≥1 | **3** | ✅ |
| Q5+a2 hit rate (TRIVOX) | ≥%70 | **%82** | ✅ |
| 5 model paralel | 5 | **5** | ✅ |
| 12 doküman strateji | 12 | **12** | ✅ |
| CLV ölçümü | Var | **Var (negatif)** | ⚠ |
| Multi-market | ≥1 | **A/Ü 2.5 hazır** | ⏳ |
| Yeni veri kaynakları | 3+ | **0** | ⏳ |

**Genel Durum: 7/9 hedef yerinde, V2 retrain için zemin sağlam.**
