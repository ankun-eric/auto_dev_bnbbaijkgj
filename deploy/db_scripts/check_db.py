import sys
sys.path.insert(0, "/app")
from app.core.database import engine
from sqlalchemy import inspect
i = inspect(engine)
t = i.get_table_names()
print("Tables:", len(t))
for tn in sorted(t):
    print(" - " + tn)
