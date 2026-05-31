# 06_PRODUCTION — Canlı Sistem

Bu klasör, modeller backtest'ten geçtikten sonra **gerçek zamanlı** olarak çalışan üretim sistemini içerir.

## Yaşam Döngüsü

```
[Veri Toplama] → [Feature Update] → [Model Tahmin] → [Edge Filter]
       ▲                                                    │
       │                                                    ▼
       │                                            [Kelly Sizing]
       │                                                    │
       │                                                    ▼
       │                                            [Bahis Önerisi]
       │                                                    │
       │                                                    ▼
       │                                            [Sen ONAY ver]
       │                                                    │
       │                                                    ▼
       │                                            [iddaa.com'da bet]
       │                                                    │
       │                                                    ▼
       └──────────────────────────────────────── [Log + CLV takip]
```

**Kritik:** Sistem **otomatik bahis koymaz**. Sadece öneri üretir. Onayı sen verirsin.

Neden:
1. iddaa ToS otomasyon yasaklıyor
2. Hesap güvenliği (otomatik pattern → ban)
3. Son insan kararı = lineup/sakatlık son dakika check'i

## Klasör Yapısı (Planlanan)

```
06_PRODUCTION/
├── daily_pipeline.py             (her gün çalışan ana script)
├── scheduler/
│   ├── cron_config.yaml          (zamanlama)
│   └── jobs/
│       ├── morning_data_pull.py
│       ├── pre_match_prediction.py  (maç öncesi 2-4 saat)
│       └── closing_odds_snapshot.py (maç öncesi 10 dk)
├── alerts/
│   ├── telegram_bot.py           (yüksek edge bulunca bildir)
│   └── email_notifier.py
├── dashboard/
│   ├── streamlit_app.py          (gerçek zamanlı görsel panel)
│   └── components/
├── config/
│   ├── leagues.yaml              (hangi liglere bakıyoruz)
│   ├── markets.yaml              (hangi pazarlara bahis)
│   └── thresholds.yaml           (edge filtresi, Kelly çarpanı vb.)
└── logs/
    └── (rotating logs)
```

## Günlük Akış (Tipik)

| Saat (TR) | İşlem |
|---|---|
| 08:00 | Veri toplama: gece sonuçları, lineup haberleri, sakatlıklar |
| 09:00 | Model retraining (haftada 1 kez, Pazartesi) |
| 10:00 | Gün içi maçlar için ön tahmin |
| 14:00 | Akşam maçları için ön tahmin (lineup çıkmış) |
| Maç-3saat | Final tahmin + edge hesabı + Kelly öneri |
| Maç-2saat | **Sen onaylarsan** → iddaa'da bahis koy |
| Maç-10dk | Closing odds snapshot (CLV için) |
| Maç sonrası | Sonuç logla, P&L güncelle |

## Bahis Önerisi Çıktısı (Örnek)

```json
{
  "match_id": "TR1_2026_GS_FB_20260530",
  "kickoff_tr": "2026-05-30 20:00",
  "league": "Süper Lig",
  "fixture": "Galatasaray vs Fenerbahçe",
  "market": "Toplam Gol Üst/Alt 2.5",
  "selection": "Üst 2.5",
  "model_probability": 0.612,
  "fair_odds": 1.634,
  "iddaa_odds": 1.85,
  "edge_pct": 13.2,
  "confidence_interval": [0.58, 0.64],
  "kelly_fraction": 0.041,
  "recommended_stake": "410 TL (bankroll: 10.000 TL × 0.25 Kelly × 0.165)",
  "correlated_bets_warning": "Aynı maçta 'KG var' bahsi açıkken bu beti açma",
  "model_breakdown": {
    "dixon_coles": 0.59,
    "xg_poisson": 0.63,
    "meta_learner": 0.612
  },
  "factors": [
    "Galatasaray xG (son 5): 2.1",
    "Fenerbahçe xG (son 5): 1.8",
    "Galatasaray ev sahibi avantaj: +0.3 gol",
    "Hava: yağışsız, 18°C — pozitif"
  ]
}
```

## Operasyonel Disiplin

- **Bot kullanma** — iddaa'da otomatik bahis ToS ihlali
- **Hızlı oran avı yapma** — Sharp piyasayı yenmeye çalışmak değil, edge'i avlıyoruz
- **Lineup gelmeden büyük bahis koyma** — Star oyuncu yoksa model yanılır
- **Stake'i hissine göre değiştirme** — "Bu sefer içime doğdu" → en pahalı cümle
