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


def m_izleme_kapisi(conn) -> dict:
    """İZLEME — belge §3.7'nin iki devre kesicisi ölçülüyor mu.

    Belge iki otomatik durdurma tetikleyicisi tanımlıyor:
      1. KAYAN PENCEREDE CLV — son 100 bahiste ortalama CLV negatife
         dönerse ajan askıya alınır. Gerekçe: CLV öncü göstergedir,
         sonuçtan önce bozulur. Kâr eğrisi hâlâ yukarı bakarken CLV
         aşağı dönmüşse edge çoktan kapanmıştır.
      2. DÜŞÜŞ DEVRE KESİCİ — tepe noktadan %25 düşüşte TÜM sistem
         durur. Gerekçe (§1.1): çarpımsal asimetri. %50 kayıptan
         başabaşa dönmek %100 kazanç ister; düşüş getiriden
         matematiksel olarak daha pahalıdır.

    ⚠️ BU BULGU YALNIZ ÖLÇER, DURDURMAZ. Otomatik askıya alma canlı ve
    geri alınması zor bir eylemdir; sistemin kendi sözleşmesi (taban
    freni %50, ihtar, kadro dışı) farklı eşiklerle zaten çalışıyor.
    Belgenin eşikleri DAHA SIKI — ikisi çakışmadan önce hangisinin
    doğru olduğu ölçülmeli. O yüzden burada uyarı üretilir, eylem
    değil.
    """
    # ── 1) sistem düşüşü: tepeden bugüne ──
    # ⚠️ YÜRÜRLÜKTEKİ DÖNEM ve SAHADAKİ AJAN — ikisi birlikte.
    # "era_start IS NULL OR ..." koşulu İZİN VERİCİ bir yedek: ajan
    # olmayan portföyler (era_start NULL) ve emekli ajanlar (dönem 2'de
    # kaldılar, kendi era_start'larına göre eski kuponları hâlâ "dönem
    # içi") bu koşuldan GEÇER. İlk ölçümde tam bu oldu: dönem 3 kasası
    # (11.868 ₺) dönem 2 kuponlarıyla karşılaştırıldı ve %48,4 düşüş
    # çıktı. Kasa ile kupon AYNI evrenden olmalı.
    kup = conn.execute(
        "SELECT pc.settled_at sa, COALESCE(pc.pnl,0) pnl "
        "FROM paper_coupons pc JOIN paper_portfolio pp "
        "ON pp.portfolio_id = pc.portfolio_id "
        "WHERE pc.status IN ('won','lost') AND pc.settled_at IS NOT NULL "
        "AND pp.era_no = (SELECT MAX(COALESCE(era_no,1)) "
        "                 FROM paper_portfolio) "
        "AND pp.era_start IS NOT NULL "
        # Dönemin BAŞINDAN — ajanın kendi penceresinden değil: bir ajana
        # kredi + yeni pencere açılınca (CESUR v1.2, 17.09) eski kayıpları
        # sistem düşüşünden SİLİNMEMELİ. (Kayan pencere CLV aşağıda ajanın
        # kendi penceresinde kalır — o bir ajan hükmüdür.)
        "AND pc.created_at >= (SELECT MIN(p2.era_start) FROM paper_portfolio p2 "
        "WHERE p2.era_no = pp.era_no) "
        "ORDER BY pc.settled_at").fetchall()
    # ⚠️ DÜŞÜŞ KASAYA GÖRE ÖLÇÜLÜR, KÂR EĞRİSİNE GÖRE DEĞİL.
    # İlk halim tepe'yi kümülatif PnL eğrisinin tepesi alıyordu ve o
    # eğri SIFIRDAN başlıyor: +50'ye çıkıp −600'e düşen bir seri
    # 650/50 = %1300 düşüş veriyordu. Canlıda %1293,7 çıktı ve saçma
    # olduğu için yakalandı. Belgenin tanımı (§2.2) "tepe noktadan en
    # derin kayıp" ve ölçek BANKROLL'dur: kasa = başlangıç + Σpnl.
    ib = conn.execute(
        "SELECT COALESCE(SUM(initial_bankroll),0) FROM paper_portfolio "
        "WHERE era_no = (SELECT MAX(COALESCE(era_no,1)) "
        "                FROM paper_portfolio)").fetchone()[0]
    ib = float(ib or 0)
    if ib <= 0:
        return {"n": 0, "yetersiz": True}
    kasa = ib
    tepe, dus_oran = ib, 0.0
    for r in kup:
        kasa += float(dict(r)["pnl"] or 0)
        tepe = max(tepe, kasa)
        if tepe > 0:
            dus_oran = max(dus_oran, (tepe - kasa) / tepe)

    # ── 2) ajan başına kayan pencere CLV (son 100 bahis) ──
    rows = conn.execute(
        "SELECT pb.portfolio_id p, pb.clv, pb.kickoff_utc ko "
        "FROM paper_bets pb JOIN paper_portfolio pp "
        "ON pp.portfolio_id = pb.portfolio_id "
        "WHERE pb.clv IS NOT NULL "
        "AND pp.era_no = (SELECT MAX(COALESCE(era_no,1)) "
        "                 FROM paper_portfolio) "
        "AND pp.era_start IS NOT NULL "
        "AND pb.kickoff_utc >= pp.era_start "
        "ORDER BY pb.kickoff_utc").fetchall()
    try:
        from agents import PROFILES
        aktif = {k for k, v in PROFILES.items() if not v.get("retired")}
    except Exception:
        aktif = set()
    by: dict = {}
    for r in rows:
        d = dict(r)
        if aktif and d["p"] not in aktif:
            continue
        by.setdefault(d["p"], []).append(float(d["clv"]))

    bozuk, olculen = [], 0
    for p, v in by.items():
        pencere = v[-100:]
        if len(pencere) < 20:            # 20 altında kayan pencere gürültü
            continue
        olculen += 1
        ort = sum(pencere) / len(pencere)
        if ort < 0:
            bozuk.append((p.rsplit("_", 1)[0], ort, len(pencere)))

    bozuk.sort(key=lambda z: z[1])
    ayrinti = (f"en derin düşüş tepeden %{dus_oran*100:.1f} (eşik %25) · "
               f"kasa {kasa:,.0f}/{ib:,.0f} ₺ · kayan pencere CLV "
               f"ölçülen {olculen} ajan, negatif {len(bozuk)}")
    if bozuk:
        ayrinti += " → " + ", ".join(
            f"{ad} {o*100:+.2f}% (n={n})" for ad, o, n in bozuk[:4])
    # ⚠️ KURAL: sistem düşüşü %25'in ALTINDA ve hiçbir ajanın kayan
    # pencere CLV'si negatif DEĞİL. İkisi birlikte — biri bozulmuşsa
    # devre kesici konuşmalı.
    return {
        "n": len(rows), "deger": dus_oran * 100.0,
        "detay": ayrinti,
        "gecti": (dus_oran < 0.25) and (len(bozuk) == 0),
    }


