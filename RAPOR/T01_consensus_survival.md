# T01 — Haftalık Konsensüs Survival

**Versiyon:** v1.0
**Tarih:** 2026-05-27T20:57:02
**Veri:** 4 sezon × 3 lig × signal_snapshots tablosundan

---

## Hipotez

Her hafta için: en az 3 sinyal mevcut + en az 2'si aynı yön konsensüsü oluşturmuş maçlardan **en yüksek score'lu olanı** pick et.

Başarı ölçütü: **Positive Weeks Ratio (PWR)** > %50.

---

## Sonuçlar

| Metrik | Değer |
|---|---|
| Toplam hafta pick | **100** |
| Kazanan pick | 62 |
| Hit rate | **62.0%** |
| ROI (per pick) | **+15.34%** |
| **PWR (positive weeks)** | **62.0%** |
| Avg odd | 1.97 |
| Bootstrap CI95 | [-5.5%, +37.1%] |
| Toplam PnL (1 birim/hafta) | +15.34 |
| Verdikt | **⚠️ BELİRSİZ** |

## Per-Sezon

| Sezon | n | Hit% | ROI |
|---|---:|---:|---:|
| 2223 | 34 | 65% | +22.88% |
| 2324 | 35 | 71% | +29.26% |
| 2425 | 31 | 48% | -8.65% |

## Per-Lig

| Lig | n | Hit% | ROI |
|---|---:|---:|---:|
| D1 | 28 | 64% | +14.25% |
| E0 | 72 | 61% | +15.76% |

---

## Yorum

- **PWR 62%** → %50 üstü, başarılı
- **CI95 [-5.5%, +37.1%]** → sıfırı içeriyor = belirsiz

**Picks CSV:** `07_LOG_VE_RAPORLAR/T01_picks.csv`
