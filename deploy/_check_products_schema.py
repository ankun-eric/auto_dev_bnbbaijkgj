import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client, run_cmd

ssh = create_client()
try:
    cmd = (
        "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db "
        "mysql -uroot -pbini_health_2026 bini_health "
        "-e 'SELECT COLUMN_NAME FROM information_schema.columns "
        "WHERE TABLE_SCHEMA=\"bini_health\" AND TABLE_NAME=\"products\" "
        "ORDER BY ORDINAL_POSITION' 2>&1"
    )
    out, err, code = run_cmd(ssh, cmd, timeout=30)
    print(out)
    if err:
        print('STDERR:', err)
finally:
    ssh.close()
