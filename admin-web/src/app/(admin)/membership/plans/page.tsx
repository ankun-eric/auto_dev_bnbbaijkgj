'use client';

/**
 * [会员中心 PRD v1.0 终稿对齐 2026-05-26] 付费会员套餐管理页
 *
 * 路径：/membership/plans
 * 字段对齐：
 *   套餐名 name / 套餐说明 description / 月价 price_month / 年价 price_year
 *   max_managed / ai_outbound_call_count / emergency_ai_call_count / max_managed_by
 *   discount_rate / is_active / is_recommended / sort_order
 */

import React, { useEffect, useState } from 'react';
import {
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
  Alert,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, CrownOutlined,
  SettingOutlined, StarFilled, PoweroffOutlined,
} from '@ant-design/icons';
import Link from 'next/link';
import { del, get, post, put } from '@/lib/api';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

interface MembershipPlan {
  id: number;
  name: string;
  description: string | null;
  price_month: number | null;
  price_year: number | null;
  max_managed: number;
  ai_outbound_call_count: number;
  emergency_ai_call_count: number;
  max_managed_by: number;
  discount_rate: number | null;
  is_active: boolean;
  is_recommended: boolean;
  sort_order: number;
}

const fmtLimit = (n: number | null | undefined) => {
  if (n === -1) return <Tag color="purple">不限</Tag>;
  if (n === null || n === undefined) return '—';
  return `${n} 次/月`;
};
const fmtPersons = (n: number | null | undefined) => {
  if (n === -1) return <Tag color="purple">不限</Tag>;
  if (n === null || n === undefined) return '—';
  return `${n} 人`;
};

