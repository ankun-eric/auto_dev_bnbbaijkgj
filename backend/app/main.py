import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import (
    admin,
    admin_merchant,
    admin_search,
    ai_center,
    auth,
    chat,
    chat_history,
    content,
    cos,
    customer_service,
    drug,
    drug_identify_share,
    email_notify,
    expert,
    family,
    health_profile,
    home_config,
    knowledge,
    notice,
    notification,
    ocr,
    ocr_details,
    order,
    plan,
    points,
    merchant,
    prompt_templates,
    report,
    search,
    service,
    sms,
    tcm,
    upload,
    wechat_push,
)
from app.core.database import Base, engine
from app.services.schema_sync import sync_register_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await sync_register_schema(conn)
    from app.init_data import init_default_data
    await init_default_data()
    yield


app = FastAPI(title="宾尼小康 AI健康管家", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(health_profile.router)
app.include_router(chat.router)
app.include_router(chat_history.router)
app.include_router(tcm.router)
app.include_router(service.router)
app.include_router(order.router)
app.include_router(expert.router)
app.include_router(points.router)
app.include_router(plan.router)
app.include_router(family.router)
app.include_router(content.router)
app.include_router(notification.router)
app.include_router(customer_service.router)
app.include_router(drug.router)
app.include_router(upload.router)
app.include_router(admin.router)
app.include_router(admin_merchant.router)
app.include_router(merchant.router)
app.include_router(sms.router)
app.include_router(email_notify.router)
app.include_router(wechat_push.router)
app.include_router(knowledge.router)
app.include_router(cos.router)
app.include_router(ai_center.router)
app.include_router(report.router)
app.include_router(report.admin_router)
app.include_router(ocr.router)
app.include_router(ocr.admin_router)
app.include_router(ocr_details.router)
app.include_router(ocr_details.user_router)
app.include_router(prompt_templates.router)
app.include_router(drug_identify_share.router)
app.include_router(home_config.router)
app.include_router(home_config.admin_router)
app.include_router(notice.router)
app.include_router(notice.admin_router)
app.include_router(search.router)
app.include_router(admin_search.router)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "bini-health-api"}
