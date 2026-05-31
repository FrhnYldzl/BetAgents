# 🔍 DUE DILIGENCE FINAL — Acquirer Raporu

**Acquirer perspektifi:** Mackolik / iddaa.com seviyesinde değerleme
**Tarih:** 2026-05-27
**Sonuç:** ⚠️ **MIXED** — strong backtest, weak live performance

---

## EXECUTIVE SUMMARY (3 dakikalık özet)

### Ürün
**TRIVOX + EUVOX** — Çoklu sinyal konsensüs tabanlı bahis kupon önerme motorları.
Türk Süper Lig (TRIVOX) + 5 Avrupa ligi (EUVOX).

### Backtest Performansı (4 sezon, 10.657 maç)
| Model | n kupon | ROI brüt | ROI net | Yıllık net |
|---|---:|---:|---:|---:|
| TRIVOX (T1) | 109 | +51.5% | +38.7% | +10.5K TL |
| EUVOX (6-lig) | 956 | +18.4% | +9.8% | +23.5K TL |

### 🚨 KRİTİK BULGU — 2025-26 Canlı Sezon

| Model | n kupon | ROI |
|---|---:|---:|
| TRIVOX | 6 | **-100%** ⚠️ |
| EUVOX | 92 | **-0.8%** ⚠️ |

**Backtest +51%/+18% → Canlı -100%/-1%. Edge buhar gibi uçtu.**

---

## 20 DD SORUSU ÖZET

### Strateji (Q1-5)
- Pazar büyük ama doygun (Mackolik dominant)
- Defansif moat **yok** (data public, kod replike edilebilir)
- Customer acquisition cost bilinmiyor (pre-revenue)

### Teknik Edge (Q6-10)
- Akademik metodoloji ✅
- Backtest evidence ✅
- Live evidence **YOK** ❌
- Proprietary data **YOK** ❌
- Code lisans defansif **DEĞİL** ❌

### Performans (Q11-15)
- Out-of-sample backtest pozitif ✅
- 2526 canlı negatif ❌
- CLV ölçülmedi (kırmızı bayrak) ❌
- Sharpe backtest 1.38, canlı bilinmez

### Live Prediction (Q16-20)
- Forward prediction capability **var**
- Real-time data pipeline **yok** (closing odds gecikmeli)
- **Edge zamanla degrade ediyor** (2122 → 2526: +39% → -100%)

---

## ACQUIRER POSITIONING

### "Bunu satın almalı mıyım?"

#### Senaryo A: Defensive Buy (rakip alıyor diye)
- **Yapma.** Replikasyon kolay, 3 ay içinde sıfırdan kurulur.

#### Senaryo B: Talent Acquisition
- Ekip akademik disiplinli, sistematik düşünüyor
- ~200-500K TL bütçeyle aquire edilebilir (talent + IP)
- **Yapılabilir** — düşük risk, makul ödeme

#### Senaryo C: Product Acquisition
- Pre-revenue, canlı validation yok
- ❌ **Yapma** — 6 ay shadow run sonrası tekrar değerlendir

#### Senaryo D: Strategic Investment
- Mackolik/iddaa.com'a entegre tahmin servisi olarak lisanslama
- **Earnout-based**: aylık 1000 TL × 100 kullanıcı milestone
- ✅ **Yapılabilir** — risk paylaşımı

---

## KRİTİK DİYALOG (Hard Questions)

### "Backtest +51%, canlı -100%. Açıklayın."

**Honest cevap:**
1. **Sample küçük** (n=6 TRIVOX) — istatistiksel olarak anlamsız
2. **Sezon ortası, closing odds eksik** — model son maç verisini görmedi
3. **Bookmaker adaptation** — Pinnacle/iddaa son yıllarda model öğrendi
4. **Overfit riski** — 16 farklı test'ten en iyiyi seçtik

### "Canlı ne zaman validate olacak?"

- 2526 sezonu Mayıs 2026'da bitince tam replikasyon
- Live shadow run 4-8 hafta gerekli
- En erken **6 ay sonra** doğrulama

