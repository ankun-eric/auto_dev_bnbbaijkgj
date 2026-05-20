"""[PRD-AI-PAGE-OPTIM-V1 2026-05-21] 种子包数据中心

把过去散落在 4 个迁移脚本里的「启动时自动写入种子数据」，
集中收敛到本目录下，由「管理后台 → 系统设置 → 种子数据导入」按需触发。

每个种子包都是一个 SeedPackDefinition，包含：
- code: 唯一标识
- name: 中文名
- description: 简介
- summary: 内容摘要
- source: 标准/出处
- install(db): 安装函数（事务由调用方包裹）
- uninstall(db): 卸载函数
- detect(db): 检测当前数据库状态，返回 'installed' / 'not_installed' / 'partial' / 'modified'
"""

from .registry import SEED_PACK_REGISTRY, SeedPackDefinition, list_packs, get_pack

__all__ = ["SEED_PACK_REGISTRY", "SeedPackDefinition", "list_packs", "get_pack"]
