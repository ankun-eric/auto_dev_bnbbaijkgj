"""[BUGFIX HS-V2-ALTER 2026-05-28] check current columns of home_safety_callback_log/config on prod DB."""
from _ssh_helper import run

CMD = (
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db "
    "mysql -uroot -pbini_health_2026 -N bini_health -e "
    "\"SELECT 'LOG:' AS tag; SHOW COLUMNS FROM home_safety_callback_log; "
    "SELECT 'CFG:' AS tag; SHOW COLUMNS FROM home_safety_callback_config;\" 2>&1 | grep -vi 'using a password'"
)
rc, out, err = run(CMD, timeout=60)
print(out)
if err:
    print("ERR:", err)
print("RC=", rc)
