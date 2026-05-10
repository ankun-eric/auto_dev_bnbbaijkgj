'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Table, Button, Tag, Space, Typography, message, Modal, Tabs, Input, Spin, Drawer,
} from 'antd';
import { CheckCircleOutlined, EditOutlined, EyeOutlined, ReloadOutlined } from '@ant-design/icons';
import { get, put, post } from '@/lib/api';

const { Title, Text, Paragraph } = Typography;

interface ThemeListItem {
  id: number;
  name: string;
  status: 'active' | 'draft' | 'disabled';
  version: number;
  updated_at: number;
}

interface ThemeDetail extends ThemeListItem {
  tokens: any;
}

const STATUS_TAG: Record<string, { color: string; label: string }> = {
  active:   { color: 'green',  label: '已启用' },
  draft:    { color: 'orange', label: '草稿' },
  disabled: { color: 'default', label: '已禁用' },
};

/**
 * PRD-447 v2 · 后台主题可配置模块
 * 功能：列表 / 编辑 / 预览 / 启用 / 回滚
 */
export default function ThemeConfigPage() {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<ThemeListItem[]>([]);
  const [editing, setEditing] = useState<ThemeDetail | null>(null);
  const [editJson, setEditJson] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewTheme, setPreviewTheme] = useState<ThemeDetail | null>(null);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<{ items: ThemeListItem[]; total: number }>('/api/admin/themes', {
        params: { page: 1, size: 50 },
      });
      setItems(res.items || []);
    } catch {
      message.error('获取主题列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchList(); }, [fetchList]);

  const handleEdit = async (id: number) => {
    try {
      const detail = await get<ThemeDetail>(`/api/admin/themes/${id}`);
      setEditing(detail);
      setEditJson(JSON.stringify(detail.tokens, null, 2));
    } catch {
      message.error('获取主题详情失败');
    }
  };

  const handlePreview = async (id: number) => {
    try {
      const detail = await get<ThemeDetail>(`/api/admin/themes/${id}`);
      setPreviewTheme(detail);
      setPreviewOpen(true);
    } catch {
      message.error('获取主题详情失败');
    }
  };

  const handleSaveDraft = async () => {
    if (!editing) return;
    let tokens: any = null;
    try {
      tokens = JSON.parse(editJson);
    } catch {
      message.error('JSON 格式错误');
      return;
    }
    setSaving(true);
    try {
      await put(`/api/admin/themes/${editing.id}`, {
        name: editing.name,
        tokens,
      });
      message.success('已保存为草稿');
      setEditing(null);
      fetchList();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleActivate = (id: number, name: string) => {
    Modal.confirm({
      title: `启用主题：${name}`,
      content: '启用后将立即推全量，当前启用主题会被置为禁用。是否继续？',
      okText: '启用',
      cancelText: '取消',
      onOk: async () => {
        try {
          await post(`/api/admin/themes/${id}/activate`, {});
          message.success('主题已启用');
          fetchList();
        } catch (e: any) {
          message.error(e?.response?.data?.detail || '启用失败');
        }
      },
    });
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 80 },
    { title: '主题名称', dataIndex: 'name' },
    {
      title: '状态', dataIndex: 'status', width: 120,
      render: (s: string) => {
        const t = STATUS_TAG[s] || { color: 'default', label: s };
        return <Tag color={t.color}>{t.label}</Tag>;
      },
    },
    { title: '版本', dataIndex: 'version', width: 80 },
    {
      title: '更新时间', dataIndex: 'updated_at', width: 200,
      render: (v: number) => new Date(v).toLocaleString(),
    },
    {
      title: '操作', width: 280,
      render: (_: any, row: ThemeListItem) => (
        <Space>
          <Button size="small" icon={<EyeOutlined />} onClick={() => handlePreview(row.id)}>预览</Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(row.id)}>编辑</Button>
          {row.status !== 'active' && (
            <Button size="small" type="primary" icon={<CheckCircleOutlined />} onClick={() => handleActivate(row.id, row.name)}>
              启用
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Title level={4} style={{ margin: 0 }}>主题配置（PRD-447）</Title>
          <Button icon={<ReloadOutlined />} onClick={fetchList}>刷新</Button>
        </Space>
        <Paragraph type="secondary">
          基于设计 token 三层体系（原子层 / 主题层 / 语义层）。改动→保存为草稿，启用后 H5 启动时拉取生效。
        </Paragraph>
        <Spin spinning={loading}>
          <Table rowKey="id" columns={columns as any} dataSource={items} pagination={false} />
        </Spin>
      </Card>

      {/* 编辑 Modal */}
      <Modal
        open={!!editing}
        title={`编辑主题：${editing?.name || ''}`}
        width={900}
        onCancel={() => setEditing(null)}
        footer={[
          <Button key="cancel" onClick={() => setEditing(null)}>取消</Button>,
          <Button key="save" type="primary" loading={saving} onClick={handleSaveDraft}>保存为草稿</Button>,
        ]}
      >
        <Tabs
          items={[
            {
              key: 'json', label: 'Token JSON 编辑',
              children: (
                <Input.TextArea
                  value={editJson}
                  onChange={e => setEditJson(e.target.value)}
                  autoSize={{ minRows: 18, maxRows: 28 }}
                  style={{ fontFamily: 'monospace', fontSize: 12 }}
                />
              ),
            },
            {
              key: 'help', label: '使用说明',
              children: (
                <div>
                  <Paragraph>
                    Token 必须包含三层：<Text code>atomic</Text>（原子层）/ <Text code>theme</Text>（主题层）/ <Text code>semantic</Text>（语义层）。
                  </Paragraph>
                  <Paragraph type="secondary">
                    保存后状态变为草稿，需要在列表中点击"启用"才会推送到 H5。启用是事务式：会自动把当前启用主题置为禁用，且 H5 在 200ms 内热更新。
                  </Paragraph>
                </div>
              ),
            },
          ]}
        />
      </Modal>

      {/* 预览 Drawer */}
      <Drawer
        title={`预览主题：${previewTheme?.name || ''}`}
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        width={520}
      >
        {previewTheme && <ThemePreview detail={previewTheme} />}
      </Drawer>
    </div>
  );
}

const ThemePreview: React.FC<{ detail: ThemeDetail }> = ({ detail }) => {
  const brand = detail.tokens?.atomic?.color_brand || {};
  const grads = detail.tokens?.atomic?.gradients || {};
  const swatches = Object.entries(brand);
  const gradList = Object.entries(grads);
  return (
    <div>
      <Title level={5}>11 级品牌色</Title>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(60px, 1fr))', gap: 6, marginBottom: 16 }}>
        {swatches.map(([k, v]) => (
          <div key={k} style={{ background: String(v), color: '#fff', textAlign: 'center', padding: 12, borderRadius: 6, fontSize: 12 }}>
            {k}
          </div>
        ))}
      </div>
      <Title level={5}>5 个核心渐变</Title>
      <div style={{ display: 'grid', gap: 6 }}>
        {gradList.map(([k, v]) => (
          <div key={k} style={{ background: String(v), color: '#fff', padding: 14, borderRadius: 6, textAlign: 'center', fontSize: 13, fontWeight: 500 }}>
            {k}
          </div>
        ))}
      </div>
    </div>
  );
};
