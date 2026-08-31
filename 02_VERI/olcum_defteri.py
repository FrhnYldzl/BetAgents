"""
📓 ÖLÇÜM DEFTERİ — her bulgu tekrar koşulabilir bir testtir
============================================================
Bir bulgu, ölçüldüğü gün doğru olduğu için sonsuza kadar doğru kalmaz.
Bu projede ROI +%9,7'den −%0,1'e düştü (n 133→216) ve "edge sıralaması
çalışıyor" hükmü tek ajanın 15 bahsine dayandığı anlaşıldı. İkisi de
ancak TEKRAR ÖLÇÜLDÜĞÜ için yakalandı.

Bu modül, 31 Ağustos 2026'da elle koşulan dokuz ölçümü kalıcı hâle
getirir. Her kayıt şunu taşır:

    KURAL      — ön kayıtlı karar kuralı. Sonuç görülmeden yazılır ki
                 sonradan esnetilemesin.
    HEDEF      — hangi örneklemde tekrar bakılacak.
    ÖLÇÜM      — gerçek veriyi okuyan fonksiyon. Sabit sayı YOK.

⚠️ EN ÖNEMLİ KURAL: buradaki hiçbir fonksiyon geçmiş bir sonucu
sabit olarak döndürmez. Hepsi canlı veritabanını yeniden okur. Bir
bulgu çürüdüyse burası onu söylemek zorundadır.

    python olcum_defteri.py                 # hepsini koş
    python olcum_defteri.py K_BECERI        # tek ölçüm
    python olcum_defteri.py --hizli         # ağır olanları atla
    python olcum_defteri.py --gecmis        # arşivi göster
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db

SPLIT = "2024-01-01"


# ══════════════════════════════════════════════════════════════
# yardımcılar
# ══════════════════════════════════════════════════════════════

def _roi(rows) -> float:
    if not rows:
        return 0.0
    return sum(((r["o"] - 1.0) if r["won"] else -1.0) for r in rows) / len(rows)


def _se(rows) -> float:
    if len(rows) < 2:
        return 0.0
    v = [((r["o"] - 1.0) if r["won"] else -1.0) for r in rows]
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1)) / math.sqrt(len(v))


def _norm(vals: list[float]) -> list[float]:
    """marjsız olasılıklar — oran vektöründen."""
    inv = [1.0 / v for v in vals]
    s = sum(inv)
    return [x / s for x in inv]


def _iddaa_1x2(conn, extra: str = "") -> list[dict]:
    rows = conn.execute(
        "SELECT substr(CAST(kickoff_utc AS TEXT),1,10) d, home_score h, "
        "away_score a, closing_1 o1, closing_X ox, closing_2 o2 "
        "FROM matches_v2 WHERE is_settled=1 AND home_score IS NOT NULL "
        "AND closing_1>1.01 AND closing_X>1.01 AND closing_2>1.01 "
        "AND closing_source='iddaa' " + extra).fetchall()
    out = []
    for x in rows:
        d = dict(x)
        q = _norm([float(d["o1"]), float(d["ox"]), float(d["o2"])])
        res = "1" if d["h"] > d["a"] else ("0" if d["h"] == d["a"] else "2")
        for i, sel in enumerate(["1", "0", "2"]):
            out.append({"d": d["d"], "sel": sel, "q": q[i],
                        "o": float([d["o1"], d["ox"], d["o2"]][i]),
                        "won": sel == res})
    return out


# ══════════════════════════════════════════════════════════════
# ÖLÇÜMLER — her biri canlı veriyi yeniden okur
# ══════════════════════════════════════════════════════════════

def m_marj_haritasi(conn) -> dict:
    """Etkin marj, olasılık dilimlerine göre değişiyor mu?
    Uzun oranlarda %24, favorilerde %9,8 ölçülmüştü (16.137 seçim)."""
    obs = _iddaa_1x2(conn)
    if len(obs) < 2000:
        return {"n": len(obs), "yetersiz": True}
    lo = [x for x in obs if x["q"] < 0.25]
    hi = [x for x in obs if x["q"] >= 0.55]
    if len(lo) < 200 or len(hi) < 200:
        return {"n": len(obs), "yetersiz": True}
    r_lo, r_hi = _roi(lo), _roi(hi)
    gap = (r_hi - r_lo) * 100
    return {
        "n": len(obs), "deger": gap,
        "detay": (f"uzun oran (q<%25) n={len(lo)} ROI {r_lo*100:+.1f}% · "
                  f"favori (q>=%55) n={len(hi)} ROI {r_hi*100:+.1f}%"),
        "gecti": gap >= 8.0,
    }


def m_beraberlik(conn) -> dict:
    """Beraberlik herhangi bir dilimde kurtarıyor mu?"""
    obs = [x for x in _iddaa_1x2(conn) if x["sel"] == "0"]
    if len(obs) < 500:
        return {"n": len(obs), "yetersiz": True}
    d = sorted(obs, key=lambda z: z["q"])
    n = len(d)
    best, best_lbl = -9.9, ""
    for i in range(4):
        g = d[i * n // 4:(i + 1) * n // 4]
        r = _roi(g)
        if r > best:
            best, best_lbl = r, f"q~%{sum(z['q'] for z in g)/len(g)*100:.0f} n={len(g)}"
    return {
        "n": n, "deger": best * 100,
        "detay": f"tüm beraberlikler ROI {_roi(obs)*100:+.1f}% · en iyi dilim {best_lbl}",
        "gecti": best > -0.10,          # kural: bir dilim -%10'un üstüne çıkarsa tez dirilir
    }


def m_k_beceri(conn) -> dict:
    """Beceri katsayısı k — MARJSIZ edge ile. Marjlı tanım k'yı
    ölçemez: varyansın çoğu marj farkıdır (bkz. shrinkage.py)."""
    import shrinkage
    rows = conn.execute(
        "SELECT pb.market mk, pb.pick pk, pb.odds o, pb.model_prob mp, pb.status st, "
        "m.closing_1 c1, m.closing_X cx, m.closing_2 c2, "
        "m.closing_over25 cu, m.closing_under25 ca, "
        "m.closing_btts_yes bv, m.closing_btts_no bn "
        "FROM paper_bets pb JOIN matches_v2 m ON m.match_id=pb.match_id "
        "WHERE pb.status IN ('won','lost') AND pb.odds>1.01 AND pb.model_prob>0"
    ).fetchall()
    D = []
    for x in rows:
        d = dict(x)
        mk = (d["mk"] or "").upper()
        pk = (d["pk"] or "").strip().upper()
        try:
            if mk == "1X2":
                v, i = [d["c1"], d["cx"], d["c2"]], {"1": 0, "0": 1, "X": 1, "2": 2}.get(pk)
            elif mk in ("UST_25", "ALT_25", "OU2.5"):
                v = [d["cu"], d["ca"]]
                i = 0 if (mk == "UST_25" or pk in ("UST", "ÜST")) else 1
            elif mk in ("KG_VAR", "KG_YOK"):
                v, i = [d["bv"], d["bn"]], (0 if mk == "KG_VAR" else 1)
            else:
                continue
            if i is None or any(z is None or float(z) <= 1.01 for z in v):
                continue
            q = _norm([float(z) for z in v])[i]
            mp = float(d["mp"])
            if not (0 < mp < 1) or q <= 0:
                continue
            of = 1.0 / q
            D.append({"e": mp / q - 1.0, "o": of,
                      "r": (of - 1.0) if d["st"] == "won" else -1.0})
        except Exception:
            continue
    if len(D) < 100:
        return {"n": len(D), "yetersiz": True}
    fit = shrinkage.estimate_k(D, control_odds=True)
    if not fit:
        return {"n": len(D), "yetersiz": True}
    kanit = fit["ci_lo"] > 0            # kural: güven aralığı sıfırı DIŞLARSA beceri kanıtlı
    return {
        "n": fit["n"], "deger": fit["k_raw"],
        "ci": (fit["ci_lo"], fit["ci_hi"]),
        "detay": (f"k={fit['k_raw']:+.3f} ±{fit['se_k']:.3f} "
                  f"[{fit['ci_lo']:+.2f},{fit['ci_hi']:+.2f}] "
                  f"μ₀={fit['mu0']*100:+.1f}%"
                  + ("  ⛔ " + fit["degenerate_reason"] if fit["degenerate"] else "")),
        "gecti": kanit and not fit["degenerate"],
    }


def m_ucuz_bolge_kapisi(conn) -> dict:
    """q>=%55 kapısı gerçekten kazandırıyor mu? (31.08 testinde HAYIR:
    ajanlar zaten orada, kapı -1.2 puan zarar veriyordu.)"""
    rows = conn.execute(
        "SELECT pb.market mk, pb.pick pk, pb.odds o, pb.status st, "
        "m.closing_1 c1, m.closing_X cx, m.closing_2 c2, "
        "m.closing_over25 cu, m.closing_under25 ca, "
        "m.closing_btts_yes bv, m.closing_btts_no bn "
        "FROM paper_bets pb JOIN matches_v2 m ON m.match_id=pb.match_id "
        "WHERE pb.status IN ('won','lost') AND pb.odds>1.01").fetchall()
    keep, drop = [], []
    for x in rows:
        d = dict(x)
        mk = (d["mk"] or "").upper()
        pk = (d["pk"] or "").strip().upper()
        try:
            if mk == "1X2":
                v, i = [d["c1"], d["cx"], d["c2"]], {"1": 0, "0": 1, "X": 1, "2": 2}.get(pk)
                draw = pk in ("0", "X")
            elif mk in ("UST_25", "ALT_25", "OU2.5"):
                v = [d["cu"], d["ca"]]
                i = 0 if (mk == "UST_25" or pk in ("UST", "ÜST")) else 1
                draw = False
            elif mk in ("KG_VAR", "KG_YOK"):
                v, i = [d["bv"], d["bn"]], (0 if mk == "KG_VAR" else 1)
                draw = False
            else:
                continue
            if i is None or any(z is None or float(z) <= 1.01 for z in v):
                continue
            q = _norm([float(z) for z in v])[i]
        except Exception:
            continue
        rec = {"o": float(d["o"]), "won": d["st"] == "won"}
        (keep if (q >= 0.55 and not draw) else drop).append(rec)
    if len(keep) < 100 or len(drop) < 30:
        return {"n": len(keep) + len(drop), "yetersiz": True}
    gain = (_roi(keep) - _roi(drop)) * 100
    return {
        "n": len(keep) + len(drop), "deger": gain,
        "detay": (f"geçen n={len(keep)} ROI {_roi(keep)*100:+.1f}% · "
                  f"elenen n={len(drop)} ROI {_roi(drop)*100:+.1f}%"),
        "gecti": gain >= 3.0,
    }


def m_kombo_korelasyon(conn) -> dict:
    """iddaa kombo pazarlarında korelasyonu doğru fiyatlıyor mu?
    Kitabın ima ettiği katsayı, tarihsel gerçek katsayıya eşitse EDGE YOK."""
    import collections
    FB, UB = [0.33, 0.45, 0.58], [0.45, 0.55]

    def band(p, e):
        for i, v in enumerate(e):
            if p < v:
                return i
        return len(e)

    hist = [dict(x) for x in conn.execute(
        "SELECT substr(CAST(kickoff_utc AS TEXT),1,10) d, home_score h, away_score a, "
        "closing_1 o1, closing_X ox, closing_2 o2, closing_over25 ou, closing_under25 un "
        "FROM matches_v2 WHERE is_settled=1 AND home_score IS NOT NULL "
        "AND closing_1>1.01 AND closing_X>1.01 AND closing_2>1.01 "
        "AND closing_over25>1.01 AND closing_under25>1.01").fetchall()]
    B = collections.defaultdict(list)
    for x in hist:
        if x["d"] >= SPLIT:
            continue
        q1 = _norm([float(x["o1"]), float(x["ox"]), float(x["o2"])])[0]
        qU = _norm([float(x["ou"]), float(x["un"])])[0]
        B[(band(q1, FB), band(qU, UB))].append(x)

    def res_of(x):
        return "1" if x["h"] > x["a"] else ("0" if x["h"] == x["a"] else "2")

    live = conn.execute(
        "SELECT iddaa_event_id ev, market m, selection s, odd o FROM market_odds "
        "WHERE market IN ('1X2','OU2.5','1X2_OU') ORDER BY ts").fetchall()
    last = {}
    for r in live:
        d = dict(r)
        last[(d["ev"], d["m"], d["s"])] = float(d["o"])

    def grab(ev, mk, sels):
        vs = []
        for s in sels:
            v = last.get((ev, mk, s))
            if not v or v <= 1.01:
                return None
            vs.append(v)
        return dict(zip(sels, _norm(vs)))

    devs, nev = [], 0
    for ev in sorted({k[0] for k in last}):
        q3 = grab(ev, "1X2", ["1", "0", "2"])
        qo = grab(ev, "OU2.5", ["Üst", "Alt"])
        cells = [f"{r} ve {u}" for r in ("1", "0", "2") for u in ("Üst", "Alt")]
        pc = grab(ev, "1X2_OU", cells)
        if not (q3 and qo and pc):
            continue
        nev += 1
        b = (band(q3["1"], FB), band(qo["Üst"], UB))
        sel = B.get(b)
        if not sel or len(sel) < 300:
            continue
        for r in ("1", "0", "2"):
            for u in ("Üst", "Alt"):
                n = len(sel)
                j = sum(1 for x in sel if res_of(x) == r
                        and ((float(x["h"]) + float(x["a"]) > 2.5) == (u == "Üst"))) / n
                pa = sum(1 for x in sel if res_of(x) == r) / n
                pb = sum(1 for x in sel
                         if (float(x["h"]) + float(x["a"]) > 2.5) == (u == "Üst")) / n
                if pa * pb <= 0:
                    continue
                c_true = j / (pa * pb)
                c_book = pc[f"{r} ve {u}"] / (q3[r] * qo[u])
                if c_book > 0:
                    devs.append(c_true / c_book - 1)
    if nev < 30 or not devs:
        return {"n": nev, "yetersiz": True}
    w = sum(devs) / len(devs) * 100
    return {
        "n": nev, "deger": w,
        "detay": f"{nev} event · {len(devs)} hücre · ağırlıklı marjsız sapma {w:+.1f}%",
        "gecti": abs(w) >= 3.0,     # kural: |sapma| >= %3 ise kitapta HATA var demektir
    }


def m_surekli_kalibrasyon(conn) -> dict:
    """Sürekli skor modeli hâlâ kalibre mi? (sınav dilimi)"""
    import goal_model as gm
    import score_sets as ss
    rows = conn.execute(
        "SELECT substr(CAST(kickoff_utc AS TEXT),1,10) d, home_score h, away_score a, "
        "closing_1 o1, closing_X ox, closing_2 o2, closing_over25 ou, closing_under25 un "
        "FROM matches_v2 WHERE is_settled=1 AND home_score IS NOT NULL "
        "AND closing_1>1.01 AND closing_X>1.01 AND closing_2>1.01 "
        "AND closing_over25>1.01 AND closing_under25>1.01 "
        "AND substr(CAST(kickoff_utc AS TEXT),1,10) >= '" + SPLIT + "'").fetchall()
    # ⚠️ KAPSAM, kalibrasyonun FIT EDİLDİĞİ küme ile aynı olmalı.
    # İlk sürümde yalnız 1X2_OU ölçülüyordu ama CALIB_RATIO üç pazarın
    # tamamından (16 hücre) fit edilmişti — kural bir kümede, ölçüm başka
    # kümedeydi. Defterin ilk koşusu bunu yakaladı.
    R = []
    for x in rows:
        d = dict(x)
        q = _norm([float(d["o1"]), float(d["ox"]), float(d["o2"])])
        qU = _norm([float(d["ou"]), float(d["un"])])[0]
        h, a = int(d["h"]), int(d["a"])
        winners = ([ss.combo_winner(r_, u_) for r_ in ("1", "0", "2")
                    for u_ in ("U", "A", "V", "Y")]
                   + [ss.ou_btts_winner(o_, k_) for o_ in ("U", "A")
                      for k_ in ("V", "Y")])
        for w in winners:
            p, _, _, _ = ss.score_set_prob_cont(q[0], q[1], qU, w)
            if p <= 0:
                continue
            R.append({"p": p, "won": w(h, a)})
    if len(R) < 2000:
        return {"n": len(R), "yetersiz": True}
    v = sorted(R, key=lambda z: z["p"])
    n = len(v)
    err = 0.0
    for i in range(10):
        g = v[i * n // 10:(i + 1) * n // 10]
        err += abs(sum(z["p"] for z in g) / len(g)
                   - sum(1 for z in g if z["won"]) / len(g))
    err = err / 10 * 100
    return {
        "n": n, "deger": err,
        "detay": f"ortalama mutlak kalibrasyon hatası {err:.3f} puan (sınav dilimi)",
        "gecti": err <= 0.50,
    }


def m_hareket_sinyali(conn) -> dict:
    """Yumuşak açılış → keskin kapanış hareketi sonucu öngörüyor mu?
    Bu, ölçülmüş TEK pozitif sinyaldir (+%5,6 örnek-dışı)."""
    rows = conn.execute(
        "SELECT substr(CAST(kickoff_utc AS TEXT),1,10) d, home_score h, away_score a, "
        "opening_1 a1, opening_X ax, opening_2 a2, "
        "closing_1 c1, closing_X cx, closing_2 c2 "
        "FROM matches_v2 WHERE is_settled=1 AND home_score IS NOT NULL "
        "AND opening_1>1.01 AND opening_X>1.01 AND opening_2>1.01 "
        "AND closing_1>1.01 AND closing_X>1.01 AND closing_2>1.01 "
        "AND opening_source <> closing_source").fetchall()
    obs = []
    for x in rows:
        d = dict(x)
        qo = _norm([float(d["a1"]), float(d["ax"]), float(d["a2"])])
        qc = _norm([float(d["c1"]), float(d["cx"]), float(d["c2"])])
        res = "1" if d["h"] > d["a"] else ("0" if d["h"] == d["a"] else "2")
        for i, sel in enumerate(["1", "0", "2"]):
            obs.append({"d": d["d"], "move": qc[i] - qo[i], "won": sel == res,
                        "o": float([d["a1"], d["ax"], d["a2"]][i])})
    te = [x for x in obs if x["d"] >= SPLIT]
    if len(te) < 1000:
        return {"n": len(te), "yetersiz": True}
    d = sorted(te, key=lambda z: z["move"])
    hi = d[4 * len(d) // 5:]
    r = _roi(hi)
    return {
        "n": len(te), "deger": r * 100,
        "detay": (f"sınav dilimi · fiyatı en çok yükselen %20: n={len(hi)} "
                  f"ROI {r*100:+.1f}% (±{_se(hi)*100:.1f})"),
        "gecti": r > 0,
    }


def m_kirilganlik(conn) -> dict:
    """Kırılganlık, kalibrasyon sonrası artık bir hata kaynağı mı?
    (Değilse ceza uygulanmamalı — 31.08'de değildi.)"""
    import score_sets as ss
    rows = conn.execute(
        "SELECT home_score h, away_score a, closing_1 o1, closing_X ox, closing_2 o2, "
        "closing_over25 ou, closing_under25 un FROM matches_v2 "
        "WHERE is_settled=1 AND home_score IS NOT NULL AND closing_1>1.01 "
        "AND closing_X>1.01 AND closing_2>1.01 AND closing_over25>1.01 "
        "AND closing_under25>1.01 AND substr(CAST(kickoff_utc AS TEXT),1,10) >= '"
        + SPLIT + "'").fetchall()
    frag = []
    for x in rows:
        d = dict(x)
        q = _norm([float(d["o1"]), float(d["ox"]), float(d["o2"])])
        qU = _norm([float(d["ou"]), float(d["un"])])[0]
        for r_ in ("1", "0", "2"):
            for u_ in ("U", "A"):
                w = ss.combo_winner(r_, u_)
                p, _, top, isf = ss.score_set_prob_cont(q[0], q[1], qU, w)
                if p <= 0 or not isf:
                    continue
                frag.append({"p": p, "won": w(int(d["h"]), int(d["a"]))})
    if len(frag) < 1000:
        return {"n": len(frag), "yetersiz": True}
    pr = sum(z["p"] for z in frag) / len(frag)
    ac = sum(1 for z in frag if z["won"]) / len(frag)
    ratio = ac / pr if pr else 0
    return {
        "n": len(frag), "deger": ratio,
        "detay": f"kırılgan hücreler: tahmin %{pr*100:.2f} · gerçek %{ac*100:.2f} · oran {ratio:.3f}",
        "gecti": abs(ratio - 1.0) < 0.05,   # kural: |oran-1|<%5 ise ceza GEREKMEZ
    }


# ══════════════════════════════════════════════════════════════
# DEFTER — kural ve hedef, sonuç görülmeden yazılır
# ══════════════════════════════════════════════════════════════

FINDINGS = {
    "MARJ_HARITASI": {
        "baslik": "Etkin marj olasılık dilimine göre değişiyor",
        "kural": "favori − uzun oran farkı ≥ 8 puan · değilse harita REDDEDİLİR",
        "hedef": "Ekim 2026 · iddaa fiyatları 6+ ay olunca",
        "onceki": "+13,6 puan (31.08.2026, 16.137 seçim, örnek-dışı YOK)",
        "fn": m_marj_haritasi, "agir": False,
    },
    "K_BECERI": {
        "baslik": "Beceri katsayısı k — edge sıralaması bilgi taşıyor mu",
        "kural": "güven aralığı sıfırı DIŞLARSA beceri kanıtlı · aksi hâlde kanıt yok",
        "hedef": "kapanmış bahis ≥ 2.000",
        "onceki": "k=+0,082 ±0,682 [−1,25,+1,42] · kanıt YOK (31.08, n=835)",
        "fn": m_k_beceri, "agir": False,
    },
    "KOMBO_KORELASYON": {
        "baslik": "iddaa kombo korelasyonunu yanlış fiyatlıyor mu",
        "kural": "|sapma| ≥ %3 ise kitapta HATA var · altındaysa edge YOK",
        "hedef": "event ≥ 300",
        "onceki": "+%0,1 sapma · edge YOK (31.08, 76 event)",
        "fn": m_kombo_korelasyon, "agir": False,
    },
    "BERABERLIK": {
        "baslik": "Beraberlik herhangi bir dilimde kurtarıyor mu",
        "kural": "bir dilim −%10'un üstüne çıkarsa tez DİRİLİR",
        "hedef": "Ekim 2026",
        "onceki": "en iyi dilim −%17,6 · tez ÖLÜ (31.08, 5.379 seçim)",
        "fn": m_beraberlik, "agir": False,
    },
    "UCUZ_BOLGE_KAPISI": {
        "baslik": "q≥%55 kapısı kazandırıyor mu",
        "kural": "geçen − elenen ≥ 3 puan olmalı · altındaysa kapı GEREKSİZ",
        "hedef": "kapanmış bahis ≥ 2.000",
        "onceki": "−1,2 puan · kapı ZARARLI (31.08, n=1.094)",
        "fn": m_ucuz_bolge_kapisi, "agir": False,
    },
    "HAREKET_SINYALI": {
        "baslik": "Yumuşak → keskin fiyat hareketi sonucu öngörüyor mu",
        "kural": "sınav diliminde üst dilim ROI > 0 olmalı",
        "hedef": "iddaa ile eşzamanlı keskin fiyat toplanınca tekrar",
        "onceki": "+%5,6 (±2,7) · ÖRNEK-DIŞI DOĞRULANDI (31.08, 54.366 seçim)",
        "fn": m_hareket_sinyali, "agir": False,
    },
    "SUREKLI_KALIBRASYON": {
        "baslik": "Sürekli skor modeli hâlâ kalibre mi",
        "kural": "ortalama mutlak hata ≤ 0,50 puan",
        "hedef": "3 ayda bir · model değişirse hemen",
        "onceki": "0,344 puan (31.08, 137.552 sınav gözlemi)",
        "fn": m_surekli_kalibrasyon, "agir": True,
    },
    "KIRILGANLIK": {
        "baslik": "Kırılganlık cezası gerekli mi",
        "kural": "|gerçek/tahmin − 1| < %5 ise ceza GEREKMEZ",
        "hedef": "skor modeli değişirse",
        "onceki": "oran 0,974–1,067 · ceza GEREKSİZ (31.08)",
        "fn": m_kirilganlik, "agir": True,
    },
}


# ══════════════════════════════════════════════════════════════
# arşiv
# ══════════════════════════════════════════════════════════════

def _ensure(conn) -> None:
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS measurement_runs ("
            "ts TEXT, finding_id TEXT, n INTEGER, value REAL, "
            "passed INTEGER, detail TEXT)")
        conn.commit()
    except Exception:
        conn.rollback()


def _onceki(conn, fid: str) -> dict | None:
    """Bu ölçümün en son arşivlenmiş sonucu — hüküm değişimini yakalamak
    için. Asıl değer sık koşmakta değil, DEĞİŞİMİ farketmekte."""
    try:
        r = conn.execute(
            "SELECT ts, n, value, passed FROM measurement_runs "
            "WHERE finding_id=? ORDER BY ts DESC LIMIT 1", (fid,)).fetchone()
        return dict(r) if r else None
    except Exception:
        conn.rollback()
        return None


def _archive(conn, fid: str, res: dict) -> None:
    from datetime import datetime
    try:
        conn.execute(
            "INSERT INTO measurement_runs (ts, finding_id, n, value, passed, detail) "
            "VALUES (?,?,?,?,?,?)",
            (datetime.utcnow().isoformat(), fid, int(res.get("n") or 0),
             float(res.get("deger") or 0.0),
             1 if res.get("gecti") else 0, str(res.get("detay") or "")[:400]))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"    ⚠️ arşive yazılamadı: {e}")


