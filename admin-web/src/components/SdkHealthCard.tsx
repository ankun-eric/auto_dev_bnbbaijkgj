'use client';

/**
 * [2026-05-05 SDK 健康看板] 支付配置页顶部「环境自检」卡片（精简版）
 *
 * 行为：
 * - 调用 GET /api/admin/health/sdk 获取快照
 * - 默认仅渲染指定分组（默认 payment）；可通过 group prop 指定其他分组
 * - 全绿：折叠成单行 ✅
 * - 任意红：展开红色 banner，逐项展示缺失 SDK + 安装命令 + 一键复制按钮
 */
import React, { useEffect, useState } from 'react';
import { Alert, Button, Space, Tag, Tooltip, message } from 'antd';
import { CheckCircleTwoTone, ReloadOutlined, CopyOutlined } from '@ant-design/icons';
import { get, post } from '@/lib/api';

export interface SdkHealthItem {
  key: string;
  name: string;
  level: 'core' | 'optional';
  group: string;
  install_cmd: string;
  usage: string;
  ok: boolean;
  error: string | null;
  version: string | null;
}

export interface SdkHealthSnapshot {
  ok: boolean;
  summary: { total: number; ok: number; missing_core: number; missing_optional: number };
  groups: Record<string, SdkHealthItem[]>;
  checked_at: string | null;
}

interface Props {
  /** 仅展示此分组的 SDK 项；不传则等同于 payment */
  group?: 'core' | 'payment' | 'sms' | 'storage' | 'other';
  /** 标题文案，默认「支付环境自检」 */
  title?: string;
  /** 当某 SDK 失败时的提示前缀，默认「支付」 */
  scopeLabel?: string;
}

export default function SdkHealthCard({
  group = 'payment',
  title = '支付环境自检',
  scopeLabel = '支付',
}: Props) {
  const [loading, setLoading] = useState<boolean>(true);
  const [snap, setSnap] = useState<SdkHealthSnapshot | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await get<SdkHealthSnapshot>('/api/admin/health/sdk');
      setSnap(data);
    } catch (e: any) {
      // 不阻塞页面其他操作；仅打 toast
      const detail = e?.response?.data?.detail;
      const status = e?.response?.status;
      if (status === 503) {
        message.error('核心运行时依赖缺失，请联系运维');
      } else if (status === 403 || status === 401) {
        // 非管理员 token：不显示告警，静默隐藏
      } else {
        const msg = typeof detail === 'string' ? detail : `加载失败：HTTP ${status || '未知'}`;
        message.warning(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await post<SdkHealthSnapshot>('/api/admin/health/sdk/refresh', {});
      setSnap(data);
      message.success('已重新检测');
    } catch (e: any) {
      message.error('重新检测失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  if (!snap) {
    return null;
  }

  const items: SdkHealthItem[] = snap.groups?.[group] || [];
  if (items.length === 0) {
    return null;
  }

  const failed = items.filter((it) => !it.ok);
  const allGreen = failed.length === 0;

  const onCopy = async (cmd: string) => {
    try {
      await navigator.clipboard.writeText(cmd);
      message.success('已复制安装命令');
    } catch {
      message.error('复制失败，请手动选中');
    }
  };

  if (allGreen) {
    return (
      <Alert
        type="success"
        showIcon
        icon={<CheckCircleTwoTone twoToneColor="#52c41a" />}
        message={
          <Space>
            <span>{title}通过：{items.length} 项依赖均正常</span>
            <Button size="small" icon={<ReloadOutlined />} onClick={refresh} loading={loading}>
              重新检测
            </Button>
          </Space>
        }
        style={{ marginBottom: 16 }}
      />
    );
  }

  return (
    <Alert
      type="error"
      showIcon
      style={{ marginBottom: 16 }}
      message={
        <Space>
          <span>
            {scopeLabel}环境自检发现 {failed.length} 个 SDK 缺失，相关功能将不可用
          </span>
          <Button size="small" icon={<ReloadOutlined />} onClick={refresh} loading={loading}>
            重新检测
          </Button>
        </Space>
      }
      description={
        <div style={{ marginTop: 8 }}>
          {failed.map((it) => (
            <div key={it.key} style={{ marginBottom: 8 }}>
              <Space wrap>
                <Tag color="red">缺失</Tag>
                <strong>{it.name}</strong>
                <Tooltip title={it.usage}>
                  <Tag>{it.usage}</Tag>
                </Tooltip>
                <code style={{ background: '#fff2f0', padding: '2px 6px', borderRadius: 4 }}>
                  {it.install_cmd}
                </code>
                <Button
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => onCopy(it.install_cmd)}
                >
                  复制
                </Button>
              </Space>
              {it.error && (
                <div style={{ color: '#a8071a', marginTop: 4, fontSize: 12 }}>
                  报错：{it.error}
                </div>
              )}
            </div>
          ))}
          <div style={{ marginTop: 4, color: '#666', fontSize: 12 }}>
            提示：在容器中执行上方安装命令后，重启 backend 容器即可恢复。
          </div>
        </div>
      }
    />
  );
}
