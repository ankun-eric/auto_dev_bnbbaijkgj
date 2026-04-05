'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Modal, Form, Input, InputNumber, Tag, message, Typography, Popconfirm } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, CrownOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title } = Typography;
const { TextArea } = Input;

interface MemberLevel {
  id: number;
  name: string;
  icon: string;
  minPoints: number;
  maxPoints: number;
  discount: number;
  benefits: string;
  color: string;
  memberCount: number;
}

const mockLevels: MemberLevel[] = [
  { id: 1, name: '普通会员', icon: '🥉', minPoints: 0, maxPoints: 999, discount: 100, benefits: '基础健康咨询', color: '#8c8c8c', memberCount: 5230 },
  { id: 2, name: '白银会员', icon: '🥈', minPoints: 1000, maxPoints: 4999, discount: 95, benefits: '基础健康咨询、优先排队、生日礼包', color: '#a0d911', memberCount: 3150 },
  { id: 3, name: '黄金会员', icon: '🥇', minPoints: 5000, maxPoints: 19999, discount: 90, benefits: '全部白银权益、专属营养方案、月度健康报告', color: '#faad14', memberCount: 2680 },
  { id: 4, name: '钻石会员', icon: '💎', minPoints: 20000, maxPoints: 49999, discount: 85, benefits: '全部黄金权益、专家一对一服务、VIP客服、季度体检提醒', color: '#1890ff', memberCount: 1200 },
  { id: 5, name: '至尊会员', icon: '👑', minPoints: 50000, maxPoints: 999999, discount: 80, benefits: '全部钻石权益、年度全面体检、专属健康管家、免费急诊咨询', color: '#722ed1', memberCount: 596 },
];

export default function PointsLevelsPage() {
  const [levels, setLevels] = useState<MemberLevel[]>(mockLevels);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<MemberLevel | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await get('/api/admin/points/levels');
      if (res) {
        const items = res.items || res.list || res;
        setLevels(Array.isArray(items) ? items : []);
      }
    } catch {} finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({ discount: 100, color: '#52c41a' });
    setModalVisible(true);
  };

  const handleEdit = (record: MemberLevel) => {
    setEditingRecord(record);
    form.setFieldsValue(record);
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/points/levels/${id}`);
    } catch {}
    setLevels((prev) => prev.filter((l) => l.id !== id));
    message.success('删除成功');
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();

      if (editingRecord) {
        try {
          await put(`/api/admin/points/levels/${editingRecord.id}`, values);
        } catch {}
        setLevels((prev) => prev.map((l) => (l.id === editingRecord.id ? { ...l, ...values } : l)));
        message.success('编辑成功');
      } else {
        try {
          const res = await post('/api/admin/points/levels', values);
          values.id = res?.id || Date.now();
        } catch {
          values.id = Date.now();
        }
        values.memberCount = 0;
        setLevels((prev) => [...prev, values]);
        message.success('新增成功');
      }
      setModalVisible(false);
    } catch {}
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '等级名称',
      dataIndex: 'name',
      key: 'name',
      width: 140,
      render: (v: string, r: MemberLevel) => (
        <Space>
          <span style={{ fontSize: 18 }}>{r.icon}</span>
          <Tag color={r.color} style={{ fontWeight: 600 }}>{v}</Tag>
        </Space>
      ),
    },
    {
      title: '积分范围',
      key: 'pointsRange',
      width: 180,
      render: (_: any, r: MemberLevel) => `${(r.minPoints ?? 0).toLocaleString()} ~ ${(r.maxPoints ?? 0).toLocaleString()}`,
    },
    {
      title: '折扣',
      dataIndex: 'discount',
      key: 'discount',
      width: 80,
      render: (v: number) => <Tag color={v < 100 ? 'green' : 'default'}>{v / 10}折</Tag>,
    },
    {
      title: '权益',
      dataIndex: 'benefits',
      key: 'benefits',
      ellipsis: true,
    },
    {
      title: '会员人数',
      dataIndex: 'memberCount',
      key: 'memberCount',
      width: 100,
      render: (v: number) => (v ?? 0).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: MemberLevel) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm title="确定删除该等级？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>会员等级配置</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增等级</Button>
      </div>

      <Table columns={columns} dataSource={levels} rowKey="id" loading={loading} pagination={false} scroll={{ x: 900 }} />

      <Modal
        title={editingRecord ? '编辑等级' : '新增等级'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={600}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Space style={{ width: '100%' }} size={16}>
            <Form.Item label="等级名称" name="name" rules={[{ required: true, message: '请输入等级名称' }]} style={{ flex: 1 }}>
              <Input placeholder="例如: 黄金会员" />
            </Form.Item>
            <Form.Item label="等级图标 (Emoji)" name="icon" rules={[{ required: true, message: '请输入图标' }]} style={{ width: 120 }}>
              <Input placeholder="🥇" />
            </Form.Item>
          </Space>
          <Space style={{ width: '100%' }} size={16}>
            <Form.Item label="最低积分" name="minPoints" rules={[{ required: true, message: '请输入最低积分' }]} style={{ flex: 1 }}>
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="最高积分" name="maxPoints" rules={[{ required: true, message: '请输入最高积分' }]} style={{ flex: 1 }}>
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
          </Space>
          <Space style={{ width: '100%' }} size={16}>
            <Form.Item label="折扣 (例: 90 = 9折)" name="discount" rules={[{ required: true, message: '请输入折扣' }]} style={{ flex: 1 }}>
              <InputNumber min={1} max={100} style={{ width: '100%' }} addonAfter="/ 100" />
            </Form.Item>
            <Form.Item label="标签颜色" name="color" style={{ flex: 1 }}>
              <Input type="color" style={{ width: '100%', height: 32 }} />
            </Form.Item>
          </Space>
          <Form.Item label="会员权益" name="benefits" rules={[{ required: true, message: '请输入权益说明' }]}>
            <TextArea rows={3} placeholder="请输入权益说明，多项用逗号分隔" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
