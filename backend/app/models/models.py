import enum
from datetime import date, datetime

from sqlalchemy import (
    DECIMAL,
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import mapped_column, relationship

from app.core.database import Base


# ──────────────── Enums ────────────────


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"
    doctor = "doctor"
    merchant = "merchant"
    content_editor = "content_editor"  # v8: 内容运营角色


class IdentityType(str, enum.Enum):
    user = "user"
    merchant_owner = "merchant_owner"
    merchant_staff = "merchant_staff"


class MerchantMemberRole(str, enum.Enum):
    owner = "owner"
    staff = "staff"


class SessionType(str, enum.Enum):
    health_qa = "health_qa"
    symptom_check = "symptom_check"
    tcm = "tcm"
    tcm_tongue = "tcm_tongue"
    tcm_face = "tcm_face"
    drug_query = "drug_query"
    customer_service = "customer_service"
    drug_identify = "drug_identify"
    constitution_test = "constitution_test"
    # [2026-04-23] 报告解读/对比对话化
    report_interpret = "report_interpret"
    report_compare = "report_compare"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class MessageType(str, enum.Enum):
    text = "text"
    image = "image"
    voice = "voice"
    report = "report"


class ServiceType(str, enum.Enum):
    online = "online"
    offline = "offline"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    refunded = "refunded"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    processing = "processing"
    completed = "completed"
    cancelled = "cancelled"


class AppointmentStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    completed = "completed"
    cancelled = "cancelled"


class PointsType(str, enum.Enum):
    signin = "signin"
    task = "task"
    invite = "invite"
    purchase = "purchase"
    redeem = "redeem"
    checkin = "checkin"
    deduct = "deduct"
    completeProfile = "completeProfile"


class IndicatorStatus(str, enum.Enum):
    normal = "normal"
    abnormal = "abnormal"
    critical = "critical"


class ContentStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class NotificationType(str, enum.Enum):
    system = "system"
    order = "order"
    health = "health"
    promotion = "promotion"


class ContentTypeEnum(str, enum.Enum):
    article = "article"
    video = "video"


class FulfillmentType(str, enum.Enum):
    in_store = "in_store"  # 到店服务（暖橙角标）
    delivery = "delivery"  # 快递配送（科技蓝角标）
    virtual = "virtual"    # 改造④：虚拟商品（尊贵紫角标，如在线问诊咨询券、电子券码等）


class ProductStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    draft = "draft"


class CategoryStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class AppointmentMode(str, enum.Enum):
    none = "none"
    date = "date"
    time_slot = "time_slot"
    custom_form = "custom_form"


class PurchaseAppointmentMode(str, enum.Enum):
    # 对齐方案：下单即预约 / 先下单后预约
    # 为了兼容老数据，保留 must_appoint / appoint_later 作为别名值
    purchase_with_appointment = "purchase_with_appointment"
    appointment_later = "appointment_later"
    must_appoint = "must_appoint"
    appoint_later = "appoint_later"


class FormFieldType(str, enum.Enum):
    text = "text"
    textarea = "textarea"
    radio = "radio"
    checkbox = "checkbox"
    date = "date"
    time = "time"
    image = "image"
    phone = "phone"
    id_card = "id_card"
    address = "address"


class UnifiedOrderStatus(str, enum.Enum):
    pending_payment = "pending_payment"
    pending_shipment = "pending_shipment"
    pending_receipt = "pending_receipt"
    pending_use = "pending_use"
    pending_review = "pending_review"
    completed = "completed"
    cancelled = "cancelled"


class RefundStatusEnum(str, enum.Enum):
    none = "none"
    applied = "applied"
    reviewing = "reviewing"
    approved = "approved"
    rejected = "rejected"
    returning = "returning"
    refund_success = "refund_success"


class UnifiedPaymentMethod(str, enum.Enum):
    wechat = "wechat"
    alipay = "alipay"
    points = "points"


class CouponType(str, enum.Enum):
    full_reduction = "full_reduction"
    discount = "discount"
    voucher = "voucher"
    free_trial = "free_trial"


class CouponScope(str, enum.Enum):
    all = "all"
    category = "category"
    product = "product"


class CouponStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class UserCouponStatus(str, enum.Enum):
    unused = "unused"
    used = "used"
    expired = "expired"


class RefundRequestStatus(str, enum.Enum):
    pending = "pending"
    reviewing = "reviewing"
    approved = "approved"
    rejected = "rejected"
    returning = "returning"
    completed = "completed"


class PointsMallItemType(str, enum.Enum):
    virtual = "virtual"
    physical = "physical"
    service = "service"
    third_party = "third_party"
    coupon = "coupon"  # v3.1 新增 — 修复 Bug1：后台创建优惠券类商品时 400 报错


class CSSessionStatus(str, enum.Enum):
    waiting = "waiting"
    active = "active"
    closed = "closed"


class CSSessionType(str, enum.Enum):
    ai = "ai"
    human = "human"


class CSSenderType(str, enum.Enum):
    user = "user"
    agent = "agent"
    ai = "ai"


class MenuIconType(str, enum.Enum):
    emoji = "emoji"
    image = "image"


class MenuLinkType(str, enum.Enum):
    internal = "internal"
    external = "external"
    miniprogram = "miniprogram"


class BannerLinkType(str, enum.Enum):
    none = "none"
    internal = "internal"
    external = "external"
    miniprogram = "miniprogram"


# ──────────────── 用户体系 ────────────────


class User(Base):
    __tablename__ = "users"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone = mapped_column(String(20), unique=True, nullable=True, index=True)
    password_hash = mapped_column(String(255), nullable=True)
    nickname = mapped_column(String(100), nullable=True)
    avatar = mapped_column(String(500), nullable=True)
    role = mapped_column(Enum(UserRole), default=UserRole.user, nullable=False)
    wechat_openid = mapped_column(String(100), unique=True, nullable=True)
    apple_id = mapped_column(String(100), unique=True, nullable=True)
    member_card_no = mapped_column(String(50), unique=True, nullable=True, index=True)
    member_card_no_old = mapped_column(String(64), nullable=True)
    member_level = mapped_column(Integer, default=0)
    points = mapped_column(Integer, default=0)
    status = mapped_column(String(20), default="active")
    user_no = mapped_column(String(8), unique=True, nullable=True, index=True)
    referrer_no = mapped_column(String(8), nullable=True, index=True)
    is_superuser = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    chat_font_size = mapped_column(String(20), default="standard")
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    health_profile = relationship("HealthProfile", back_populates="user", uselist=True)
    family_members = relationship("FamilyMember", back_populates="user", foreign_keys="FamilyMember.user_id")
    chat_sessions = relationship("ChatSession", back_populates="user")
    orders = relationship("Order", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    points_records = relationship("PointsRecord", back_populates="user")
    health_plans = relationship("HealthPlan", back_populates="user")
    articles = relationship("Article", back_populates="author")


class RelationType(Base):
    __tablename__ = "relation_types"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(50), nullable=False)
    sort_order = mapped_column(Integer, default=0)
    is_active = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FamilyMember(Base):
    __tablename__ = "family_members"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    member_user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    relationship_type = mapped_column(String(50), nullable=False)
    nickname = mapped_column(String(100), nullable=True)
    birthday = mapped_column(Date, nullable=True)
    gender = mapped_column(String(10), nullable=True)
    height = mapped_column(Float, nullable=True)
    weight = mapped_column(Float, nullable=True)
    medical_histories = mapped_column(JSON, nullable=True)
    allergies = mapped_column(JSON, nullable=True)
    status = mapped_column(String(20), default="active")
    is_self = mapped_column(Boolean, default=False, nullable=False)
    relation_type_id = mapped_column(Integer, ForeignKey("relation_types.id"), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="family_members", foreign_keys=[user_id])
    member_user = relationship("User", foreign_keys=[member_user_id])
    relation_type = relationship("RelationType")


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone = mapped_column(String(20), nullable=False, index=True)
    code = mapped_column(String(10), nullable=False)
    type = mapped_column(String(20), nullable=False)
    expires_at = mapped_column(DateTime, nullable=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class AccountIdentity(Base):
    __tablename__ = "account_identities"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    identity_type = mapped_column(Enum(IdentityType), nullable=False)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "identity_type", name="uq_account_identity_user_type"),)


class MerchantProfile(Base):
    __tablename__ = "merchant_profiles"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    nickname = mapped_column(String(100), nullable=True)
    avatar = mapped_column(String(500), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MerchantStore(Base):
    __tablename__ = "merchant_stores"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_name = mapped_column(String(100), nullable=False)
    store_code = mapped_column(String(50), nullable=False, unique=True, index=True)
    contact_name = mapped_column(String(100), nullable=True)
    contact_phone = mapped_column(String(20), nullable=True)
    address = mapped_column(String(255), nullable=True)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MerchantStoreMembership(Base):
    __tablename__ = "merchant_store_memberships"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    store_id = mapped_column(Integer, ForeignKey("merchant_stores.id"), nullable=False, index=True)
    member_role = mapped_column(Enum(MerchantMemberRole), nullable=False)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "store_id", name="uq_merchant_store_member"),)

    store = relationship("MerchantStore")


class MerchantStorePermission(Base):
    __tablename__ = "merchant_store_permissions"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    membership_id = mapped_column(Integer, ForeignKey("merchant_store_memberships.id"), nullable=False, index=True)
    module_code = mapped_column(String(50), nullable=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("membership_id", "module_code", name="uq_merchant_store_permission"),)

    membership = relationship("MerchantStoreMembership")


class MerchantNotification(Base):
    __tablename__ = "merchant_notifications"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    store_id = mapped_column(Integer, ForeignKey("merchant_stores.id"), nullable=True, index=True)
    title = mapped_column(String(200), nullable=False)
    content = mapped_column(Text, nullable=True)
    is_read = mapped_column(Boolean, default=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    store = relationship("MerchantStore")


class MerchantOrderVerification(Base):
    __tablename__ = "merchant_order_verifications"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id = mapped_column(Integer, ForeignKey("orders.id"), nullable=False, unique=True, index=True)
    store_id = mapped_column(Integer, ForeignKey("merchant_stores.id"), nullable=False, index=True)
    verified_by_user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    verified_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    store = relationship("MerchantStore")
    order = relationship("Order")


# ──────────────── 健康档案 ────────────────


class HealthProfile(Base):
    __tablename__ = "health_profiles"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    family_member_id = mapped_column(Integer, ForeignKey("family_members.id"), nullable=True)
    name = mapped_column(String(100), nullable=True)
    height = mapped_column(Float, nullable=True)
    weight = mapped_column(Float, nullable=True)
    blood_type = mapped_column(String(10), nullable=True)
    gender = mapped_column(String(10), nullable=True)
    birthday = mapped_column(Date, nullable=True)
    smoking = mapped_column(String(20), nullable=True)
    drinking = mapped_column(String(20), nullable=True)
    exercise_habit = mapped_column(String(50), nullable=True)
    sleep_habit = mapped_column(String(50), nullable=True)
    diet_habit = mapped_column(String(50), nullable=True)
    chronic_diseases = mapped_column(JSON, nullable=True)
    medical_histories = mapped_column(JSON, nullable=True)
    allergies = mapped_column(JSON, nullable=True)
    drug_allergies = mapped_column(Text, nullable=True)
    food_allergies = mapped_column(Text, nullable=True)
    other_allergies = mapped_column(Text, nullable=True)
    genetic_diseases = mapped_column(JSON, nullable=True)
    guide_count = Column(Integer, default=0, nullable=False, server_default="0")
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="health_profile")
    family_member = relationship("FamilyMember")


