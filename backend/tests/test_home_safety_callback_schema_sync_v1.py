"""[BUGFIX HS-V2-ALTER 2026-05-28] 回归测试：确保 schema_sync 中包含 home_safety 回调表 7 个新字段的自动迁移。

背景：发布 HOME-SAFETY-V2-REVISION 后，ORM 模型新增了 7 个字段（log 表 6 个 + config 表 1 个），
但 _sync_home_safety_v2 没有对已存在的表执行 ALTER，导致线上 MySQL 触发 1054 Unknown column / HTTP 500。
本测试通过静态扫描 schema_sync.py 源码，确保每个新字段都有对应的 ADD COLUMN 语句。
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def schema_sync_source() -> str:
    p = Path(__file__).resolve().parent.parent / "app" / "services" / "schema_sync.py"
    return p.read_text(encoding="utf-8")


_LOG_FIELDS = [
    ("request_method", "ALTER TABLE home_safety_callback_log ADD COLUMN request_method"),
    ("request_url", "ALTER TABLE home_safety_callback_log ADD COLUMN request_url"),
    ("response_status", "ALTER TABLE home_safety_callback_log ADD COLUMN response_status"),
    ("response_body", "ALTER TABLE home_safety_callback_log ADD COLUMN response_body"),
    ("processed_at", "ALTER TABLE home_safety_callback_log ADD COLUMN processed_at"),
    ("device_sn", "ALTER TABLE home_safety_callback_log ADD COLUMN device_sn"),
]


@pytest.mark.parametrize("field_name, alter_snippet", _LOG_FIELDS)
def test_callback_log_has_alter_for_field(schema_sync_source: str, field_name: str, alter_snippet: str):
    assert alter_snippet in schema_sync_source, (
        f"[HS-V2-ALTER] schema_sync 缺少 home_safety_callback_log.{field_name} 的 ALTER 语句，"
        f"将导致已存在该表的环境查询时报 1054 Unknown column / HTTP 500"
    )


def test_callback_config_has_alter_for_last_push_judge_basis(schema_sync_source: str):
    snippet = "ALTER TABLE home_safety_callback_config ADD COLUMN last_push_judge_basis"
    assert snippet in schema_sync_source, (
        "[HS-V2-ALTER] schema_sync 缺少 home_safety_callback_config.last_push_judge_basis 的 ALTER 语句，"
        "将导致已存在该表的环境保存配置时报 1054 Unknown column / HTTP 500"
    )
