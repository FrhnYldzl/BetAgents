# HAFTALIK BAKIM — bütünlük denetimi

BetAgents bahislerinin (`paper_bets`, `paper_coupons`) haftalık denetimi. Tabloları
**yalnız okur**; hiçbir şeyi yazmaz, hiçbir şeyi düzeltmez — neyin bozuk olduğunu
söyler. Kendi kaydı `bk_kosu` tablosunda (her çalıştırma saklanır, eğilim görünür).

Panel: SİSTEM › Haftalık Bakım. Son çalıştırma 7 günden eskiyse sayfa ilk
açıldığında kendiliğinden koşar; "Şimdi çalıştır" ile her an koşturulur. Ayrı bir
zamanlayıcı süreci yok.

## Kontroller

| kademe | kontrol | beklenen |
|---|---|---|
| ALARM | sonuçlandırma doğruluğu — her sonuç skordan yeniden hesaplanır | 0 |
| ALARM | aynı kuponda tekrar eden ayak (gerçek çift kayıt) | 0 |
| ALARM | geçersiz oran (≤ 1,00 ya da > 1000) | 0 |
| İZLE | başlamasından 48 saat geçip hâlâ açık bahis | azalmalı |
| İZLE | ajanı boş (sahipsiz) bahis | azalmalı |
| İZLE | lig kodu `ALL` ya da boş olan pay (eşik %50) | azalmalı |
| İZLE | CLV'si ölçülebilen sonuçlanmış bahis payı (eşik %50) | artmalı |
| BİLGİ | ajan filtre uyumu — oran bandı ve pazarlar | adıyla tutarlı |
| BİLGİ | ajan istatistiği şişmesi — aynı ayağın birden çok kupona girmesi | ×1,00'a yakın |

Sağlık › Defter sekmesini **tamamlar**: o kupon düzeyinde erken ödemeyi yakalar
(1 Eylül 2026 hatası); bu paket bahis düzeyinde her sonucu skordan yeniden hesaplar.

## İlk denetimin bulguları (21.09.2026, 1.630 bahis)

- Sonuçlandırma **kusursuz**: 1.271 sonuçlanmış bahis, 0 hata.
- Ajanlar kendi oran bantlarına ve pazarlarına uyuyor.
- **5 bahis 1,00 oranla alınmış** (ÜST 2.5, büyük favori maçları) — pazar kapalıyken
  fiyat yakalanmış olmalı; bahis yerleştirme hatası.
- 1 gerçek çift kayıt, 1 bayat açık bahis, 19 sahipsiz bahis.
- **Lig kodu %86 `ALL`** — lig bazlı filtre ve analiz fiilen kör.
- İstatistik şişmesi: UST_25 ×1,24 · ALT_25 ×1,22 · GUCLU_FAV ×1,21.

```
python 11_BAKIM/bakim_kontrol.py      # denetimi konsolda çalıştır (yazma yok)
```

## hatasizlik.py — her sayfa, her modül, her üreteç

```
python 11_BAKIM/hatasizlik.py          # TAM denetim · commit öncesi bu (~45 sn)
python 11_BAKIM/hatasizlik.py --hizli  # ÜRETEÇ aşamasını atlar (~30 sn)
```

`--hizli` geliştirme döngüsü için: atlanan aşama raporda `· (AŞAMA ATLANDI ·
--hizli)` satırı olarak **görünür** ve sonda "TAM DENETİM DEĞİL" yazar —
sessizce geçilse "denetimden geçti" sanılırdı. Commit öncesi bayraksız koşulur.

Her satırın süresi ölçülür, en pahalı adımlar sonda listelenir: darboğaz ayrı
bir profilleme betiği gerektirmeden görünür.

⚠️ Ölçüm yaparken önizleme sunucusu (streamlit, port 8610) **kapalı** olmalı:
açıkken SQLite kilidi denetimi belirgin şekilde yavaşlatır.