def m_kapanis_tahmini(conn) -> dict:
    """KAPANIŞ ORANI ÖNGÖRÜLEBİLİR Mİ — belge §3.1'in sınavı.

    Belge diyor ki: ajanlar MAÇ SONUCUNU tahmin ediyor, bu yanlış
    hedeftir. Doğru hedef KAPANIŞ ORANI — maç sonucu ikili ve
    gürültülü, kapanış oranı sürekli ve her maçta zengin sinyal verir.
    "Kapanış oranını açılıştan daha iyi tahmin edebilen model, tanım
    gereği fiyat üstünlüğüne sahiptir."

    Bu bulgu o iddiayı YENİ AJAN KURMADAN sınar — yeni ajan aylık iş,
    önce yönün mümkün olup olmadığı ölçülmeli.

    ⚠️ Öngörülebilirlik KÂR DEĞİLDİR. Kapanışı bilmek, açılış fiyatını
    yakalayabilmek ve marjı aşmak ayrı işlerdir. Bu bulgu CLV'nin
    öngörülebilir olduğunu söyler — belgeye göre CLV edge'in gerçek
    ölçütüdür, ama tek başına marjı yenmez.
    """
    import kapanis_tahmini as KT
    r = KT.olc(conn)
    if r.get("yetersiz"):
        return {"n": r.get("n", 0), "yetersiz": True}
    # ⚠️ KURAL: ÖRNEK-DIŞI yön isabeti > %55 VE hata iyileşmesi > %3.
    # İkisi birlikte şart: yön doğru ama iyileşme yoksa büyüklük
    # yanlıştır; iyileşme var ama yön şanssa model gürültüyü
    # düzleştiriyordur, bilgi taşımıyordur.
    gecti = (r["yon"] > 0.55) and (r["iyilesme"] > 0.03)
    return {
        "n": r["n"], "deger": r["deger"],
        "detay": (f"sınav dilimi n={r['sinav']:,} · yön isabeti "
                  f"{r['yon']*100:.1f}% (şans %50) · MAE "
                  f"{r['taban_mae']*100:.2f}% → {r['model_mae']*100:.2f}% "
                  f"(iyileşme {r['iyilesme']*100:+.1f}%)"),
        "gecti": gecti,
    }


