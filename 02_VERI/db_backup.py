"""
DB Backup Script — bahis_agent.db
Her calistirmada timestamp'li yedek olusturur.
Cron/Task Scheduler ile haftada bir calistir.
"""
import shutil
from pathlib import Path
from datetime import datetime

DB_PATH    = Path("02_VERI/bahis_agent.db")
BACKUP_DIR = Path("02_VERI/backups")
BACKUP_DIR.mkdir(exist_ok=True)

ts = datetime.now().strftime("%Y%m%d_%H%M")
dest = BACKUP_DIR / f"bahis_agent_{ts}.db"
shutil.copy2(DB_PATH, dest)

# Keep only last 7 backups
backups = sorted(BACKUP_DIR.glob("bahis_agent_*.db"))
for old in backups[:-7]:
    old.unlink()
    print(f"Silindi: {old.name}")

size_mb = dest.stat().st_size / 1024 / 1024
print(f"Yedek alindi: {dest.name} ({size_mb:.1f} MB)")
print(f"Toplam yedek: {len(list(BACKUP_DIR.glob('*.db')))} dosya")
