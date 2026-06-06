import re
line = '@app.get("/api/health")'
m = re.search(r"""@app\.(get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"]""", line)
if m:
    print(f"MATCH: {m.group(1)} {m.group(2)}")
else:
    print("NO MATCH")
