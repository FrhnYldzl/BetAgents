# 07_LOG_VE_RAPORLAR — Bet Geçmişi ve Performans Takibi

Bu klasör, BAHIS AGENT'ın **gerçek performansının kanıtıdır**. Backtest umut, log gerçektir.

## İki Tür Kayıt

### 1. Bet Log (her bahis için 1 satır)

```
bet_id, timestamp_placed, match_id, market, selection,
model_prob, fair_odds, iddaa_odds_placed, iddaa_odds_closing,
stake, bankroll_at_time, edge_pct, kelly_fraction,
result, payout, pnl, clv_pct, notes
```

Format: `bet_log.parquet` (veya CSV başlangıçta)

### 2. Bankroll Snapshot (günlük)

```
date, bankroll_start, bankroll_end, deposits, withdrawals,
n_bets, n_wins, total_staked, total_pnl, running_roi_pct,
current_drawdown_pct
```

## Klasör Yapısı (Planlanan)

```
07_LOG_VE_RAPORLAR/
├── bet_log.parquet               (tüm bahisler, append-only)
├── bankroll_history.csv          (günlük snapshot)
├── reports/
│   ├── weekly/
│   │   └── 2026_W22.html
│   ├── monthly/
│   │   └── 2026_05.html
│   └── yearly/
│       └── 2026.html
├── clv_analysis/
│   └── (CLV trendi ve dağılımı)
└── post_mortem/                  (büyük kayıp olduğunda inceleme)
    └── 2026_05_15_kotu_hafta.md
```

## Haftalık Rapor İçeriği (Otomatik Üretilir)

1. **Özet Metrikler**
   - Bu hafta bet sayısı
   - Net P&L (₺)
   - ROI (%)
   - Ortalama CLV (%)
   - Mevcut drawdown (%)

2. **Karşılaştırma**
   - Backtest beklentisine göre durum
   - Sezon başına göre durum

3. **En İyi / En Kötü 5 Bet**
   - Hangileri tuttu, hangileri çakıldı
   - Modelin haklı/haksız olduğu yerler

4. **Model Sağlık Kontrolü**
   - Calibration drift var mı? (modelin "%70" dediği gerçekten %70 mı tutuyor?)
   - Pazar bazlı performans dağılımı

5. **Risk Sinyalleri**
   - Yaklaşan stop-loss eşikleri
   - Aynı bahis tipinde yığılma uyarısı

## Bet Log Kayıt Disiplini

**Her bahisi anında logla.** Hafızana güvenme. Sonradan girmek = bias.

Her bet için zorunlu alanlar:
- ✅ Bahis koyduğun zamandaki iddaa oranı
- ✅ Modelin o anki olasılık tahmini
- ✅ Stake miktarı
- ✅ Bankroll durumu (o anki)
- ✅ Maç başlangıcındaki closing odds (CLV için sonra eklenir)
- ✅ Final sonuç + P&L

## CLV Takibi — En Önemli Sinyal

CLV (Closing Line Value), uzun vadeli karlılığın **en güvenilir erken sinyalidir**. ROI'nın istatistiksel anlamlı olması 500+ bet gerektirirken, ortalama CLV 100 bet'te bile yön verir.

### Hesap
```
clv_pct = ((iddaa_odds_placed / iddaa_odds_closing) - 1) × 100
```

### Yorum
| 100 bet ortalama CLV | Anlamı |
|---|---|
| > %3 | Çok güçlü — uzun vadede karlı olma ihtimali %95+ |
| %1 - %3 | İyi sinyal — model gerçek edge yakalıyor |
| %0 - %1 | Marjinal — komisyon yiyebilir |
| < %0 | Model yön doğruluğunu yakalayamıyor → revize |

### Neden ROI'dan İyi?
- Tek maçta %15 ROI yapabilirsin ama şanstan (variance)
- CLV doğrudan modelin tahmin gücünü ölçer, sonuçtan bağımsız
- Pinnacle gibi sharp piyasanın closing odds'u "consensus truth" sayılır

## Post-Mortem Disiplini

Kötü hafta/ay geçtiğinde **mutlaka** post-mortem yazılır:

1. Bu döneme ait tüm bet'leri tek tek geç
2. Her birinde:
   - Model olasılığı ne kadar haklıydı?
   - Bilgi açığı var mıydı? (eksik veri, geç lineup)
   - Karar süreci doğru muydu?
3. Pattern çıkar: belirli bir pazar/lig zayıf mı?
4. Action item: model parametresi mi değişmeli, veri mi eksik?

Post-mortem **suçlama değil, öğrenme**. Şansın olduğu ya da olmadığı kabul edilir.
