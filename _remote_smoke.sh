#!/usr/bin/env bash
BASE=https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com
echo "---containers---"
docker ps --filter name=6b099ed3 --format '{{.Names}}\t{{.Status}}'
echo "---health-profile---"
curl -sS -o /dev/null -w "HTTP:%{http_code}\n" "$BASE/health-profile"
echo "---health-metric blood_glucose---"
curl -sS -o /dev/null -w "HTTP:%{http_code}\n" "$BASE/health-metric/blood_glucose"
echo "---old /glucose (redirect placeholder)---"
curl -sS -o /dev/null -w "HTTP:%{http_code}\n" "$BASE/glucose"
echo "---api GET /latest (no auth)---"
curl -sS "$BASE/api/glucose-v1/latest" -w "\nHTTP:%{http_code}\n"
echo "---api PATCH /records/1/scene (no auth)---"
curl -sS -X PATCH "$BASE/api/glucose-v1/records/1/scene" -H "Content-Type: application/json" -d '{"scene":"fasting"}' -w "\nHTTP:%{http_code}\n"
echo "---api purge-all wrong token---"
curl -sS -X POST "$BASE/api/glucose-v1/admin/purge-all?confirm_token=WRONG" -w "\nHTTP:%{http_code}\n"
echo "---db counts---"
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 bini_health -e "SELECT 'records' AS t, COUNT(*) AS c FROM health_glucose_record UNION ALL SELECT 'alerts', COUNT(*) FROM health_glucose_alert UNION ALL SELECT 'reminders', COUNT(*) FROM health_glucose_reminder;" 2>&1 | grep -v Warning
echo "---backups---"
ls -la $HOME/6b099ed3-7175-4a78-91f4-44570c84ed27/_glucose_backup_*.sql 2>/dev/null | tail -3
