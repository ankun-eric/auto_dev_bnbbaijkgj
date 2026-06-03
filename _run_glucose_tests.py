"""Run glucose tests inside backend container."""
from _ssh_helper import run

cmd = (
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend '
    'python -m pytest tests/test_glucose_v1_20260530.py -v --tb=short --no-header'
)
rc, out, err = run(cmd, timeout=300)
print(out[-6000:])
if err:
    print("STDERR:", err[-2000:])
print("RC=", rc)
