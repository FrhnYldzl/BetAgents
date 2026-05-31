@echo off
cd /d "%~dp0"
python db_backup.py
echo.
echo Backup tamamlandi. Devam etmek icin bir tusa basin...
pause
