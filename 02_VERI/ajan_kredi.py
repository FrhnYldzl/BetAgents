"""
💳 AJAN KREDİSİ — düzeltilen bir ajana yeni kasa ve TEMİZ ölçüm penceresi
=========================================================================
Kullanıcı kararı (17.09.2026): "Cesur'da sorun var, incele, düzeltme yapıp
kredi açalım — çok başarılı bir ajandı."

NE YAPAR: ajanın portföy satırında ölçüm penceresini ŞİMDİYE çeker
(era_start), kasayı `tutar`a döndürür, ihtar/kadro-dışı işaretlerini
temizler ve ajan günlüğüne gerekçeli bir kayıt yazar.

NE YAPMAZ: hiçbir kupon silinmez. Eski pencerenin kuponları arşivde kalır.
Sayaçlar (recompute_portfolio), mola (_loss_streak), günlük limit ve ajan
tabloları era_start'tan SONRAKİ kuponlara baktığı için yeni pencereye
karışmazlar. Kasa da recompute'ta pencereden yeniden hesaplanır — eski
pencerede açık kalan bir kuponun sonucu yeni kasaya SIZMAZ.

NEDEN "KASAYA PARA EKLE" DEĞİL: strateji değişti (CESUR v1.2). Eski
sürümün kayıpları yeni sürümün karnesine yazılırsa v1.2 hiç ölçülemez;
eski karne silinirse de kayıp saklanmış olur. Yeni pencere ikisini korur.

Değişiklikten önce satır yedeklenir: yedek_ajan_kredi.json

    python ajan_kredi.py CESUR_V1 --dry
    python ajan_kredi.py CESUR_V1 --tutar 1000 --gerekce "..."
"""
from __future__ import annotations

import json
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

YEDEK = THIS_DIR / "yedek_ajan_kredi.json"


def kredi_ac(pid: str, tutar: float = 1000.0, gerekce: str = "",
             dry: bool = False) -> dict:
    conn = db.connect()
    try:
        r = conn.execute("SELECT * FROM paper_portfolio WHERE portfolio_id=?",
                         (pid,)).fetchone()
        if not r:
            print(f"❌ {pid} portföyü yok")
            return {}
        eski = {k: (None if v is None else str(v)) for k, v in dict(r).items()}
        acik = conn.execute(
            "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? "
            "AND status='open'", (pid,)).fetchone()[0]
        cb = float(eski.get("current_bankroll") or 0)
        ib = float(eski.get("initial_bankroll") or 0)
        print(f"💳 KREDİ — {pid}")
        print(f"   eski pencere : başlangıç {str(eski.get('era_start'))[:16]} · "
              f"kasa {cb:,.0f} / {ib:,.0f} ₺ · ihtar {eski.get('ihtar_count')} · "
              f"kadro dışı {eski.get('benched')}")
        print(f"   yeni pencere : başlangıç ŞİMDİ · kasa {tutar:,.0f} ₺ · ihtar 0")
        if acik:
            print(f"   ⚠️ {acik} açık kupon ESKİ pencerede kalır — sonucu yeni "
                  f"kasaya yazılmaz (recompute pencereye bakar)")
        if gerekce:
            print(f"   gerekçe      : {gerekce}")
        if dry:
            print("   (dry-run — değişiklik yok)")
            return {"dry": True}

        kayitlar = []
        if YEDEK.is_file():
            try:
                kayitlar = json.loads(YEDEK.read_text(encoding="utf-8"))
            except Exception:
                kayitlar = []
        simdi = datetime.utcnow().isoformat()
        kayitlar.append({"pid": pid, "ts": simdi, "eski_satir": eski,
                         "tutar": tutar, "gerekce": gerekce})
        YEDEK.write_text(json.dumps(kayitlar, ensure_ascii=False, indent=1),
                         encoding="utf-8")

        conn.execute(
            "UPDATE paper_portfolio SET initial_bankroll=?, current_bankroll=?, "
            "peak_bankroll=?, total_staked=0, total_return=0, total_coupons=0, "
            "won_coupons=0, total_bets=0, total_wins=0, benched=0, "
            "ihtar_count=0, era_start=?, updated_at=? WHERE portfolio_id=?",
            (tutar, tutar, tutar, simdi, simdi, pid))
        # ⚠️ ÖNCE kasa işlemi kalıcı olur, günlük AYRI işlemde yazılır: günlük
        # yazımı başarısız olursa PostgreSQL işlemi iptal eder ve aynı
        # işlemdeki kasa güncellemesi de SESSİZCE geri alınırdı.
        conn.commit()
        try:
            from agents import _journal
            _journal(conn, pid, "💳 KREDİ + YENİ ÖLÇÜM PENCERESİ",
                     f"Eski pencere ({str(eski.get('era_start'))[:10]} başlangıçlı): "
                     f"kasa {cb:.0f}/{ib:.0f} TL. Yeni pencere {simdi[:16]}, "
                     f"kasa {tutar:.0f} TL, ihtar sıfır. Eski kuponlar arşivde; "
                     f"sayaç, mola ve kasa yeni pencereden hesaplanır. "
                     f"Gerekçe: {gerekce or '—'}")
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"   (günlüğe yazılamadı — kasa işlemi yine de kalıcı: {e})")
        print(f"✅ {pid}: yeni pencere {simdi[:16]} · kasa {tutar:,.0f} ₺ · "
              f"yedek {YEDEK.name}")
        return {"pid": pid, "era_start": simdi, "tutar": tutar}
    finally:
        conn.close()


if __name__ == "__main__":
    a = sys.argv[1:]
    pid = next((x for x in a if not x.startswith("--")), None)
    if not pid:
        print(__doc__)
        sys.exit(1)
    tutar = 1000.0
    gerekce = ""
    if "--tutar" in a:
        tutar = float(a[a.index("--tutar") + 1])
    if "--gerekce" in a:
        gerekce = a[a.index("--gerekce") + 1]
    kredi_ac(pid, tutar=tutar, gerekce=gerekce, dry="--dry" in a)
