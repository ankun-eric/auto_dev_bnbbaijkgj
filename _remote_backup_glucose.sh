#!/usr/bin/env bash
set -u
TS=$(date +%Y%m%d_%H%M%S)
BACKUP=$HOME/6b099ed3-7175-4a78-91f4-44570c84ed27/_glucose_backup_${TS}.sql
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysqldump -uroot -pbini_health_2026 bini_health health_glucose_record health_glucose_alert health_glucose_reminder > "$BACKUP" 2> /tmp/_glucose_backup_err.txt || echo "[warn] mysqldump returned non-zero (some tables may not exist)"
echo "---file---"
ls -la "$BACKUP"
echo "---bytes---"
wc -c "$BACKUP"
echo "---err---"
cat /tmp/_glucose_backup_err.txt
echo "---head---"
head -10 "$BACKUP"
