"""
🔴 KIRMIZI TAKIM MOTORU — kombo korelasyon değeri
==================================================
TEK MOTOR, ÜÇ PAZAR. Her Kırmızı ajan aynı matematiği farklı bir kombo
pazarında uygular:
    🎰 ÇARPAN  → 1X2_OU    ("1 ve Üst")
    🔺 SİMETRİ → OU_BTTS   ("Alt ve Yok")   ⭐ en güçlü korelasyon
    ✖️ KAVŞAK  → 1X2_BTTS  ("0 ve Var")

MANTIK: adil oran = (bileşen oranlarının çarpımı) ÷ korelasyon katsayısı.
Katsayı maç profiline koşulludur (combo_tables.py). iddaa'nın verdiği
kombine oranı adil oranı MIN_EDGE kadar aşıyorsa değer vardır.

İZOLASYON: aday kaynağı YALNIZ `market_odds` tablosudur. matches_v2'ye
dokunmaz, sinyal motorunu çağırmaz. MAVİ TAKIM bu hesaptan hiçbir şey
okumaz; Kırmızı ajanlar KONSEY oylamasında yoktur.

    python multiplier_agent.py            # tüm pazarlar
    python multiplier_agent.py OU_BTTS    # tek pazar
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
from combo_tables import (MARKETS, band, strength_factor, EDGE_MULT,
                          STRENGTH_APPLIES)
import score_sets as ss

MIN_EDGE = 0.08
MIN_ODDS = 2.50
MAX_ODDS = 40.0
# 🛑 AKIL SAĞLIĞI TAVANI: "çok iyi görünen edge, edge değil HATADIR."
# %60 üstü bir açık, iddaa'nın para dağıttığı anlamına gelmez — bizim
# modelimizin o hücrede yanlış olduğu anlamına gelir. Reddedilir.
MAX_EDGE = 0.60


def _now() -> str:
    return datetime.utcnow().isoformat()


def _load_latest() -> tuple[dict, dict]:
    """market_odds'tan her (maç, pazar, seçim) için EN SON fiyat."""
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT iddaa_event_id, league_code, kickoff_utc, home_team, away_team, "
            "market, selection, odd, lead_h FROM market_odds "
            "WHERE kickoff_utc > ? ORDER BY ts", (_now(),)).fetchall()
    except Exception:
        conn.rollback()
        conn.close()
        return {}, {}
    conn.close()
    latest, meta = {}, {}
    for r in rows:
        ev = str(r[0])
        latest[(ev, r[5], r[6])] = float(r[7] or 0)
        meta[ev] = {"lg": r[1], "ko": r[2], "home": r[3], "away": r[4], "lead": r[8]}
    return latest, meta


def _norm_probs(latest: dict, ev: str, market: str) -> dict | None:
    """Bir pazarın marjsızlaştırılmış olasılıkları."""
    if market == "1X2":
        o1 = latest.get((ev, "1X2", "1"))
        ox = latest.get((ev, "1X2", "0")) or latest.get((ev, "1X2", "X"))
        o2 = latest.get((ev, "1X2", "2"))
        if not all((o1, ox, o2)):
            return None
        s = 1/o1 + 1/ox + 1/o2
        return {"1": (1/o1)/s, "0": (1/ox)/s, "2": (1/o2)/s,
                "_odds": {"1": o1, "0": ox, "2": o2}}
    if market == "OU2.5":
        ou = latest.get((ev, "OU2.5", "Üst"))
        al = latest.get((ev, "OU2.5", "Alt"))
        if not all((ou, al)):
            return None
        s = 1/ou + 1/al
        return {"U": (1/ou)/s, "A": (1/al)/s, "_odds": {"U": ou, "A": al}}
    if market == "BTTS":
        v = latest.get((ev, "BTTS", "Var"))
        y = latest.get((ev, "BTTS", "Yok"))
        if not all((v, y)):
            return None
        s = 1/v + 1/y
        return {"V": (1/v)/s, "Y": (1/y)/s, "_odds": {"V": v, "Y": y}}
    return None


