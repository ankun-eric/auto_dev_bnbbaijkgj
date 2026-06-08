from app.database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
tables = inspector.get_table_names()
print(f'Table count: {len(tables)}')
for t in sorted(tables):
    cols = [c['name'] for c in inspector.get_columns(t)]
    print(f'  {t}: {len(cols)} cols')
