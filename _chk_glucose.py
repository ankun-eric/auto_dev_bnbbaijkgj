"""Check glucose tables and API health."""
from _ssh_helper import run

rc, out, err = run(
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 '
    '-e "USE bini_health; SHOW TABLES LIKE \'health_glucose%\';"',
    timeout=60,
)
print("--- TABLES ---")
print(out)
if err:
    print("STDERR:", err)

rc, out, err = run(
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend '
    'python -c "from app.api.glucose_v1 import judge_level, judge_crisis; '
    'print(judge_level(7.5, 1), judge_crisis(17.0))"',
    timeout=60,
)
print("--- IMPORT TEST ---")
print(out)
if err:
    print("STDERR:", err)