def m_sidak_kapisi(conn) -> dict:
    """SEÇİM YANLILIĞI — kaç ajan Šidák eşiğini geçiyor?

    Kaynak: TAHMİN SİSTEMİ v3 §1.4 ve §3.4.

    Sorun şu: m ajan test edip en iyisini seçmek, seçilenin
    performansını yukarı saptırır. Bu örneklem gürültüsünden AYRI ve
    ondan daha sinsi bir problemdir — hiçbir ajanın gerçek edge'i
    olmasa bile, yeterince ajan denenirse birkaçı TESADÜFEN mükemmel
    görünür. Sistem bu cezayı hiç ödemiyordu: bir ajan "İYİ" hükmü
    alırken kaç ajan arasından seçildiği hesaba girmiyordu.

    Düzeltme iki katmanlı:
      1. α_ajan = 1 − (1 − α_aile)^(1/m)          (Šidák)
      2. m yerine ETKİN ajan sayısı: m/(1+(m−1)ρ)  (§3.4)
         Korelasyonlu ajanlar tek ajan gibi davranır; nominal sayı
         kullanmak cezayı olduğundan AĞIR yapar.

    Eşik her ajanın KENDİ fiyatına göre: p₀ = ortalama(1/oran).
    Soru "isabet yüksek mi" değil, "fiyatın beklediğinden anlamlı
    yüksek mi" — tek yönlü tam binom testi.
    """
    import kanit as K

    rows = conn.execute(
        "SELECT pb.portfolio_id p, pb.odds o, pb.status st, "
        "m.matchday d, m.home_team h, m.away_team a, pb.market mk, pb.pick pk "
        "FROM paper_bets pb JOIN matches_v2 m ON m.match_id = pb.match_id "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pb.portfolio_id "
        "WHERE pb.status IN ('won','lost') AND pb.odds > 1.01 "
        "AND (pp.era_start IS NULL OR pb.kickoff_utc >= pp.era_start)"
    ).fetchall()
    if not rows:
        return {"n": 0, "yetersiz": True}

    # emekli ajanlar sayılmaz: bugünün kararını etkilemiyorlar
    try:
        from agents import PROFILES
        aktif = {k for k, v in PROFILES.items() if not v.get("retired")}
    except Exception:
        aktif = set()

    by: dict = {}
    sec: dict = {}
    for x in rows:
        r = dict(x)
        p = r["p"]
        if aktif and p not in aktif:
            continue
        by.setdefault(p, []).append(r)
        sec.setdefault(p, set()).add(
            (r["d"], r["h"], r["a"], r["mk"], r["pk"]))
    if not by:
        return {"n": 0, "yetersiz": True}

    # ── ρ: tüm ajan çiftlerinin ortalama örtüşmesi ──
    ajanlar = sorted(by)
    oranlar = []
    for i, x in enumerate(ajanlar):
        for y in ajanlar[i + 1:]:
            A, B = sec[x], sec[y]
            kucuk = min(len(A), len(B))
            if kucuk < 8:
                continue
            oranlar.append(len(A & B) / kucuk)
    ro = (sum(oranlar) / len(oranlar)) if oranlar else 0.0

    m = len(ajanlar)
    m_etkin = K.etkin_ajan(m, ro)
    alpha = K.sidak_alpha(max(round(m_etkin), 1))

    gecen, olculen = 0, 0
    for p, v in by.items():
        n = len(v)
        if n < 10:                       # 10 altında eşik anlamsız
            continue
        olculen += 1
        won = sum(1 for z in v if z["st"] == "won")
        p0 = sum(1.0 / float(z["o"]) for z in v) / n
        g = K.gereken_isabet(n, p0, alpha)
        if g and g[1] <= 1.0 and (won / n) >= g[1]:
            gecen += 1

    return {
        "n": len(rows), "deger": float(gecen),
        "detay": (f"{m} ajan · ortalama örtüşme ρ={ro*100:.0f}% → "
                  f"ETKİN {m_etkin:.1f} ajan · ajan güveni "
                  f"{(1-alpha)*100:.2f}% · ölçülen {olculen} ajandan "
                  f"{gecen}'i eşiği geçiyor"),
        # ⚠️ KURAL: en az BİR ajan Šidák eşiğini geçmeli. Geçmiyorsa
        # "hangi ajan iyi" sorusunun cevabı yok — seçim yanlılığı
        # düzeltildikten sonra hiçbiri kanıtlanmış değil.
        "gecti": gecen >= 1,
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


def m_clv(conn) -> dict:
    """CLV — kapanış çizgisini yenebiliyor muyuz?

    Bahiste beceriye dair en güçlü TEK gösterge budur: girdiğin fiyat,
    kapanış fiyatından iyiyse piyasadan önce doğru tarafı görmüşsün
    demektir. Sonuçtan bağımsızdır — kaybettiğin bahiste bile pozitif
    CLV, seçimin doğru olduğunu söyler.

    ⚠️ CLV tek başına marjı YENMEZ. iddaa'nın %17,6'lık marjını aşmak
    için +%17,6 CLV gerekir; öyle bir şey yok. CLV'nin işi kâr vaadi
    değil, ÖNCÜ GÖSTERGE: pozitifse sinyalde bilgi var demektir."""
    rows = conn.execute(
        "SELECT clv FROM paper_bets WHERE clv IS NOT NULL").fetchall()
    v = []
    for r in rows:
        try:
            v.append(float(dict(r)["clv"]))
        except Exception:
            continue
    if len(v) < 200:
        return {"n": len(v), "yetersiz": True}
    n = len(v)
    m = sum(v) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1)) / math.sqrt(n)
    t = (m / sd) if sd > 1e-12 else 0.0
    beat = sum(1 for x in v if x > 0) / n
    sifir = sum(1 for x in v if abs(x) < 1e-9) / n
    return {
        "n": n, "deger": m * 100,
        "detay": (f"ortalama {m*100:+.2f}% (t={t:+.2f}) · "
                  f"kapanışı geçen %{beat*100:.1f} · "
                  f"hiç oynamayan %{sifir*100:.1f}"),
        "gecti": t > 1.96,      # kural: sıfırdan ANLAMLI şekilde büyük
    }


