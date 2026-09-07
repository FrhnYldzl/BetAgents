"""
🔻 ERA 3 — AJAN TASFİYESİ ve TEMİZ ÖLÇÜM PENCERESİ
====================================================
Kullanıcı kararı (2026-09-07): "EUVOX en değer verdiğim ajan, o
etkilenmesin. CESUR ve AVCI'dan da memnunum, geri kalanını radikal bir
şekilde değerlendirelim. Mavi ve Kırmızı Takım kalabilir. ERA 3'ü 0'dan
eleyerek kapatmakta problemim yok. Daha az ama başarılı ajanlarla
gitmek istiyorum."

ÖLÇÜLEN DURUM (era-2, 2026-09-07):
  Rastgele kontrol JOKER 4. sırada — onu yalnız 3 ajan geçiyor ve
  üçü de ÖLÇÜLEMEZ ya da GÜRÜLTÜ. 19 ajanın 15'i rastgelenin ALTINDA.
  15 ajanın n'i 30'un altında — yani çoğu hakkında hüküm verilemez.

KURAL (sonuç-kör — sonuçlara bakılmadan önce yazıldı):
  KALIR:
    1. Kullanıcının koruduğu ajanlar (EUVOX, CESUR, AVCI)
    2. JOKER — rastgele KONTROL çizgisi. Metodolojik zorunluluk:
       kontrolü kaldırmak, kalan ajanların bir şey bilip bilmediğini
       ÖLÇME yeteneğini yok eder. "Daha az ajan" kontrolü değil
       kopyaları eler.
    3. Kırmızı takım (CARPAN, SIMETRI, KAVSAK, BANT, DEVRE) —
       kullanıcı takımın kalmasını istedi ve bunlar AYRI hipotezler
       (farklı pazar çiftlerinin korelasyonu), kopya değil. Henüz
       ölçülemedi (toplam n=12); ERA 3 onlara temiz pencere verir.
  GİDER:
    4. Sözleşmesi düşenler (2 ihtar VE kasa 0) — sözleşme zaten
       söylemiş, biz sadece uyguluyoruz
    5. Korumalı bir ajanla %40+ örtüşenler — bağımsız görüş taşımıyor
    6. Geriye kalan her şey: hiçbiri İYİ hükmü almadı ve "daha az ama
       başarılı" istendi

SİLMEK YOK: ajan PROFILES'ta `retired: True` işaretlenir. Geçmişi,
kuponları, kasası arşivde durur — yalnız YENİ bahis üretmez. Karar
geri alınabilir (bayrağı kaldırmak yeter).

ERA 3: kalan ajanların era_start'ı BUGÜN, era_no=3, kasa initial'a
döner. Era-2 kuponları arşivde kalır ama sayaçlara girmez.

    python era3_tasfiye.py --dry     # planı göster
    python era3_tasfiye.py           # uygula
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db

KORUMALI = {"EUVOX_V1", "CESUR_V1", "AVCI_V1"}
KONTROL = {"JOKER_V1"}
KIRMIZI = {"CARPAN_V1", "SIMETRI_V1", "KAVSAK_V1", "BANT_V1", "DEVRE_V1"}
# ajan DEĞİL — defter/arşiv, tasfiyeye girmez
AJAN_DISI = {"OPUS5_V1", "PAPER_V1", "KURUCU_V2"}

KALIR = KORUMALI | KONTROL | KIRMIZI


def plan():
    from agents import PROFILES
    kalir, gider = [], []
    for p in PROFILES:
        (kalir if p in KALIR else gider).append(p)
    return sorted(kalir), sorted(gider)


def uygula(dry: bool = False) -> dict:
    kalir, gider = plan()
    print(f"🔻 ERA 3 TASFİYESİ\n")
    print(f"  KALIR ({len(kalir)}):")
    for p in kalir:
        nd = ("korumalı" if p in KORUMALI else
              ("KONTROL çizgisi" if p in KONTROL else "kırmızı takım"))
        print(f"     {p.replace('_V1',''):12s} — {nd}")
    print(f"\n  GİDER ({len(gider)}) — retired, silinmez:")
    for p in gider:
        print(f"     {p.replace('_V1','')}")
    print(f"\n  DOKUNULMAZ (ajan değil): "
          f"{', '.join(sorted(AJAN_DISI))}")

    if dry:
        print("\n  (dry-run — değişiklik yok)")
        return {"kalir": len(kalir), "gider": len(gider)}

    # 1) agents.py: retired bayrağı
    P = THIS_DIR / "agents.py"
    s = P.read_text(encoding="utf-8")
    import re
    n_iso = 0
    for p in gider:
        # ⚠️ "zaten retired mi" kontrolu KOMSU AJANI GORMEMELI.
        # Ilk halim sabit 900 karakterlik bir pencere kullaniyordu ve o
        # pencere bir SONRAKI ajanin blogu icine tasiyordu: MEMUR
        # alfabetik olarak once islendi, bayragi eklendi, TEMKINLI'nin
        # penceresi ona uzandi ve "zaten var" sanip ATLADI. TEMKINLI
        # sessizce aktif kaldi — dogrulama yapmasaydim fark etmezdim.
        # Artik pencere ajanin KENDI blogu: acilis suslu parantezden
        # kendi kapanisina kadar.
        blok = re.search(r'"' + p + r'":\s*\{(.*?)^    \}',
                         s, re.S | re.M)
        if blok and '"retired":' in blok.group(1):
            continue
        d = re.search(r'("' + p + r'":\s*\{.*?\n(\s*)"name":\s*[^\n]*\n)',
                      s, re.S)
        if not d:
            print(f"     !!! {p} agents.py'de bulunamadı")
            continue
        s = (s[:d.end(1)] + d.group(2) +
             '"retired": True,   # ERA 3 tasfiyesi (2026-09-07)\n' +
             s[d.end(1):])
        n_iso += 1
    P.write_text(s, encoding="utf-8")
    print(f"\n✅ {n_iso} ajan agents.py'de retired işaretlendi.")

    # 2) ERA 3 — yalnız KALAN ajanlar için temiz pencere
    now = datetime.utcnow().isoformat()
    conn = db.connect()
    try:
        n_era = 0
        for p in kalir:
            r = conn.execute("SELECT initial_bankroll FROM paper_portfolio "
                             "WHERE portfolio_id=?", (p,)).fetchone()
            if not r:
                continue
            ib = float(r[0] or 1000)
            conn.execute(
                "UPDATE paper_portfolio SET era_start=?, era_no=3, "
                "current_bankroll=?, peak_bankroll=?, "
                "ihtar_count=0, benched=0 WHERE portfolio_id=?",
                (now, ib, ib, p))
            n_era += 1
        conn.commit()
        print(f"✅ {n_era} ajan ERA 3'e alındı "
              f"(era_start={now[:16]}, kasa initial'a döndü, ihtar sıfırlandı).")
        print("   Era-2 kuponları ARŞİVDE — silinmedi, yalnız sayaçlara girmiyor.")
    finally:
        conn.close()
    return {"kalir": len(kalir), "gider": len(gider), "era": n_era}


if __name__ == "__main__":
    uygula(dry="--dry" in sys.argv)
