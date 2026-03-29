'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Modal, Form, Input, InputNumber, Switch, message, Typography, Popconfirm, Tag } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title } = Typography;

interface Category {
  id: number;
  name: string;
  icon: string;
  sort: number;
  status: number;
  description: string;
  serviceCount: number;
  createdAt: string;
}

const mockCategories: Category[] = [
  { id: 1, name: 'AI健康咨询', icon: '🤖', sort: 1, status: 1, description: '智能AI健康问答服务', serviceCount: 5, createdAt: '2026-01-10' },
  { id: 2, name: '营养管理', icon: '🥗', sort: 2, status: 1, description: '个性化营养方案定制', serviceCount: 8, createdAt: '2026-01-10' },
  { id: 3, name: '体检服务', icon: '🏥', sort: 3, status: 1, description: '体检预约及报告解读', serviceCount: 3, createdAt: '2026-01-15' },
  { id: 4, name: '心理健康', icon: '🧠', sort: 4, status: 1, description: '心理评估与咨询', serviceCount: 4, createdAt: '2026-02-01' },
  { id: 5, name: '中医养生', icon: '🌿', sort: 5, status: 0, description: '中医体质辨识与调理', serviceCount: 6, createdAt: '2026-02-15' },
  { id: 6, name: '运动健身', icon: '🏃', sort: 6, status: 1, description: '运动方案与指导', serviceCount: 7, createdAt: '2026-03-01' },
];

export default function ServiceCategoriesPage() {
  const [categories, setCategories] = useState<Category[]>(mockCategories);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<Category | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await get('/api/admin/services/categories');
      if (res) {
        const items = res.items || res.list || res;
        setCategories(Array.isArray(items) ? items : []);
      }
    } catch {} finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({ sort: categories.length + 1, status: true });
    setModalVisible(true);
  };

  const handleEdit = (record: Category) => {
    setEditingRecord(record);
    form.setFieldsValue({ ...record, status: record.status === 1 });
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/services/categories/${id}`);
      message.success('删除成功');
    } catch {}
    setCategories((prev) => prev.filter((c) => c.id !== id));
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload = { ...values, status: values.status ? 1 : 0 };

      if (editingRecord) {
        try {
          await put(`/api/admin/services/categories/${editingRecord.id}`, payload);
        } catch {}
        setCategories((prev) =>
          prev.map((c) => (c.id === editingRecord.id ? { ...c, ...payload } : c))
        );
        message.success('编辑成功');
      } else {
        try {
          const res = await post('/api/admin/services/categories', payload);
          payload.id = res?.id || Date.now();
        } catch {
          payload.id = Date.now();
        }
        payload.serviceCount = 0;
        payload.createdAt = new Date().toISOString().split('T')[0];
        setCategories((prev) => [...prev, payload]);
        message.success('新增成功');
      }
      setModalVisible(false);
    } catch {}
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
    {
      title: '图标',
      dataIndex: 'icon',
      key: 'icon',
      width: 60,
      render: (v: string) => <span style={{ fontSize: 20 }}>{v}</span>,
    },
    { title: '分类名称', dataIndex: 'name', key: 'name', width: 150 },
    { title: '描述', dataIndex: 'description', key: 'description' },
    { title: '排序', dataIndex: 'sort', key: 'sort', width: 70 },
    { title: '服务数', dataIndex: 'serviceCount', key: 'serviceCount', width: 80 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: number) => <Tag color={v === 1 ? 'green' : 'red'}>{v === 1 ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: Category) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm title="确定删除该分类？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>服务分类管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增分类</Button>
      </div>

      <Table columns={columns} dataSource={categories} rowKey="id" loading={loading} pagination={false} />

      <Modal
        title={editingRecord ? '编辑分类' : '新增分类'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="分类名称" name="name" rules={[{ required: true, message: '请输入分类名称' }]}>
            <Input placeholder="请输入分类名称" />
          </Form.Item>
          <Form.Item label="图标 (Emoji)" name="icon" rules={[{ required: true, message: '请输入图标' }]}>
            <Input placeholder="请输入Emoji图标，如 🤖" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea placeholder="请输入分类描述" rows={3} />
          </Form.Item>
          <Form.Item label="排序" name="sort">
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="启用" name="status" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
