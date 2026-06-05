import sys
sys.path.insert(0, "/app")
from app.core.database import Base, engine
Base.metadata.create_all(bind=engine)
print("create_all DONE")
