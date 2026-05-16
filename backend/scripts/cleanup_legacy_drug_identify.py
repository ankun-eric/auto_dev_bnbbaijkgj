"""[BUG_FIX_用药识别千图一答 2026-05-16] 历史"假识别"数据清理脚本

历史问题：在视觉模型升级之前，``/api/drugs/identify`` 走的是"纯文本模型 + 文件名描述"
链路，所有用户的拍照识药结果都是模型瞎编的常见药品。这些数据本身没有任何参考价值，
继续保留会让用户基于错误识别结果做出错误用药决策（合规与安全风险）。

本脚本会：

1. **先备份**：把全部历史 ``drug_identify_details`` 行复制到归档表
   ``drug_identify_details_archive_legacy_20260516``（首次运行时自动 CREATE TABLE）。
2. **再清理**：删除新版上线之前产生的"假识别"记录，按以下两个条件取并集：
    - ``ai_structured_result`` 为空 / 缺少标准字段（旧版没有视觉结构化输出）；
    - 或 ``created_at < CUTOFF_TIME``（视觉版部署时间）。
3. 同时清理与其关联的 ``ocr_call_records`` 中 ``scene_name='拍照识药'``且
   ``ai_structured_result`` 为空的"伪识别"流水。

使用方式（在后端容器内）::

    python -m backend.scripts.cleanup_legacy_drug_identify --apply

不加 ``--apply`` 时默认 dry-run，只打印将要影响的行数，不动数据。
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# 允许从 backend/ 直接运行
HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text  # noqa: E402

from app.core.database import async_session  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# 视觉版用药识别上线时间（建议保留一个稍早的安全时间），早于该时间的全部 detail 视为旧版"假识别"
CUTOFF_TIME = os.environ.get("DRUG_VLM_CUTOFF_TIME", "2026-05-16 16:00:00")

ARCHIVE_TABLE = "drug_identify_details_archive_legacy_20260516"


async def main(apply_changes: bool) -> int:
    async with async_session() as session:
        # 0. 总数
        total_row = await session.execute(text("SELECT COUNT(*) FROM drug_identify_details"))
        total = total_row.scalar_one() or 0
        logger.info("当前 drug_identify_details 总记录数：%d", total)
        if total == 0:
            logger.info("无任何用药识别历史记录，无需清理。")
            return 0

        # 1. 备份（CREATE TABLE LIKE + INSERT SELECT，幂等）
        if apply_changes:
            await session.execute(
                text(f"CREATE TABLE IF NOT EXISTS {ARCHIVE_TABLE} LIKE drug_identify_details")
            )
            arch_count_row = await session.execute(text(f"SELECT COUNT(*) FROM {ARCHIVE_TABLE}"))
            arch_count = arch_count_row.scalar_one() or 0
            if arch_count == 0:
                await session.execute(
                    text(f"INSERT INTO {ARCHIVE_TABLE} SELECT * FROM drug_identify_details")
                )
                logger.info("已把 %d 行原始数据备份到 %s", total, ARCHIVE_TABLE)
            else:
                logger.info("%s 已存在 %d 行备份，跳过重复备份", ARCHIVE_TABLE, arch_count)
        else:
            logger.info("[dry-run] 将创建归档表 %s 并备份 %d 行（实际未执行）", ARCHIVE_TABLE, total)

        # 2. 定位"旧版假识别"记录
        # 判定条件：created_at < CUTOFF_TIME 或 ai_structured_result 为 NULL/{}
        detail_q = text(
            """
            SELECT COUNT(*) FROM drug_identify_details
            WHERE created_at < :cutoff
               OR ai_structured_result IS NULL
               OR JSON_EXTRACT(ai_structured_result, '$.medicines') IS NULL
            """
        )
        detail_cnt_row = await session.execute(detail_q, {"cutoff": CUTOFF_TIME})
        detail_cnt = detail_cnt_row.scalar_one() or 0
        logger.info("旧版假识别 drug_identify_details 命中行数：%d / %d", detail_cnt, total)

        ocr_q = text(
            """
            SELECT COUNT(*) FROM ocr_call_records
            WHERE scene_name = '拍照识药'
              AND (created_at < :cutoff OR ai_structured_result IS NULL)
            """
        )
        ocr_cnt_row = await session.execute(ocr_q, {"cutoff": CUTOFF_TIME})
        ocr_cnt = ocr_cnt_row.scalar_one() or 0
        logger.info("旧版假识别 ocr_call_records（拍照识药）命中行数：%d", ocr_cnt)

        if not apply_changes:
            logger.info("[dry-run] 未执行任何 DELETE，加 --apply 才会真正删除。")
            return 0

        # 3. 真正清理
        del_detail = await session.execute(
            text(
                """
                DELETE FROM drug_identify_details
                WHERE created_at < :cutoff
                   OR ai_structured_result IS NULL
                   OR JSON_EXTRACT(ai_structured_result, '$.medicines') IS NULL
                """
            ),
            {"cutoff": CUTOFF_TIME},
        )
        del_ocr = await session.execute(
            text(
                """
                DELETE FROM ocr_call_records
                WHERE scene_name = '拍照识药'
                  AND (created_at < :cutoff OR ai_structured_result IS NULL)
                """
            ),
            {"cutoff": CUTOFF_TIME},
        )
        await session.commit()
        logger.info("已删除 drug_identify_details 行数：%d", del_detail.rowcount or 0)
        logger.info("已删除 ocr_call_records 行数：%d", del_ocr.rowcount or 0)
        logger.info("备份表 %s 仍保留全部原始数据，可随时恢复。", ARCHIVE_TABLE)
        return 0


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="真正执行清理；不加该参数默认 dry-run。",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    started = datetime.utcnow()
    code = asyncio.run(main(apply_changes=args.apply))
    elapsed = (datetime.utcnow() - started).total_seconds()
    logger.info("清理脚本结束（apply=%s, elapsed=%.1fs）", args.apply, elapsed)
    sys.exit(code)