export default function MembershipPlansPage() {
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editing, setEditing] = useState<MembershipPlan | null>(null);
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await get<any>('/api/admin/membership/plans?include_inactive=true');
      const list = Array.isArray(res) ? res : res?.items || res?.list || [];
      setPlans(list);
    } catch (e: any) {
      message.error('加载套餐列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleAdd = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      max_managed: 3,
      ai_outbound_call_count: 0,
      emergency_ai_call_count: 0,
      max_managed_by: 3,
      is_active: true,
      is_recommended: false,
      sort_order: 0,
    });
    setModalVisible(true);
  };

  const handleEdit = (record: MembershipPlan) => {
    setEditing(record);
    form.setFieldsValue(record);
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      const res: any = await del(`/api/admin/membership/plans/${id}`);
      if (res?.soft_deleted) {
        message.warning(res.reason || '已有历史订阅引用，仅停用');
      } else {
        message.success('已删除');
      }
      fetchData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  const handleToggle = async (id: number) => {
    try {
      await put(`/api/admin/membership/plans/${id}/toggle`, {});
      message.success('状态已切换');
      fetchData();
    } catch (e: any) {
      message.error('切换失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editing) {
        await put(`/api/admin/membership/plans/${editing.id}`, values);
        message.success('已保存');
      } else {
        await post('/api/admin/membership/plans', values);
        message.success('已新增');
      }
      setModalVisible(false);
      fetchData();
    } catch (e: any) {
      if (e?.response?.data?.detail) {
        message.error(e.response.data.detail);
      } else if (!e?.errorFields) {
        message.error('保存失败');
      }
    }
  };

  const columns = [
    {
      title: '#',
      width: 60,
      render: (_: any, __: any, idx: number) => idx + 1,
    },
    {
      title: '套餐名',
      dataIndex: 'name',
      width: 180,
      render: (name: string, record: MembershipPlan) => (
        <Space direction="vertical" size={0}>
          <Space>
            <CrownOutlined style={{ color: record.is_recommended ? '#D4AF37' : '#999' }} />
            <strong style={{ color: record.is_recommended ? '#D4AF37' : undefined }}>
              {name}
            </strong>
            {record.is_recommended && (
              <Tag color="gold" icon={<StarFilled />}>推荐</Tag>
            )}
            {!record.is_active && <Tag color="default">已停用</Tag>}
          </Space>
          {record.description && (
            <span style={{ color: '#999', fontSize: 12 }}>{record.description}</span>
          )}
        </Space>
      ),
    },
    {
      title: '月价',
      dataIndex: 'price_month',
      width: 100,
      render: (v: number | null) => (v != null ? `¥${Number(v).toFixed(2)}` : '—'),
    },
    {
      title: '年价',
      dataIndex: 'price_year',
      width: 100,
      render: (v: number | null) => (v != null ? `¥${Number(v).toFixed(2)}` : '—'),
    },
    { title: '可管理健康档案', dataIndex: 'max_managed', width: 120, render: fmtPersons },
    { title: 'AI 外呼', dataIndex: 'ai_outbound_call_count', width: 100, render: fmtLimit },
    { title: '紧急呼叫', dataIndex: 'emergency_ai_call_count', width: 100, render: fmtLimit },
    { title: '被管理上限', dataIndex: 'max_managed_by', width: 100, render: fmtPersons },
    {
      title: '商城折扣',
      dataIndex: 'discount_rate',
      width: 100,
      render: (r: number | null) => (r != null ? <Tag color="blue">{Number(r).toFixed(2)} 折</Tag> : '—'),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 80,
      render: (v: boolean) => (v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>),
    },
    {
      title: '推荐',
      dataIndex: 'is_recommended',
      width: 70,
      render: (v: boolean) => (v ? <Tag color="gold" icon={<StarFilled />}>推荐</Tag> : '—'),
    },
    {
      title: '操作',
      key: 'action',
      width: 240,
      render: (_: any, r: MembershipPlan) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(r)}>
            编辑
          </Button>
          <Button
            size="small"
            icon={<PoweroffOutlined />}
            onClick={() => handleToggle(r.id)}
          >
            {r.is_active ? '停用' : '启用'}
          </Button>
          <Popconfirm title="确定删除该套餐？" onConfirm={() => handleDelete(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>
            <CrownOutlined style={{ color: '#D4AF37' }} /> 付费会员套餐管理
          </Title>
          <Paragraph type="secondary" style={{ marginTop: 4 }}>
            会员中心 PRD v1.0 终稿：套餐字段已对齐为 max_managed / ai_outbound_call_count /
            emergency_ai_call_count / max_managed_by；推荐套餐用户端展示金色描边 + 推荐角标。
          </Paragraph>
        </div>
        <Space>
          <Link href="/membership/free-quota">
            <Button icon={<SettingOutlined />}>免费会员额度配置</Button>
          </Link>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            新增套餐
          </Button>
        </Space>
      </Space>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={plans}
        loading={loading}
        pagination={false}
        rowClassName={(r) => (r.is_recommended ? 'recommended-row' : '')}
        scroll={{ x: 1400 }}
      />

      <style jsx global>{`
        .recommended-row td {
          background: linear-gradient(90deg, #FFF8E7 0%, #FFFBF0 100%) !important;
          border-left: 3px solid #D4AF37 !important;
        }
        .recommended-row:hover td {
          background: linear-gradient(90deg, #FFF1D6 0%, #FFF6E0 100%) !important;
        }
      `}</style>

      <Modal
        title={editing ? '编辑套餐' : '新增套餐'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={760}
        destroyOnClose
      >
        <Alert
          type="info"
          showIcon
          message="数量字段填 -1 表示不限；月价/年价留空表示不展示对应购买按钮"
          style={{ marginBottom: 16 }}
        />
        <Form form={form} layout="vertical">
          <Form.Item label="套餐名称" name="name" rules={[{ required: true }]}>
            <Input placeholder="如 守护版 / 家庭版" maxLength={50} />
          </Form.Item>
          <Form.Item label="套餐说明" name="description">
            <TextArea rows={2} placeholder="简短描述（可选）" maxLength={255} />
          </Form.Item>

          <Space size="large" style={{ width: '100%' }}>
            <Form.Item label="月价（30 天，留空=不支持月购）" name="price_month">
              <InputNumber min={0} step={0.01} style={{ width: 200 }} />
            </Form.Item>
            <Form.Item label="年价（365 天，留空=不支持年购）" name="price_year">
              <InputNumber min={0} step={0.01} style={{ width: 200 }} />
            </Form.Item>
            <Form.Item label="商城折扣（0~1，留空=无折扣）" name="discount_rate"
              tooltip="如 0.9 表示 9 折；仅后台可配，用户端不展示">
              <InputNumber min={0} max={1} step={0.01} style={{ width: 200 }} />
            </Form.Item>
          </Space>

          <Space size="large" style={{ width: '100%' }}>
            <Form.Item label="可管理健康档案数（不含本人）" name="max_managed" rules={[{ required: true }]}
              tooltip="[PRD-HEALTH-ARCHIVE-MGR-V1 2026-05-29] 字段名保留 max_managed；填写「可管理家人健康档案数」，用户端展示时自动 +1 含本人。-1=不限">
              <InputNumber min={-1} style={{ width: 220 }} />
            </Form.Item>
            <Form.Item label="AI 外呼提醒（次/月）" name="ai_outbound_call_count"
              rules={[{ required: true }]} tooltip="-1=不限">
              <InputNumber min={-1} style={{ width: 180 }} />
            </Form.Item>
          </Space>

          <Space size="large" style={{ width: '100%' }}>
            <Form.Item label="紧急 AI 呼叫（次/月）" name="emergency_ai_call_count"
              rules={[{ required: true }]} tooltip="-1=不限">
              <InputNumber min={-1} style={{ width: 180 }} />
            </Form.Item>
            <Form.Item label="被管理人数上限" name="max_managed_by"
              rules={[{ required: true }]} tooltip="-1=不限">
              <InputNumber min={-1} style={{ width: 180 }} />
            </Form.Item>
          </Space>

          <Space size="large" style={{ width: '100%' }}>
            <Form.Item label="排序（越小越靠前）" name="sort_order">
              <InputNumber style={{ width: 180 }} />
            </Form.Item>
            <Form.Item label="是否启用" name="is_active" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item label="是否推荐（金色描边+推荐角标）" name="is_recommended" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  );
}
