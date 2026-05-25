'use client';

/**
 * [Bug 修复 v1.2 §6] 紧急呼叫触发源管理 - 卡片网格化改造
 *
 * 关键变更：
 * - 顶部 120px 天蓝 Hero 区 + 4 个统计数字（总数 / 内置 / 自定义 / 启用中）
 * - 响应式卡片网格（≥1600:4 / ≥1200:3 / <1200:2）
 * - 主色 #1890FF / 圆角 20px / 阴影 0 4px 16px rgba(24,144,255,0.08)
 * - 卡片：图标 + 名称 + 启停 Switch + 描述 + 适用设备 + 操作菜单 + 内置/自定义徽章
 * - 内置：编辑/删除菜单项灰色禁用；自定义：可编辑/删除（二次确认）
 * - 旧 Table 实现保留为 page.legacy.tsx 作为回滚兜底
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  Tag, Space, Typography, message, Button, Modal, Form, Switch,
  InputNumber, Input, Dropdown, Empty, Spin, Tooltip,
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, MoreOutlined, EditOutlined, DeleteOutlined,
  CheckCircleFilled, CloseCircleFilled, BellOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Paragraph, Text } = Typography;

const COLOR = {
  primary: '#1890FF',
  primaryDark: '#096DD9',
  primaryLight: '#69C0FF',
  primaryBg: '#E6F7FF',
  pageBg: '#F0F8FF',
  success: '#52C41A',
  warning: '#FAAD14',
  danger: '#FF4D4F',
  gray: '#8C8C8C',
};

interface EmergencySource {
  id: number;
  source_code: string;
  source_name: string;
  description?: string;
  is_enabled: boolean;
  is_builtin: boolean;
  trigger_condition?: string;
  applicable_device_type?: string;
  sort_order: number;
  created_at?: string;
}

interface Stats {
  total: number;
  builtin: number;
  custom: number;
  enabled: number;
  disabled: number;
}

// 内置 4 种触发源图标映射
const SOURCE_ICONS: Record<string, string> = {
  health_data_abnormal: '❤️',
  smoke_alarm: '🔥',
  water_alarm: '💧',
  emergency_button: '🆘',
};

function PageHero({ title, subtitle, statItems }: {
  title: string;
  subtitle: string;
  statItems: { label: string; value: number | string }[];
}) {
  return (
    <div
      style={{
        height: 120,
        background: `linear-gradient(135deg, ${COLOR.primary} 0%, ${COLOR.primaryDark} 100%)`,
        borderRadius: 20,
        padding: '20px 28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: '0 4px 16px rgba(24, 144, 255, 0.18)',
        marginBottom: 24,
        color: '#fff',
      }}
    >
      <div>
        <div style={{ fontSize: 22, fontWeight: 700, lineHeight: 1.3 }}>{title}</div>
        <div style={{ fontSize: 14, color: 'rgba(255,255,255,0.7)', marginTop: 4 }}>{subtitle}</div>
      </div>
      <Space size={12} wrap>
        {statItems.map((it) => (
          <div
            key={it.label}
            style={{
              background: 'rgba(255,255,255,0.18)',
              borderRadius: 12,
              padding: '8px 18px',
              minWidth: 80,
              textAlign: 'center',
              backdropFilter: 'blur(4px)',
            }}
          >
            <div style={{ fontSize: 24, fontWeight: 700, lineHeight: 1.1 }}>{it.value}</div>
            <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.9)', marginTop: 2 }}>{it.label}</div>
          </div>
        ))}
      </Space>
    </div>
  );
}

function SourceCard({
  data, onToggle, onEdit, onDelete,
}: {
  data: EmergencySource;
  onToggle: (rec: EmergencySource, checked: boolean) => void;
  onEdit: (rec: EmergencySource) => void;
  onDelete: (rec: EmergencySource) => void;
}) {
  const [hover, setHover] = useState(false);
  const icon = SOURCE_ICONS[data.source_code] || '🔔';

  const menuItems = [
    {
      key: 'edit',
      label: '编辑',
      icon: <EditOutlined />,
      disabled: data.is_builtin,
      onClick: () => { if (!data.is_builtin) onEdit(data); },
    },
    {
      key: 'delete',
      label: <span style={{ color: data.is_builtin ? COLOR.gray : COLOR.danger }}>删除</span>,
      icon: <DeleteOutlined />,
      disabled: data.is_builtin,
      onClick: () => { if (!data.is_builtin) onDelete(data); },
    },
  ];

  return (
    <div
      style={{
        background: '#FFFFFF',
        borderRadius: 20,
        padding: 20,
        boxShadow: hover
          ? '0 6px 20px rgba(24, 144, 255, 0.16)'
          : '0 4px 16px rgba(24, 144, 255, 0.08)',
        transform: hover ? 'translateY(-2px)' : 'none',
        transition: 'all 0.2s ease',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        height: '100%',
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0, flex: 1 }}>
          <div
            style={{
              width: 44, height: 44, borderRadius: 12,
              background: COLOR.primaryBg,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 24, flexShrink: 0,
            }}
          >
            {icon}
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 16, fontWeight: 600, color: '#1F2937', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {data.source_name}
            </div>
            <div style={{ fontSize: 12, color: COLOR.gray, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {data.source_code}
            </div>
          </div>
        </div>
        <Switch
          checked={data.is_enabled}
          onChange={(c) => onToggle(data, c)}
          style={{ background: data.is_enabled ? COLOR.success : undefined }}
        />
      </div>

      <Paragraph
        ellipsis={{ rows: 2 }}
        style={{ fontSize: 13, color: '#4B5563', margin: 0, minHeight: 36 }}
      >
        {data.description || '—'}
      </Paragraph>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <Tag style={{
          borderRadius: 12,
          background: data.is_builtin ? COLOR.primaryBg : '#F9F0FF',
          border: `1px solid ${data.is_builtin ? '#91D5FF' : '#D3ADF7'}`,
          color: data.is_builtin ? COLOR.primary : '#722ED1',
          margin: 0,
        }}>
          {data.is_builtin ? '内置' : '自定义'}
        </Tag>
        {data.applicable_device_type && (
          <Tag style={{ borderRadius: 12, background: '#F0F0F0', border: 'none', color: '#595959', margin: 0 }}>
            {data.applicable_device_type}
          </Tag>
        )}
        {data.is_enabled ? (
          <Tag style={{ borderRadius: 12, background: '#F6FFED', border: '1px solid #B7EB8F', color: COLOR.success, margin: 0 }}>
            <CheckCircleFilled style={{ marginRight: 4 }} />启用
          </Tag>
        ) : (
          <Tag style={{ borderRadius: 12, background: '#F5F5F5', border: '1px solid #D9D9D9', color: COLOR.gray, margin: 0 }}>
            <CloseCircleFilled style={{ marginRight: 4 }} />停用
          </Tag>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'auto' }}>
        <Tooltip title={data.is_builtin ? '内置触发源仅可启停，不可编辑/删除' : ''}>
          <Dropdown menu={{ items: menuItems }} trigger={['click']} placement='bottomRight'>
            <Button
              type='text'
              icon={<MoreOutlined />}
              shape='circle'
              size='small'
              data-testid={`source-actions-${data.id}`}
            />
          </Dropdown>
        </Tooltip>
      </div>
    </div>
  );
}

export default function EmergencySourcesPage() {
  const [data, setData] = useState<EmergencySource[]>([]);
  const [stats, setStats] = useState<Stats>({ total: 0, builtin: 0, custom: 0, enabled: 0, disabled: 0 });
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<EmergencySource | null>(null);
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res: any = await get('/api/admin/emergency-sources');
      const items = res?.items || res?.data?.items || [];
      setData(items);
      setStats(res?.stats || {
        total: items.length,
        builtin: items.filter((i: EmergencySource) => i.is_builtin).length,
        custom: items.filter((i: EmergencySource) => !i.is_builtin).length,
        enabled: items.filter((i: EmergencySource) => i.is_enabled).length,
        disabled: items.filter((i: EmergencySource) => !i.is_enabled).length,
      });
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const openAdd = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ is_enabled: true, sort_order: 100 });
    setModalOpen(true);
  };

  const openEdit = (rec: EmergencySource) => {
    if (rec.is_builtin) {
      message.warning('内置触发源不可编辑，仅可启停');
      return;
    }
    setEditing(rec);
    form.setFieldsValue(rec);
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const vals = await form.validateFields();
      if (editing) {
        await put(`/api/admin/emergency-sources/${editing.id}`, vals);
        message.success('已更新');
      } else {
        await post('/api/admin/emergency-sources', vals);
        message.success('已新增');
      }
      setModalOpen(false);
      fetchData();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    }
  };

  const handleToggle = async (rec: EmergencySource, checked: boolean) => {
    try {
      await put(`/api/admin/emergency-sources/${rec.id}`, { is_enabled: checked });
      message.success(checked ? '已启用' : '已停用');
      fetchData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '操作失败');
    }
  };

  const handleDelete = async (rec: EmergencySource) => {
    if (rec.is_builtin) {
      message.warning('内置触发源不可删除，仅可禁用');
      return;
    }
    try {
      await del(`/api/admin/emergency-sources/${rec.id}`);
      message.success('已删除');
      fetchData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  const confirmDelete = (rec: EmergencySource) => {
    if (rec.is_builtin) {
      message.warning('内置触发源不可删除，仅可禁用');
      return;
    }
    Modal.confirm({
      title: '确认删除该触发源？',
      content: <span>触发源 <Text strong>{rec.source_name}</Text> 删除后不可恢复，确定继续？</span>,
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: () => handleDelete(rec),
    });
  };

  return (
    <div style={{ background: COLOR.pageBg, minHeight: 'calc(100vh - 112px)', margin: -24, padding: 24 }}>
      <PageHero
        title='紧急呼叫触发源管理'
        subtitle='管理内置 4 种 + 自定义紧急呼叫触发源；内置项仅可启停，自定义项可编辑/删除'
        statItems={[
          { label: '总数', value: stats.total },
          { label: '内置', value: stats.builtin },
          { label: '自定义', value: stats.custom },
          { label: '启用中', value: stats.enabled },
        ]}
      />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space size={8}>
          <BellOutlined style={{ color: COLOR.primary, fontSize: 16 }} />
          <Text strong style={{ fontSize: 16 }}>触发源列表</Text>
          <Text type='secondary' style={{ fontSize: 13 }}>共 {data.length} 项</Text>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchData} style={{ borderRadius: 22 }}>
            刷新
          </Button>
          <Button
            type='primary'
            icon={<PlusOutlined />}
            onClick={openAdd}
            style={{
              borderRadius: 22, height: 36,
              background: COLOR.primary, borderColor: COLOR.primary,
            }}
          >
            新增触发源
          </Button>
        </Space>
      </div>

      <Spin spinning={loading}>
        {data.length === 0 ? (
          <div style={{ background: '#fff', borderRadius: 20, padding: 60 }}>
            <Empty description='暂无触发源' />
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gap: 16,
              gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            }}
          >
            {data.map((rec) => (
              <SourceCard
                key={rec.id}
                data={rec}
                onToggle={handleToggle}
                onEdit={openEdit}
                onDelete={confirmDelete}
              />
            ))}
          </div>
        )}
      </Spin>

      <Modal
        title={editing ? '编辑触发源' : '新增触发源'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        destroyOnClose
        width={600}
        okButtonProps={{ style: { borderRadius: 22, background: COLOR.primary, borderColor: COLOR.primary } }}
        cancelButtonProps={{ style: { borderRadius: 22 } }}
      >
        <Form form={form} layout='vertical'>
          <Form.Item
            label='触发源编码'
            name='source_code'
            rules={[{ required: true, message: '请输入编码' }]}
            extra='唯一标识，建议小写英文+下划线，如 gas_alarm'
          >
            <Input disabled={!!editing} placeholder='如 gas_alarm' />
          </Form.Item>
          <Form.Item label='触发源名称' name='source_name' rules={[{ required: true }]}>
            <Input placeholder='如 燃气报警器' />
          </Form.Item>
          <Form.Item label='描述' name='description'>
            <Input.TextArea rows={2} placeholder='触发源详细说明' />
          </Form.Item>
          <Form.Item label='适用设备类型' name='applicable_device_type'>
            <Input placeholder='如 wifi-gas-sensor' />
          </Form.Item>
          <Form.Item label='触发条件配置（JSON）' name='trigger_condition'>
            <Input.TextArea rows={2} placeholder='可选，JSON 格式描述阈值等' />
          </Form.Item>
          <Form.Item label='排序' name='sort_order' initialValue={100}>
            <InputNumber min={0} max={9999} />
          </Form.Item>
          <Form.Item label='启用' name='is_enabled' valuePropName='checked' initialValue={true}>
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
