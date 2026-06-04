import os, zipfile, time, secrets

ROOT = os.path.dirname(os.path.abspath(__file__))
MP = os.path.join(ROOT, "miniprogram")
ts = time.strftime("%Y%m%d_%H%M%S")
rand = secrets.token_hex(2)
name = f"miniprogram_aihome_scrollhint_{ts}_{rand}.zip"
out = os.path.join(ROOT, name)

EXCLUDE_DIRS = {"node_modules", ".git", "miniprogram_npm", "__pycache__"}

count = 0
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for base, dirs, files in os.walk(MP):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            fp = os.path.join(base, f)
            # zip 内根目录为 miniprogram/
            arc = os.path.relpath(fp, ROOT)
            z.write(fp, arc)
            count += 1
print("ZIP:", name)
print("FILES:", count)
print("SIZE:", round(os.path.getsize(out)/1024, 1), "KB")
with open(os.path.join(ROOT, "_mp_scrollhint_zipname.txt"), "w") as f:
    f.write(name)
