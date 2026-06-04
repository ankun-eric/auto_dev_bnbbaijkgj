import os, zipfile, datetime, secrets

SRC = r"C:\auto_output\bnbbaijkgj\miniprogram"
EXCLUDE_DIRS = {"node_modules", ".git", "miniprogram_npm", "__pycache__"}

ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
rand = secrets.token_hex(2)
zip_name = f"miniprogram_{ts}_{rand}.zip"
zip_path = os.path.join(r"C:\auto_output\bnbbaijkgj", zip_name)

count = 0
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            full = os.path.join(root, f)
            arc = os.path.relpath(full, SRC)  # zip root = contents of miniprogram
            zf.write(full, arc)
            count += 1

size = os.path.getsize(zip_path)
print("ZIP_NAME:", zip_name)
print("ZIP_PATH:", zip_path)
print("FILES:", count)
print("SIZE_BYTES:", size)
# sanity: app.json must be at zip root
with zipfile.ZipFile(zip_path) as zf:
    names = zf.namelist()
    print("HAS_APP_JSON_AT_ROOT:", "app.json" in names)