### "EUVOX neden daha iyi tutuyor?"

- 6-lig diversifikasyon variance düşürür
- Hit rate %29 (4-sezon avg %33'e yakın) — sinyaller hâlâ çalışıyor
- Sadece ROI sınırda → bookmaker margin yiyor

### "Hangisini alırsan?"

- **TRIVOX:** Selective ama outlier-heavy (Top 5 = %88 PnL). Risky.
- **EUVOX:** Volume + diversification. Canlıda neredeyse breakeven.
- **Ne ikisi de alarmda değil.** Yani: **bekle**.

---

## RİSK MATRİSİ

| Risk | Olasılık | Etki | Toplam |
|---|:---:|:---:|:---:|
| Edge erosion (canlı zaten -%1) | YÜKSEK | YÜKSEK | 🔴 KIRMIZI |
| Bookmaker adaptation | YÜKSEK | ORTA | 🟡 SARI |
| Replikasyon (rakip kopyalar) | YÜKSEK | ORTA | 🟡 SARI |
| Data dependency (Football-Data, Understat) | DÜŞÜK | ORTA | 🟢 YEŞİL |
| Regulatory (gambling law değişimi) | ORTA | YÜKSEK | 🟡 SARI |
| Sample size (n=109 TRIVOX) | YÜKSEK | DÜŞÜK | 🟢 YEŞİL |

---

## FİNANSAL DEĞERLEME (Spekülatif)

### Senaryo 1: "Olduğu gibi al"
- Pre-revenue
- IP + ekip + metodoloji
- **Maksimum bid: 100-300K TL** (talent + lookback)

### Senaryo 2: "6 ay sonra al"
- Live edge devam ediyorsa: 500K - 2M TL
- Live edge devam etmiyorsa: 50K TL (sıfıra yakın)

### Senaryo 3: "Lisanslama"
- Yıllık 50K TL + revenue share %10-20
- Yatırımcı için **en düşük risk**

---

## KARAR ÖNERİSİ (Acquirer için)

```yaml
acquisition_decision: WAIT_AND_SEE

actions:
  - immediate:
    - "200K TL ön teklif: ekip + IP, milestone'lara bağlı"
    - "6 ay shadow run koşullu satın alma"
    - "CLV doğrulaması iste (Pinnacle opening odds erişimi)"

  - 6_ay_sonra_test:
    - "TRIVOX/EUVOX live ROI ≥ +5% net mi?"
    - "Sample n ≥ 500 mi?"
    - "Bookmaker'lar adapte olmadı mı?"

  - if_validated:
    - "Tam satın alma 1-3M TL aralığında"
    - "Mackolik/iddaa.com altında ürün hattı"

  - if_failed:
    - "Earnout iptal, walk away"
    - "Sadece IP/metodoloji düşük fiyatla al (50K TL)"
```

---

## 🎓 BİLİM İNSANI'NIN DÜRÜST ÖZÜ

> **Bu ürün akademik standartla geliştirildi. Backtest evidence güçlü.**
>
> Ancak **canlı performans henüz kanıtlanmadı**. 2526 sezonu (n=6 + n=92):
> - TRIVOX: 0 tutuş / 6 kupon → -100%
> - EUVOX: 27/92 → -0.8%
>
> Bu **edge erosion** veya **overfit** alarmıdır. Acquirer dürüstçe bilmeli.
>
> **Tavsiye:** **6 ay shadow run + milestone-based deal.** Hemen full acquisition **YAPMA**.

---

## EKLER

- 📂 `RAPOR/DD_20_QUESTIONS.md` — 20 soru detaylı cevaplar
- 📂 `RAPOR/DD_live_prediction_2526.md` — 2526 hafta-hafta sonuçlar
- 📂 `RAPOR/MODEL_v1_2_FINAL.md` — Teknik final özet
- 📂 `RAPOR/YATIRIMCI_SUNUMU.md` — Olumlu satış sunumu (kontrast için)

---

**Dürüst due diligence: backtest güzel, canlı zayıf. Bekle.**