def _enrichment() -> dict:
    """⭐ ARTIK-BİLGİ: h2h/form özellikleri. Piyasa fiyatı sabit tutulduğunda
    bunlar EKSTRA bilgi taşıyor (18.059 maçta ölçüldü):
      · h2h beraberlik oranı yüksek → gerçek X, piyasadan +2.0 puan fazla
      · h2h gol ortalaması orta     → gerçek ÜST, piyasadan +2.8 puan fazla
      · h2h KG oranı düşük          → gerçek ÜST, piyasadan +2.9 puan fazla
    Tek başına marjı kapatmıyor (−%7/−%9) ama kombo korelasyonuyla
    ÇARPILINCA anlamlı. Bu yüzden kapı olarak kullanılır, bahis olarak değil.
    (Yalnız OKUMA — MAVİ TAKIM'ın hiçbir hesabına dokunmaz.)"""
    conn = db.connect()
    out = {}
    try:
        for r in conn.execute(
                "SELECT external_id_iddaa, h2h_n, h2h_draws, h2h_avg_goals, "
                "h2h_btts_rate, home_clean_sheet_5g, away_clean_sheet_5g "
                "FROM matches_v2 WHERE is_settled=0 "
                "AND external_id_iddaa IS NOT NULL").fetchall():
            out[str(r[0])] = {
                "h2h_n": r[1] or 0, "h2h_draws": r[2] or 0,
                "h2h_goals": r[3], "h2h_btts": r[4],
                "cs": (r[5] or 0) + (r[6] or 0),
            }
    except Exception:
        conn.rollback()
    finally:
        conn.close()
    return out


def _residual_ok(pick: str, e: dict | None) -> bool:
    """Aday, artık-bilgiyle AYNI yönü gösteriyor mu? Veri yoksa geçer."""
    if not e:
        return True
    d_rate = (e["h2h_draws"] / e["h2h_n"]) if e["h2h_n"] >= 4 else None
    g = e.get("h2h_goals")
    b = e.get("h2h_btts")
    p = pick or ""
    # beraberlik ayağı: h2h'de beraberlik geçmişi ortalamanın üstünde olmalı
    if p.startswith("0 "):
        if d_rate is not None and d_rate < 0.26:
            return False
    # ÜST / KG VAR ayağı: h2h gollü olmalı
    if "Üst" in p or "Var" in p:
        if g is not None and g < 2.30:
            return False
    # ALT / KG YOK ayağı: h2h az gollü olmalı
    if "Alt" in p or "Yok" in p:
        if g is not None and g > 3.10:
            return False
        if b is not None and b > 0.70:
            return False
    return True