def m_mimar_fiyat_gecmisi(conn) -> dict:
    """MİMAR — iddaa'nın KENDİ fiyat geçmişinde erken oynamak kapanıştan
    iyi fiyat getiriyor mu? Ön kayıtlı karar (price_history.py).

    Kuralın METNİ fiyat kaydı başlarken yazıldı (price_history.py):
      1. Fiyatlar hareket ediyor mu?  → maçların ≥%30'unda ≥0.05
      2. Yön tahmin edilebiliyor mu?  → bir özellik tabandan ≥8 puan
                                        sapmalı VE eğitim+sınavda tutmalı
      3. Erken oynamanın CLV kazancı  → ≥+3 puan
      4. (3) < +3 puan ise MİMAR KONSEPTİ REDDEDİLİR.

    OPERASYONEL TANIM — 13.09.2026'da, SAYILARA BAKILMADAN yazıldı.
    Metin bazı ayrıntıları açık bırakıyordu; hepsi burada, sonuçtan önce
    sabitlendi ki sonuç görülünce esnetilemesin:
      · Birim: başlama saati GEÇMİŞ maç; yalnız maç öncesi kayıtlar
        (lead_h > 0). Açılış = ilk kayıt, kapanış = son kayıt (kayıt
        yalnız fiyat DEĞİŞİNCE yazılır → son kayıt başlama anının fiyatı).
      · Gözlenebilirlik: ilk kayıt başlamadan ≥6 saat önce (3 saatlik
        çekimle en az iki fırsat). Geç görülen maçın "hareketsiz"
        görünmesi yokluktur, bilgi değil — o maç sayılmaz.
      · Yeterlilik: ≥300 uygun maç (price_history.test_stage_b eşiği).
        Altında karar VERİLMEZ: ertelenir, reddedilmez.
      · (1) hareket: maçın 7 fiyatından herhangi birinde |kapanış−açılış|.
      · (2) yön: seçim başına "kısaldı" = kapanış < açılış − 0,005. Maçlar
        başlama saatine göre sıralanır: ilk %70 eğitim, son %30 sınav.
        Açılış ANINDA bilinen dört özellik dilimlenir: pazar, oran düzeyi,
        açılışın öne süresi, lig kodlu mu. Dilim eğitimde ve sınavda AYNI
        YÖNDE ≥8 puan sapmalı; her iki tarafta n ≥ 30 (ürünün tek eşiği).
      · (3) CLV: strateji YALNIZ eğitimde seçilir — eğitimde kısalmaya
        ≥8 puan yatkın dilimler. Kazanç SINAVDA ölçülür: o dilimlerdeki
        seçimlerin ortalama (açılış/kapanış − 1). Eğitimde böyle dilim
        yoksa strateji yoktur; ölçülen, sınavdaki tüm seçimleri erken
        oynamanın kazancıdır.
      · Hüküm yalnız (3)'e bağlı (kural 4); (1) ve (2) gerekçe olarak
        raporlanır.

    ⚠️ Metindeki "tablo silinir" adımı OTOMATİK DEĞİL. Silmek geri
    alınamaz; ölçüm RED derse bu fonksiyon yalnız SÖYLER, silmez.
    """
    from datetime import datetime
    alanlar = ("o1", "ox", "o2", "over25", "under25", "btts_yes", "btts_no")
    try:
        rows = conn.execute(
            "SELECT iddaa_event_id ev, ts, kickoff_utc ko, league_code lg, "
            "lead_h lh, o1, ox, o2, over25, under25, btts_yes, btts_no "
            "FROM odds_history WHERE lead_h > 0 "
            "ORDER BY iddaa_event_id, ts").fetchall()
    except Exception:
        conn.rollback()                 # tablo yoksa: henüz birikim yok
        return {"n": 0, "yetersiz": True}

    simdi = datetime.utcnow().isoformat()
    olay: dict = {}
    for x in rows:
        d = dict(x)
        ko = str(d.get("ko") or "").replace(" ", "T")[:19]
        if not ko or ko >= simdi:       # başlamamış maçın kapanışı yok
            continue
        d["ko"] = ko
        olay.setdefault(str(d["ev"]), []).append(d)

    maclar = []
    for ev, L in olay.items():
        try:
            if float(L[0]["lh"] or 0) < 6.0:
                continue
        except (TypeError, ValueError):
            continue
        maclar.append((L[0]["ko"], ev, L[0], L[-1]))
    n = len(maclar)
    if n < 300:
        return {"n": n, "yetersiz": True}
    maclar.sort(key=lambda z: (z[0], z[1]))

    def _f(v):
        try:
            v = float(v)
            return v if v > 1.0 else None
        except (TypeError, ValueError):
            return None

    # (1) HAREKET
    hareketli = 0
    secimler = []           # (sıra, alan, açılış, kapanış, öne_sa, kodlu)
    for i, (_ko, _ev, ilk, son) in enumerate(maclar):
        en_buyuk = 0.0
        kodlu = str(ilk.get("lg") or "") not in ("", "ALL", "None")
        for a in alanlar:
            o, c = _f(ilk.get(a)), _f(son.get(a))
            if o is None or c is None:
                continue
            en_buyuk = max(en_buyuk, abs(c - o))
            secimler.append((i, a, o, c, float(ilk["lh"]), kodlu))
        if en_buyuk >= 0.05:
            hareketli += 1
    pay = hareketli / n
    k1 = pay >= 0.30

    # (2) YÖN — zamana göre ilk %70 eğitim, son %30 sınav
    kesim = int(n * 0.7)
    egit = [s for s in secimler if s[0] < kesim]
    sinav = [s for s in secimler if s[0] >= kesim]
    if not egit or not sinav:
        return {"n": n, "yetersiz": True}

    def _kisa(s) -> bool:
        return s[3] < s[2] - 0.005

    def _dilimler(s):
        _i, a, o, _c, lh, kodlu = s
        duzey = ("<1,6" if o < 1.6 else "1,6–2,2" if o < 2.2
                 else "2,2–3,5" if o < 3.5 else "≥3,5")
        sure = "<24sa" if lh < 24 else ("24–72sa" if lh < 72 else "≥72sa")
        return (("pazar", a), ("oran", duzey), ("öne", sure),
                ("lig", "kodlu" if kodlu else "kodsuz"))

    taban_e = sum(1 for s in egit if _kisa(s)) / len(egit)
    taban_s = sum(1 for s in sinav if _kisa(s)) / len(sinav)
    say: dict = {}
    for grup, kume in (("e", egit), ("s", sinav)):
        for s in kume:
            for dl in _dilimler(s):
                t = say.setdefault(dl, {"e": [0, 0], "s": [0, 0]})
                t[grup][0] += 1
                t[grup][1] += 1 if _kisa(s) else 0
    tutan, en_iyi = [], None
    for dl, t in say.items():
        ne, ke = t["e"]
        ns, ks = t["s"]
        if ne < 30 or ns < 30:
            continue
        se, ss = ke / ne - taban_e, ks / ns - taban_s
        guc = min(abs(se), abs(ss)) if se * ss > 0 else 0.0
        if en_iyi is None or guc > en_iyi[0]:
            en_iyi = (guc, dl, se, ss)
        if se * ss > 0 and abs(se) >= 0.08 and abs(ss) >= 0.08:
            tutan.append(dl)
    k2 = bool(tutan)

    # (3) ERKEN OYNAMA CLV — strateji eğitimde seçilir, sınavda ölçülür
    secili = {dl for dl, t in say.items()
              if t["e"][0] >= 30 and (t["e"][1] / t["e"][0] - taban_e) >= 0.08}
    if secili:
        oyna = [s for s in sinav if any(dl in secili for dl in _dilimler(s))]
        strateji = f"eğitimde kısalmaya yatkın {len(secili)} dilim"
    else:
        oyna = list(sinav)
        strateji = "yatkın dilim yok → sınavdaki tüm seçimler"
    clv = (sum(s[2] / s[3] - 1.0 for s in oyna) / len(oyna) * 100) if oyna else 0.0
    k3 = clv >= 3.0

    # BELİRSİZLİK — hükmü DEĞİŞTİRMEZ, ne kadar sağlam olduğunu söyler.
    # Karar planlanan ~2.400 maç yerine daha az maçla verilebilir; o zaman
    # soru "eşik güven aralığının içinde mi" olur. Aynı maçın seçimleri
    # birlikte kayar, bağımsız değildir: standart hata MAÇ kümelerine göre
    # (kümelenmiş, küçük örneklem düzeltmeli). Naif SE aralığı dar gösterirdi.
    _xb = clv / 100.0
    _eg: dict = {}
    for s in oyna:
        _eg[s[0]] = _eg.get(s[0], 0.0) + (s[2] / s[3] - 1.0 - _xb)
    n_mac = len(_eg)
    if n_mac >= 2:
        _se = math.sqrt(sum(e * e for e in _eg.values())
                        * n_mac / (n_mac - 1)) / len(oyna)
        ust = (_xb + 1.96 * _se) * 100
    else:
        ust = float("nan")

    _en = (f"{en_iyi[1][0]}={en_iyi[1][1]} eğitim {en_iyi[2]*100:+.1f}p / "
           f"sınav {en_iyi[3]*100:+.1f}p" if en_iyi else "ölçülebilir dilim yok")
    return {
        "n": n, "deger": clv, "ust": ust, "n_mac": n_mac,
        "detay": (f"{n} maç · (1) hareket≥0,05 %{pay*100:.0f} "
                  f"{'✓' if k1 else '✗'} · (2) en güçlü dilim {_en} "
                  f"{'✓' if k2 else '✗'} · (3) erken oynama CLV {clv:+.2f}p "
                  f"({strateji}; sınav {len(oyna)} seçim / {n_mac} maç; %95 "
                  f"üst sınır {ust:+.2f}p) {'✓' if k3 else '✗'} · " +
                  ("KONSEPT AYAKTA" if k3 else "KURAL 4: MİMAR REDDEDİLDİ")),
        "gecti": k3,
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
    "IZLEME_KAPISI": {
        "baslik": "Devre kesiciler — sistem düşüşü ve kayan pencere CLV",
        "kural": "sistem düşüşü tepeden < %25 VE hiçbir ajanın son 100 "
                 "bahiste CLV'si negatif değil",
        "hedef": "her koşuda · belge §3.7 otomatik durdurma tetikleyicileri",
        "onceki": "ilk ölçüm (12.09.2026) · kaynak: TAHMİN SİSTEMİ v3 §3.7",
        "fn": m_izleme_kapisi, "agir": False,
    },
    "KAPANIS_TAHMINI": {
        "baslik": "Kapanış oranı açılıştan öngörülebilir mi (fiyat üstünlüğü)",
        "kural": "örnek-dışı yön isabeti > %55 VE hata iyileşmesi > %3 · "
                 "ikisi birlikte şart",
        "hedef": "her koşuda · iddaa fiyat geçmişi biriktikçe güçlenir",
        "onceki": "ilk ölçüm (12.09.2026) · kaynak: TAHMİN SİSTEMİ v3 §3.1",
        "fn": m_kapanis_tahmini, "agir": True,
    },
    "MIMAR_FIYAT_GECMISI": {
        "baslik": "MİMAR — iddaa'da erken oynamak kapanıştan iyi fiyat getiriyor mu",
        "kural": "sınavda erken oynama CLV ≥ +3 puan · altındaysa MİMAR "
                 "REDDEDİLİR (price_history.py ön kaydı, kural 4)",
        "hedef": "tek seferlik karar · ≥300 uygun maç",
        "onceki": "karar koşusu 13.09.2026 · 649 maç · tanım sayılara "
                  "bakılmadan sabitlendi",
        # Ön kayıt TEK SEFERLİK bir karardı — worker bunu artık koşmaz,
        # arayüz satırı "karar kesin" diye işaretler. Gerekçe ve bilinçli
        # sapma (tablo silinmedi): price_history.py başındaki KARAR bloğu.
        "kapandi": ("13.09.2026 · RED — erken oynama CLV −0,20p (eşik +3; "
                    "%95 üst sınır +0,10p) · yeniden sınanmaz · tablo "
                    "bilinçli sapmayla saklanıyor"),
        "fn": m_mimar_fiyat_gecmisi, "agir": False,
    },
    "SIDAK_KAPISI": {
        "baslik": "Seçim yanlılığı düzeltildikten sonra kaç ajan ayakta",
        "kural": "en az BİR ajan Šidák eşiğini geçmeli · geçmezse "
                 "'hangi ajan iyi' sorusunun cevabı YOK",
        "hedef": "ajan başına n ≥ 200 (belge §2.7)",
        "onceki": "ilk ölçüm (12.09.2026) · kaynak: TAHMİN SİSTEMİ v3 §1.4",
        "fn": m_sidak_kapisi, "agir": False,
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
    "CLV": {
        "baslik": "Kapanış çizgisini yenebiliyor muyuz",
        "kural": "ortalama CLV sıfırdan ANLAMLI büyük (t > 1,96) olmalı",
        "hedef": "her koşuda · bahis biriktikçe güçlenir",
        "onceki": "ilk ölçüm (31.08.2026)",
        "fn": m_clv, "agir": False,
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
        # 🔒 KARAR KESİN — ön kaydı TEK SEFERLİK bir karar olan bulgu (MİMAR
        # gibi) her gün yeniden ölçülmez. Reddedilmiş bir konsepti günlük
        # sınamak "geçene kadar dene" demektir: eşik çevresindeki şans
        # dalgalanması bir gün hükmü çevirir. Karar koşusu arşivde durur.
        if f.get("kapandi"):
            print(f"\n▸ {fid} — 🔒 karar kesin: {f['kapandi']}")
            skip += 1
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
