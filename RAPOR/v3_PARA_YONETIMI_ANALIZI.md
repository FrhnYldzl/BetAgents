# 💰 Para Yönetimi Analizi — Hedef% ve Süre

**Soru:** %20 hedef yerine **daha fazla** deseydik, ya da **süre** koysaydık sistem farklı mı davranırdı?
**Yöntem:** Monte Carlo (20.000 dönem/senaryo) — `02_VERI/sim_money_mgmt.py`. Dönem: hedef/stop(-15%)/süre dolunca biter.

---

## Sonuçlar

### Senaryo A — BAŞABAŞ (edge=0, iyimser)
| Hedef | Süre | Hedef tuttu | Stop yedi | Süre doldu |
|---|---|---|---|---|
| **%20** | 30g | **38.5%** | 56.3% | 5.3% |
| %35 | 30g | 22.1% | 59.0% | 18.9% |
| %50 | 30g | 10.6% | 60.1% | 29.3% |
| %20 | süresiz | 41.3% | 58.7% | 0% |
| %50 | süresiz | 24.2% | **75.8%** | 0% |

### Senaryo B — GERÇEKÇİ (edge≈-10%, backtest'e yakın)
| Hedef | Süre | Hedef tuttu | Stop yedi | Süre doldu |
|---|---|---|---|---|
| **%20** | 30g | **20.8%** | 75.0% | 4.2% |
| %35 | 30g | 8.6% | 78.4% | 13.0% |
| %50 | 30g | 3.1% | 78.9% | 18.1% |
| %50 | süresiz | 5.8% | **94.2%** | 0% |

---

## Yorum (dürüst)

### 1) Daha yüksek hedef deseydik? → **DAHA KÖTÜ olurdu**
Hedef %20→%50 çıkınca **hedefe ulaşma olasılığı çöküyor** (38%→11% / gerçekçide 21%→3%), stop-out ise sabit/artıyor. Sebep yapısal: hedef +%20 ama stop −%15 → **stop daha YAKIN**, ona daha sık çarpılıyor. Hedefi büyütmek = uzak bir hedefi kovalarken yolda durdurulmak. **%20 zaten daha ulaşılabilir/sağlam seçim.**

### 2) Süre koysaydık? → **Zaten var (30 gün) ve FAYDALI**
Süre limiti, kaybeden dönemleri stop'a varmadan **kesip resetliyor** (stop% düşüyor: %50 hedefte 30g→%60 stop vs süresiz→%76 stop). Yani süre = **disiplin mekanizması**: kötü gidişi sınırlar, periyodik kâr-kilitleme yaptırır. **Daha KISA süre (14-21g) → daha hızlı kâr-kilit/zarar-kes** (daha temkinli).

### 3) Asıl gerçek: bu ayarlar EDGE üretmez
Medyan sonuç tüm senaryolarda ~4.200 TL (5.000 altı) → **negatif/sıfır edge'de hiçbir hedef/süre ayarı para bastırmaz.** Hedef ve süre yalnız **riski/yolu** şekillendirir, **beklenen getiriyi değil.** Para basmanın tek yolu **edge** (model kalitesi), hedef/süre değil.

---

## Öneri
- **Hedefi YÜKSELTME** — %20 zaten optimum-üstü; %35-50 sadece stop-out riskini artırır. Edge kanıtlanana kadar istersen **%10-15'e DÜŞÜR** (daha hızlı kâr-kilit, daha az stop maruziyeti).
- **30 günlük süreyi KORU** (iyi disiplin). İstersen **14-21 güne çek** → daha sık review + kâr-kilit.
- **Asimetri:** target +%20 / stop −%15 → stop daha sık. Çok temkinli istiyorsan target/stop oranını dengele (ör. +%15/−%15).
- **Esas kaldıraç edge'tir:** canlı TRADE birikimi + (ileride) model iyileştirmesi pozitif edge gösterirse, O ZAMAN daha yüksek hedef + Kelly mantıklı olur.

> Özet: "Daha fazla hedef" işe yaramazdı (daha çok stop). "Süre" zaten var ve faydalı (kısaltmak daha temkinli yapar). Gerçek iş edge'te.

---

*Sim: 20.000 dönem/senaryo · varsayım: 4 K3 kupon/gün, stake %1.8, kombine oran 3.8, stop −%15 · `02_VERI/sim_money_mgmt.py`*
