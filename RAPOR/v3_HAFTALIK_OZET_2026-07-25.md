# 📊 HAFTALIK YÖNETİCİ ÖZETİ — 25 Temmuz 2026

## 1) İYİ GİDENLER ✅
- **Tam otonomi kanıtlandı**: worker 3 saatte bir düzenli (heartbeat ✓); bu hafta
  KURUCU_V2'ye ~33, ajanlara ~10 kuponu WORKER kurdu (manuel müdahale yok).
  Fetch taze (10:46), settle/CLV/sayaç-senkron/stray temizliği sorunsuz.
- **Ajan Ligi tamamlandı**: 11 oyuncu · sözleşme sistemi (ihtar→kadro dışı→kasa
  devri) · skor tablosu + oyuncu sayfaları + ajan journal'ları · Era-1 arşivi.
- **Veri-doğumlu ajanlar**: ⏰ ERKENKUŞ (arşivin tek pozitif cebi: >48sa %80/+1.3)
  ve 🔥 POPÜLER (iddaa'nın gerçek 13 yazarı + konsensüs + sharp) sahada.
- **CLV karnesi işliyor**: 553 ölçülen bahis (ort +0.64%, beat %30) — metodoloji
  altyapısı hazır; sezonla anlamlanacak.
- Haftanın kritik bug'ları kapatıldı: motor açlığı, PG abort-zinciri,
  çoklu-ajan MAX_OPEN, sayaç kaymaları, mobil sidebar.

## 2) KÖTÜ GİDENLER ❌
- **P&L her yerde kırmızı** (off-season gürültüsü + verimli pazar duvarı):
  KURUCU_V2 ilk haftada **−16.7%** (36 kupon — hâlâ fazla agresif, stop-reset
  döngüsü sürüyor) · POPÜLER **−31.7%** (1W/7L — yazar track-record verisi
  olgunlaşmadan oynadı) · MEMUR −20.3% · AVCI −7.1% · TEMKİNLİ −8.0%.
- **Üç ajan hiç oynamadı**: HOCA & SİMYACI (model çift-onay/değer şartı 6 günde
  HİÇ oluşmadı — eşikler pratikte boş küme olabilir) ve ERKENKUŞ (48sa+Avrupa
  filtresi off-season programında çok dar). Yarınki (26 Tem) İLK lig
  değerlendirmesinde pasiflik ihtarı riski taşıyorlar.
- **Edge hâlâ yok**: beat-rate %30; kanıt-iyi pazarlar bile bu hafta zayıf.
  Gerçek sınav Ağustos'ta.

## 3) GELİŞTİRME ÖNERİLERİ 🔧
- **A. "Ağustos'a köprü" freni**: sezona kadar tüm aktif ajanlarda stake ×0.5 ve
  KURUCU_V2 günlük kupon limitini düşür (36/hafta off-season'da israf).
- **B. POPÜLER koruması**: yazar Wilson track-record'u olgunlaşana dek (settled
  n≥10 yazar sayısı artana kadar) yalnız SHARP-teyitli pick + yarım stake.
- **C. Pasif üçlü kararı (ACİL — yarın ilk lig değerlendirmesi)**: hipotez
  ajanlarının (HOCA/SİMYACI/ERKENKUŞ) eşiklerini hafif gevşet VEYA pasiflik
  ihtarını bunlar için 10 güne esnet; yoksa tasarım gereği yarın ihtar yerler.
- **D. Sezon hazırlığı hazır**: 10 Ağu aktivasyon görevi + 21 Ağu emniyet
  kontrolü kurulu; TRIVOX/EUVOX kasaları bekliyor (Süper Lig: 14 Ağustos).
- **E. Madencilik derslerini filtreye çevir**: Asya-sabah (06-12 UTC) bloğu
  tüm ajanlara yasak bölge yapılabilir (−%19.7 kanıtı).