class DiseasePreset(Base):
    __tablename__ = "disease_presets"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(100), nullable=False)
    category = mapped_column(String(20), nullable=False)
    sort_order = mapped_column(Integer, default=0)
    is_active = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AllergyRecord(Base):
    __tablename__ = "allergy_records"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    allergy_type = mapped_column(String(50), nullable=False)
    allergy_name = mapped_column(String(100), nullable=False)
    severity = mapped_column(String(20), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class MedicalHistory(Base):
    __tablename__ = "medical_histories"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    disease_name = mapped_column(String(200), nullable=False)
    diagnosis_date = mapped_column(Date, nullable=True)
    status = mapped_column(String(20), nullable=True)
    notes = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class FamilyMedicalHistory(Base):
    __tablename__ = "family_medical_histories"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    relationship_type = mapped_column(String(50), nullable=False)
    disease_name = mapped_column(String(200), nullable=False)
    notes = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class MedicationRecord(Base):
    __tablename__ = "medication_records"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    medicine_name = mapped_column(String(200), nullable=False)
    dosage = mapped_column(String(100), nullable=True)
    frequency = mapped_column(String(100), nullable=True)
    start_date = mapped_column(Date, nullable=True)
    end_date = mapped_column(Date, nullable=True)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class VisitRecord(Base):
    __tablename__ = "visit_records"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    hospital = mapped_column(String(200), nullable=True)
    department = mapped_column(String(100), nullable=True)
    diagnosis = mapped_column(Text, nullable=True)
    visit_date = mapped_column(Date, nullable=True)
    notes = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class CheckupReport(Base):
    __tablename__ = "checkup_reports"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    report_date = mapped_column(Date, nullable=True)
    report_type = mapped_column(String(50), nullable=True)
    file_url = mapped_column(String(500), nullable=True)
    thumbnail_url = mapped_column(String(500), nullable=True)
    # [2026-04-23] 体检报告多图修复：完整原图与缩略图 URL 列表（JSON）
    # - file_url / thumbnail_url 保留作封面用，保证老接口兼容
    # - file_urls / thumbnail_urls 用于多图展示；为 NULL 时由接口层 fallback 为 [file_url]
    file_urls = mapped_column(JSON, nullable=True)
    thumbnail_urls = mapped_column(JSON, nullable=True)
    file_type = mapped_column(String(20), default="image")
    ocr_result = mapped_column(JSON, nullable=True)
    ai_analysis = mapped_column(Text, nullable=True)
    ai_analysis_json = mapped_column(JSON, nullable=True)
    indicators = mapped_column(JSON, nullable=True)
    abnormal_count = mapped_column(Integer, default=0)
    health_score = mapped_column(Integer, nullable=True)
    status = mapped_column(String(20), default="pending")
    family_member_id = mapped_column(Integer, ForeignKey("family_members.id"), nullable=True, index=True)
    share_token = mapped_column(String(100), nullable=True, unique=True)
    share_expires_at = mapped_column(DateTime, nullable=True)
    # [2026-04-23] 报告解读对话化 - 新增字段
    title = mapped_column(String(100), nullable=True)
    interpret_session_id = mapped_column(Integer, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    family_member = relationship("FamilyMember")
    checkup_indicators = relationship("CheckupIndicator", back_populates="report")
    alerts = relationship("ReportAlert", back_populates="report")


class CheckupIndicator(Base):
    __tablename__ = "checkup_indicators"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id = mapped_column(Integer, ForeignKey("checkup_reports.id"), nullable=False, index=True)
    indicator_name = mapped_column(String(100), nullable=False)
    value = mapped_column(String(50), nullable=True)
    unit = mapped_column(String(50), nullable=True)
    reference_range = mapped_column(String(100), nullable=True)
    status = mapped_column(Enum(IndicatorStatus), default=IndicatorStatus.normal)
    category = mapped_column(String(100), nullable=True)
    advice = mapped_column(String(500), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    report = relationship("CheckupReport", back_populates="checkup_indicators")


# ──────────────── AI对话 ────────────────


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_type = mapped_column(Enum(SessionType), nullable=False)
    title = mapped_column(String(200), nullable=True)
    family_member_id = mapped_column(Integer, ForeignKey("family_members.id"), nullable=True)
    model_name = mapped_column(String(100), nullable=True)
    message_count = mapped_column(Integer, default=0)
    is_pinned = mapped_column(Boolean, default=False)
    is_deleted = mapped_column(Boolean, default=False)
    symptom_info = mapped_column(JSON, nullable=True)
    share_token = mapped_column(String(100), nullable=True, unique=True)
    device_info = mapped_column(String(500), nullable=True)
    ip_address = mapped_column(String(50), nullable=True)
    ip_location = mapped_column(String(100), nullable=True)
    # [2026-04-23] 报告解读/对比对话化 - 新增字段
    report_id = mapped_column(Integer, nullable=True)
    member_relation = mapped_column(String(32), nullable=True)
    compare_report_ids = mapped_column(String(64), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", order_by="ChatMessage.created_at")
    family_member = relationship("FamilyMember")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id = mapped_column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = mapped_column(Enum(MessageRole), nullable=False)
    content = mapped_column(Text, nullable=False)
    message_type = mapped_column(Enum(MessageType), default=MessageType.text)
    file_url = mapped_column(String(500), nullable=True)
    response_time_ms = mapped_column(Integer, nullable=True)
    prompt_tokens = mapped_column(Integer, nullable=True)
    completion_tokens = mapped_column(Integer, nullable=True)
    image_urls = mapped_column(JSON, nullable=True)
    file_urls = mapped_column(JSON, nullable=True)
    message_metadata = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


# ──────────────── 中医辨证 ────────────────


class TCMConfig(Base):
    __tablename__ = "tcm_configs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    tongue_diagnosis_enabled = mapped_column(Boolean, default=False)
    face_diagnosis_enabled = mapped_column(Boolean, default=False)
    constitution_test_enabled = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TCMDiagnosis(Base):
    __tablename__ = "tcm_diagnoses"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tongue_image_url = mapped_column(String(500), nullable=True)
    face_image_url = mapped_column(String(500), nullable=True)
    constitution_type = mapped_column(String(50), nullable=True)
    tongue_analysis = mapped_column(Text, nullable=True)
    face_analysis = mapped_column(Text, nullable=True)
    syndrome_analysis = mapped_column(Text, nullable=True)
    health_plan = mapped_column(Text, nullable=True)
    family_member_id = mapped_column(Integer, ForeignKey("family_members.id"), nullable=True, index=True)
    constitution_description = mapped_column(String(500), nullable=True)
    advice_summary = mapped_column(String(1000), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    family_member = relationship("FamilyMember")
    answers = relationship("ConstitutionAnswer", back_populates="diagnosis")


class ConstitutionQuestion(Base):
    __tablename__ = "constitution_questions"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_text = mapped_column(Text, nullable=False)
    question_group = mapped_column(String(50), nullable=True)
    options = mapped_column(JSON, nullable=True)
    order_num = mapped_column(Integer, default=0)


class ConstitutionAnswer(Base):
    __tablename__ = "constitution_answers"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    diagnosis_id = mapped_column(Integer, ForeignKey("tcm_diagnoses.id"), nullable=False, index=True)
    question_id = mapped_column(Integer, ForeignKey("constitution_questions.id"), nullable=False)
    answer_value = mapped_column(String(200), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    diagnosis = relationship("TCMDiagnosis", back_populates="answers")
    question = relationship("ConstitutionQuestion")


# ──────────────── 服务与订单 ────────────────


class ServiceCategory(Base):
    __tablename__ = "service_categories"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(100), nullable=False)
    icon = mapped_column(String(500), nullable=True)
    description = mapped_column(Text, nullable=True)
    sort_order = mapped_column(Integer, default=0)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    items = relationship("ServiceItem", back_populates="category")


class ServiceItem(Base):
    __tablename__ = "service_items"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id = mapped_column(Integer, ForeignKey("service_categories.id"), nullable=False, index=True)
    name = mapped_column(String(200), nullable=False)
    description = mapped_column(Text, nullable=True)
    price = mapped_column(Numeric(10, 2), nullable=False)
    original_price = mapped_column(Numeric(10, 2), nullable=True)
    images = mapped_column(JSON, nullable=True)
    service_type = mapped_column(Enum(ServiceType), default=ServiceType.online)
    stock = mapped_column(Integer, default=0)
    sales_count = mapped_column(Integer, default=0)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("ServiceCategory", back_populates="items")


class Order(Base):
    __tablename__ = "orders"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no = mapped_column(String(50), unique=True, nullable=False, index=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    service_item_id = mapped_column(Integer, ForeignKey("service_items.id"), nullable=False)
    quantity = mapped_column(Integer, default=1)
    total_amount = mapped_column(Numeric(10, 2), nullable=False)
    paid_amount = mapped_column(Numeric(10, 2), default=0)
    points_deduction = mapped_column(Integer, default=0)
    payment_method = mapped_column(String(50), nullable=True)
    payment_status = mapped_column(Enum(PaymentStatus), default=PaymentStatus.pending)
    order_status = mapped_column(Enum(OrderStatus), default=OrderStatus.pending)
    verification_code = mapped_column(String(20), nullable=True)
    verified_at = mapped_column(DateTime, nullable=True)
    verified_by = mapped_column(Integer, nullable=True)
    shipping_info = mapped_column(JSON, nullable=True)
    address = mapped_column(Text, nullable=True)
    notes = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="orders")
    service_item = relationship("ServiceItem")
    review = relationship("OrderReview", back_populates="order", uselist=False)


class OrderReview(Base):
    __tablename__ = "order_reviews"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id = mapped_column(Integer, ForeignKey("orders.id"), unique=True, nullable=False)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    rating = mapped_column(Integer, nullable=False)
    content = mapped_column(Text, nullable=True)
    images = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="review")
    user = relationship("User")


# ──────────────── 专家/医生 ────────────────


class Expert(Base):
    __tablename__ = "experts"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), unique=True, nullable=True)
    name = mapped_column(String(100), nullable=False)
    title = mapped_column(String(100), nullable=True)
    hospital = mapped_column(String(200), nullable=True)
    department = mapped_column(String(100), nullable=True)
    specialties = mapped_column(Text, nullable=True)
    introduction = mapped_column(Text, nullable=True)
    avatar = mapped_column(String(500), nullable=True)
    consultation_fee = mapped_column(Numeric(10, 2), default=0)
    rating = mapped_column(Float, default=5.0)
    review_count = mapped_column(Integer, default=0)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    schedules = relationship("ExpertSchedule", back_populates="expert")


class ExpertSchedule(Base):
    __tablename__ = "expert_schedules"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    expert_id = mapped_column(Integer, ForeignKey("experts.id"), nullable=False, index=True)
    date = mapped_column(Date, nullable=False)
    time_slot = mapped_column(String(50), nullable=False)
    max_appointments = mapped_column(Integer, default=10)
    current_appointments = mapped_column(Integer, default=0)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    expert = relationship("Expert", back_populates="schedules")


class Appointment(Base):
    __tablename__ = "appointments"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expert_id = mapped_column(Integer, ForeignKey("experts.id"), nullable=False, index=True)
    schedule_id = mapped_column(Integer, ForeignKey("expert_schedules.id"), nullable=False)
    appointment_date = mapped_column(Date, nullable=False)
    time_slot = mapped_column(String(50), nullable=False)
    status = mapped_column(Enum(AppointmentStatus), default=AppointmentStatus.pending)
    notes = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    expert = relationship("Expert")
    schedule = relationship("ExpertSchedule")


# ──────────────── 积分与会员 ────────────────


class PointsRecord(Base):
    __tablename__ = "points_records"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    points = mapped_column(Integer, nullable=False)
    type = mapped_column(Enum(PointsType), nullable=False)
    description = mapped_column(String(200), nullable=True)
    order_id = mapped_column(Integer, ForeignKey("orders.id"), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="points_records")


class MemberLevel(Base):
    __tablename__ = "member_levels"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    level_name = mapped_column(String(50), nullable=False)
    icon = mapped_column(String(50), nullable=True)
    min_points = mapped_column(Integer, default=0)
    max_points = mapped_column(Integer, default=0)
    discount_rate = mapped_column(Float, default=1.0)
    benefits = mapped_column(JSON, nullable=True)
    color = mapped_column(String(20), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class SignInRecord(Base):
    __tablename__ = "sign_in_records"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    sign_date = mapped_column(Date, nullable=False)
    consecutive_days = mapped_column(Integer, default=1)
    points_earned = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "sign_date", name="uq_user_sign_date"),)

    user = relationship("User")


class PointsMallItem(Base):
    __tablename__ = "points_mall_items"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(200), nullable=False)
    description = mapped_column(Text, nullable=True)
    images = mapped_column(JSON, nullable=True)
    # v3.1: 枚举存储为 VARCHAR（不使用 SQLAlchemy Enum 的强约束），避免追加 coupon 时需要 ALTER
    type = mapped_column(String(30), default="virtual", nullable=False)
    price_points = mapped_column(Integer, nullable=False)
    stock = mapped_column(Integer, default=0)
    status = mapped_column(String(20), default="active")
    # v3.1 新增字段（PRD F4 + Bug2 打通）
    detail_html = mapped_column(Text, nullable=True, comment="富文本详情 HTML")
    ref_coupon_id = mapped_column(Integer, nullable=True, comment="type=coupon 时关联 coupons.id")
    ref_service_id = mapped_column(Integer, nullable=True, comment="type=service 时关联 products.id")
    limit_per_user = mapped_column(Integer, default=0, nullable=False, comment="每人限兑次数 0=不限")
    # v1.1 新增：三态流转 + 无缝替换
    goods_status = mapped_column(
        String(16), default="draft", nullable=False,
        comment="draft/on_sale/off_sale 三态；覆盖旧 status 字段用于精细管控"
    )
    replaced_by_goods_id = mapped_column(Integer, nullable=True, comment="被哪个商品替代（复制新建）")
    copied_from_goods_id = mapped_column(Integer, nullable=True, comment="从哪个商品复制而来")
    sort_weight = mapped_column(Integer, default=0, nullable=False, comment="排序权重，越大越靠前")
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class PointsMallGoodsChangeLog(Base):
    """v1.1 新增：商品修改历史日志表。

    仅针对锁定清单中"可改，留痕"字段（title、主图、轮播图）记录变更。
    """
    __tablename__ = "points_mall_goods_change_log"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    goods_id = mapped_column(Integer, ForeignKey("points_mall_items.id"), nullable=False, index=True)
    field_key = mapped_column(String(64), nullable=False, comment="字段英文 key（如 title / main_image）")
    field_name = mapped_column(String(64), nullable=False, comment="字段中文名")
    old_value = mapped_column(Text, nullable=True)
    new_value = mapped_column(Text, nullable=True)
    operator_id = mapped_column(Integer, nullable=True)
    operator_name = mapped_column(String(64), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class PointsExchange(Base):
    __tablename__ = "points_exchanges"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    item_id = mapped_column(Integer, ForeignKey("points_mall_items.id"), nullable=False)
    points_spent = mapped_column(Integer, nullable=False)
    quantity = mapped_column(Integer, default=1)
    status = mapped_column(String(20), default="pending")
    shipping_info = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    item = relationship("PointsMallItem")


# ──────────────── 积分兑换记录 v3（优惠券 + 体验服务） ────────────────
class PointExchangeRecord(Base):
    """v3 新增：积分兑换记录表（承载券 + 体验服务两种商品；实物走 orders 系统）。"""
    __tablename__ = "point_exchange_records"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no = mapped_column(String(32), nullable=False, unique=True, index=True,
                             comment="兑换单号 EX+yyyyMMdd+6位流水")
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    goods_id = mapped_column(Integer, nullable=False, comment="PointsMallItem.id")
    goods_type = mapped_column(String(20), nullable=False,
                                comment="coupon/service/virtual/physical/third_party")
    goods_name = mapped_column(String(200), nullable=False)
    goods_image = mapped_column(String(500), nullable=True)
    points_cost = mapped_column(Integer, nullable=False)
    quantity = mapped_column(Integer, default=1, nullable=False)

    status = mapped_column(String(20), default="success", nullable=False, index=True,
                            comment="pending/success/failed/used/expired/cancelled")
    exchange_time = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expire_at = mapped_column(DateTime, nullable=True)
    used_at = mapped_column(DateTime, nullable=True)

    # 虚拟券 / 服务券关联
    ref_coupon_id = mapped_column(Integer, nullable=True, comment="关联券模板 ID")
    ref_user_coupon_id = mapped_column(Integer, nullable=True, comment="关联 user_coupons.id")

    # 体验服务关联
    ref_service_type = mapped_column(String(30), nullable=True,
                                      comment="expert/physical_exam/tcm/health_plan")
    ref_service_id = mapped_column(Integer, nullable=True)

    # 实物（实际走订单系统，此处冗余订单号）
    ref_order_no = mapped_column(String(32), nullable=True)

    remark = mapped_column(String(500), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = mapped_column(DateTime, default=datetime.utcnow,
                                onupdate=datetime.utcnow, nullable=False)

    user = relationship("User")


# ──────────────── 健康计划 ────────────────


class HealthPlan(Base):
    __tablename__ = "health_plans"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_name = mapped_column(String(200), nullable=False)
    plan_type = mapped_column(String(50), nullable=True)
    content = mapped_column(JSON, nullable=True)
    ai_generated = mapped_column(Boolean, default=False)
    start_date = mapped_column(Date, nullable=True)
    end_date = mapped_column(Date, nullable=True)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="health_plans")
    tasks = relationship("HealthTask", back_populates="plan")


class HealthTask(Base):
    __tablename__ = "health_tasks"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id = mapped_column(Integer, ForeignKey("health_plans.id"), nullable=False, index=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    task_name = mapped_column(String(200), nullable=False)
    task_type = mapped_column(String(50), nullable=True)
    task_time = mapped_column(String(50), nullable=True)
    reminder_time = mapped_column(String(50), nullable=True)
    status = mapped_column(String(20), default="pending")
    points_reward = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    plan = relationship("HealthPlan", back_populates="tasks")
    user = relationship("User")
    check_ins = relationship("TaskCheckIn", back_populates="task")


class TaskCheckIn(Base):
    __tablename__ = "task_check_ins"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id = mapped_column(Integer, ForeignKey("health_tasks.id"), nullable=False, index=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    check_in_date = mapped_column(Date, nullable=False)
    notes = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    task = relationship("HealthTask", back_populates="check_ins")
    user = relationship("User")


# ──────────────── 健康知识 ────────────────


class Article(Base):
    __tablename__ = "articles"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    title = mapped_column(String(300), nullable=False)
    content = mapped_column(Text, nullable=False)
    content_html = mapped_column(Text, nullable=True)  # v8: 富文本 HTML 正文（优先于 content）
    summary = mapped_column(String(500), nullable=True)
    cover_image = mapped_column(String(500), nullable=True)
    author_id = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    author_name = mapped_column(String(100), nullable=True)  # v8: 作者/来源文本字段
    category = mapped_column(String(50), nullable=True)
    tags = mapped_column(JSON, nullable=True)
    view_count = mapped_column(Integer, default=0)
    like_count = mapped_column(Integer, default=0)
    comment_count = mapped_column(Integer, default=0)  # v8
    is_top = mapped_column(Boolean, default=False)  # v8
    published_at = mapped_column(DateTime, nullable=True)  # v8: 发布时间
    status = mapped_column(Enum(ContentStatus), default=ContentStatus.draft)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author = relationship("User", back_populates="articles", foreign_keys=[author_id])


class ArticleCategory(Base):
    """v8 新增：文章分类（替代现有 Article.category 文本字段）"""
    __tablename__ = "article_categories"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(50), unique=True, nullable=False)
    sort_order = mapped_column(Integer, default=0)
    is_enabled = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class News(Base):
    """v8 新增：资讯"""
    __tablename__ = "news"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    title = mapped_column(String(300), nullable=False)
    cover_image = mapped_column(String(500), nullable=True)
    summary = mapped_column(String(500), nullable=True)
    content_html = mapped_column(Text, nullable=False)
    tags = mapped_column(String(500), nullable=True)  # 逗号分隔
    source = mapped_column(String(100), nullable=True)
    status = mapped_column(Enum(ContentStatus), default=ContentStatus.draft)
    is_top = mapped_column(Boolean, default=False)
    view_count = mapped_column(Integer, default=0)
    like_count = mapped_column(Integer, default=0)
    comment_count = mapped_column(Integer, default=0)
    published_at = mapped_column(DateTime, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NewsTagHistory(Base):
    """v8 新增：资讯标签历史（用于联想下拉）"""
    __tablename__ = "news_tag_history"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag = mapped_column(String(50), unique=True, nullable=False)
    use_count = mapped_column(Integer, default=1)
    last_used_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Comment(Base):
    __tablename__ = "comments"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_type = mapped_column(Enum(ContentTypeEnum), nullable=False)
    content_id = mapped_column(Integer, nullable=False, index=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id = mapped_column(Integer, ForeignKey("comments.id"), nullable=True)
    content = mapped_column(Text, nullable=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    replies = relationship("Comment")


class Favorite(Base):
    __tablename__ = "favorites"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content_type = mapped_column(String(20), nullable=False)
    content_id = mapped_column(Integer, nullable=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "content_type", "content_id", name="uq_user_favorite"),)

    user = relationship("User")


# ──────────────── 消息通知 ────────────────


class Notification(Base):
    __tablename__ = "notifications"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = mapped_column(String(200), nullable=False)
    content = mapped_column(Text, nullable=True)
    type = mapped_column(Enum(NotificationType), default=NotificationType.system)
    is_read = mapped_column(Boolean, default=False)
    extra_data = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")


# ──────────────── 系统配置 ────────────────


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key = mapped_column(String(100), unique=True, nullable=False)
    config_value = mapped_column(Text, nullable=True)
    config_type = mapped_column(String(20), nullable=True)
    description = mapped_column(String(200), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIModelTemplate(Base):
    __tablename__ = "ai_model_templates"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(100), nullable=False)
    base_url = mapped_column(String(500), nullable=False)
    model_name = mapped_column(String(100), nullable=False)
    icon = mapped_column(String(50), nullable=False)
    description = mapped_column(String(500), nullable=False)
    status = mapped_column(Integer, default=1)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIModelConfig(Base):
    __tablename__ = "ai_model_configs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_name = mapped_column(String(100), nullable=False)
    base_url = mapped_column(String(500), nullable=False)
    model_name = mapped_column(String(100), nullable=False)
    api_key_encrypted = mapped_column(String(500), nullable=True)
    is_active = mapped_column(Boolean, default=False)
    max_tokens = mapped_column(Integer, default=4096)
    temperature = mapped_column(Float, default=0.7)
    template_id = mapped_column(Integer, ForeignKey("ai_model_templates.id"), nullable=True)
    template_synced_at = mapped_column(DateTime, nullable=True)
    last_test_status = mapped_column(String(20), nullable=True)
    last_test_time = mapped_column(DateTime, nullable=True)
    last_test_message = mapped_column(String(500), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    template = relationship("AIModelTemplate")


class SmsConfig(Base):
    __tablename__ = "sms_configs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider = mapped_column(String(20), nullable=False, default="tencent")
    secret_id = mapped_column(String(255), nullable=True)
    secret_key_encrypted = mapped_column(String(500), nullable=True)
    sdk_app_id = mapped_column(String(50), nullable=True)
    sign_name = mapped_column(String(100), nullable=True)
    template_id = mapped_column(String(50), nullable=True)
    app_key = mapped_column(String(255), nullable=True)
    access_key_id = mapped_column(String(255), nullable=True)
    access_key_secret_encrypted = mapped_column(String(500), nullable=True)
    is_active = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SmsLog(Base):
    __tablename__ = "sms_logs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone = mapped_column(String(20), nullable=False, index=True)
    code = mapped_column(String(10), nullable=True)
    template_id = mapped_column(String(50), nullable=True)
    provider = mapped_column(String(20), nullable=True)
    status = mapped_column(String(20), nullable=False)
    error_message = mapped_column(Text, nullable=True)
    is_test = mapped_column(Boolean, default=False)
    operator_id = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    template_params = mapped_column(String(1000), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class SmsTemplate(Base):
    __tablename__ = "sms_templates"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(100), nullable=False)
    provider = mapped_column(String(20), nullable=False)
    template_id = mapped_column(String(100), nullable=False)
    content = mapped_column(String(500), nullable=True)
    sign_name = mapped_column(String(50), nullable=True)
    scene = mapped_column(String(20), nullable=True)
    variables = mapped_column(Text, nullable=True)
    status = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    to_email = mapped_column(String(200), nullable=False, index=True)
    subject = mapped_column(String(500), nullable=False)
    content = mapped_column(Text, nullable=True)
    status = mapped_column(String(20), nullable=False)
    error_message = mapped_column(String(500), nullable=True)
    is_test = mapped_column(Boolean, default=False)
    operator_id = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)


# ──────────────── 客服 ────────────────


class CustomerServiceSession(Base):
    __tablename__ = "customer_service_sessions"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_id = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    status = mapped_column(Enum(CSSessionStatus), default=CSSessionStatus.waiting)
    type = mapped_column(Enum(CSSessionType), default=CSSessionType.ai)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])
    agent = relationship("User", foreign_keys=[agent_id])
    messages = relationship("CustomerServiceMessage", back_populates="session", order_by="CustomerServiceMessage.created_at")


class CustomerServiceMessage(Base):
    __tablename__ = "customer_service_messages"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id = mapped_column(Integer, ForeignKey("customer_service_sessions.id"), nullable=False, index=True)
    sender_type = mapped_column(Enum(CSSenderType), nullable=False)
    sender_id = mapped_column(Integer, nullable=True)
    content = mapped_column(Text, nullable=False)
    message_type = mapped_column(String(20), default="text")
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    session = relationship("CustomerServiceSession", back_populates="messages")


# ──────────────── 知识库管理 ────────────────


class KnowledgeEntryType(str, enum.Enum):
    qa = "qa"
    doc = "doc"


class KnowledgeDisplayMode(str, enum.Enum):
    direct = "direct"
    ai_rewrite = "ai_rewrite"


class MatchType(str, enum.Enum):
    exact = "exact"
    semantic = "semantic"
    keyword = "keyword"


class FallbackStrategy(str, enum.Enum):
    ai_fallback = "ai_fallback"
    fixed_text = "fixed_text"
    human_service = "human_service"
    recommend = "recommend"


class ImportSourceType(str, enum.Enum):
    excel = "excel"
    csv = "csv"
    word = "word"
    pdf = "pdf"
    txt = "txt"
    markdown = "markdown"
    url = "url"


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(200), nullable=False)
    description = mapped_column(Text, nullable=True)
    status = mapped_column(String(20), default="active")
    is_global = mapped_column(Boolean, default=False)
    entry_count = mapped_column(Integer, default=0)
    active_entry_count = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = mapped_column(Integer, ForeignKey("users.id"), nullable=True)


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    kb_id = mapped_column(Integer, ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    type = mapped_column(Enum(KnowledgeEntryType), nullable=False)
    question = mapped_column(Text, nullable=True)
    title = mapped_column(String(500), nullable=True)
    content_json = mapped_column(JSON, nullable=True)
    keywords = mapped_column(JSON, nullable=True)
    display_mode = mapped_column(Enum(KnowledgeDisplayMode), default=KnowledgeDisplayMode.direct)
    status = mapped_column(String(20), default="active")
    hit_count = mapped_column(Integer, default=0)
    last_hit_at = mapped_column(DateTime, nullable=True)
    embedding_vector = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    knowledge_base = relationship("KnowledgeBase")


class KnowledgeEntryProduct(Base):
    __tablename__ = "knowledge_entry_products"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id = mapped_column(Integer, ForeignKey("knowledge_entries.id"), nullable=False, index=True)
    product_id = mapped_column(Integer, nullable=False)
    product_type = mapped_column(String(20), nullable=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class KnowledgeSearchConfig(Base):
    __tablename__ = "knowledge_search_configs"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope = mapped_column(String(50), nullable=False, unique=True)
    config_json = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KnowledgeFallbackConfig(Base):
    __tablename__ = "knowledge_fallback_configs"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene = mapped_column(String(50), nullable=False, unique=True)
    strategy = mapped_column(Enum(FallbackStrategy), default=FallbackStrategy.ai_fallback)
    custom_text = mapped_column(Text, nullable=True)
    recommend_count = mapped_column(Integer, default=3)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KnowledgeSceneBinding(Base):
    __tablename__ = "knowledge_scene_bindings"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene = mapped_column(String(50), nullable=False, index=True)
    kb_id = mapped_column(Integer, ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    is_primary = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class KnowledgeHitLog(Base):
    __tablename__ = "knowledge_hit_logs"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id = mapped_column(Integer, ForeignKey("knowledge_entries.id"), nullable=False, index=True)
    kb_id = mapped_column(Integer, ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    match_type = mapped_column(Enum(MatchType), nullable=False)
    match_score = mapped_column(Float, nullable=True)
    user_question = mapped_column(Text, nullable=True)
    search_time_ms = mapped_column(Integer, nullable=True)
    user_feedback = mapped_column(String(20), nullable=True)
    session_id = mapped_column(Integer, nullable=True)
    message_id = mapped_column(Integer, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class KnowledgeMissedQuestion(Base):
    __tablename__ = "knowledge_missed_questions"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    question = mapped_column(Text, nullable=False)
    scene = mapped_column(String(50), nullable=True)
    count = mapped_column(Integer, default=1)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KnowledgeImportTask(Base):
    __tablename__ = "knowledge_import_tasks"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    kb_id = mapped_column(Integer, ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    source_type = mapped_column(Enum(ImportSourceType), nullable=False)
    source_url = mapped_column(String(1000), nullable=True)
    file_path = mapped_column(String(500), nullable=True)
    status = mapped_column(String(20), default="processing")
    result_json = mapped_column(JSON, nullable=True)
    created_by = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ──────────────── AI中心配置 ────────────────


class AiSensitiveWord(Base):
    __tablename__ = "ai_sensitive_words"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    sensitive_word = mapped_column(String(200), nullable=False)
    replacement_word = mapped_column(String(200), nullable=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AiPromptConfig(Base):
    __tablename__ = "ai_prompt_configs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_type = mapped_column(String(50), unique=True, nullable=False)
    display_name = mapped_column(String(100), nullable=False)
    system_prompt = mapped_column(Text, nullable=True)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AiDisclaimerConfig(Base):
    __tablename__ = "ai_disclaimer_configs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_type = mapped_column(String(50), unique=True, nullable=False)
    display_name = mapped_column(String(100), nullable=False)
    disclaimer_text = mapped_column(Text, nullable=True)
    is_enabled = mapped_column(Boolean, default=True)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CosConfig(Base):
    __tablename__ = "cos_configs"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    secret_id = mapped_column(String(255), nullable=True)
    secret_key_encrypted = mapped_column(String(500), nullable=True)
    bucket = mapped_column(String(200), nullable=True)
    region = mapped_column(String(50), nullable=True)
    image_prefix = mapped_column(String(200), default="images/")
    video_prefix = mapped_column(String(200), default="videos/")
    file_prefix = mapped_column(String(200), default="files/")
    is_active = mapped_column(Boolean, default=False)
    cdn_domain = Column(String(300), nullable=True, comment='CDN加速域名')
    cdn_protocol = Column(String(10), default='https', comment='CDN协议')
    test_passed = Column(Boolean, default=False, comment='连接测试是否通过')
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CosFile(Base):
    __tablename__ = "cos_files"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_key = mapped_column(String(500), nullable=False, unique=True)
    file_url = mapped_column(String(1000), nullable=False)
    file_type = mapped_column(String(50), nullable=True)
    file_size = mapped_column(Integer, nullable=True)
    original_name = mapped_column(String(300), nullable=True)
    module = mapped_column(String(50), nullable=True)
    ref_id = mapped_column(Integer, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class CosUploadLimit(Base):
    __tablename__ = "cos_upload_limits"
    id = Column(Integer, primary_key=True, autoincrement=True)
    module = Column(String(50), unique=True, nullable=False)
    module_name = Column(String(100))
    max_size_mb = Column(Integer, default=50)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class CosMigrationTask(Base):
    __tablename__ = "cos_migration_tasks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String(20), default='scanning')
    total_files = Column(Integer, default=0)
    migrated_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    total_size = Column(BigInteger, default=0)
    migrated_size = Column(BigInteger, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    created_by = Column(Integer, nullable=True)


class CosMigrationDetail(Base):
    __tablename__ = "cos_migration_details"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, nullable=False)
    module = Column(String(50))
    original_url = Column(String(1000))
    cos_url = Column(String(1000), nullable=True)
    file_size = Column(Integer, default=0)
    status = Column(String(20), default='pending')
    error_message = Column(String(500), nullable=True)
    migrated_at = Column(DateTime, nullable=True)


# ──────────────── 体检报告相关配置 ────────────────


class OcrConfig(Base):
    __tablename__ = "ocr_configs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    enabled = mapped_column(Boolean, default=True)
    api_key = mapped_column(String(200), nullable=True)
    secret_key_encrypted = mapped_column(String(500), nullable=True)
    ocr_type = mapped_column(String(50), default="general_basic")
    access_token = mapped_column(Text, nullable=True)
    token_expires_at = mapped_column(DateTime, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReportAlert(Base):
    __tablename__ = "report_alerts"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    report_id = mapped_column(Integer, ForeignKey("checkup_reports.id"), nullable=False, index=True)
    indicator_name = mapped_column(String(100), nullable=False)
    alert_type = mapped_column(String(50), nullable=False)
    alert_message = mapped_column(Text, nullable=True)
    is_read = mapped_column(Boolean, default=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    report = relationship("CheckupReport", back_populates="alerts")


# ──────────────── OCR 多厂商识别 ────────────────


class OcrProviderConfig(Base):
    __tablename__ = "ocr_provider_configs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_name = mapped_column(String(50), unique=True, nullable=False)
    display_name = mapped_column(String(100), nullable=False)
    config_json = mapped_column(JSON, nullable=True)
    is_enabled = mapped_column(Boolean, default=False)
    is_preferred = mapped_column(Boolean, default=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OcrSceneTemplate(Base):
    __tablename__ = "ocr_scene_templates"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene_name = mapped_column(String(100), unique=True, nullable=False)
    prompt_content = mapped_column(Text, nullable=True)
    is_preset = mapped_column(Boolean, default=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OcrCallRecord(Base):
    __tablename__ = "ocr_call_records"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene_name = mapped_column(String(100), nullable=True)
    provider_name = mapped_column(String(50), nullable=False)
    status = mapped_column(String(20), nullable=False)
    original_image_url = mapped_column(String(1000), nullable=True)
    ocr_raw_text = mapped_column(Text, nullable=True)
    ai_structured_result = mapped_column(JSON, nullable=True)
    error_message = mapped_column(Text, nullable=True)
    image_count = mapped_column(Integer, default=1, nullable=False)
    image_urls = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class OcrCallStatistics(Base):
    __tablename__ = "ocr_call_statistics"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_name = mapped_column(String(50), nullable=False, index=True)
    call_date = mapped_column(Date, nullable=False, index=True)
    total_calls = mapped_column(Integer, default=0)
    success_calls = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("provider_name", "call_date", name="uq_ocr_stats_provider_date"),
    )


class OcrUploadConfig(Base):
    __tablename__ = "ocr_upload_configs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    max_batch_count = mapped_column(Integer, default=5)
    max_file_size_mb = mapped_column(Integer, default=5)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CheckupReportDetail(Base):
    __tablename__ = "checkup_report_details"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    user_phone = mapped_column(String(20), nullable=True)
    user_nickname = mapped_column(String(100), nullable=True)
    report_type = mapped_column(String(50), nullable=True)
    abnormal_count = mapped_column(Integer, default=0)
    summary = mapped_column(Text, nullable=True)
    status = mapped_column(String(20), default="normal")
    provider_name = mapped_column(String(50), nullable=False)
    original_image_url = mapped_column(String(1000), nullable=True)
    # [2026-04-23] 体检报告多图修复：Admin 详情多图完整列表
    original_image_urls = mapped_column(JSON, nullable=True)
    ocr_raw_text = mapped_column(Text, nullable=True)
    ai_structured_result = mapped_column(JSON, nullable=True)
    abnormal_indicators = mapped_column(JSON, nullable=True)
    ocr_call_record_id = mapped_column(Integer, ForeignKey("ocr_call_records.id"), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class DrugIdentifyDetail(Base):
    __tablename__ = "drug_identify_details"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    user_phone = mapped_column(String(20), nullable=True)
    user_nickname = mapped_column(String(100), nullable=True)
    drug_name = mapped_column(String(200), nullable=True)
    drug_category = mapped_column(String(50), nullable=True)
    dosage = mapped_column(Text, nullable=True)
    precautions = mapped_column(Text, nullable=True)
    provider_name = mapped_column(String(50), nullable=False)
    original_image_url = mapped_column(String(1000), nullable=True)
    ocr_raw_text = mapped_column(Text, nullable=True)
    ai_structured_result = mapped_column(JSON, nullable=True)
    ocr_call_record_id = mapped_column(Integer, ForeignKey("ocr_call_records.id"), nullable=True)
    session_id = mapped_column(Integer, ForeignKey("chat_sessions.id"), nullable=True)
    family_member_id = mapped_column(Integer, ForeignKey("family_members.id"), nullable=True)
    status = mapped_column(String(20), default="success")
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession")
    family_member = relationship("FamilyMember")


# ──────────────── 聊天分享 ────────────────


class ChatShareRecord(Base):
    __tablename__ = "chat_share_records"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    share_token = mapped_column(String(64), unique=True, nullable=False, index=True)
    session_id = mapped_column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    user_message_id = mapped_column(Integer, ForeignKey("chat_messages.id"), nullable=False)
    ai_message_id = mapped_column(Integer, ForeignKey("chat_messages.id"), nullable=False)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    view_count = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession")
    user_message = relationship("ChatMessage", foreign_keys=[user_message_id])
    ai_message = relationship("ChatMessage", foreign_keys=[ai_message_id])
    user = relationship("User")


# ──────────────── Prompt 模板管理 ────────────────


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(100), nullable=False)
    prompt_type = mapped_column(String(50), nullable=False)
    content = mapped_column(Text, nullable=False)
    version = mapped_column(Integer, default=1)
    is_active = mapped_column(Boolean, default=True)
    parent_id = mapped_column(Integer, ForeignKey("prompt_templates.id"), nullable=True)
    preview_input = mapped_column(Text, nullable=True)
    created_by = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ──────────────── 分享链接 ────────────────


class ShareLink(Base):
    __tablename__ = "share_links"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    link_token = mapped_column(String(64), unique=True, nullable=False)
    link_type = mapped_column(String(20), nullable=False)
    record_id = mapped_column(Integer, nullable=False)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    view_count = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime, default=datetime.utcnow)


# ──────────────── 首页配置 ────────────────


class HomeMenuItem(Base):
    __tablename__ = "home_menu_items"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(20), nullable=False)
    icon_type = mapped_column(Enum(MenuIconType), nullable=False, default=MenuIconType.emoji)
    icon_content = mapped_column(String(500), nullable=False)
    link_type = mapped_column(Enum(MenuLinkType), nullable=False, default=MenuLinkType.internal)
    link_url = mapped_column(String(500), nullable=False)
    miniprogram_appid = mapped_column(String(100), nullable=True)
    sort_order = mapped_column(Integer, nullable=False, default=0)
    is_visible = mapped_column(Boolean, nullable=False, default=True)
    created_at = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class HomeBanner(Base):
    __tablename__ = "home_banners"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_url = mapped_column(String(500), nullable=False)
    link_type = mapped_column(Enum(BannerLinkType), nullable=False, default=BannerLinkType.none)
    link_url = mapped_column(String(500), nullable=True)
    miniprogram_appid = mapped_column(String(100), nullable=True)
    sort_order = mapped_column(Integer, nullable=False, default=0)
    is_visible = mapped_column(Boolean, nullable=False, default=True)
    created_at = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# ──────────────── 统一搜索 ────────────────


class SearchHistory(Base):
    __tablename__ = "search_histories"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    keyword = mapped_column(String(200), nullable=False)
    search_count = mapped_column(Integer, default=1)
    created_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "keyword", name="uq_search_history_user_keyword"),)

    user = relationship("User")


class SearchHotWord(Base):
    __tablename__ = "search_hot_words"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword = mapped_column(String(200), unique=True, nullable=False)
    search_count = mapped_column(Integer, default=0)
    result_count = mapped_column(Integer, default=0)
    category_hint = mapped_column(String(50), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SearchRecommendWord(Base):
    __tablename__ = "search_recommend_words"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword = mapped_column(String(200), nullable=False)
    sort_order = mapped_column(Integer, default=0)
    category_hint = mapped_column(String(50), nullable=True)
    is_active = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SearchBlockWord(Base):
    __tablename__ = "search_block_words"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword = mapped_column(String(200), unique=True, nullable=False)
    block_mode = mapped_column(String(20), default="full")
    tip_content = mapped_column(String(500), nullable=True)
    is_active = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class SearchLog(Base):
    __tablename__ = "search_logs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, nullable=True, index=True)
    keyword = mapped_column(String(200), nullable=False, index=True)
    result_count = mapped_column(Integer, default=0)
    result_counts_json = mapped_column(Text, nullable=True)
    clicked_type = mapped_column(String(50), nullable=True)
    clicked_item_id = mapped_column(Integer, nullable=True)
    source = mapped_column(String(20), default="text")
    ip_address = mapped_column(String(50), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AsrConfig(Base):
    __tablename__ = "asr_configs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider = mapped_column(String(20), default="tencent")
    app_id = mapped_column(String(100), nullable=True)
    secret_id = mapped_column(String(200), nullable=True)
    secret_key_encrypted = mapped_column(String(500), nullable=True)
    is_enabled = mapped_column(Boolean, default=False)
    supported_dialects = mapped_column(String(200), default="普通话,粤语")
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DrugSearchKeyword(Base):
    __tablename__ = "drug_search_keywords"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword = mapped_column(String(100), unique=True, nullable=False)
    is_active = mapped_column(Boolean, default=True)


# ──────────────── 首页公告栏 ────────────────


class HomeNotice(Base):
    __tablename__ = "home_notices"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    content = mapped_column(Text, nullable=False)
    link_url = mapped_column(String(500), nullable=True)
    start_time = mapped_column(DateTime, nullable=False)
    end_time = mapped_column(DateTime, nullable=False)
    is_enabled = mapped_column(Boolean, nullable=False, default=True)
    sort_order = mapped_column(Integer, nullable=False, default=0)
    created_at = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# ──────────────── 底部导航配置 ────────────────


class BottomNavConfig(Base):
    __tablename__ = "bottom_nav_config"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(20), nullable=False)
    icon_key = mapped_column(String(50), nullable=False)
    path = mapped_column(String(200), nullable=False)
    sort_order = mapped_column(Integer, nullable=False, default=0)
    is_visible = mapped_column(Boolean, nullable=False, default=True)
    is_fixed = mapped_column(Boolean, nullable=False, default=False)
    created_at = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# ──────────────── 健康计划V2 ────────────────


class MedicationReminder(Base):
    __tablename__ = "medication_reminders"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    medicine_name = mapped_column(String(200), nullable=False)
    dosage = mapped_column(String(100), nullable=True)
    time_period = mapped_column(String(20), nullable=True)
    remind_time = mapped_column(String(10), nullable=True)
    notes = mapped_column(Text, nullable=True)
    is_paused = mapped_column(Boolean, default=False)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    check_ins = relationship("MedicationCheckIn", back_populates="reminder")


class MedicationCheckIn(Base):
    __tablename__ = "medication_check_ins"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    reminder_id = mapped_column(Integer, ForeignKey("medication_reminders.id"), nullable=False, index=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    check_in_date = mapped_column(Date, nullable=False)
    check_in_time = mapped_column(DateTime, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    reminder = relationship("MedicationReminder", back_populates="check_ins")
    user = relationship("User")


class HealthCheckInItem(Base):
    __tablename__ = "health_checkin_items"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = mapped_column(String(200), nullable=False)
    target_value = mapped_column(Float, nullable=True)
    target_unit = mapped_column(String(50), nullable=True)
    remind_times = mapped_column(JSON, nullable=True)
    repeat_frequency = mapped_column(String(50), default="daily")
    custom_days = mapped_column(JSON, nullable=True)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    records = relationship("HealthCheckInRecord", back_populates="item")


class HealthCheckInRecord(Base):
    __tablename__ = "health_checkin_records"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id = mapped_column(Integer, ForeignKey("health_checkin_items.id"), nullable=False, index=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    check_in_date = mapped_column(Date, nullable=False)
    actual_value = mapped_column(Float, nullable=True)
    is_completed = mapped_column(Boolean, default=False)
    check_in_time = mapped_column(DateTime, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    item = relationship("HealthCheckInItem", back_populates="records")
    user = relationship("User")


class PlanTemplateCategory(Base):
    __tablename__ = "plan_template_categories"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(100), nullable=False)
    description = mapped_column(Text, nullable=True)
    icon = mapped_column(String(50), nullable=True)
    sort_order = mapped_column(Integer, default=0)
    preset_tasks = mapped_column(JSON, nullable=True)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    recommended_plans = relationship("RecommendedPlan", back_populates="category")


class RecommendedPlan(Base):
    __tablename__ = "recommended_plans"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id = mapped_column(Integer, ForeignKey("plan_template_categories.id"), nullable=False, index=True)
    name = mapped_column(String(200), nullable=False)
    description = mapped_column(Text, nullable=True)
    target_audience = mapped_column(String(200), nullable=True)
    duration_days = mapped_column(Integer, nullable=True)
    cover_image = mapped_column(String(500), nullable=True)
    is_published = mapped_column(Boolean, default=True)
    sort_order = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    category = relationship("PlanTemplateCategory", back_populates="recommended_plans")
    tasks = relationship("RecommendedPlanTask", back_populates="plan")


class RecommendedPlanTask(Base):
    __tablename__ = "recommended_plan_tasks"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id = mapped_column(Integer, ForeignKey("recommended_plans.id"), nullable=False, index=True)
    task_name = mapped_column(String(200), nullable=False)
    target_value = mapped_column(Float, nullable=True)
    target_unit = mapped_column(String(50), nullable=True)
    sort_order = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    plan = relationship("RecommendedPlan", back_populates="tasks")


class UserPlan(Base):
    __tablename__ = "user_plans"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category_id = mapped_column(Integer, ForeignKey("plan_template_categories.id"), nullable=True)
    source_type = mapped_column(String(20), default="custom")
    recommended_plan_id = mapped_column(Integer, ForeignKey("recommended_plans.id"), nullable=True)
    plan_name = mapped_column(String(200), nullable=False)
    description = mapped_column(Text, nullable=True)
    duration_days = mapped_column(Integer, nullable=True)
    current_day = mapped_column(Integer, default=1)
    status = mapped_column(String(20), default="active")
    start_date = mapped_column(Date, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    category = relationship("PlanTemplateCategory")
    recommended_plan = relationship("RecommendedPlan")
    tasks = relationship("UserPlanTask", back_populates="plan")


class UserPlanTask(Base):
    __tablename__ = "user_plan_tasks"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id = mapped_column(Integer, ForeignKey("user_plans.id"), nullable=False, index=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    task_name = mapped_column(String(200), nullable=False)
    target_value = mapped_column(Float, nullable=True)
    target_unit = mapped_column(String(50), nullable=True)
    sort_order = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    plan = relationship("UserPlan", back_populates="tasks")
    user = relationship("User")
    records = relationship("UserPlanTaskRecord", back_populates="task")


class UserPlanTaskRecord(Base):
    __tablename__ = "user_plan_task_records"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id = mapped_column(Integer, ForeignKey("user_plan_tasks.id"), nullable=False, index=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    check_in_date = mapped_column(Date, nullable=False)
    actual_value = mapped_column(Float, nullable=True)
    is_completed = mapped_column(Boolean, default=False)
    check_in_time = mapped_column(DateTime, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    task = relationship("UserPlanTask", back_populates="records")
    user = relationship("User")


class DefaultHealthTask(Base):
    __tablename__ = "default_health_tasks"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(200), nullable=False)
    description = mapped_column(Text, nullable=True)
    target_value = mapped_column(Float, nullable=True)
    target_unit = mapped_column(String(50), nullable=True)
    category_type = mapped_column(String(50), nullable=True)
    template_category_id = mapped_column(Integer, ForeignKey("plan_template_categories.id"), nullable=True)
    sort_order = mapped_column(Integer, default=0)
    is_active = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    template_category = relationship("PlanTemplateCategory")


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    source_type = mapped_column(String(50), nullable=False)
    source_id = mapped_column(Integer, nullable=True)
    title = mapped_column(String(200), nullable=False)
    content = mapped_column(Text, nullable=True)
    status = mapped_column(String(20), default="pending")
    scheduled_time = mapped_column(DateTime, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")


# ──────────────── 城市定位 ────────────────


class City(Base):
    __tablename__ = "cities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, comment="城市名称(如北京市)")
    short_name = Column(String(20), nullable=False, comment="城市简称(如北京)")
    pinyin = Column(String(100), nullable=False, comment="拼音(如beijing)")
    first_letter = Column(String(1), nullable=False, comment="拼音首字母(如B)")
    province = Column(String(50), nullable=False, comment="所属省份")
    longitude = Column(DECIMAL(10, 6), nullable=True, comment="城市中心经度")
    latitude = Column(DECIMAL(10, 6), nullable=True, comment="城市中心纬度")
    is_hot = Column(Boolean, default=False, comment="是否热门城市")
    hot_sort = Column(Integer, default=0, comment="热门排序(越小越靠前)")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ──────────────── 功能按钮与数字人 ────────────────


class ChatFunctionButton(Base):
    __tablename__ = "chat_function_buttons"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(50), nullable=False)
    icon_url = mapped_column(String(500), nullable=True)
    button_type = mapped_column(String(50), nullable=False)
    sort_weight = mapped_column(Integer, default=0)
    is_enabled = mapped_column(Boolean, default=True)
    params = mapped_column(JSON, nullable=True)
    ai_reply_mode = mapped_column(String(50), nullable=True, default="complete_analysis")
    photo_tip_text = mapped_column(String(500), nullable=True, default="请确保药品名称、品牌、规格完整，拍摄清晰")
    max_photo_count = mapped_column(Integer, nullable=True, default=5)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DigitalHuman(Base):
    __tablename__ = "digital_humans"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(100), nullable=False)
    silent_video_url = mapped_column(String(500), nullable=False)
    speaking_video_url = mapped_column(String(500), nullable=False)
    tts_voice_id = mapped_column(String(100), nullable=True)
    description = mapped_column(Text, nullable=True)
    thumbnail_url = mapped_column(String(500), nullable=True)
    is_enabled = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VoiceCallRecord(Base):
    __tablename__ = "voice_call_records"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    digital_human_id = mapped_column(Integer, nullable=True)
    chat_session_id = mapped_column(Integer, nullable=True)
    start_time = mapped_column(DateTime, nullable=False)
    end_time = mapped_column(DateTime, nullable=True)
    duration_seconds = mapped_column(Integer, nullable=True)
    dialog_content = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class VoiceServiceConfig(Base):
    __tablename__ = "voice_service_configs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key = mapped_column(String(100), unique=True, nullable=False)
    config_value = mapped_column(Text, nullable=False)
    config_type = mapped_column(String(50), nullable=False)
    description = mapped_column(String(200), nullable=True)
    updated_by = mapped_column(Integer, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ──────────────── 家庭健康档案共管 ────────────────


class ManagementStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    cancelled = "cancelled"


class InvitationStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    expired = "expired"
    cancelled = "cancelled"


class FamilyManagement(Base):
    __tablename__ = "family_management"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    manager_user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    managed_user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    managed_member_id = mapped_column(Integer, ForeignKey("family_members.id"), nullable=True)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    cancelled_at = mapped_column(DateTime, nullable=True)
    cancelled_by = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    manager = relationship("User", foreign_keys=[manager_user_id])
    managed_user = relationship("User", foreign_keys=[managed_user_id])


class FamilyInvitation(Base):
    __tablename__ = "family_invitations"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    invite_code = mapped_column(String(64), unique=True, nullable=False, index=True)
    inviter_user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    member_id = mapped_column(Integer, ForeignKey("family_members.id"), nullable=False)
    status = mapped_column(String(20), default="pending")
    expires_at = mapped_column(DateTime, nullable=False)
    accepted_by = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    accepted_at = mapped_column(DateTime, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    inviter = relationship("User", foreign_keys=[inviter_user_id])
    member = relationship("FamilyMember")


class ManagementOperationLog(Base):
    __tablename__ = "management_operation_logs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    management_id = mapped_column(Integer, ForeignKey("family_management.id"), nullable=False)
    operator_user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    operation_type = mapped_column(String(50), nullable=False)
    operation_detail = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    operator = relationship("User", foreign_keys=[operator_user_id])


# ──────────────── 系统消息 ────────────────


class SystemMessage(Base):
    __tablename__ = "system_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_type = Column(String(50), nullable=False)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    sender_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    related_business_id = Column(String(100), nullable=True)
    related_business_type = Column(String(50), nullable=True)
    click_action = Column(String(200), nullable=True)
    click_action_params = Column(JSON, nullable=True)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

    recipient = relationship("User", foreign_keys=[recipient_user_id])
    sender = relationship("User", foreign_keys=[sender_user_id])


# ──────────────── 商品体系 ────────────────


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(100), nullable=False)
    parent_id = mapped_column(Integer, ForeignKey("product_categories.id"), nullable=True, index=True)
    icon = mapped_column(String(500), nullable=True)
    description = mapped_column(Text, nullable=True)
    sort_order = mapped_column(Integer, default=0)
    status = mapped_column(Enum(CategoryStatus), default=CategoryStatus.active)
    level = mapped_column(Integer, default=1)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = relationship("ProductCategory", remote_side="ProductCategory.id", backref="children")


class AppointmentForm(Base):
    __tablename__ = "appointment_forms"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(200), nullable=False)
    description = mapped_column(Text, nullable=True)
    # 状态：active/inactive，默认 active；用于表单库启用/停用（BUG-PRODUCT-APPT-001）
    status = mapped_column(String(20), default="active", nullable=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    fields = relationship("AppointmentFormField", back_populates="form", order_by="AppointmentFormField.sort_order")


class AppointmentFormField(Base):
    __tablename__ = "appointment_form_fields"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    form_id = mapped_column(Integer, ForeignKey("appointment_forms.id"), nullable=False, index=True)
    field_type = mapped_column(Enum(FormFieldType), nullable=False)
    label = mapped_column(String(200), nullable=False)
    placeholder = mapped_column(String(200), nullable=True)
    required = mapped_column(Boolean, default=False)
    options = mapped_column(JSON, nullable=True)
    sort_order = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    form = relationship("AppointmentForm", back_populates="fields")


class Product(Base):
    __tablename__ = "products"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(200), nullable=False)
    category_id = mapped_column(Integer, ForeignKey("product_categories.id"), nullable=False, index=True)
    fulfillment_type = mapped_column(Enum(FulfillmentType), nullable=False)
    original_price = mapped_column(Numeric(10, 2), nullable=False)
    sale_price = mapped_column(Numeric(10, 2), nullable=False)
    images = mapped_column(JSON, nullable=True)
    video_url = mapped_column(String(500), nullable=True)
    description = mapped_column(Text, nullable=True)
    symptom_tags = mapped_column(JSON, nullable=True)
    stock = mapped_column(Integer, default=0)
    valid_start_date = mapped_column(Date, nullable=True)
    valid_end_date = mapped_column(Date, nullable=True)
    points_exchangeable = mapped_column(Boolean, default=False)
    points_price = mapped_column(Integer, default=0)
    points_deductible = mapped_column(Boolean, default=False)
    redeem_count = mapped_column(Integer, default=1)
    appointment_mode = mapped_column(Enum(AppointmentMode), default=AppointmentMode.none)
    purchase_appointment_mode = mapped_column(Enum(PurchaseAppointmentMode), nullable=True)
    custom_form_id = mapped_column(Integer, ForeignKey("appointment_forms.id"), nullable=True)
    # ── 预约联动 UI 新增字段（BUG-PRODUCT-APPT-001）──
    advance_days = mapped_column(Integer, nullable=True)  # date 模式：提前可预约天数
    daily_quota = mapped_column(Integer, nullable=True)  # date 模式：单日最大预约人数
    time_slots = mapped_column(JSON, nullable=True)  # time_slot 模式：时段列表 [{start,end,capacity}]
    faq = mapped_column(JSON, nullable=True)
    recommend_weight = mapped_column(Integer, default=0)
    sales_count = mapped_column(Integer, default=0)
    status = mapped_column(Enum(ProductStatus), default=ProductStatus.draft)
    sort_order = mapped_column(Integer, default=0)
    payment_timeout_minutes = mapped_column(Integer, default=15)
    # ── 商品弹窗优化 v2 新增字段 ──
    product_code_list = mapped_column(JSON, nullable=True)  # 产品条码列表（最多10个）
    spec_mode = mapped_column(Integer, default=1)  # 1=统一规格 2=多规格
    main_video_url = mapped_column(String(500), nullable=True)  # 主图视频 URL
    selling_point = mapped_column(String(200), nullable=True)  # 商品卖点（100 字以内）
    description_rich = mapped_column(Text, nullable=True)  # 富文本 HTML
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("ProductCategory")
    custom_form = relationship("AppointmentForm")
    stores = relationship("ProductStore", back_populates="product")
    skus = relationship("ProductSku", back_populates="product", cascade="all, delete-orphan")


class ProductSku(Base):
    """商品规格（SKU）"""
    __tablename__ = "product_skus"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id = mapped_column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    spec_name = mapped_column(String(50), nullable=False)  # 规格名称，同商品内不重复
    sale_price = mapped_column(Numeric(10, 2), nullable=False, default=0)
    origin_price = mapped_column(Numeric(10, 2), nullable=True)
    stock = mapped_column(Integer, default=0)
    is_default = mapped_column(Boolean, default=False)  # 是否默认规格（每商品仅 1 条）
    status = mapped_column(Integer, default=1)  # 1=启用 2=停用
    sort_order = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("product_id", "spec_name", name="uq_product_sku_name"),)

    product = relationship("Product", back_populates="skus")


class ProductStore(Base):
    __tablename__ = "product_stores"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id = mapped_column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    store_id = mapped_column(Integer, ForeignKey("merchant_stores.id"), nullable=False, index=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("product_id", "store_id", name="uq_product_store"),)

    product = relationship("Product", back_populates="stores")
    store = relationship("MerchantStore")


# ──────────────── 收货地址 ────────────────


class UserAddress(Base):
    __tablename__ = "user_addresses"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = mapped_column(String(100), nullable=False)
    phone = mapped_column(String(20), nullable=False)
    province = mapped_column(String(50), nullable=False)
    city = mapped_column(String(50), nullable=False)
    district = mapped_column(String(50), nullable=False)
    street = mapped_column(String(255), nullable=False)
    is_default = mapped_column(Boolean, default=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


# ──────────────── 优惠券 ────────────────


class Coupon(Base):
    __tablename__ = "coupons"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(200), nullable=False)
    type = mapped_column(Enum(CouponType), nullable=False)
    condition_amount = mapped_column(Numeric(10, 2), default=0)
    discount_value = mapped_column(Numeric(10, 2), default=0)
    discount_rate = mapped_column(Float, default=1.0)
    scope = mapped_column(Enum(CouponScope), default=CouponScope.all)
    scope_ids = mapped_column(JSON, nullable=True)
    total_count = mapped_column(Integer, default=0)
    claimed_count = mapped_column(Integer, default=0)
    used_count = mapped_column(Integer, default=0)
    # 仅"领取后 N 天"模式 (3/7/15/30/60/90/180/365)
    validity_days = mapped_column(Integer, default=30, nullable=False)
    # 兼容字段（已废弃，仅保留供历史数据迁移期读取，业务逻辑不再使用）
    valid_start = mapped_column(DateTime, nullable=True)
    valid_end = mapped_column(DateTime, nullable=True)
    status = mapped_column(Enum(CouponStatus), default=CouponStatus.active)
    # ─── V2.1 新增：下架（禁删除）相关字段 ───
    is_offline = mapped_column(Boolean, default=False, nullable=False, server_default="0", index=True)
    offline_reason = mapped_column(String(255), nullable=True)
    offline_at = mapped_column(DateTime, nullable=True)
    offline_by = mapped_column(Integer, nullable=True)
    # ─── V2.1 预留：积分兑换次数上限（None=无限） ───
    points_exchange_limit = mapped_column(Integer, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserCoupon(Base):
    __tablename__ = "user_coupons"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    coupon_id = mapped_column(Integer, ForeignKey("coupons.id"), nullable=False, index=True)
    status = mapped_column(Enum(UserCouponStatus), default=UserCouponStatus.unused)
    used_at = mapped_column(DateTime, nullable=True)
    order_id = mapped_column(Integer, nullable=True)
    # 领取时根据 Coupon.validity_days 计算的过期时刻
    expire_at = mapped_column(DateTime, nullable=True, index=True)
    # 来源：self / direct / new_user / redeem_code
    source = mapped_column(String(30), default="self")
    grant_id = mapped_column(Integer, nullable=True, index=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    coupon = relationship("Coupon")


# ──────────────── 优惠券发放 / 兑换码 / 第三方合作方 ────────────────


class CouponGrant(Base):
    """优惠券发放记录"""
    __tablename__ = "coupon_grants"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    coupon_id = mapped_column(Integer, ForeignKey("coupons.id"), nullable=False, index=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    user_phone = mapped_column(String(20), nullable=True, index=True)
    # self / direct / new_user / redeem_code
    method = mapped_column(String(30), nullable=False, index=True)
    # granted / used / recalled / expired
    status = mapped_column(String(30), default="granted", index=True)
    granted_at = mapped_column(DateTime, default=datetime.utcnow, index=True)
    used_at = mapped_column(DateTime, nullable=True)
    order_no = mapped_column(String(50), nullable=True)
    operator_id = mapped_column(Integer, nullable=True)
    operator_name = mapped_column(String(100), nullable=True)
    user_coupon_id = mapped_column(Integer, ForeignKey("user_coupons.id"), nullable=True, index=True)
    # 关联的发放任务 / 兑换码批次
    batch_id = mapped_column(Integer, nullable=True, index=True)
    redeem_code = mapped_column(String(64), nullable=True)
    # 回收原因
    recall_reason = mapped_column(Text, nullable=True)
    extra = mapped_column(JSON, nullable=True)


class CouponCodeBatch(Base):
    """兑换码批次（A: 一码通用 / C+: 一次性唯一码）"""
    __tablename__ = "coupon_code_batches"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    coupon_id = mapped_column(Integer, ForeignKey("coupons.id"), nullable=False, index=True)
    # universal / unique
    code_type = mapped_column(String(20), nullable=False, default="universal")
    name = mapped_column(String(200), nullable=True)
    # 总码数（unique 模式）
    total_count = mapped_column(Integer, default=0)
    # 已使用数
    used_count = mapped_column(Integer, default=0)
    # 一码通用模式下的统一码
    universal_code = mapped_column(String(64), nullable=True, index=True)
    # 每码 / 每用户 限领次数（universal 模式：每个用户最多兑换次数；unique 模式恒为 1）
    per_user_limit = mapped_column(Integer, default=1)
    # 第三方合作方ID（C+ 模式必填）
    partner_id = mapped_column(Integer, ForeignKey("partners.id"), nullable=True, index=True)
    # 状态：active / disabled
    status = mapped_column(String(20), default="active")
    created_by = mapped_column(Integer, nullable=True)
    # ─── V2.1：批次编号（强确认作废用） + 一码通用领取上限 + 兑换码独立有效期 + 整批作废 ───
    batch_no = mapped_column(String(64), nullable=True, unique=True, index=True)
    claim_limit = mapped_column(Integer, nullable=True)  # 一码通用必填；一次性唯一码自动 = total_count
    expire_at = mapped_column(DateTime, nullable=True)
    voided_at = mapped_column(DateTime, nullable=True, index=True)
    voided_by = mapped_column(Integer, nullable=True)
    void_reason = mapped_column(String(255), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class CouponRedeemCode(Base):
    """兑换码池（仅 unique 模式逐条入库）"""
    __tablename__ = "coupon_redeem_codes"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id = mapped_column(Integer, ForeignKey("coupon_code_batches.id"), nullable=False, index=True)
    coupon_id = mapped_column(Integer, ForeignKey("coupons.id"), nullable=False, index=True)
    code = mapped_column(String(64), unique=True, nullable=False, index=True)
    # available / sold / used / disabled
    status = mapped_column(String(20), default="available", index=True)
    # 第三方售出状态回传（available -> sold -> used）
    sold_at = mapped_column(DateTime, nullable=True)
    sold_to_user_phone = mapped_column(String(50), nullable=True)
    used_at = mapped_column(DateTime, nullable=True)
    used_by_user_id = mapped_column(Integer, nullable=True)
    partner_id = mapped_column(Integer, ForeignKey("partners.id"), nullable=True, index=True)
    # ─── V2.1：单个作废 ───
    voided_at = mapped_column(DateTime, nullable=True, index=True)
    voided_by = mapped_column(Integer, nullable=True)
    void_reason = mapped_column(String(255), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class CouponOpLog(Base):
    """V2.1 优惠券操作日志（下架/上架/作废码/作废批次）"""
    __tablename__ = "coupon_op_logs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    op_type = mapped_column(String(32), nullable=False, index=True)  # offline/online/void_code/void_batch
    target_type = mapped_column(String(32), nullable=False)  # coupon/batch/code
    target_id = mapped_column(Integer, nullable=False, index=True)
    operator_id = mapped_column(Integer, nullable=False, index=True)
    operator_name = mapped_column(String(100), nullable=True)
    reason = mapped_column(String(500), nullable=True)
    extra = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Partner(Base):
    """第三方合作方"""
    __tablename__ = "partners"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(200), nullable=False)
    contact_name = mapped_column(String(100), nullable=True)
    contact_phone = mapped_column(String(50), nullable=True)
    # 接入模式：offline_only / api / both
    mode = mapped_column(String(20), default="api")
    api_key = mapped_column(String(64), unique=True, nullable=True, index=True)
    # SHA256 签名密钥（明文存储，仅管理员可见；可以加密但简化）
    api_secret = mapped_column(String(128), nullable=True)
    # active / disabled
    status = mapped_column(String(20), default="active")
    notes = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ──────────────── 资金安全审核 ────────────────


class AuditPhone(Base):
    """系统管理 → 审核手机号配置"""
    __tablename__ = "audit_phones"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone = mapped_column(String(20), nullable=False, index=True)
    note = mapped_column(String(200), nullable=True)
    enabled = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditRequest(Base):
    """审核申请单（优惠券发放/批量回收/兑换码批量等）"""
    __tablename__ = "audit_requests"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 业务类型：coupon_grant / coupon_recall / redeem_batch / redeem_disable
    biz_type = mapped_column(String(40), nullable=False, index=True)
    # 风险级别：low / high
    risk_level = mapped_column(String(10), nullable=False, default="low")
    # 状态：pending / approved / rejected / returned / cancelled
    status = mapped_column(String(20), default="pending", index=True)
    # 业务参数（payload，审核通过后回放执行）
    payload = mapped_column(JSON, nullable=False)
    # 摘要信息（用于审核列表展示）
    summary = mapped_column(String(500), nullable=True)
    # 估算面值与张数（用于风险评级展示）
    est_amount = mapped_column(Numeric(12, 2), default=0)
    est_count = mapped_column(Integer, default=0)
    # 审批模式：any（任一通过）/ joint（联合）
    approval_mode = mapped_column(String(20), default="any")
    requester_id = mapped_column(Integer, nullable=True)
    requester_name = mapped_column(String(100), nullable=True)
    return_reason = mapped_column(Text, nullable=True)
    modify_note = mapped_column(Text, nullable=True)
    approver_id = mapped_column(Integer, nullable=True)
    approver_name = mapped_column(String(100), nullable=True)
    approved_at = mapped_column(DateTime, nullable=True)
    # 已通过的审核人列表（联合模式用）
    approvals = mapped_column(JSON, nullable=True)
    # 操作留痕
    history = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditCode(Base):
    """审核短信验证码记录"""
    __tablename__ = "audit_codes"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone = mapped_column(String(20), nullable=False, index=True)
    code = mapped_column(String(10), nullable=False)
    request_id = mapped_column(Integer, nullable=True, index=True)
    expires_at = mapped_column(DateTime, nullable=False)
    used = mapped_column(Boolean, default=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AuditLockout(Base):
    """验证码错误锁定记录"""
    __tablename__ = "audit_lockouts"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone = mapped_column(String(20), nullable=False, index=True)
    fail_count = mapped_column(Integer, default=0)
    locked_until = mapped_column(DateTime, nullable=True)
    last_fail_at = mapped_column(DateTime, default=datetime.utcnow)


# ──────────────── 统一订单 ────────────────


class UnifiedOrder(Base):
    __tablename__ = "unified_orders"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no = mapped_column(String(50), unique=True, nullable=False, index=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    total_amount = mapped_column(Numeric(10, 2), nullable=False)
    paid_amount = mapped_column(Numeric(10, 2), default=0)
    points_deduction = mapped_column(Integer, default=0)
    payment_method = mapped_column(Enum(UnifiedPaymentMethod), nullable=True)
    coupon_id = mapped_column(Integer, ForeignKey("coupons.id"), nullable=True)
    coupon_discount = mapped_column(Numeric(10, 2), default=0)
    status = mapped_column(Enum(UnifiedOrderStatus), default=UnifiedOrderStatus.pending_payment)
    refund_status = mapped_column(Enum(RefundStatusEnum), default=RefundStatusEnum.none)
    shipping_address_id = mapped_column(Integer, ForeignKey("user_addresses.id"), nullable=True)
    shipping_info = mapped_column(JSON, nullable=True)
    tracking_number = mapped_column(String(100), nullable=True)
    tracking_company = mapped_column(String(100), nullable=True)
    notes = mapped_column(Text, nullable=True)
    payment_timeout_minutes = mapped_column(Integer, default=15)
    paid_at = mapped_column(DateTime, nullable=True)
    shipped_at = mapped_column(DateTime, nullable=True)
    received_at = mapped_column(DateTime, nullable=True)
    completed_at = mapped_column(DateTime, nullable=True)
    cancelled_at = mapped_column(DateTime, nullable=True)
    cancel_reason = mapped_column(Text, nullable=True)
    auto_confirm_days = mapped_column(Integer, default=7)
    has_reviewed = mapped_column(Boolean, default=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")
    coupon = relationship("Coupon")
    shipping_address = relationship("UserAddress")
    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id = mapped_column(Integer, ForeignKey("unified_orders.id"), nullable=False, index=True)
    product_id = mapped_column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    sku_id = mapped_column(Integer, ForeignKey("product_skus.id"), nullable=True, index=True)
    sku_name = mapped_column(String(50), nullable=True)
    product_name = mapped_column(String(200), nullable=False)
    product_image = mapped_column(String(500), nullable=True)
    product_price = mapped_column(Numeric(10, 2), nullable=False)
    quantity = mapped_column(Integer, default=1)
    subtotal = mapped_column(Numeric(10, 2), nullable=False)
    fulfillment_type = mapped_column(Enum(FulfillmentType), nullable=False)
    verification_code = mapped_column(String(20), nullable=True)
    verification_qrcode_token = mapped_column(String(100), nullable=True)
    total_redeem_count = mapped_column(Integer, default=1)
    used_redeem_count = mapped_column(Integer, default=0)
    appointment_data = mapped_column(JSON, nullable=True)
    appointment_time = mapped_column(DateTime, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = relationship("UnifiedOrder", back_populates="items")
    product = relationship("Product")


class OrderRedemption(Base):
    __tablename__ = "order_redemptions"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_item_id = mapped_column(Integer, ForeignKey("order_items.id"), nullable=False, index=True)
    redeemed_by_user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    store_id = mapped_column(Integer, ForeignKey("merchant_stores.id"), nullable=True)
    redeemed_at = mapped_column(DateTime, default=datetime.utcnow)
    notes = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    order_item = relationship("OrderItem")
    redeemed_by = relationship("User")
    store = relationship("MerchantStore")


# ──────────────── 会员码与签到 ────────────────


class MemberQRToken(Base):
    __tablename__ = "member_qr_tokens"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = mapped_column(String(100), unique=True, nullable=False)
    expires_at = mapped_column(DateTime, nullable=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class CheckinRecord(Base):
    __tablename__ = "checkin_records"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    store_id = mapped_column(Integer, ForeignKey("merchant_stores.id"), nullable=False, index=True)
    staff_user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    points_earned = mapped_column(Integer, default=0)
    checked_in_at = mapped_column(DateTime, default=datetime.utcnow)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])
    store = relationship("MerchantStore")
    staff = relationship("User", foreign_keys=[staff_user_id])


class StoreVisitRecord(Base):
    __tablename__ = "store_visit_records"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    store_id = mapped_column(Integer, ForeignKey("merchant_stores.id"), nullable=False, index=True)
    staff_user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    visited_at = mapped_column(DateTime, default=datetime.utcnow)
    consumption_amount = mapped_column(Numeric(10, 2), default=0)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])
    store = relationship("MerchantStore")
    staff = relationship("User", foreign_keys=[staff_user_id])


# ──────────────── 退款 ────────────────


class RefundRequest(Base):
    __tablename__ = "refund_requests"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id = mapped_column(Integer, ForeignKey("unified_orders.id"), nullable=False, index=True)
    order_item_id = mapped_column(Integer, ForeignKey("order_items.id"), nullable=True, index=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reason = mapped_column(Text, nullable=True)
    refund_amount = mapped_column(Numeric(10, 2), nullable=False)
    status = mapped_column(Enum(RefundRequestStatus), default=RefundRequestStatus.pending)
    admin_user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    admin_notes = mapped_column(Text, nullable=True)
    return_tracking_number = mapped_column(String(100), nullable=True)
    return_tracking_company = mapped_column(String(100), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = relationship("UnifiedOrder")
    order_item = relationship("OrderItem")
    user = relationship("User", foreign_keys=[user_id])
    admin = relationship("User", foreign_keys=[admin_user_id])
