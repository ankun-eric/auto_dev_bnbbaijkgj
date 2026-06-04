"""打包小程序 zip：仅包含完整 miniprogram 目录。"""
import os, zipfile, time

ROOT = "miniprogram"
TS = time.strftime("%Y%m%d-%H%M%S")
OUT = f"_mp_health_plan_checkin_v1_{TS}.zip"

skip_dirs = {"node_modules", ".git", ".DS_Store", "miniprogram_npm/.cache"}
skip_files = {".DS_Store"}

count = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d not in skip_dirs]
        for fn in fns:
            if fn in skip_files: continue
            p = os.path.join(dp, fn)
            arc = os.path.relpath(p, ROOT)
            z.write(p, arc)
            count += 1

size = os.path.getsize(OUT)
print(f"[OK] {OUT}  files={count}  size={size/1024:.1f} KB")
with open("_mp_health_plan_zipname.txt","w",encoding="utf-8") as f:
    f.write(OUT)