def candidates(combo_market: str = "1X2_OU", min_edge: float = MIN_EDGE,
               min_odds: float = MIN_ODDS, max_odds: float = MAX_ODDS,
               residual_gate: bool = True) -> list[dict]:
    cfg = MARKETS.get(combo_market)
    if not cfg:
        return []
    latest, meta = _load_latest()
    if not latest:
        return []
    enr = _enrichment() if residual_gate else {}
    (mk_a, edges_a) = cfg["band_a"]
    (mk_b, edges_b) = cfg["band_b"]
    out: list[dict] = []
    for ev, m in meta.items():
        pa = _norm_probs(latest, ev, mk_a)
        pb = _norm_probs(latest, ev, mk_b)
        if not pa or not pb:
            continue
        # bant: a için ilk kod (1X2'de "1", OU'da "U"), b için ilk kod
        key_a = "0" if mk_a == "1X2" else "U"   # 1X2'de bant P(X)'ten
        key_b = "U" if mk_b == "OU2.5" else "V"
        ba = band(pa[key_a], edges_a)
        bb = band(pb[key_b], edges_b)
        for ca in cfg["a_sel"]:
            for cb in cfg["b_sel"]:
                c = cfg["table"].get((ba, bb, ca, cb))
                if not c:
                    continue
                sel = cfg["label"](ca, cb)
                combo = latest.get((ev, combo_market, sel))
                if not combo:
                    continue
                # ⚠️ DERS: korelasyon katsayısı MARJSIZ olasılıklardan
                # türetildi (gerçek sıklık ÷ marjinallerin çarpımı). Bu yüzden
                # adil oran da MARJSIZ olasılıklardan hesaplanmalı. Önce
                # marjlı oranları çarpmıştım — iki marj birden düşüyordu ve
                # edge'ler ~%30 şişik çıkıyordu.
                qa, qb = pa.get(ca), pb.get(cb)
                if not qa or not qb:
                    continue
                # 🎯 SKOR KÜMESİ YÖNTEMİ (birincil): kombine aslında bir skor
                # kümesi bahsidir. Kazandıran skorların ampirik kütlesi,
                # korelasyon çarpımından %34.9 daha isabetli kalibre
                # (50.916 örnek-dışı gözlem). Küme kurulamazsa korelasyona düş.
                # ⚠️ DERS: profil anahtarı P(ev sahibi) ve P(üst) ister —
                # bunlar kombinenin BİLEŞENLERİNDEN gelmeyebilir. Örneğin
                # OU_BTTS'in bileşenleri A/Ü ve KG'dir, 1X2 yoktur; 1X2_BTTS'te
                # de A/Ü yoktur. Önce bileşenlerden dene, yoksa maçın kendi
                # 1X2 / OU2.5 fiyatından çek. (Bunu yapmayınca KAVŞAK ve
                # SİMETRİ sessizce eski korelasyon yöntemine düşüyordu.)
                q1 = pa.get("1") if mk_a == "1X2" else None
                qU = pb.get("U") if mk_b == "OU2.5" else (
                    pa.get("U") if mk_a == "OU2.5" else None)
                if q1 is None:
                    _p = _norm_probs(latest, ev, "1X2")
                    q1 = _p.get("1") if _p else None
                if qU is None:
                    _p = _norm_probs(latest, ev, "OU2.5")
                    qU = _p.get("U") if _p else None
                # 🎯 SÜREKLİ MODEL için P(beraberlik) de lazım — λ çözümü
                # üç marjsız fiyattan yapılır (q1, qX, qÜst).
                qx = pa.get("0") if mk_a == "1X2" else None
                if qx is None:
                    _p = _norm_probs(latest, ev, "1X2")
                    qx = _p.get("0") if _p else None
                winner = None
                if combo_market == "1X2_OU":
                    winner = ss.combo_winner(ca, cb)
                elif combo_market == "1X2_BTTS":
                    winner = ss.combo_winner(ca, cb)
                elif combo_market == "OU_BTTS":
                    winner = ss.ou_btts_winner(ca, cb)
                p_set = n_sc = top_sh = 0
                fragile = False
                method = ""
                # ── ÖNCE SÜREKLİ (bantsız). Bantlı model %10 ile %32'lik
                # mazlumu aynı kovaya atıyordu ve argmax tam oraya
                # gidiyordu: ölçülen sahte edge +%132.8 → gerçekte −%15.9.
                if winner is not None and None not in (q1, qx, qU):
                    p_set, n_sc, top_sh, fragile = ss.score_set_prob_cont(
                        q1, qx, qU, winner)
                    if p_set > 0:
                        method = "skor kümesi (sürekli)"
                # ── bantlıya yalnızca λ çözülemezse düş
                if p_set <= 0 and winner is not None and None not in (q1, qU):
                    p_set, n_sc, top_sh, fragile = ss.score_set_prob(
                        q1, qU, winner)
                    if p_set > 0:
                        method = "skor kümesi (BANTLI — yedek)"
                        # bantlı modelde kırılganlık düzeltmesi ÖLÇÜLDÜ ve
                        # gerçek; sürekli modelde yok (kalibrasyon yutuyor).
                        p_set *= (ss.FRAGILE_FACTOR if fragile else 1.0)

                if p_set > 0:
                    p_joint = p_set
                    sf_label = (f"{n_sc} skor · tek-skor payı %{top_sh*100:.0f}"
                                + (" · KIRILGAN" if fragile else " · sağlam"))
                else:
                    method = "korelasyon"
                    if STRENGTH_APPLIES.get(combo_market, True):
                        sfx, sf_label = strength_factor(ca, qa, cb, qb)
                    else:
                        sfx, sf_label = 1.0, "güç etkisi yok (ölçüldü)"
                    p_joint = c * qa * qb * sfx
                if p_joint <= 0:
                    continue
                fair = 1.0 / p_joint
                oa = pa["_odds"].get(ca)
                ob = pb["_odds"].get(cb)
                naive = (oa * ob) if (oa and ob) else 0
                edge = combo / fair - 1
                # 🛡 risk-ayarlı eşik: zayıf bölgede daha fazla marj iste.
                # ⚠️ Kırılganlık cezası YALNIZCA bantlı/korelasyon yolunda.
                # Sürekli modelde ölçüldü: kalibrasyon sonrası kırılgan
                # kümelerde artık sapma yok (0.974-1.067), hatta en kırılgan
                # kova EKSİK tahmin ediliyor. Orada 1.5x uygulamak, ölçülmemiş
                # bir katsayıyı devralmak olurdu.
                _frag_mult = 1.5 if (fragile and "sürekli" not in method) else 1.0
                need = min_edge * _frag_mult * EDGE_MULT.get(sf_label, 1.0)
                if edge < need or edge > MAX_EDGE:
                    continue                      # 🛑 akıl sağlığı tavanı
                if not (min_odds <= combo <= max_odds):
                    continue
                if residual_gate and not _residual_ok(sel, enr.get(ev)):
                    continue
                out.append({
                    "event_id": ev, "league": m["lg"], "kickoff": m["ko"],
                    "home": m["home"], "away": m["away"],
                    "market": combo_market, "pick": sel, "odds": combo,
                    "fair": round(fair, 2), "naive": round(naive, 2),
                    "corr": c, "edge": round(edge * 100, 1), "lead": m["lead"],
                    "strength": p_joint, "strength_label": sf_label,
                    "method": method, "n_scores": n_sc, "top_share": top_sh,
                    "need_edge": round(need * 100, 1),
                })
    out.sort(key=lambda x: -x["edge"])
    return out


