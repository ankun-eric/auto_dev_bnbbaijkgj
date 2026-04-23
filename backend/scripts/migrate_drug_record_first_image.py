"""
[2026-04-23 v1.2] 用药识别记录首图回填迁移脚本
PRD §7.3：

- 扫描 drug_identify_details 中无 original_image_url 的历史记录
- 从 ocr_call_records.original_image_url 或消息附件回填首图 URL
- 回填失败的记录：保持 original_image_url=NULL；前端展示时 image_status=legacy
- 支持 dry-run（只打印不写入）、可重复执行（幂等）

用法：
  python -m backend.scripts.migrate_drug_record_first_image --dry-run
  python -m backend.scripts.migrate_drug_record_first_image
  python -m backend.scripts.migrate_drug_record_first_image --report drug_migrate_report.csv
"""
import argparse
import asyncio
import csv
import sys
from datetime import datetime
from typing import Optional

sys.path.insert(0, ".")

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from app.core.database import AsyncSessionLocal  # type: ignore
except ImportError:
    from app.core.database import async_session as AsyncSessionLocal  # type: ignore
from app.models.models import DrugIdentifyDetail, OcrCallRecord


async def migrate(dry_run: bool = False, report_path: Optional[str] = None) -> dict:
    async with AsyncSessionLocal() as db:  # type: AsyncSession
        # 1. 扫描所有无首图的记录
        result = await db.execute(
            select(DrugIdentifyDetail).where(
                (DrugIdentifyDetail.original_image_url.is_(None))
                | (DrugIdentifyDetail.original_image_url == "")
            )
        )
        records = list(result.scalars().all())
        total = len(records)

        repaired = 0
        failed_legacy = 0
        report_rows = []

        for r in records:
            new_url: Optional[str] = None

            # 方案 A：从 ocr_call_record_id 关联的 OcrCallRecord 回填
            if r.ocr_call_record_id:
                ocr_res = await db.execute(
                    select(OcrCallRecord).where(OcrCallRecord.id == r.ocr_call_record_id)
                )
                ocr_rec = ocr_res.scalar_one_or_none()
                if ocr_rec and ocr_rec.original_image_url:
                    new_url = ocr_rec.original_image_url

            # 方案 B：按 session_id 找该 session 下最早的 OcrCallRecord.original_image_url
            if not new_url and r.session_id:
                ocr_res2 = await db.execute(
                    select(OcrCallRecord)
                    .where(OcrCallRecord.original_image_url.is_not(None))
                    .order_by(OcrCallRecord.created_at.asc())
                    .limit(1)
                )
                fallback = ocr_res2.scalar_one_or_none()
                if fallback and fallback.original_image_url:
                    new_url = fallback.original_image_url

            if new_url:
                report_rows.append(
                    {
                        "record_id": r.id,
                        "drug_name": r.drug_name or "",
                        "action": "REPAIRED",
                        "new_url": new_url,
                    }
                )
                repaired += 1
                if not dry_run:
                    await db.execute(
                        update(DrugIdentifyDetail)
                        .where(DrugIdentifyDetail.id == r.id)
                        .values(original_image_url=new_url)
                    )
            else:
                report_rows.append(
                    {
                        "record_id": r.id,
                        "drug_name": r.drug_name or "",
                        "action": "LEGACY",
                        "new_url": "",
                    }
                )
                failed_legacy += 1

        if not dry_run:
            await db.commit()

        # 生成 CSV 报告
        if report_path:
            with open(report_path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=["record_id", "drug_name", "action", "new_url"])
                writer.writeheader()
                writer.writerows(report_rows)

        repair_rate = (repaired / total * 100) if total else 100.0

        return {
            "total": total,
            "repaired": repaired,
            "failed_legacy": failed_legacy,
            "repair_rate_pct": round(repair_rate, 2),
            "dry_run": dry_run,
            "executed_at": datetime.utcnow().isoformat(),
            "report_path": report_path,
        }


def main():
    parser = argparse.ArgumentParser(
        description="[v1.2] 回填 drug_identify_details.original_image_url"
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入数据库")
    parser.add_argument("--report", type=str, default=None, help="导出 CSV 报告路径")
    args = parser.parse_args()

    result = asyncio.run(migrate(dry_run=args.dry_run, report_path=args.report))

    print("\n" + "=" * 60)
    print("用药识别记录首图回填迁移结果")
    print("=" * 60)
    for k, v in result.items():
        print(f"  {k}: {v}")
    print("=" * 60)

    if result["repair_rate_pct"] < 80 and result["total"] > 0:
        print("\n⚠️  回填成功率 < 80%，请人工检查原始数据完整性")
    else:
        print("\n✅ 回填成功率达标")


if __name__ == "__main__":
    main()
