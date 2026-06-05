import sys
sys.path.insert(0, "/app")
from app.core.database import SessionLocal
from app.models import User
db = SessionLocal()
u = db.query(User).filter(User.username == "admin").first()
print("admin_exists:", u is not None)
if u:
    print("admin_role:", u.role)
db.close()
