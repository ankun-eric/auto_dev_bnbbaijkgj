import enum
from datetime import date, datetime

from sqlalchemy import (
    JSON,
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
)
from sqlalchemy.orm import mapped_column, relationship

from app.core.database import Base


# ──────────────── Enums ────────────────


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"
    doctor = "doctor"
    merchant = "merchant"


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
    drug_query = "drug_query"
    customer_service = "customer_service"


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
    deduct = "deduct"


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


class PointsMallItemType(str, enum.Enum):
    virtual = "virtual"
    physical = "physical"
    service = "service"
    third_party = "third_party"


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
    member_level = mapped_column(Integer, default=0)
    points = mapped_column(Integer, default=0)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    health_profile = relationship("HealthProfile", back_populates="user", uselist=False)
    family_members = relationship("FamilyMember", back_populates="user", foreign_keys="FamilyMember.user_id")
    chat_sessions = relationship("ChatSession", back_populates="user")
    orders = relationship("Order", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    points_records = relationship("PointsRecord", back_populates="user")
    health_plans = relationship("HealthPlan", back_populates="user")
    articles = relationship("Article", back_populates="author")


class FamilyMember(Base):
    __tablename__ = "family_members"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    member_user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    relationship_type = mapped_column(String(50), nullable=False)
    nickname = mapped_column(String(100), nullable=True)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="family_members", foreign_keys=[user_id])
    member_user = relationship("User", foreign_keys=[member_user_id])


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
    user_id = mapped_column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
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
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="health_profile")


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
    ocr_result = mapped_column(JSON, nullable=True)
    ai_analysis = mapped_column(Text, nullable=True)
    indicators = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    checkup_indicators = relationship("CheckupIndicator", back_populates="report")


class CheckupIndicator(Base):
    __tablename__ = "checkup_indicators"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id = mapped_column(Integer, ForeignKey("checkup_reports.id"), nullable=False, index=True)
    indicator_name = mapped_column(String(100), nullable=False)
    value = mapped_column(String(50), nullable=True)
    unit = mapped_column(String(50), nullable=True)
    reference_range = mapped_column(String(100), nullable=True)
    status = mapped_column(Enum(IndicatorStatus), default=IndicatorStatus.normal)
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
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


# ──────────────── 中医辨证 ────────────────


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
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
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
    min_points = mapped_column(Integer, default=0)
    max_points = mapped_column(Integer, default=0)
    discount_rate = mapped_column(Float, default=1.0)
    benefits = mapped_column(JSON, nullable=True)
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
    type = mapped_column(Enum(PointsMallItemType), default=PointsMallItemType.virtual)
    price_points = mapped_column(Integer, nullable=False)
    stock = mapped_column(Integer, default=0)
    status = mapped_column(String(20), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)


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
    cover_image = mapped_column(String(500), nullable=True)
    author_id = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    category = mapped_column(String(50), nullable=True)
    tags = mapped_column(JSON, nullable=True)
    view_count = mapped_column(Integer, default=0)
    like_count = mapped_column(Integer, default=0)
    status = mapped_column(Enum(ContentStatus), default=ContentStatus.draft)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author = relationship("User", back_populates="articles")


class Video(Base):
    __tablename__ = "videos"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    title = mapped_column(String(300), nullable=False)
    description = mapped_column(Text, nullable=True)
    video_url = mapped_column(String(500), nullable=False)
    cover_image = mapped_column(String(500), nullable=True)
    author_id = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    category = mapped_column(String(50), nullable=True)
    duration = mapped_column(Integer, default=0)
    view_count = mapped_column(Integer, default=0)
    like_count = mapped_column(Integer, default=0)
    status = mapped_column(Enum(ContentStatus), default=ContentStatus.draft)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    author = relationship("User")


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
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SmsConfig(Base):
    __tablename__ = "sms_configs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    secret_id = mapped_column(String(255), nullable=True)
    secret_key_encrypted = mapped_column(String(500), nullable=True)
    sdk_app_id = mapped_column(String(50), nullable=True)
    sign_name = mapped_column(String(100), nullable=True)
    template_id = mapped_column(String(50), nullable=True)
    app_key = mapped_column(String(255), nullable=True)
    is_active = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SmsLog(Base):
    __tablename__ = "sms_logs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone = mapped_column(String(20), nullable=False, index=True)
    code = mapped_column(String(10), nullable=True)
    template_id = mapped_column(String(50), nullable=True)
    status = mapped_column(String(20), nullable=False)
    error_message = mapped_column(Text, nullable=True)
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