def report(market: str | None = None, min_edge: float = MIN_EDGE) -> None:
    mks = [market] if market else list(MARKETS)
    for mk in mks:
        cs = candidates(mk, min_edge)
        print(f"\n🔴 {mk} — aday (edge ≥ %{min_edge*100:.0f}): {len(cs)}")
        for c in cs[:10]:
            print(f"   {str(c['home'])[:15]:15s}-{str(c['away'])[:15]:15s} "
                  f"{c['pick']:11s} @{c['odds']:6.2f} adil {c['fair']:6.2f} "
                  f"(kor {c['corr']:.2f}) → %{c['edge']:+.1f}")




# ══════════════════════════════════════════════════════════════════════
# ⚽ MODEL-FİYATLI PAZARLAR (BANT · DEVRE) — korelasyon tablosu yerine
# maçın kendi fiyatından kalibre edilen Poisson gol modeli kullanılır.
# ══════════════════════════════════════════════════════════════════════

MODEL_MARKETS = {"TOTAL_GOALS", "HT_FT", "HT_1X2", "HT_OU0.5", "HT_OU1.5"}


def model_candidates(market: str = "TOTAL_GOALS", min_edge: float = 0.10,
                     min_odds: float = 2.00, max_odds: float = 40.0) -> list[dict]:
    """iddaa'nın bant/İY fiyatını, piyasadan kalibre edilmiş Poisson modelinin
    adil fiyatıyla karşılaştırır. Model varsayımı 24.612 maçta doğrulandı
    (toplam gol dağılımı Poisson'a uyuyor); İY payı (%45) ise DOĞRULANMAMIŞ
    varsayımdır — DEVRE bunu canlıda sınar."""
    try:
        import goal_model as gm
    except Exception as e:
        print(f"  (gol modeli yüklenemedi: {e})")
        return []
    latest, meta = _load_latest()
    if not latest:
        return []
    out = []
    for ev, m in meta.items():
        o1 = latest.get((ev, "1X2", "1"))
        ox = latest.get((ev, "1X2", "0")) or latest.get((ev, "1X2", "X"))
        o2 = latest.get((ev, "1X2", "2"))
        ou = latest.get((ev, "OU2.5", "Üst"))
        un = latest.get((ev, "OU2.5", "Alt"))
        if not all((o1, ox, o2, ou, un)):
            continue
        # bu maçta hedef pazarın fiyatı var mı?
        sels = {k[2]: v for k, v in latest.items()
                if k[0] == ev and k[1] == market}
        if not sels:
            continue
        try:
            pr = gm.price_all(o1, ox, o2, ou, un)
        except Exception:
            continue
        probs = pr.get(market) or {}
        for sel, odd in sels.items():
            p = probs.get(sel)
            if not p or p <= 0:
                continue
            fair = 1.0 / p
            edge = odd / fair - 1
            if edge < min_edge or edge > MAX_EDGE:
                continue
            if not (min_odds <= odd <= max_odds):
                continue
            out.append({
                "event_id": ev, "league": m["lg"], "kickoff": m["ko"],
                "home": m["home"], "away": m["away"], "market": market,
                "pick": sel, "odds": odd, "fair": round(fair, 2),
                "naive": 0, "corr": 1.0, "edge": round(edge * 100, 1),
                "lead": m["lead"],
            })
    out.sort(key=lambda x: -x["edge"])
    return out


if __name__ == "__main__":
    report(sys.argv[1] if len(sys.argv) > 1 else None)
