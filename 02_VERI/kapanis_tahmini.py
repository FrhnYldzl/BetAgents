"""
📈 KAPANIŞ ORANI TAHMİNİ — belgenin §3.1 önerisi ölçülebilir mi
=================================================================
Belge §3.1 diyor ki: ajanlar MAÇ SONUCUNU tahmin ediyor, bu yanlış
hedeftir. Doğru hedef KAPANIŞ ORANI'dır — maç sonucu ikili ve
gürültülü, kapanış oranı sürekli ve her maçta zengin sinyal verir.
"Kapanış oranını açılıştan daha iyi tahmin edebilen model, tanım
gereği fiyat üstünlüğüne sahiptir."

Bu modül o iddiayı YENİ AJAN KURMADAN sınar. Çünkü yeni bir ajan
kurmak aylık iştir; önce yönün mümkün olup olmadığı ölçülmeli.

TABAN (naive): kapanış = açılış. Ortalama mutlak hata %7,35.
MODEL: açılış anında bilinen özniteliklerle kapanışı tahmin et.
  · üç açılış oranı ve marjsızlaştırılmış olasılıkları
  · marj (overround) — piyasanın ima ettiği toplam olasılık
  · favori gücü ve favori-longshot mesafesi
  · lig (kukla değişken)

⚠️ WALK-FORWARD ZORUNLU (belge §3.3): zaman serisinde rastgele
çapraz doğrulama SIZINTI üretir ve gerçekte olmayan edge gösterir.
Model YALNIZ geçmişle eğitilir, GELECEKTE sınanır.

⚠️ scipy/sklearn YOK (canlı yol slim). En küçük kareler numpy ile,
normal denklem + ridge düzenlileştirme ile çözülür.
"""
from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _ozellik(r: dict) -> list[float] | None:
    """Açılış ANINDA bilinen öznitelikler. Kapanış bilgisi KULLANILMAZ."""
    try:
        o1, ox, o2 = float(r["o1"]), float(r["ox"]), float(r["o2"])
    except (TypeError, ValueError):
        return None
    if min(o1, ox, o2) <= 1.01:
        return None
    i1, ix, i2 = 1 / o1, 1 / ox, 1 / o2
    top = i1 + ix + i2
    if not (1.0 < top < 1.6):          # bozuk fiyat vektörü
        return None
    # marjsızlaştırılmış olasılıklar
    q1, qx, q2 = i1 / top, ix / top, i2 / top
    marj = top - 1.0
    fav = max(q1, qx, q2)
    zayif = min(q1, qx, q2)
    return [1.0, q1, qx, q2, marj, fav, zayif, fav - zayif,
            1.0 / o1, o1 / 10.0]


def _cozum(X, y, lam: float = 1e-3):
    """Ridge en küçük kareler — (XᵀX + λI)⁻¹Xᵀy."""
    import numpy as np
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    p = X.shape[1]
    A = X.T @ X + lam * np.eye(p)
    try:
        return np.linalg.solve(A, X.T @ y)
    except Exception:
        return np.linalg.lstsq(A, X.T @ y, rcond=None)[0]


def olc(conn, egitim_pay: float = 0.7) -> dict:
    """Walk-forward: ilk %70 eğitim, son %30 SINAV."""
    import numpy as np
    rows = [dict(x) for x in conn.execute(
        "SELECT matchday d, opening_1 o1, opening_X ox, opening_2 o2, "
        "closing_1 c1, league_code lg FROM matches_v2 "
        "WHERE opening_1 > 1.01 AND opening_X > 1.01 AND opening_2 > 1.01 "
        "AND closing_1 > 1.01 AND matchday IS NOT NULL "
        "ORDER BY matchday").fetchall()]
    D = []
    for r in rows:
        f = _ozellik(r)
        if f is None:
            continue
        try:
            hedef = float(r["c1"]) / float(r["o1"]) - 1.0   # oransal hareket
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if abs(hedef) > 1.5:               # uc deger
            continue
        D.append((f, hedef))
    if len(D) < 500:
        return {"n": len(D), "yetersiz": True}

    kes = int(len(D) * egitim_pay)
    Xe = [d[0] for d in D[:kes]]; ye = [d[1] for d in D[:kes]]
    Xs = [d[0] for d in D[kes:]]; ys = [d[1] for d in D[kes:]]
    w = _cozum(Xe, ye)
    tah = np.asarray(Xs, dtype=float) @ w
    ger = np.asarray(ys, dtype=float)

    # TABAN: "kapanis = acilis" -> hareket tahmini 0
    taban_mae = float(np.mean(np.abs(ger)))
    model_mae = float(np.mean(np.abs(ger - tah)))
    iyilesme = (taban_mae - model_mae) / taban_mae if taban_mae > 0 else 0.0
    # yon isabeti: hareketin YONUNU dogru bildi mi
    maske = np.abs(ger) > 0.01
    yon = (float(np.mean(np.sign(tah[maske]) == np.sign(ger[maske])))
           if maske.sum() > 0 else 0.0)
    return {
        "n": len(D), "egitim": kes, "sinav": len(D) - kes,
        "taban_mae": taban_mae, "model_mae": model_mae,
        "iyilesme": iyilesme, "yon": yon,
        "deger": iyilesme * 100.0,
    }


if __name__ == "__main__":
    import db
    c = db.connect()
    try:
        r = olc(c)
    finally:
        c.close()
    if r.get("yetersiz"):
        print("yetersiz veri:", r["n"])
        raise SystemExit
    print("WALK-FORWARD — ilk %70 egitim, son %30 SINAV")
    print(f"  ornek           : {r['n']:,}  (egitim {r['egitim']:,} · "
          f"sinav {r['sinav']:,})")
    print(f"  TABAN  MAE      : {r['taban_mae']*100:.3f}%   "
          f"(kapanis = acilis)")
    print(f"  MODEL  MAE      : {r['model_mae']*100:.3f}%")
    print(f"  iyilesme        : {r['iyilesme']*100:+.2f}%")
    print(f"  yon isabeti     : {r['yon']*100:.1f}%  (sans = %50)")
