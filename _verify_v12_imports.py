import sys
sys.path.insert(0, 'backend')
from app.models.models import GuardianProxyPay, EmergencyCallSource, AiCallReminder
from app.models.membership_plan import MembershipPlan, FreeMemberQuota
from app.api import guardian_system_v12
print("OK - all v1.2 modules import correctly")
print("MembershipPlan fields:", [c.name for c in MembershipPlan.__table__.columns][-6:])
print("FreeMemberQuota fields:", [c.name for c in FreeMemberQuota.__table__.columns][-6:])
print("Router endpoints:", [r.path for r in guardian_system_v12.router.routes])
