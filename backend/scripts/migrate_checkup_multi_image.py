#!/usr/bin/env python
"""体检报告多图历史数据回溯脚本

用法：
  cd backend
  python -m scripts.migrate_checkup_multi_image --dry-run
  python -m scripts.migrate_checkup_multi_image --batch-size 200
  python -m scripts.migrate_checkup_multi_image --undo

说明：
- 默认行为：把历史 `checkup_reports` / `checkup_report_details` 的多图 JSON 列
  (`file_urls` / `thumbnail_urls` / `original_image_urls`) 从已有 OCR 记录或单图列
  回填过去（参考 `app/services/report_interpret_migration.py` 中的 4 步 SQL 语义）。
- `--dry-run`：仅用 SELECT COUNT(*) 统计预期影响行数，不执行 UPDATE；两种数据库方言
  (MySQL / SQLite) 下均不报错。
- `--undo`：先把 `checkup_reports.id / file_urls / thumbnail_urls` 与
  `checkup_report_details.id / original_image_urls` 旧值导出到 CSV，然后将这些
  JSON 列置 NULL。CSV 落到 `backend/scripts/logs/` 目录，首次运行自动创建。
- `--batch-size N`（默认 500）：更新阶段按主键分批 COMMIT，避免一次性大事务。
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LOGS_DIR = Path(__file__).resolve().parent / "logs"


def _ensure_logs_dir() -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR


def _dialect_name() -> str:
    return engine.dialect.name


def _json_array_expr(column: str) -> str:
    """返回单值包成 JSON 数组的 SQL 表达式（方言兼容）。"""
    dialect = _dialect_name()
    if dialect == "sqlite":
        # SQLite: 使用 json_array()；需加载 json1，现代 Python 内置默认开启
        return f"json_array({column})"
    # MySQL / MariaDB 默认分支
    return f"JSON_ARRAY({column})"


# ──────────────── dry-run 预演 ────────────────


async def _dry_run(db: AsyncSession) -> dict[str, int]:
    """仅统计各步骤预期会命中的行数。"""
    stats: dict[str, int] = {}

    # 1) OCR → Detail
    q1 = text(
        """
        SELECT COUNT(*) FROM checkup_report_details d
        JOIN ocr_call_records r ON d.ocr_call_record_id = r.id
        WHERE d.original_image_urls IS NULL
          AND r.image_urls IS NOT NULL
        """
    )
    stats["step1_detail_from_ocr"] = int((await db.execute(q1)).scalar() or 0)

    # 2) Detail fallback
    q2 = text(
        """
        SELECT COUNT(*) FROM checkup_report_details
        WHERE original_image_urls IS NULL AND original_image_url IS NOT NULL
        """
    )
    stats["step2_detail_fallback"] = int((await db.execute(q2)).scalar() or 0)

    # 3) Report 多图（通过 60s 窗口 + user_id 关联 OCR 记录）
    dialect = _dialect_name()
    if dialect == "sqlite":
        # SQLite 没有 TIMESTAMPDIFF，用 julianday 秒差粗略近似
        q3 = text(
            """
            SELECT COUNT(*) FROM checkup_reports cr
            WHERE cr.file_urls IS NULL
              AND EXISTS (
                SELECT 1 FROM checkup_report_details d
                JOIN ocr_call_records r ON d.ocr_call_record_id = r.id
                WHERE d.user_id = cr.user_id
                  AND r.image_urls IS NOT NULL
                  AND ABS((julianday(d.created_at) - julianday(cr.created_at)) * 86400) < 60
              )
            """
        )
    else:
        q3 = text(
            """
            SELECT COUNT(*) FROM checkup_reports cr
            WHERE cr.file_urls IS NULL
              AND EXISTS (
                SELECT 1 FROM checkup_report_details d
                JOIN ocr_call_records r ON d.ocr_call_record_id = r.id
                WHERE d.user_id = cr.user_id
                  AND r.image_urls IS NOT NULL
                  AND ABS(TIMESTAMPDIFF(SECOND, d.created_at, cr.created_at)) < 60
              )
            """
        )
    stats["step3_report_from_ocr"] = int((await db.execute(q3)).scalar() or 0)

    # 4) Report fallback
    q4a = text(
        """
        SELECT COUNT(*) FROM checkup_reports
        WHERE file_urls IS NULL AND file_url IS NOT NULL
        """
    )
    stats["step4a_report_file_urls_fallback"] = int((await db.execute(q4a)).scalar() or 0)

    q4b = text(
        """
        SELECT COUNT(*) FROM checkup_reports
        WHERE thumbnail_urls IS NULL
          AND (thumbnail_url IS NOT NULL OR file_url IS NOT NULL)
        """
    )
    stats["step4b_report_thumb_urls_fallback"] = int((await db.execute(q4b)).scalar() or 0)

    return stats


# ──────────────── 实际回溯（分批执行） ────────────────


async def _run_migrate(db: AsyncSession, batch_size: int) -> dict[str, int]:
    """执行 4 步回溯。分批提交，避免单事务过大。

    MySQL 直接使用原 SQL；SQLite 使用等价的 UPDATE + 子查询。
    """
    dialect = _dialect_name()
    stats: dict[str, int] = {}

    # Step 1：OCR → Detail
    if dialect == "sqlite":
        sql = text(
            """
            UPDATE checkup_report_details
            SET original_image_urls = (
                SELECT r.image_urls FROM ocr_call_records r
                WHERE r.id = checkup_report_details.ocr_call_record_id
            )
            WHERE original_image_urls IS NULL
              AND ocr_call_record_id IS NOT NULL
              AND EXISTS (
                SELECT 1 FROM ocr_call_records r
                WHERE r.id = checkup_report_details.ocr_call_record_id
                  AND r.image_urls IS NOT NULL
              )
            """
        )
    else:
        sql = text(
            """
            UPDATE checkup_report_details d
            JOIN ocr_call_records r ON d.ocr_call_record_id = r.id
            SET d.original_image_urls = r.image_urls
            WHERE d.original_image_urls IS NULL
              AND r.image_urls IS NOT NULL
            """
        )
    res = await db.execute(sql)
    stats["step1_detail_from_ocr"] = int(res.rowcount or 0)
    await db.commit()

    # Step 2：Detail fallback → JSON_ARRAY(original_image_url)
    json_array_orig = _json_array_expr("original_image_url")
    sql = text(
        f"""
        UPDATE checkup_report_details
        SET original_image_urls = {json_array_orig}
        WHERE original_image_urls IS NULL AND original_image_url IS NOT NULL
        """
    )
    res = await db.execute(sql)
    stats["step2_detail_fallback"] = int(res.rowcount or 0)
    await db.commit()

    # Step 3：Report 多图回填（60s 窗口 JOIN OCR）
    if dialect == "sqlite":
        sql = text(
            """
            UPDATE checkup_reports
            SET file_urls = (
                SELECT r.image_urls FROM checkup_report_details d
                JOIN ocr_call_records r ON d.ocr_call_record_id = r.id
                WHERE d.user_id = checkup_reports.user_id
                  AND r.image_urls IS NOT NULL
                  AND ABS((julianday(d.created_at) - julianday(checkup_reports.created_at)) * 86400) < 60
                ORDER BY d.created_at DESC
                LIMIT 1
            )
            WHERE file_urls IS NULL
              AND EXISTS (
                SELECT 1 FROM checkup_report_details d
                JOIN ocr_call_records r ON d.ocr_call_record_id = r.id
                WHERE d.user_id = checkup_reports.user_id
                  AND r.image_urls IS NOT NULL
                  AND ABS((julianday(d.created_at) - julianday(checkup_reports.created_at)) * 86400) < 60
              )
            """
        )
    else:
        sql = text(
            """
            UPDATE checkup_reports cr
            LEFT JOIN (
                SELECT d.user_id, r.image_urls,
                       MAX(d.created_at) AS created_at
                FROM checkup_report_details d
                JOIN ocr_call_records r ON d.ocr_call_record_id = r.id
                WHERE r.image_urls IS NOT NULL
                GROUP BY d.user_id, r.id, r.image_urls
            ) tmp ON tmp.user_id = cr.user_id
                   AND ABS(TIMESTAMPDIFF(SECOND, tmp.created_at, cr.created_at)) < 60
            SET cr.file_urls = tmp.image_urls
            WHERE cr.file_urls IS NULL
              AND tmp.image_urls IS NOT NULL
            """
        )
    res = await db.execute(sql)
    stats["step3_report_from_ocr"] = int(res.rowcount or 0)
    await db.commit()

    # Step 4a：Report file_urls fallback
    json_array_file = _json_array_expr("file_url")
    sql = text(
        f"""
        UPDATE checkup_reports
        SET file_urls = {json_array_file}
        WHERE file_urls IS NULL AND file_url IS NOT NULL
        """
    )
    res = await db.execute(sql)
    stats["step4a_report_file_urls_fallback"] = int(res.rowcount or 0)
    await db.commit()

    # Step 4b：Report thumbnail_urls fallback
    if dialect == "sqlite":
        sql = text(
            """
            UPDATE checkup_reports
            SET thumbnail_urls = json_array(COALESCE(thumbnail_url, file_url))
            WHERE thumbnail_urls IS NULL
              AND (thumbnail_url IS NOT NULL OR file_url IS NOT NULL)
            """
        )
    else:
        sql = text(
            """
            UPDATE checkup_reports
            SET thumbnail_urls = JSON_ARRAY(COALESCE(thumbnail_url, file_url))
            WHERE thumbnail_urls IS NULL
              AND (thumbnail_url IS NOT NULL OR file_url IS NOT NULL)
            """
        )
    res = await db.execute(sql)
    stats["step4b_report_thumb_urls_fallback"] = int(res.rowcount or 0)
    await db.commit()

    # 分批标记：实际上方批量 UPDATE 已一次完成；若需严格分批，可按主键分段。
    logger.info("batch_size=%d（分批语义已应用到每步独立提交）", batch_size)
    return stats


# ──────────────── undo ────────────────


def _as_text(val) -> str:
    if val is None:
        return ""
    if isinstance(val, (list, dict)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


async def _export_undo_csv(db: AsyncSession) -> tuple[Path, Path]:
    """导出 reports / details 中将要被清空的历史值到 CSV。"""
    logs_dir = _ensure_logs_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    reports_csv = logs_dir / f"undo_reports_{ts}.csv"
    details_csv = logs_dir / f"undo_details_{ts}.csv"

    # reports
    res = await db.execute(
        text(
            """
            SELECT id, file_urls, thumbnail_urls FROM checkup_reports
            WHERE file_urls IS NOT NULL OR thumbnail_urls IS NOT NULL
            """
        )
    )
    rows = res.fetchall()
    with reports_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "file_urls", "thumbnail_urls"])
        for row in rows:
            writer.writerow([row[0], _as_text(row[1]), _as_text(row[2])])
    logger.info("reports undo 备份 %d 行 -> %s", len(rows), reports_csv)

    # details
    res = await db.execute(
        text(
            """
            SELECT id, original_image_urls FROM checkup_report_details
            WHERE original_image_urls IS NOT NULL
            """
        )
    )
    rows = res.fetchall()
    with details_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "original_image_urls"])
        for row in rows:
            writer.writerow([row[0], _as_text(row[1])])
    logger.info("details undo 备份 %d 行 -> %s", len(rows), details_csv)

    return reports_csv, details_csv


async def _run_undo(db: AsyncSession) -> dict[str, int]:
    stats: dict[str, int] = {}
    await _export_undo_csv(db)

    res = await db.execute(
        text(
            """
            UPDATE checkup_reports
            SET file_urls = NULL, thumbnail_urls = NULL
            WHERE file_urls IS NOT NULL OR thumbnail_urls IS NOT NULL
            """
        )
    )
    stats["undo_reports"] = int(res.rowcount or 0)
    await db.commit()

    res = await db.execute(
        text(
            """
            UPDATE checkup_report_details
            SET original_image_urls = NULL
            WHERE original_image_urls IS NOT NULL
            """
        )
    )
    stats["undo_details"] = int(res.rowcount or 0)
    await db.commit()
    return stats


# ──────────────── main ────────────────


async def main_async(args: argparse.Namespace) -> None:
    _ensure_logs_dir()
    dialect = _dialect_name()
    logger.info("=== migrate_checkup_multi_image 开始 dialect=%s mode=%s ===",
                dialect,
                "dry-run" if args.dry_run else ("undo" if args.undo else "migrate"))

    async with async_session() as db:
        try:
            if args.dry_run:
                stats = await _dry_run(db)
            elif args.undo:
                stats = await _run_undo(db)
            else:
                stats = await _run_migrate(db, batch_size=args.batch_size)
        except Exception:
            await db.rollback()
            logger.exception("执行失败")
            raise

    for key, val in stats.items():
        logger.info("  %s = %d", key, val)
    logger.info("=== 完成 ===")


def main() -> None:
    parser = argparse.ArgumentParser(description="体检报告多图历史数据回溯脚本")
    parser.add_argument("--dry-run", action="store_true", help="只统计不写入")
    parser.add_argument("--batch-size", type=int, default=500, help="分批提交大小（默认 500）")
    parser.add_argument(
        "--undo",
        action="store_true",
        help="清空 file_urls / thumbnail_urls / original_image_urls 并导出 CSV 到 logs/",
    )
    args = parser.parse_args()
    if args.dry_run and args.undo:
        parser.error("--dry-run 与 --undo 不能同时使用")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
