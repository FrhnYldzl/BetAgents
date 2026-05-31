"""
Football-Data.co.uk indirici (GitHub mirror üzerinden).

Tarihsel maç sonucu + bahis oranı CSV'lerini indirir.
Birincil kaynak: https://www.football-data.co.uk/
Türkiye'den DNS-bazlı engelli olduğu için aşağıdaki açık mirror'dan çekilir:
  https://github.com/huhao930422-debug/football-odds-mirror

Kullanım:
    python football_data_downloader.py

Çıktı:
    02_VERI/raw/<lig_kodu>_<sezon>.csv   (ham CSV dosyaları)
    02_VERI/processed/matches.parquet     (birleştirilmiş, normalize)
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests

# Windows console (cp1254/cp857) Türkçe karakter problemini çöz
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ============================================================
# YAPILANDIRMA
# ============================================================

# GitHub mirror — Football-Data.co.uk birebir CSV kopyaları
# {league_slug}: super-lig, premier-league, bundesliga vb.
# {season}: 2425, 2122 ... (Football-Data sezon formatı)
MIRROR_URL = (
    "https://raw.githubusercontent.com/huhao930422-debug/"
    "football-odds-mirror/main/data/{league_slug}/season-{season}.csv"
)

# Lig kodu -> (mirror slug, açıklama)
LEAGUES = {
    "T1": ("super-lig",       "Süper Lig (Türkiye)"),
    "E0": ("premier-league",  "Premier League (İngiltere)"),
    "D1": ("bundesliga",      "Bundesliga (Almanya)"),
}

# Football-Data sezon formatı: "2425" = 2024-25 sezonu
SEASONS = ["2122", "2223", "2324", "2425", "2526"]

# Proje kökü (bu dosya YAZILIM/02_VERI/scrapers/ altında)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # YAZILIM/
RAW_DIR = PROJECT_ROOT / "02_VERI" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "02_VERI" / "processed"

REQUEST_TIMEOUT = 30
RATE_LIMIT_SEC = 1.0  # Sunucuya nazik davran

# ============================================================
# VERİ İNDİRME
# ============================================================


@dataclass
class DownloadResult:
    league_code: str
    season: str
    path: Path | None
    rows: int
    status: str  # "ok", "skip", "error"
    message: str = ""


def download_csv(league_code: str, season: str) -> DownloadResult:
    """Tek bir lig-sezon kombinasyonunu indirir."""
    slug, _name = LEAGUES[league_code]
    url = MIRROR_URL.format(league_slug=slug, season=season)
    out_path = RAW_DIR / f"{league_code}_{season}.csv"

    if out_path.exists() and out_path.stat().st_size > 1000:
        # Yerel dosya varsa ve makul boyutta ise atla
        try:
            df = pd.read_csv(out_path, encoding="utf-8-sig")
            if len(df) > 50:  # Yarım sezon bile en az 50 maç içerir
                return DownloadResult(
                    league_code, season, out_path, len(df), "skip",
                    "Yerel dosya yeterli (yenilemek için sil)"
                )
        except Exception:
            pass

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 404:
            return DownloadResult(
                league_code, season, None, 0, "error",
                f"404: bu sezon için veri yok ({slug}/{season})"
            )
        resp.raise_for_status()

        if len(resp.content) < 500:
            return DownloadResult(
                league_code, season, None, 0, "error",
                f"Çok küçük yanıt ({len(resp.content)} bytes)"
            )

        out_path.write_bytes(resp.content)
        df = pd.read_csv(out_path, encoding="utf-8-sig")
        return DownloadResult(
            league_code, season, out_path, len(df), "ok",
            f"{len(df)} satır indirildi"
        )
    except requests.HTTPError as e:
        return DownloadResult(
            league_code, season, None, 0, "error",
            f"HTTP hata: {e}"
        )
    except Exception as e:
        return DownloadResult(
            league_code, season, None, 0, "error",
            f"Hata: {type(e).__name__}: {e}"
        )


def download_all() -> list[DownloadResult]:
    """Tüm yapılandırılmış lig-sezon kombinasyonlarını indirir."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    results: list[DownloadResult] = []

    total = len(LEAGUES) * len(SEASONS)
    counter = 0
    for league_code in LEAGUES:
        for season in SEASONS:
            counter += 1
            print(f"[{counter}/{total}] {league_code} {season} ...", end=" ", flush=True)
            res = download_csv(league_code, season)
            print(f"{res.status.upper():5} | {res.message}")
            results.append(res)
            time.sleep(RATE_LIMIT_SEC)

    return results


# ============================================================
# NORMALİZASYON
# ============================================================

# Football-Data.co.uk standart kolon adları:
#   Date, HomeTeam, AwayTeam, FTHG (Full Time Home Goals),
#   FTAG (Full Time Away Goals), FTR (H/D/A),
#   B365H, B365D, B365A (Bet365 oranları)
#   B365>2.5, B365<2.5 (Üst/Alt 2.5)
#   PSH, PSD, PSA (Pinnacle açılış)
#   PSCH, PSCD, PSCA (Pinnacle kapanış)
#
# Bizim için kritik olanlar — eksiklere None koy

REQUIRED_COLS = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]

