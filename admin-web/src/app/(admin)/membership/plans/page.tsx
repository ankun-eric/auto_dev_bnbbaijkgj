'use client';

/**
 * [付费会员体系 PRD v1.1] 付费会员套餐配置页
 *
 * 路径：/membership/plans
 * 功能：
 * - 套餐列表（守护版/家庭版/年度版等）
 * - 新增/编辑/软下线套餐
 * - 字段：套餐编码、名称、月/年价格、AI 各类额度、守护人上限、商城折扣率、权益描述、是否启用、排序
 * - 与「免费会员额度」入口（同页右上角入口跳转 /membership/free-quota）
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
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, CrownOutlined, SettingOutlined } from '@ant-design/icons';
import Link from 'next/link';
import { del, get, post, put } from '@/lib/api';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

interface MembershipPlan {
  id: number;
  plan_code: string;
  name: string;
  price_monthly: number;
  price_yearly: number | null;
  ai_call_quota: number;
  ai_alert_quota: number;
  ai_remind_quota: number;
  max_guardians: number;
  discount_rate: number;
  benefits_desc: string | null;
  is_active: boolean;
  sort_order: number;
}

export default function MembershipPlansPage() {
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editing, setEditing] = useState<MembershipPlan | null>(null);
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await get('/api/admin/membership/plans?include_inactive=true');
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
      price_monthly: 0,
      price_yearly: null,
      ai_call_quota: 0,
      ai_alert_quota: 0,
      ai_remind_quota: 0,
      max_guardians: 1,
      discount_rate: 1.0,
      is_active: true,
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
      await del(`/api/admin/membership/plans/${id}`);
      message.success('已下线（软删除）');
      fetchData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '下线失败');
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
      } else if (e?.errorFields) {
        // 表单校验错误，UI 已提示
      } else {
        message.error('保存失败');
      }
    }
  };

  const columns = [
    {
      title: '套餐',
      dataIndex: 'name',
      width: 180,
      render: (name: string, record: MembershipPlan) => (
        <Space direction="vertical" size={0}>
          <Space>
            <CrownOutlined style={{ color: '#faad14' }} />
            <strong>{name}</strong>
            {!record.is_active && <Tag color="default">已下线</Tag>}
          </Space>
          <span style={{ color: '#999', fontSize: 12 }}>code: {record.plan_code}</span>
        </Space>
      ),
    },
    {
      title: '价格（月/年）',
      key: 'price',
      width: 160,
      render: (_: any, r: MembershipPlan) => (
        <div>
          <div>月：¥{Number(r.price_monthly || 0).toFixed(2)}</div>
          <div style={{ color: '#888' }}>年：{r.price_yearly != null ? `¥${Number(r.price_yearly).toFixed(2)}` : '—'}</div>
        </div>
      ),
    },
    {
      title: 'AI 电话告警',
      dataIndex: 'ai_call_quota',
      width: 110,
      render: (n: number) => `${n} 次/月`,
    },
    {
      title: 'AI 异常告警',
      dataIndex: 'ai_alert_quota',
      width: 110,
      render: (n: number) => `${n} 次/月`,
    },
    {
      title: 'AI 外呼提醒',
      dataIndex: 'ai_remind_quota',
      width: 110,
      render: (n: number) => `${n} 次/月`,
    },
    { title: '守护人上限', dataIndex: 'max_guardians', width: 100 },
    {
      title: '商城折扣',
      dataIndex: 'discount_rate',
      width: 100,
      render: (r: number) => <Tag color="blue">{Number(r).toFixed(2)} 折</Tag>,
    },
    { title: '排序', dataIndex: 'sort_order', width: 80 },
    {
      title: '启用',
      dataIndex: 'is_active',
      width: 80,
      render: (v: boolean) => (v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>),
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: any, r: MembershipPlan) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(r)}>
            编辑
          </Button>
          <Popconfirm title="下线该套餐？" onConfirm={() => handleDelete(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />}>
              下线
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
            <CrownOutlined style={{ color: '#faad14' }} /> 付费会员套餐配置
          </Title>
          <Paragraph type="secondary" style={{ marginTop: 4 }}>
            付费会员体系 v1.1：以付费订阅为核心，提供 AI 电话外呼额度、AI 提醒额度、守护人数量上限、商城折扣等可量化权益。
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

      <Table rowKey="id" columns={columns} dataSource={plans} loading={loading} pagination={false} />

      <Modal
        title={editing ? '编辑套餐' : '新增套餐'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={720}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Space size="large" style={{ width: '100%' }}>
            <Form.Item label="套餐编码" name="plan_code" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Input placeholder="如 guardian / family / annual" />
            </Form.Item>
            <Form.Item label="套餐名称" name="name" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Input placeholder="如 守护版 / 家庭版" />
            </Form.Item>
          </Space>

          <Space size="large" style={{ width: '100%' }}>
            <Form.Item label="月度价格（元）" name="price_monthly" rules={[{ required: true }]}>
              <InputNumber min={0} step={0.01} style={{ width: 180 }} />
            </Form.Item>
            <Form.Item label="年度价格（元，可选）" name="price_yearly">
              <InputNumber min={0} step={0.01} style={{ width: 180 }} />
            </Form.Item>
            <Form.Item label="商城折扣率" name="discount_rate" tooltip="0.9 表示 9 折，1.0 表示无折扣">
              <InputNumber min={0.01} max={1} step={0.01} style={{ width: 140 }} />
            </Form.Item>
          </Space>

          <Space size="large" style={{ width: '100%' }}>
            <Form.Item label="AI 电话告警额度（次/月）" name="ai_call_quota">
              <InputNumber min={0} style={{ width: 180 }} />
            </Form.Item>
            <Form.Item label="AI 异常告警额度（次/月）" name="ai_alert_quota">
              <InputNumber min={0} style={{ width: 180 }} />
            </Form.Item>
            <Form.Item label="AI 外呼提醒额度（次/月）" name="ai_remind_quota">
              <InputNumber min={0} style={{ width: 180 }} />
            </Form.Item>
          </Space>

          <Space size="large" style={{ width: '100%' }}>
            <Form.Item label="守护人数量上限" name="max_guardians" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: 180 }} />
            </Form.Item>
            <Form.Item label="排序（越小越靠前）" name="sort_order">
              <InputNumber style={{ width: 180 }} />
            </Form.Item>
            <Form.Item label="是否启用" name="is_active" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>

          <Form.Item label="套餐权益描述" name="benefits_desc">
            <TextArea rows={4} placeholder="支持纯文本或 HTML，将展示在用户端会员卡片与权益详情页" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
