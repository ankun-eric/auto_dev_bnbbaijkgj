'use client';

/**
 * [PRD-AI-PAGE-OPTIM-V1 2026-05-21] 种子数据导入管理页
 *
 * 把过去散落在 4 个迁移脚本里的「启动时自动写入种子数据」改造为：
 * - 启动迁移只做 DDL，不再写入种子数据
 * - 6 个种子包（中医体质 36 题 / PHQ-9 / GAD-7 / PSQI / 健康自查 6 维度 / 9 体质标签）
 *   集中在本页面，由运营按需「一键导入 / 一键卸载」
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import {
  CloudDownloadOutlined,
  DeleteOutlined,
  EyeOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { get, post } from '@/lib/api';

const { Title, Text, Paragraph } = Typography;

interface SeedPack {
  code: string;
  name: string;
  description: string;
  summary: string;
  source: string;
  version: string;
  status: 'installed' | 'not_installed' | 'partial' | 'modified' | 'unknown';
}

interface SeedPackDetail extends SeedPack {
  detail?: Record<string, any>;
}

const STATUS_TAG: Record<string, { color: string; text: string }> = {
  installed: { color: 'green', text: '已导入' },
  not_installed: { color: 'default', text: '未导入' },
  partial: { color: 'orange', text: '部分导入' },
  modified: { color: 'blue', text: '已被运营修改' },
  unknown: { color: 'red', text: '检测失败' },
};

export default function SeedImportPage() {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<SeedPack[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [currentPack, setCurrentPack] = useState<SeedPackDetail | null>(null);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string>('');

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<any>('/api/admin/seed-packs');
      setItems(res.items || []);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '获取种子包列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const openDetail = async (code: string) => {
    setDrawerOpen(true);
    setDrawerLoading(true);
    setCurrentPack(null);
    try {
      const res = await get<SeedPackDetail>(`/api/admin/seed-packs/${code}`);
      setCurrentPack(res);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '获取详情失败');
    } finally {
      setDrawerLoading(false);
    }
  };

  const handleInstall = async (pack: SeedPack) => {
    // 已存在 → 让用户选择 覆盖 / 跳过 / 取消
    if (pack.status === 'installed' || pack.status === 'partial' || pack.status === 'modified') {
      Modal.confirm({
        title: `检测到「${pack.name}」已有数据`,
        content: (
          <div>
            <Paragraph>请选择导入策略：</Paragraph>
            <ul>
              <li><strong>覆盖：</strong>删除现有数据后重新导入（小心：会丢失运营定制）</li>
              <li><strong>跳过：</strong>保留现有数据不动（仅在缺失项上补齐 / 安全策略）</li>
            </ul>
          </div>
        ),
        okText: '覆盖（重新导入）',
        cancelText: '跳过（保留现有）',
        okButtonProps: { danger: true },
        onOk: () => doInstall(pack, 'overwrite'),
        onCancel: () => doInstall(pack, 'skip'),
        closable: true,
      });
      return;
    }
    // 干净环境：直接安装
    Modal.confirm({
      title: `导入「${pack.name}」？`,
      content: (
        <div>
          <Paragraph>
            将导入：<strong>{pack.summary}</strong>
          </Paragraph>
          <Paragraph type="secondary">
            导入完成后，您可在「通用问卷模板管理」「功能按钮管理」「标签管理」中手动调整。
            导入数据 <strong>不会再自动恢复</strong>。
          </Paragraph>
        </div>
      ),
      okText: '继续导入',
      cancelText: '取消',
      onOk: () => doInstall(pack, 'skip'),
    });
  };

  const doInstall = async (pack: SeedPack, mode: 'overwrite' | 'skip') => {
    setActionLoading(pack.code);
    try {
      const res = await post<any>(`/api/admin/seed-packs/${pack.code}/install`, {
        conflict_mode: mode,
      });
      message.success(`「${pack.name}」导入完成（${mode === 'overwrite' ? '覆盖' : '跳过'}）`);
      console.log('[seed-import] install result:', res);
      await fetchList();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '导入失败');
    } finally {
      setActionLoading('');
    }
  };

  const handleUninstall = async (pack: SeedPack) => {
    setActionLoading(pack.code);
    try {
      const res = await post<any>(`/api/admin/seed-packs/${pack.code}/uninstall`, {});
      message.success(`「${pack.name}」已卸载`);
      console.log('[seed-import] uninstall result:', res);
      await fetchList();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '卸载失败');
    } finally {
      setActionLoading('');
    }
  };

  const columns = useMemo(
    () => [
      {
        title: '种子包',
        dataIndex: 'name',
        width: 280,
        render: (v: string, record: SeedPack) => (
          <div>
            <div style={{ fontWeight: 600 }}>{v}</div>
            <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>
              <Tag color="blue">{record.code}</Tag>
              <Tag>{record.version}</Tag>
            </div>
          </div>
        ),
      },
      {
        title: '简版说明',
        dataIndex: 'description',
        ellipsis: true,
      },
      {
        title: '包含内容（摘要）',
        dataIndex: 'summary',
        width: 320,
      },
      {
        title: '当前状态',
        dataIndex: 'status',
        width: 130,
        render: (v: string) => {
          const conf = STATUS_TAG[v] || STATUS_TAG.unknown;
          return <Tag color={conf.color}>{conf.text}</Tag>;
        },
      },
      {
        title: '操作',
        width: 340,
        render: (_: any, record: SeedPack) => (
          <Space>
            <Tooltip title="查看完整内容">
              <Button
                size="small"
                icon={<EyeOutlined />}
                onClick={() => openDetail(record.code)}
              >
                查看完整内容
              </Button>
            </Tooltip>
            <Button
              type="primary"
              size="small"
              icon={<CloudDownloadOutlined />}
              loading={actionLoading === record.code}
              onClick={() => handleInstall(record)}
              data-testid={`seed-install-${record.code}`}
            >
              一键导入
            </Button>
            <Popconfirm
              title={`确认卸载「${record.name}」？`}
              description="将删除该种子包的关联数据（模板、题目、分型规则、按钮、标签等），不可恢复。"
              okText="确认卸载"
              okButtonProps={{ danger: true }}
              onConfirm={() => handleUninstall(record)}
            >
              <Button
                size="small"
                danger
                icon={<DeleteOutlined />}
                loading={actionLoading === record.code}
                disabled={record.status === 'not_installed'}
              >
                一键卸载
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [actionLoading]
  );

  return (
    <div data-testid="seed-import-page">
      <Title level={3}>种子数据导入</Title>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="运营提示"
        description={
          <div>
            <Paragraph style={{ marginBottom: 4 }}>
              系统启动时<strong>不会</strong>再自动写入下列种子数据（问卷模板、题目、分型规则、功能按钮、体质标签）。
              如需开通某个能力，请在此页点击对应种子包的「一键导入」。
            </Paragraph>
            <Paragraph style={{ marginBottom: 0 }} type="secondary">
              导入数据后，您可在「通用问卷模板管理」「功能按钮管理」「标签管理」自由编辑，
              数据 <strong>不会被自动恢复或覆盖</strong>。
            </Paragraph>
          </div>
        }
      />

      <Space style={{ marginBottom: 12 }}>
        <Button icon={<ReloadOutlined />} onClick={fetchList} loading={loading}>
          刷新状态
        </Button>
      </Space>

      <Table
        rowKey="code"
        loading={loading}
        dataSource={items}
        columns={columns as any}
        pagination={false}
        bordered
      />

      <Drawer
        title="种子包详情"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={680}
      >
        {drawerLoading || !currentPack ? (
          <Spin />
        ) : (
          <div>
            <Card style={{ marginBottom: 16 }}>
              <Descriptions title={currentPack.name} column={1} bordered size="small">
                <Descriptions.Item label="编码">
                  <Tag color="blue">{currentPack.code}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="版本">{currentPack.version}</Descriptions.Item>
                <Descriptions.Item label="来源 / 出处">
                  {currentPack.source || '—'}
                </Descriptions.Item>
                <Descriptions.Item label="当前状态">
                  {(() => {
                    const conf = STATUS_TAG[currentPack.status] || STATUS_TAG.unknown;
                    return <Tag color={conf.color}>{conf.text}</Tag>;
                  })()}
                </Descriptions.Item>
                <Descriptions.Item label="简介">{currentPack.description}</Descriptions.Item>
                <Descriptions.Item label="包含摘要">{currentPack.summary}</Descriptions.Item>
              </Descriptions>
            </Card>

            <Card title="导入会做什么">
              {currentPack.detail?.tables_affected ? (
                <div>
                  <Paragraph>
                    <strong>受影响的数据表：</strong>
                  </Paragraph>
                  <Space wrap>
                    {(currentPack.detail.tables_affected as string[]).map((t) => (
                      <Tag color="purple" key={t}>
                        {t}
                      </Tag>
                    ))}
                  </Space>
                </div>
              ) : (
                <Text type="secondary">无受影响表元数据</Text>
              )}
              {currentPack.detail?.expected_questions !== undefined && (
                <Paragraph style={{ marginTop: 12 }}>
                  <strong>题目数量：</strong>
                  {currentPack.detail.expected_questions} 题
                </Paragraph>
              )}
              {currentPack.detail?.expected_rules !== undefined && (
                <Paragraph>
                  <strong>分型规则：</strong>
                  {currentPack.detail.expected_rules} 条
                </Paragraph>
              )}
            </Card>

            <Card title="操作说明" style={{ marginTop: 16 }}>
              <Paragraph>
                <strong>导入策略：</strong>
              </Paragraph>
              <ul>
                <li>
                  <strong>覆盖：</strong>删除现有数据后重新导入。⚠️ 会丢失运营之前的定制内容
                </li>
                <li>
                  <strong>跳过：</strong>保留现有数据不动；仅在该种子包从未导入过时执行实际写入
                </li>
              </ul>
              <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                所有操作均在事务中执行，任何一步失败将整体回滚。
              </Paragraph>
            </Card>
          </div>
        )}
      </Drawer>
    </div>
  );
}
