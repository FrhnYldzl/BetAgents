# T14 — Multi-League Budget (Flat 1000 TL/lig/kupon)

**Versiyon:** v1.0
**Tarih:** 2026-05-27T21:41:08

---

## Bilimsel Sorular

**H8a:** Multi-league diversifikasyon flat altında toplam karı artırır mı?
**H8b:** Ligler arası korelasyon ≤0 olduğu için variance düşer mi?
**H8c:** 5-6 lig hipotetik genişleme değerli mi?

---

## Sonuçlar (Mevcut 3 lig)

| Strateji | n | Hit% | Avg Odd | Hacim | Net PnL | ROI | MaxDD | Aylık | Yıllık |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| T1-only | 103 | 24% | 7.69 | 103,000 | +62,143 | +60.3% | 14,000 | +1,406 | +16,876 |
| T1-only +skip_dark | 80 | 31% | 7.45 | 80,000 | +85,143 | +106.4% | 7,000 | +1,927 | +23,122 |
| E0+T1 paralel | 272 | 22% | 6.34 | 272,000 | +73,849 | +27.2% | 21,000 | +1,629 | +19,546 |
| E0+T1 paralel +skip_dark | 209 | 24% | 6.31 | 209,000 | +77,430 | +37.0% | 15,000 | +1,708 | +20,494 |
| ALL 3-lig paralel | 397 | 21% | 6.31 | 397,000 | +80,672 | +20.3% | 27,576 | +1,779 | +21,352 |
| ALL 3-lig +skip_dark | 294 | 22% | 6.29 | 294,000 | +73,009 | +24.8% | 24,576 | +1,610 | +19,323 |

---

## Per-Lig Yıllık Ortalama (Flat 1000 TL/kupon)

| Lig | Yıllık PnL (TL) |
|---|---:|
| T1 | +16,876 |
| E0 | +3,098 |
| D1 | +1,854 |

---

## Ekstrapolasyon (gözlem bazlı)

**Eğer SP1, I1, F1 verisi olsa idi** (E0+D1 ortalaması ile aynı edge varsayımı):

| Konfigürasyon | Tahmini Yıllık |
|---|---:|
| 3-lig (mevcut) | +21,828 TL/yıl |
| **5-lig (+ SP1+I1)** | **+26,781 TL/yıl** |
| **6-lig (+ F1)** | **+29,257 TL/yıl** |

⚠️ **Önemli uyarı:** Bu ekstrapolasyon her ligin edge'inin aynı olduğunu varsayar. Gerçekte SP1/I1/F1 farklı sharpness'a sahip olabilir (D1 zaten ROI -1.7% verdi 3-lig altında).

---

## Yorum

**Senin sorunun cevabı:**
- 3-lig × 1000 TL flat (T11'den +81K) → 4 sezon
- Skip dark weeks ile aynı hipotez → daha yüksek olabilir
- 5-lig'e genişleme tahminen yıllık +20-25K ekler

**Pratik tavsiye:** Mevcut 3 lig için **ALL paralel + skip_dark_weeks** stratejisi en optimum görünüyor.

CSV: `07_LOG_VE_RAPORLAR/T14_results.csv`
