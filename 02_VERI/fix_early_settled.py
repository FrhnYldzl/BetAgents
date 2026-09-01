"""
🔧 ERKEN KAPANAN KUPON ONARIMI (tek seferlik veri düzeltmesi)
==============================================================
Hata: verify_settlements.py kuponu yeniden çözerken ayakları
`live = [b for b in bets if b[0] in ("won","lost")]` diye süzüyordu.
AÇIK ayaklar bu süzgeçten düşüyor, sonra `all(b == "won" for b in live)`
"hepsi kazandı" diyordu. Yani 3 ayaklı kuponun 1 ayağı kazanmış, 2 maçı
HENÜZ OYNANMAMIŞ olsa bile kupon `won` yazılıp kasaya para giriyordu.

Üretimde yakalandı (2026-09-01):
  SİMYACI 0ee0482e — 1 Eylül'de "kazandı" yazıldı, ayaklarından ikisi
                     2 ve 4 EYLÜL'de oynanacaktı. 137 ₺ ödendi.
  KONSEY  4f9aed6a — 3 ayaklı kupon, 2 ayağın oranıyla (1,81) ödendi;
                     gerçek kombine oran 2,35 idi.

Kök neden verify_settlements.py içinde düzeltildi (açık ayak koruması).
Bu modül GEÇMİŞ hasarı onarır — kök neden düzelmeden çalıştırmak
anlamsızdır, çünkü bir sonraki denetim aynı hatayı tekrar yazar.

KURAL (sonuç-kör — sonuçlara bakılmadan önce yazıldı):
  Kapanmış (won/lost/void) ama AÇIK ayağı olan ve KAYBEDEN ayağı
  OLMAYAN kupon karara bağlanmamıştır → `open`a döner, ödeme geri alınır.
  KAYBEDEN ayağı olan kupon `lost` KALIR: ölü kombinede kalan ayakların
  sonucu bahsi değiştirmez, erken karar doğrudur.

Silmek yok: kupon `open`a döner, settle motoru bütün ayaklar geldiğinde
kendisi doğru çözer. Portföy sayaçları recompute ile yeniden türetilir.

    python fix_early_settled.py --dry     # sadece raporla
    python fix_early_settled.py           # uygula
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db


SORGU = (
    "SELECT pc.coupon_id cid, pc.portfolio_id p, pc.status st, pc.stake sk, "
    "pc.combined_odds co, pc.actual_return ar, pc.pnl, "
    "SUM(CASE WHEN pb.status='open' THEN 1 ELSE 0 END) acik, "
    "SUM(CASE WHEN pb.status='lost' THEN 1 ELSE 0 END) kayip, "
    "COUNT(*) ayak "
    "FROM paper_coupons pc JOIN paper_bets pb ON pb.coupon_id = pc.coupon_id "
    "WHERE pc.status IN ('won','lost','void') "
    "GROUP BY pc.coupon_id, pc.portfolio_id, pc.status, pc.stake, "
    "pc.combined_odds, pc.actual_return, pc.pnl "
    "HAVING SUM(CASE WHEN pb.status='open' THEN 1 ELSE 0 END) > 0"
)

NOT_METNI = (
    "verify_settlements.py açık ayakları süzüp atıyor, kalan ayaklara bakıp "
    "kuponu 'won' yazıyordu. 3 ayaklı kuponun 1 ayağı kazanmış, 2 maçı HENÜZ "
    "OYNANMAMIŞ olsa bile para kasaya giriyordu. Kök neden düzeltildi; "
    "etkilenen kuponlar 'open'a döndürülüp ödeme geri alındı. Kural sonuç-kör: "
    "kaybeden ayağı olan kupon (ölü kombine) dokunulmadan bırakıldı."
)


def onar(dry: bool = False) -> dict:
    conn = db.connect()
    hedef: list = []
    birak: list = []
    try:
        rows = [dict(x) for x in conn.execute(SORGU).fetchall()]
        if not rows:
            print("✅ Erken kapanmış kupon yok.")
            return {"bulunan": 0, "geri_alinan": 0, "silinen_pnl": 0.0}

        print(f"🔍 Açık ayağı olan kapanmış kupon: {len(rows)}\n")
        for x in rows:
            geri = int(x["kayip"] or 0) == 0          # ← KURAL
            (hedef if geri else birak).append(x)
            print(f"   {x['cid'][:8]} {str(x['p']):13s} {x['st']:5s} "
                  f"ayak={x['ayak']} açık={x['acik']} kayıp={x['kayip']} "
                  f"pnl={float(x['pnl'] or 0):+8.2f}  → "
                  f"{'GERİ AL' if geri else 'BIRAK (ölü kombine)'}")

        d = sum(float(x["pnl"] or 0) for x in hedef)
        pids = sorted({x["p"] for x in hedef})
        print(f"\n   geri alınacak: {len(hedef)} kupon · "
              f"kasadan silinecek PnL {d:+.2f} ₺")
        print(f"   dokunulmayan : {len(birak)} kupon (ölü kombine)")
        print(f"   etkilenen ajan: {', '.join(pids) if pids else '—'}")

        if dry:
            print("\n(dry-run — değişiklik yok)")
            return {"bulunan": len(rows), "geri_alinan": 0, "silinen_pnl": d}
        if not hedef:
            return {"bulunan": len(rows), "geri_alinan": 0, "silinen_pnl": 0.0}

        now = datetime.utcnow().isoformat()
        for x in hedef:
            conn.execute(
                "UPDATE paper_coupons SET status='open', actual_return=NULL, "
                "pnl=NULL, settled_at=NULL WHERE coupon_id=?", (x["cid"],))
        conn.commit()
        print(f"\n✅ {len(hedef)} kupon 'open'a döndürüldü.")

        for pid in pids:
            try:
                conn.execute(
                    "INSERT INTO paper_journal (journal_id, portfolio_id, "
                    "entry_date, entry_type, title, content, created_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (str(uuid.uuid4()), pid, now[:10], "DATA_FIX",
                     "🔧 ERKEN KAPANAN KUPON GERİ ALINDI", NOT_METNI, now))
                conn.commit()
            except Exception:
                conn.rollback()
    finally:
        conn.close()

    from recompute_portfolio import recompute
    for pid in pids:
        r = recompute(pid, verbose=False)
        print(f"   {pid:13s} yeniden hesaplandı → kasa {r.get('bankroll')}")
    return {"bulunan": len(rows), "geri_alinan": len(hedef),
            "silinen_pnl": sum(float(x["pnl"] or 0) for x in hedef)}


if __name__ == "__main__":
    onar(dry="--dry" in sys.argv)
