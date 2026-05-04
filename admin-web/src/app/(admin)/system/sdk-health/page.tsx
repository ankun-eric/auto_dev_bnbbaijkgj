'use client';

/**
 * [2026-05-05 SDK 健康看板] 系统设置 → 环境健康检查（完整版）
 *
 * 四个分组卡片：核心运行时 / 支付 SDK / 短信 SDK / 对象存储 SDK
 * - 顶部总览：总计 / 正常 / 缺失
 * - 「重新检测」按钮触发 POST /api/admin/health/sdk/refresh
 * - 缺失项默认展开，正常项默认折叠
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert, Badge, Button, Card, Col, Collapse, Empty, Row, Space, Statistic,
  Tag, Tooltip, Typography, message,
} from 'antd';
import {
  CheckCircleTwoTone, CloseCircleTwoTone, ReloadOutlined, CopyOutlined,
  HeartOutlined, CreditCardOutlined, MessageOutlined, CloudOutlined, SafetyOutlined,
} from '@ant-design/icons';
import { get, post } from '@/lib/api';
import type { SdkHealthSnapshot, SdkHealthItem } from '@/components/SdkHealthCard';

const { Title, Paragraph, Text } = Typography;

interface GroupConfig {
  key: 'core' | 'payment' | 'sms' | 'storage' | 'other';
  title: string;
  desc: string;
  icon: React.ReactNode;
}

const GROUPS: GroupConfig[] = [
  {
    key: 'core',
    title: '核心运行时',
    desc: '影响后端能否正常启动；缺失会直接导致容器启动失败',
    icon: <SafetyOutlined />,
  },
  {
    key: 'payment',
    title: '支付 SDK',
    desc: '影响支付宝/微信等支付通道的下单与回调；缺失会让对应通道不可用',
    icon: <CreditCardOutlined />,
  },
  {
    key: 'sms',
    title: '短信 SDK',
    desc: '影响短信验证码下发；缺失会让对应短信通道不可用',
    icon: <MessageOutlined />,
  },
  {
    key: 'storage',
    title: '对象存储 SDK',
    desc: '影响图片/附件上传；缺失会让对应云存储通道不可用',
    icon: <CloudOutlined />,
  },
];

export default function SdkHealthPage() {
  const [loading, setLoading] = useState<boolean>(true);
  const [snap, setSnap] = useState<SdkHealthSnapshot | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await get<SdkHealthSnapshot>('/api/admin/health/sdk');
      setSnap(data);
    } catch (e: any) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;
      if (status === 503) {
        // 核心缺失：detail.snapshot 仍可用
        const fallback = detail?.snapshot as SdkHealthSnapshot | undefined;
        if (fallback) {
          setSnap(fallback);
        }
        message.error('核心运行时依赖缺失，详见下方');
      } else {
        message.error('加载失败：' + (typeof detail === 'string' ? detail : `HTTP ${status || '未知'}`));
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
    } catch (e) {
      message.error('重新检测失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const onCopy = async (cmd: string) => {
    try {
      await navigator.clipboard.writeText(cmd);
      message.success('已复制安装命令');
    } catch {
      message.error('复制失败，请手动选中');
    }
  };

  const summary = snap?.summary;

  const renderItem = (it: SdkHealthItem) => (
    <div key={it.key} style={{ padding: '8px 0', borderBottom: '1px dashed #eee' }}>
      <Space wrap>
        {it.ok ? (
          <CheckCircleTwoTone twoToneColor="#52c41a" />
        ) : (
          <CloseCircleTwoTone twoToneColor="#ff4d4f" />
        )}
        <strong>{it.name}</strong>
        <Tag color={it.level === 'core' ? 'red' : 'blue'}>
          {it.level === 'core' ? '核心' : '可选'}
        </Tag>
        <code style={{ background: '#f5f5f5', padding: '1px 6px', borderRadius: 4 }}>{it.key}</code>
        {it.version && <Text type="secondary">v{it.version}</Text>}
        <Tooltip title={it.usage}>
          <Text type="secondary">{it.usage}</Text>
        </Tooltip>
      </Space>
      {!it.ok && (
        <div style={{ marginTop: 6 }}>
          <Space wrap>
            <Tag color="red">缺失</Tag>
            <code style={{ background: '#fff2f0', padding: '2px 6px', borderRadius: 4 }}>
              {it.install_cmd}
            </code>
            <Button size="small" icon={<CopyOutlined />} onClick={() => onCopy(it.install_cmd)}>
              复制
            </Button>
          </Space>
          {it.error && (
            <div style={{ color: '#a8071a', marginTop: 4, fontSize: 12 }}>
              报错：{it.error}
            </div>
          )}
        </div>
      )}
    </div>
  );

  const renderGroupCard = (cfg: GroupConfig) => {
    const items = (snap?.groups?.[cfg.key] || []) as SdkHealthItem[];
    if (items.length === 0) {
      return (
        <Card size="small" title={<Space>{cfg.icon}<span>{cfg.title}</span></Space>}>
          <Empty description="本分组暂无依赖" />
        </Card>
      );
    }
    const failed = items.filter((it) => !it.ok);
    const ok = items.filter((it) => it.ok);
    return (
      <Card
        size="small"
        title={
          <Space>
            {cfg.icon}
            <span>{cfg.title}</span>
            <Badge
              count={failed.length}
              showZero
              style={{ backgroundColor: failed.length === 0 ? '#52c41a' : '#ff4d4f' }}
            />
          </Space>
        }
        extra={<Text type="secondary">{cfg.desc}</Text>}
      >
        <Collapse
          defaultActiveKey={failed.length > 0 ? ['failed'] : []}
          items={[
            {
              key: 'failed',
              label: <span style={{ color: '#ff4d4f' }}>缺失（{failed.length}）</span>,
              children: failed.length > 0 ? failed.map(renderItem) : <Empty description="无缺失" />,
            },
            {
              key: 'ok',
              label: <span style={{ color: '#52c41a' }}>正常（{ok.length}）</span>,
              children: ok.length > 0 ? ok.map(renderItem) : <Empty description="无项目" />,
            },
          ]}
        />
      </Card>
    );
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>
        <HeartOutlined /> 环境健康检查
      </Title>
      <Paragraph type="secondary">
        统一检视后端运行时依赖（核心 + 三方 SDK）的安装情况。核心依赖缺失会导致后端启动失败；
        可选 SDK 缺失不会阻塞启动，但相关功能将不可用。
      </Paragraph>

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <Space size="large" wrap>
              <Statistic title="总计" value={summary?.total ?? 0} loading={loading} />
              <Statistic
                title="正常"
                value={summary?.ok ?? 0}
                valueStyle={{ color: '#52c41a' }}
                loading={loading}
              />
              <Statistic
                title="核心缺失"
                value={summary?.missing_core ?? 0}
                valueStyle={{ color: '#ff4d4f' }}
                loading={loading}
              />
              <Statistic
                title="可选缺失"
                value={summary?.missing_optional ?? 0}
                valueStyle={{ color: '#fa8c16' }}
                loading={loading}
              />
              {snap?.checked_at && (
                <Text type="secondary">最近检测：{snap.checked_at}</Text>
              )}
            </Space>
          </Col>
          <Col>
            <Button
              type="primary"
              icon={<ReloadOutlined />}
              onClick={refresh}
              loading={loading}
            >
              重新检测
            </Button>
          </Col>
        </Row>
      </Card>

      {summary && summary.missing_core > 0 && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="核心运行时依赖缺失"
          description="后端正常情况下应在启动时直接退出；如果你看到此页，说明数据来自上次检测快照，请尽快联系运维处理。"
        />
      )}

      <Row gutter={[16, 16]}>
        {GROUPS.map((cfg) => (
          <Col xs={24} lg={12} key={cfg.key}>
            {renderGroupCard(cfg)}
          </Col>
        ))}
      </Row>
    </div>
  );
}
