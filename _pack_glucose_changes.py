"""Package the 6 changed files into a tar.gz preserving relative paths."""
import tarfile
import os

files = [
    "backend/app/api/glucose_v1.py",
    "backend/tests/test_glucose_v1_20260530.py",
    "h5-web/src/lib/bg-level.ts",
    "h5-web/src/app/health-profile/page.tsx",
    "h5-web/src/app/health-metric/[type]/page.tsx",
    "h5-web/src/app/glucose/page.tsx",
]

OUT = "_glucose_changes_20260530.tar.gz"
with tarfile.open(OUT, "w:gz") as tar:
    for f in files:
        assert os.path.exists(f), f
        tar.add(f, arcname=f)
        print(f"added {f} ({os.path.getsize(f)} bytes)")

print(f"Created {OUT}, size={os.path.getsize(OUT)} bytes")
