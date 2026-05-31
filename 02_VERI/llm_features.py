"""
SPRINT 2.3 — LLM Augmentation (Gemini + multi-LLM destekli)

VIZYON (kullanıcı sözünden):
    "AI yoluyla bulmak ve kazandırmak diğerlerinin göremediği bir yol ile."

NE YAPAR:
    Yapılandırılmamış metin (haber, yorum, sosyal medya) → yapılandırılmış feature.

KAYNAKLAR:
    - iddaa.com Yazar Yorumları (Türkçe)
    - Twitter/X (opsiyonel, key gerek)
    - Lokal haber RSS (Türkçe)
    - Transfermarkt headlines

LLM:
    - BIRINCIL: Google Gemini 1.5 Flash (free 15 RPM, 1500 RPD)
    - SECONDARY: HuggingFace local model (gerekirse)
    - FALLBACK: mock mode (key yoksa)

ÇIKTI (LightGBM feature olarak):
    motivation_score [0-1]
    key_player_doubt [0-1]
    tactical_change [0-1]
    sentiment_home [-1, +1]
    sentiment_away [-1, +1]
    injury_severity [0-1]
    narrative_strength [0-1]

KOTA YÖNETİMİ:
    Sadece edge>%1 olan maçlarda LLM çağrı (ön-filtre DC).
    Her LLM çağrısı diske cache.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

THIS_DIR = Path(__file__).resolve().parent
YAZILIM_DIR = THIS_DIR.parent
CACHE_DIR = THIS_DIR / "_cache_llm"
CACHE_DIR.mkdir(exist_ok=True, parents=True)


# ============================================================
# ENV / API KEY
# ============================================================

def _load_env() -> dict[str, str]:
    env_path = YAZILIM_DIR / ".env"
    out = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    # Env vars override
    for k in ["GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]:
        if k in os.environ:
            out[k] = os.environ[k]
    return out


ENV = _load_env()
GEMINI_KEY = ENV.get("GEMINI_API_KEY", "")
LLM_MODE = "live" if GEMINI_KEY else "mock"


# ============================================================
# FEATURE ŞEMASI
# ============================================================

EMPTY_FEATURES = {
    "motivation_score": 0.5,        # 0=düşük motivasyon, 1=yüksek (cup final)
    "key_player_doubt": 0.0,        # 0=tam kadro, 1=büyük kayıp
    "tactical_change": 0.0,         # 0=istikrar, 1=büyük değişim (yeni hoca)
    "sentiment_home": 0.0,          # -1=kötü mood, +1=iyi
    "sentiment_away": 0.0,
    "injury_severity": 0.0,         # 0=temiz, 1=ağır sakatlık
    "narrative_strength": 0.5,      # 0=zayıf hikaye, 1=uzun seri
    "_source": "default_empty",
}


PROMPT_TEMPLATE = """Sen bir spor analisti AI'sın. Aşağıdaki maç hakkındaki haberleri / yorumları oku
ve maçı etkileyebilecek faktörleri SAYISAL skorlar olarak çıkar.

MAÇ: {home} (ev) vs {away} (deplasman)
TARİH: {match_date}
LİG: {league}

İLGİLİ METİNLER:
{texts}

JSON çıktısı ver (sadece JSON, başka açıklama yok):
{{
  "motivation_score": <0-1 arasında bir sayı, 0=düşük motivasyon, 1=cup finali gibi yüksek>,
  "key_player_doubt": <0-1, kilit oyuncu sakatlığı/cezası riski>,
  "tactical_change": <0-1, yeni hoca / taktik değişimi riski>,
  "sentiment_home": <-1 ile +1 arası, ev sahibi taraf moral>,
  "sentiment_away": <-1 ile +1 arası, deplasman moral>,
  "injury_severity": <0-1, takım için sakatlık etkisi>,
  "narrative_strength": <0-1, takımın son dönemdeki hikaye gücü>
}}

Açıklama yapma, sadece JSON döndür."""


# ============================================================
# CACHE
# ============================================================

def _cache_key(home: str, away: str, match_date: str, texts_hash: str) -> str:
    payload = f"{home}|{away}|{match_date}|{texts_hash}"
    return hashlib.sha1(payload.encode()).hexdigest()


def _cache_get(key: str) -> dict | None:
    p = CACHE_DIR / f"{key}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _cache_set(key: str, features: dict) -> None:
    p = CACHE_DIR / f"{key}.json"
    p.write_text(json.dumps({
        **features,
        "_cached_at": datetime.now().isoformat(),
    }, ensure_ascii=False), encoding="utf-8")


# ============================================================
# LLM ÇAĞRISI
# ============================================================

class LLMError(Exception):
    pass


def call_gemini(prompt: str, temperature: float = 0.1) -> str:
    """Gemini API'ye prompt gönder, response döndür."""
    if not GEMINI_KEY:
        raise LLMError("GEMINI_API_KEY .env dosyasında yok")

    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "temperature": temperature,
                "response_mime_type": "application/json",
            }
        )
        return response.text or ""
    except Exception as e:
        # Fallback: eski SDK
        try:
            import google.generativeai as old_genai
            old_genai.configure(api_key=GEMINI_KEY)
            model = old_genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": temperature,
                    "response_mime_type": "application/json",
                }
            )
            return response.text
        except Exception as e2:
            raise LLMError(f"Gemini fail: {e} | fallback: {e2}") from e2


