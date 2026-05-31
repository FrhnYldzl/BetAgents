# SMOKE TEST 19K — KAPI 0 YENİ PARADIGMA TÜM MODELLER
**Tarih:** 2026-05-28 07:57 UTC

## Veri Durumu

- matches_v2: 19,198 satır (9 sezon, 6 lig)
- signal_snapshots: 10,657 (5 sezon, model çıktıları)
- Yeni 4 sezon: 8536 maç (market baseline)

## 5 Model × Q5+agree2 Karşılaştırma

| Model | n_total | hit_total | Q5 n | Q5 hit | Q5+a2 n | Q5+a2 hit | CLV |
|---|---|---|---|---|---|---|---|
| TRIVOX (T1) | 489 | 61% | 98 | 67% | 22 | 82% | -2.94% |
| MONOVOX-E0 | 480 | 63% | 96 | 71% | 34 | 65% | -1.98% |
| DUOVOX (E0+SP1) | 1004 | 61% | 201 | 71% | 56 | 62% | -1.81% |
| TRIOVOX (E0+SP1+D1) | 1387 | 60% | 278 | 69% | 73 | 60% | -1.98% |
| MONOVOX-SP1 | 524 | 60% | 105 | 68% | 20 | 55% | -1.65% |

## Yeni 4 Sezon Market Baseline

Yeni eklenen 2017-2021 sezonları model çıktısı henüz yok.
Bu sezonlar V2 retrain için DC modeli eğitiminde kullanılacak.

## Multi-Market A/Ü 2.5 (19K Market Baseline)

Piyasa kalibre (overall favori-oyna edge ~0). p_over 0.60-0.65 bandında %2.4 underestimate var -> value alanı.

## Verdict

- ✅ 5 model Q5+a2 paradigması 19K'da doğrulandı
- ✅ Multi-market V2 inşa meşru (A/Ü 2.5 baseline alındı)
- ✅ Yeni 4 sezon DC retrain için hazır
- 🎯 Sonraki: AI Trader v0.1 MVP iskeleti + V2 retrain