def gecmis(conn, limit: int = 40) -> None:
    _ensure(conn)
    rows = conn.execute(
        "SELECT ts, finding_id, n, value, passed FROM measurement_runs "
        "ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    if not rows:
        print("arşiv boş — henüz koşulmamış.")
        return
    print(f"{'tarih':17s}{'ölçüm':22s}{'n':>8s}{'değer':>10s}{'hüküm':>9s}")
    for r in rows:
        d = dict(r)
        print(f"{str(d['ts'])[:16]:17s}{str(d['finding_id']):22s}"
              f"{d['n']:8d}{d['value']:10.3f}"
              f"{'GEÇTİ' if d['passed'] else 'kaldı':>9s}")


def run(ids: list[str] | None = None, hizli: bool = False) -> None:
    conn = db.connect()
    _ensure(conn)
    sel = ids or list(FINDINGS)
    print("=" * 78)
    print("  📓 ÖLÇÜM DEFTERİ — kurallar sonuç görülmeden yazıldı")
    print("=" * 78)
    ok = fail = skip = 0
    degisim: list[str] = []
    for fid in sel:
        f = FINDINGS.get(fid)
        if not f:
            print(f"\n  ⚠️ bilinmeyen ölçüm: {fid}")
            continue
        if hizli and f["agir"]:
            print(f"\n▸ {fid} — atlandı (--hizli)")
            skip += 1
            continue
        print(f"\n▸ {fid} · {f['baslik']}")
        print(f"    KURAL   {f['kural']}")
        print(f"    HEDEF   {f['hedef']}")
        print(f"    ÖNCEKİ  {f['onceki']}")
        try:
            res = f["fn"](conn)
        except Exception as e:
            conn.rollback()
            print(f"    🔴 ÖLÇÜLEMEDİ: {type(e).__name__}: {e}")
            fail += 1
            continue
        if res.get("yetersiz"):
            print(f"    ⏳ ÖRNEKLEM YETERSİZ (n={res.get('n')}) — hedefe ulaşınca tekrar")
            skip += 1
            continue
        print(f"    ŞİMDİ   {res['detay']}")
        print(f"    HÜKÜM   {'✅ KURAL SAĞLANDI' if res['gecti'] else '❌ kural sağlanmadı'}")
        prev = _onceki(conn, fid)
        if prev is not None:
            was = bool(prev["passed"])
            if was != bool(res["gecti"]):
                msg = (f"{fid}: {'GEÇTİ' if was else 'kaldı'} → "
                       f"{'GEÇTİ' if res['gecti'] else 'kaldı'}  "
                       f"({prev['value']:+.3f} → {res['deger']:+.3f}, "
                       f"n {prev['n']}→{res['n']})")
                degisim.append(msg)
                print(f"    🔔 HÜKÜM DEĞİŞTİ — önceki koşu {str(prev['ts'])[:16]}")
        _archive(conn, fid, res)
        ok += 1 if res["gecti"] else 0
        fail += 0 if res["gecti"] else 1
    conn.close()
    print("\n" + "=" * 78)
    print(f"  kural sağlayan {ok} · sağlamayan {fail} · atlanan {skip}")
    if degisim:
        print("\n  🔔 HÜKÜM DEĞİŞEN ÖLÇÜM — asıl haber budur:")
        for m in degisim:
            print(f"     • {m}")
        print("     Bir bulgunun çürümesi de güçlenmesi de karar gerektirir.")
    else:
        print("  hüküm değişimi yok — bulgular önceki koşuyla aynı yönde.")
    print("  ⚠️ 'sağlamadı' bir arıza değil, bir HÜKÜMDÜR — konsept o kadar.")
    print("=" * 78)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--gecmis" in sys.argv:
        c = db.connect()
        gecmis(c)
        c.close()
    else:
        run(args or None, hizli="--hizli" in sys.argv)