def extract_features_via_llm(
    home: str, away: str, match_date: str,
    texts: list[str] | None = None,
    league: str = "futbol",
) -> dict:
    """
    LLM çağırarak maç feature'larını çıkar.

    Args:
        home, away   : takım adları
        match_date   : "YYYY-MM-DD"
        texts        : ilgili haber/yorum metinleri (Türkçe veya İng)
        league       : lig adı

    Returns:
        Feature dict (EMPTY_FEATURES şeması).
    """
    if texts is None:
        texts = []

    texts_combined = "\n".join(f"- {t}" for t in texts[:10]) or "[Metin sağlanmadı]"
    texts_hash = hashlib.sha1(texts_combined.encode()).hexdigest()[:12]
    ck = _cache_key(home, away, match_date, texts_hash)

    # Cache hit
    cached = _cache_get(ck)
    if cached:
        return cached

    # Mock mode (key yok)
    if LLM_MODE == "mock":
        features = _mock_features(home, away, match_date)
        _cache_set(ck, features)
        return features

    # Live Gemini
    prompt = PROMPT_TEMPLATE.format(
        home=home, away=away, match_date=match_date,
        league=league, texts=texts_combined,
    )

    try:
        raw = call_gemini(prompt)
        # Parse JSON
        try:
            data = json.loads(raw)
        except Exception:
            # JSON'u içeren parçayı çek
            import re
            m = re.search(r"\{[^}]+\}", raw, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
            else:
                raise LLMError(f"JSON parse fail: {raw[:200]}")

        features = {**EMPTY_FEATURES, **data, "_source": "gemini-2.5-flash"}
        # Numerik clamp
        for k, (lo, hi) in [
            ("motivation_score", (0, 1)), ("key_player_doubt", (0, 1)),
            ("tactical_change", (0, 1)), ("injury_severity", (0, 1)),
            ("narrative_strength", (0, 1)),
            ("sentiment_home", (-1, 1)), ("sentiment_away", (-1, 1)),
        ]:
            v = float(features.get(k, EMPTY_FEATURES[k]))
            features[k] = max(lo, min(hi, v))
        _cache_set(ck, features)
        return features

    except LLMError as e:
        print(f"  LLM hata: {e} → mock'a düş")
        features = _mock_features(home, away, match_date)
        features["_source"] = "mock_after_error"
        _cache_set(ck, features)
        return features


# ============================================================
# MOCK MODE (key yokken deterministik fake feature)
# ============================================================

def _mock_features(home: str, away: str, match_date: str) -> dict:
    """
    Deterministik mock: takım+tarih hash'ine göre 'yapay' sayılar.
    Live LLM gelene kadar UI/pipeline test için.
    """
    h = hashlib.md5(f"{home}{away}{match_date}".encode()).digest()
    # 0-255 byte'larından normalize
    def to_01(b): return b / 255.0
    def to_signed(b): return (b / 127.5) - 1.0

    return {
        "motivation_score": to_01(h[0]) * 0.6 + 0.3,  # 0.3-0.9 arası
        "key_player_doubt": to_01(h[1]) * 0.5,         # 0-0.5
        "tactical_change":  to_01(h[2]) * 0.3,         # 0-0.3
        "sentiment_home":   to_signed(h[3]) * 0.5,     # -0.5 to +0.5
        "sentiment_away":   to_signed(h[4]) * 0.5,
        "injury_severity":  to_01(h[5]) * 0.4,
        "narrative_strength": to_01(h[6]),
        "_source": "mock",
    }


# ============================================================
# CLI DEMO
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print(f"SPRINT 2.3 — LLM Augmentation Demo")
    print(f"Mode: {LLM_MODE} (Gemini key {'BULUNDU' if GEMINI_KEY else 'YOK — mock kullanılır'})")
    print("=" * 60)

    # Test maç
    home, away = "Galatasaray", "Fenerbahce"
    mdate = "2026-05-30"
    sample_texts = [
        "Galatasaray Fenerbahce derbisinde son hazırlıklara devam ediyor.",
        "Lider Galatasaray'ın yıldız oyuncusu sakatlık şüphesi nedeniyle riskli.",
        "Fenerbahce'de teknik direktör değişikliğinin etkisi tartışılıyor.",
        "Derbi öncesi taraftarlardan büyük destek.",
    ]

    print(f"\nMaç: {home} vs {away}  ({mdate})")
    print(f"Metinler: {len(sample_texts)} satır")

    features = extract_features_via_llm(
        home, away, mdate, sample_texts, league="Türkiye Süper Lig"
    )

    print(f"\nFeatures (kaynak: {features.get('_source')}):")
    for k, v in features.items():
        if k.startswith("_"):
            continue
        if isinstance(v, (int, float)):
            print(f"  {k:24s} = {v:+.3f}")
        else:
            print(f"  {k:24s} = {v}")

    print(f"\nCache: {CACHE_DIR}")