ODDS_COLS = {
    # 1X2 oranları (Bet365 açılış)
    "odds_home_b365": "B365H",
    "odds_draw_b365": "B365D",
    "odds_away_b365": "B365A",
    # Pinnacle 1X2 açılış
    "odds_home_pin_open": "PSH",
    "odds_draw_pin_open": "PSD",
    "odds_away_pin_open": "PSA",
    # Pinnacle 1X2 kapanış (CLV referansı için ALTIN STANDART)
    "odds_home_pin_close": "PSCH",
    "odds_draw_pin_close": "PSCD",
    "odds_away_pin_close": "PSCA",
    # Alt/Üst 2.5 (Bet365)
    "odds_over25_b365": "B365>2.5",
    "odds_under25_b365": "B365<2.5",
    # Alt/Üst 2.5 (Pinnacle kapanış)
    "odds_over25_pin_close": "PC>2.5",
    "odds_under25_pin_close": "PC<2.5",
}


def normalize_single_csv(path: Path, league_code: str, season: str) -> pd.DataFrame:
    """Tek bir ham CSV'yi standardize edilmiş dataframe'e dönüştürür."""
    # Mirror CSV'leri UTF-8 BOM ile geliyor
    df = pd.read_csv(path, encoding="utf-8-sig")

    # Bazı CSV'ler trailing boş satırlar içeriyor
    df = df.dropna(subset=["HomeTeam", "AwayTeam"], how="any")

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name}: zorunlu kolonlar eksik: {missing}")

    # Tarihi parse et (Football-Data tarih formatları: dd/mm/yy veya dd/mm/yyyy)
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")

    out = pd.DataFrame({
        "match_date": df["Date"],
        "league": league_code,
        "season": season,
        "home_team": df["HomeTeam"].astype(str).str.strip(),
        "away_team": df["AwayTeam"].astype(str).str.strip(),
        "home_goals": pd.to_numeric(df["FTHG"], errors="coerce").astype("Int64"),
        "away_goals": pd.to_numeric(df["FTAG"], errors="coerce").astype("Int64"),
        "result": df["FTR"].astype(str).str.strip(),  # H, D, A
    })

    # Oran kolonlarını ekle (varsa)
    for our_name, source_name in ODDS_COLS.items():
        if source_name in df.columns:
            out[our_name] = pd.to_numeric(df[source_name], errors="coerce")
        else:
            out[our_name] = pd.NA

    # Final temizlik: sonucu olan maçları tut, oran yoksa da olsun
    out = out.dropna(subset=["match_date", "home_team", "away_team"])
    out = out[out["home_team"].str.len() > 0]

    return out.reset_index(drop=True)


def normalize_all() -> pd.DataFrame:
    """RAW_DIR'deki tüm CSV'leri birleştirir, normalize eder."""
    frames: list[pd.DataFrame] = []
    files = sorted(RAW_DIR.glob("*.csv"))
    if not files:
        raise FileNotFoundError(
            f"{RAW_DIR} altında CSV yok. Önce download_all() çalıştır."
        )

    for path in files:
        # Dosya adı: T1_2425.csv → league=T1, season=2425
        try:
            stem = path.stem  # "T1_2425"
            league_code, season = stem.split("_", 1)
        except ValueError:
            print(f"  uyarı: '{path.name}' format dışı, atlanıyor")
            continue

        try:
            frame = normalize_single_csv(path, league_code, season)
            frames.append(frame)
            print(f"  {path.name:20} → {len(frame):4} maç")
        except Exception as e:
            print(f"  hata {path.name}: {e}")

    if not frames:
        raise RuntimeError("Hiçbir dosya başarıyla normalize edilemedi.")

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(["match_date", "league"]).reset_index(drop=True)
    return combined


def save_processed(df: pd.DataFrame) -> Path:
    """Birleştirilmiş veriyi parquet olarak kaydet."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "matches.parquet"
    try:
        df.to_parquet(out_path, index=False)
    except Exception as e:
        # pyarrow yoksa CSV fallback
        out_path = PROCESSED_DIR / "matches.csv"
        df.to_csv(out_path, index=False)
        print(f"  not: parquet yazılamadı ({e}), CSV fallback kullanıldı")
    return out_path


# ============================================================
# MAIN
# ============================================================


def main() -> int:
    print("=" * 60)
    print("BAHIS AGENT — Football-Data.co.uk Veri İndirici")
    print("=" * 60)
    print(f"Hedef ligler: {', '.join(LEAGUES.keys())}")
    print(f"Sezonlar    : {', '.join(SEASONS)}")
    print(f"Çıktı klasör: {RAW_DIR}")
    print()

    print("[1/2] İndirme...")
    results = download_all()
    ok = sum(1 for r in results if r.status == "ok")
    skip = sum(1 for r in results if r.status == "skip")
    err = sum(1 for r in results if r.status == "error")
    total_rows = sum(r.rows for r in results)
    print(f"\nÖzet: ✓ {ok} indirildi, → {skip} atlandı, ✗ {err} hata")
    print(f"Toplam satır: {total_rows}")

    if ok == 0 and skip == 0:
        print("\nİndirme başarısız. İnternet bağlantısı veya URL'leri kontrol et.")
        return 1

    print("\n[2/2] Normalize ediliyor...")
    try:
        df = normalize_all()
        out_path = save_processed(df)
        print(f"\n✓ İşlenmiş veri kaydedildi: {out_path}")
        print(f"  Toplam maç: {len(df):,}")
        print(f"  Tarih aralığı: {df['match_date'].min().date()} → {df['match_date'].max().date()}")
        print(f"  Lig dağılımı:")
        for lig, count in df["league"].value_counts().items():
            print(f"    {lig}: {count:,} maç")
    except Exception as e:
        print(f"\n✗ Normalize sırasında hata: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
