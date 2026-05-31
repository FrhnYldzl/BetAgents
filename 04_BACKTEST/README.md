# 04_BACKTEST — Geçmiş Veri ile Strateji Testi

Bu klasör, modeller canlı paraya değmeden önce strateji'nin geçmiş veride pozitif EV ürettiğini KANITLAMAK içindir.

## Felsefe

**Backtest'siz canlıya çıkmak = kumar.**

Bir modelin yıllık %15 ROI getirdiğini iddia ediyorsan, bunu en az 2 sezon **out-of-time** veride göstermelisin. İlk sezonda %30 yapıp ikinci sezonda %20 kaybeden model, varyansla oynayan bir modeldir — edge'i yoktur.

## Walk-Forward Validation Şeması

```
[Train: 2020-21]                                          → Model_v1
                  [Test: 2021-22]                         → ROI, CLV ölç
[Train: 2020-22]                                          → Model_v2
                                  [Test: 2022-23]         → ROI, CLV ölç
[Train: 2020-23]                                          → Model_v3
                                                  [Test: 2023-24] → ROI, CLV ölç
```

**Asla** test setiyle hiperparametre ayarlama. Sadece **en son** modeli son sezonda göster ve sonra dokunma.

## Klasör Yapısı (Planlanan)

```
04_BACKTEST/
├── engine/
│   ├── backtest_engine.py        (ana simülasyon motoru)
│   ├── bet_simulator.py          (Kelly + portfolio sizing)
│   └── walk_forward.py
├── strategies/
│   ├── value_bet_strategy.py     (edge > %X varsa bet)
│   ├── closing_line_strategy.py  (sadece CLV+ trade'leri tut)
│   └── kelly_fractional.py
├── reports/                      (her run sonrası rapor)
│   ├── 2024_TR1_dixon_coles.html
│   └── ...
└── notebooks/
    └── strategy_analysis.ipynb
```

## Rapor İçeriği (Her Backtest'ten Sonra)

Bir backtest çalıştığında otomatik üretilen rapor:

1. **Performans Özeti**
   - Toplam bet sayısı
   - Net ROI (%)
   - Sharpe-equivalent
   - Maximum Drawdown (%)
   - Ortalama CLV (%)
   - Win rate (kazanç oranı değil — break-even oran)

2. **Kalibrasyon**
   - Reliability diagram (modelin "%60" dediği bahislerin %60'ı tutmuş mu?)
   - Brier score per market

3. **Pazar Bazlı Detay**
   - Hangi pazarlarda edge var? (1X2 / Alt/Üst / KG / Handikap)
   - Hangi ligde model çalışıyor, hangisinde çuvallıyor?

4. **Dağılım Analizleri**
   - Edge dağılımı
   - Stake dağılımı
   - PnL dağılımı (sol kuyruk = drawdown riski)

5. **Sanity Checks**
   - "Past data leakage" var mı? (geleceği train'e karıştırdın mı)
   - Survivorship bias?
   - Bet sayısı istatistiksel anlamlı mı? (< 200 ise dikkat)

## Tuzaklar (Backtest'te Sık Yapılan Hatalar)

| Tuzak | Etki | Çözüm |
|---|---|---|
| Past data leakage | Sahte %30 ROI | Time-aware split |
| Survivorship bias | Kapanan ligler/takımlar görünmez | Tüm liglerden veri |
| In-sample tuning | Test set sonuçları uydurma | OOT validation |
| Sürtünme yok sayma | Komisyon, slippage hesaplanmaz | %3-5 ek maliyet ekle |
| Açılış oranı kullanmak | Gerçekte o oranı yakalayamazsın | Bahisin alındığı dakikadaki oran |
| Aşırı küçük sample | "Edge buldum!" sahte sinyal | Min 500 bet |

## Backtest Kabul Kriterleri (Canlıya Geçmeden Önce)

Model canlıya geçirilmeden önce şu eşikleri geçmeli:

- ✅ Min 1000 bet üzerinde test edilmiş
- ✅ Out-of-time ROI > %3
- ✅ Ortalama CLV > %2
- ✅ Maximum drawdown < %20
- ✅ Brier score iddaa açılış oranlarından daha düşük
- ✅ Calibration curve diagonal'a yakın
- ✅ En az 2 farklı sezonda tutarlı (tek sezon şans olabilir)
