# 03_MODELLER — Olasılık Modelleri

Bu klasör, BAHIS AGENT'ın "beyni" — her bahis pazarı için olasılık tahmin eden istatistiksel modelleri içerir.

## Model Mimarisi (Ensemble Yaklaşım)

Tek model değil, birden fazla modelin meta-learner ile birleştirildiği bir **ensemble** kuruyoruz. Bu, Jim Simons / Renaissance felsefesinin temelidir: tek bir teoriye değil, birbirinden bağımsız sinyallere güven.

```
                    ┌─────────────────┐
                    │  Meta-Learner   │
                    │  (LightGBM)     │
                    │  Final p_model  │
                    └────────▲────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────┴───────┐    ┌───────┴───────┐    ┌──────┴────────┐
│ Dixon-Coles   │    │  Elo + Logit  │    │  xG Poisson   │
│ (skor dağılım)│    │  (1X2)        │    │  (Alt/Üst,KG) │
└───────────────┘    └───────────────┘    └───────────────┘
        ▲                    ▲                    ▲
        │                    │                    │
   tarihsel skor       takım rating       Understat xG
```

## Modeller (Öncelik Sırası)

### Model 1: Dixon-Coles (Futbol Skor Modeli)
- **Çıktı:** Tüm olası skorların olasılık matrisi (P[i,j] for i,j in 0..7)
- **Bundan türetilir:** 1X2, Alt/Üst, KG, Handikap, Maç Skoru, İY/MS
- **Veri ihtiyacı:** Son 2-3 sezon lig sonuçları
- **Güç:** Düşük skorlu sonuçları doğru modeller (Maher Poisson'un eksiği)
- **Zayıf yön:** Takım gücünü statik kabul eder → time decay eklenir

### Model 2: Elo + Logistic Regression
- **Çıktı:** Maç sonucu (1X2) olasılıkları
- **Veri ihtiyacı:** Takım Elo rating geçmişi (kendi hesaplayacağız)
- **Güç:** Hızlı, anlaşılır, sürekli güncellenebilir
- **Zayıf yön:** Sadece sonuç bilgisi (skor farkı ağırlığını manuel ayarlamak gerek)

### Model 3: xG-Based Poisson
- **Çıktı:** Beklenen gol sayıları → Poisson dağılım → Alt/Üst, KG
- **Veri ihtiyacı:** Understat veya FBRef xG verisi
- **Güç:** Şans faktörünü filtreler (1-0 kazanan ama xG 0.3 olan takım gerçekte daha kötü oynamıştır)
- **Zayıf yön:** Sadece Avrupa büyük ligler için kapsamlı xG var

### Model 4: Meta-Learner (LightGBM)
- **Girdi:** Yukarıdaki 3 modelin çıktıları + ek özellikler (lineup gücü, hava, hakem, rest days, vb.)
- **Çıktı:** Final olasılık tahmini
- **Eğitim:** Geçmiş maçlarda her alt-modelin tahmin doğruluğuna göre ağırlıklandırma öğrenir

## Klasör Yapısı (Planlanan)

```
03_MODELLER/
├── base/
│   ├── dixon_coles.py
│   ├── elo_rating.py
│   ├── xg_poisson.py
│   └── meta_learner.py
├── calibration/
│   ├── platt_scaling.py
│   ├── isotonic_regression.py
│   └── calibration_curves.py
├── evaluation/
│   ├── log_loss.py
│   ├── brier_score.py
│   └── rank_probability_score.py
├── trained/                      (eğitilmiş model dosyaları)
│   ├── dixon_coles_TR1_2026.pkl
│   └── ...
└── notebooks/                    (deneysel analiz)
    └── *.ipynb
```

## Model Değerlendirme Metrikleri

Modeller **kazandı/kaybetti** ile değil, **olasılık kalibrasyonu** ile değerlendirilir:

| Metrik | Ne ölçer | Hedef |
|---|---|---|
| **Brier Score** | Olasılık tahmin hatası | < 0.20 (1X2 için) |
| **Log Loss** | Bilgi teorik kayıp | iddaa açılış oranlarından daha düşük |
| **Calibration Curve** | "%70 dediğinde gerçekten %70 mı çıkıyor?" | Diagonal'a yakın |
| **CLV (en önemli)** | Açılış → kapanış oran hareketi | Ortalama > %2 |

## Kritik Felsefe

- **Model çıktısı = OLASILIK, fiyat değil.** Fiyat (oran) bahis sitesine aittir. Bizim işimiz olasılığı doğru tahmin etmek.
- **Aşırı uyum (overfitting) en büyük düşman.** Backtest'te %15 ROI veren model çoğunlukla geleceğe geçmiyor.
- **Out-of-time validation şart.** Train: 2020-2023, Validation: 2024, Test: 2025. Karıştırma.
