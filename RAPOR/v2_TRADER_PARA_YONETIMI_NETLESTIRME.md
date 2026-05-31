# 🎯 YÖNETİCİ ÖZETİ — 8504 Trader Para Yönetimi Netleştirme

**Tarih:** 2026-05-30  
**Karar:** Hedefli (aylık +%20, kâr kilitleme) + karışık kupon zamanlaması  
**Dosyalar:** [`paper_engine.py`](../02_VERI/paper_engine.py) · [`auto_play.py`](../02_VERI/auto_play.py) · [`app_trader.py`](../08_AI_TRADER/app_trader.py)

---

## SİSTEM 3 KATMANDA — NASIL ÇALIŞIR

### 1. DATA (Veri)
```
fetch_iddaa_live.py  →  iddaa.com'un O GÜN sunduğu maçlar (yaz ligleri dahil)
fetch_results.py     →  biten maçların final skoru (sc alanı, st≥6=bitti)
Oranlar: 1X2 + KG + ALT/ÜST
```

### 2. MODEL (Karar)
```
evaluate_match()        →  her maça sinyal (model_prob, edge, score)
build_session_coupons() →  4 kupon tipi, min 2 ayak:
    K2_FAVORI  · K2_VALUE · K2_KARISIK · K3_KOMBO
Mükerrer engeli: bir maç tek kuponda (hem run-içi hem run-arası)
```

### 3. TRADE (Para Yönetimi) — ⭐ YENİ: HEDEFLİ DÖNEM
```
DÖNEM:    Aylık (30 gün)
HEDEF:    Dönem başı × 1.20  (+%20)
STAKE:    Dönem başı bankroll'un %'si (dönem içinde STABİL)
          K2_FAVORI %2.5 · K2_VALUE/KARISIK %2.0 · K3_KOMBO %1.5
STOP:     -%15'te dönem durur
```

---

## ❓ SENİN SORULARININ NET CEVABI

### "Güçlü sinyal var ama kuponu bugün mü oynuyor?"
**EVET — kupon anında açılır, oran kilitlenir.** Ama kupon 2-3 ayaklı kombine; bir ayak bugün, biri 2 gün sonra olabilir. Kupon **en son maç bitince** sonuçlanır. Bu yüzden "sonuçlar ufak ufak geliyor."

### "5000 TL'yi sürekli mi artırmalı, hedefli mi?"
**Senin kararın: HEDEFLİ.** Sistem artık şöyle:

```
Dönem başı:  5.082 TL
Hedef:       6.099 TL  (+%20)
─────────────────────────────────────
[████░░░░░░░░░░░░░░░░] %0  →  ilerledikçe dolar
─────────────────────────────────────
Hedef tutunca → kâr KİLİTLENİR, yeni dönem 6.099'dan başlar
Stop-loss (-%15) → dönem durur, korunur
```

**Neden bu daha iyi:**
- Stake'ler dönem içinde **stabil** → 2-3 galibiyet stake'i şişirmez, kayıplar küçültmez
- Hedefe ulaşınca **kâr garantiye alınır** (locked_profit)
- Disiplinli: "ne zaman duracağını" bilen sistem
- Ölçülebilir: her dönem +%20 hedefi net

---

## BOŞLUKLAR — ÖNCE vs SONRA

| Boşluk | Önce | Sonra |
|---|---|---|
| Para stratejisi | Sabit flat % | ✅ Hedefli dönem (+%20) |
| Günlük/aylık hedef | Yok | ✅ Aylık +%20, ilerleme çubuğu |
| Take-profit | Yok | ✅ Hedef tutunca kâr kilitlenir |
| Stop-loss | Yok | ✅ -%15'te dönem durur |
| Stake stabilitesi | current_bankroll (oynak) | ✅ period_start (stabil) |
| Mükerrer kupon | Vardı | ✅ Çift katmanlı engel |
| Bitmiş maç skoru | Çekilmiyordu | ✅ fetch_results otomatik |

---

## OTOMATİK DÖNGÜ (Tam Otonom)

```
[AutoPlay 09:00 + 18:00]
  ├── Dönem aktif mi? (hedef tutmadıysa)
  ├── iddaa maçları çek
  ├── model değerlendir → kupon oluştur (dönem-başı stake ile)
  └── 5000 TL hesaba kaydet

[AutoSettle her 90 dk]
  ├── biten maç skorlarını çek (fetch_results)
  ├── kuponları kapat → Journal'a yaz
  └── bankroll güncelle → hedef ilerleme güncellenir

[Hedef tutunca]
  └── kâr kilitlenir, yeni dönem başlar, döngü devam
```

---

## ŞU ANKİ DURUM

```
Bankroll:     5.082 TL
Dönem başı:   5.082 TL
Hedef:        6.099 TL (+%20)
İlerleme:     %0 (yeni dönem)
Açık kupon:   5
Kazanan:      2 (Al Urooba +44, Heidelberg +39)
Kilitli kâr:  0 TL (ilk dönem)
```

**Ayarlanabilir parametreler** (paper_portfolio tablosunda):
- `monthly_target_pct`: 0.20 (+%20) → istersen %15 veya %30 yapılır
- `stop_loss_pct`: -0.15 (-%15) → koruma seviyesi

---

*Rapor: 2026-05-30 · Para yönetimi: Hedefli dönem · Zamanlama: Karışık kombine*
