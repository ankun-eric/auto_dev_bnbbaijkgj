'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Modal, Form, Input, InputNumber, Select, Switch, Upload, message, Typography, Tag, Popconfirm, Image } from 'antd';
import { PlusOutlined, EditOutlined, UploadOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import { get, post, put } from '@/lib/api';

const { Title } = Typography;
const { TextArea } = Input;

interface ServiceItem {
  id: number;
  name: string;
  categoryId: number;
  categoryName: string;
  price: number;
  originalPrice: number;
  stock: number;
  sales: number;
  status: number;
  image: string;
  description: string;
  createdAt: string;
}

const mockItems: ServiceItem[] = [
  { id: 1, name: 'AI智能问诊', categoryId: 1, categoryName: 'AI健康咨询', price: 9.9, originalPrice: 29.9, stock: 999, sales: 1256, status: 1, image: '', description: '24小时AI智能健康问诊服务', createdAt: '2026-01-20' },
  { id: 2, name: '深度健康咨询', categoryId: 1, categoryName: 'AI健康咨询', price: 99, originalPrice: 199, stock: 500, sales: 328, status: 1, image: '', description: '深度AI健康分析与建议', createdAt: '2026-01-25' },
  { id: 3, name: '个性化营养方案', categoryId: 2, categoryName: '营养管理', price: 299, originalPrice: 599, stock: 200, sales: 156, status: 1, image: '', description: '根据个人体质定制营养方案', createdAt: '2026-02-01' },
  { id: 4, name: '体检报告解读', categoryId: 3, categoryName: '体检服务', price: 49, originalPrice: 99, stock: 1000, sales: 892, status: 1, image: '', description: 'AI智能解读体检报告', createdAt: '2026-02-10' },
  { id: 5, name: '心理健康评估', categoryId: 4, categoryName: '心理健康', price: 149, originalPrice: 299, stock: 300, sales: 234, status: 1, image: '', description: '专业心理健康量表评估', createdAt: '2026-02-20' },
  { id: 6, name: '中医体质辨识', categoryId: 5, categoryName: '中医养生', price: 199, originalPrice: 399, stock: 150, sales: 98, status: 0, image: '', description: '传统中医九种体质辨识', createdAt: '2026-03-01' },
];

const categoryOptions = [
  { label: 'AI健康咨询', value: 1 },
  { label: '营养管理', value: 2 },
  { label: '体检服务', value: 3 },
  { label: '心理健康', value: 4 },
  { label: '中医养生', value: 5 },
  { label: '运动健身', value: 6 },
];

export default function ServiceItemsPage() {
  const [items, setItems] = useState<ServiceItem[]>(mockItems);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<ServiceItem | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: mockItems.length });
  const [form] = Form.useForm();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const res = await get('/api/admin/services/items', { page, pageSize });
      if (res) {
        const items = res.items || res.list || res;
        setItems(Array.isArray(items) ? items : []);
        setPagination((prev) => ({ ...prev, current: page, total: res.total ?? (Array.isArray(items) ? items.length : 0) }));
      }
    } catch {} finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({ status: true, stock: 999 });
    setModalVisible(true);
  };

  const handleEdit = (record: ServiceItem) => {
    setEditingRecord(record);
    form.setFieldsValue({ ...record, status: record.status === 1 });
    setModalVisible(true);
  };

  const handleToggleStatus = async (record: ServiceItem) => {
    const newStatus = record.status === 1 ? 0 : 1;
    try {
      await put(`/api/admin/services/items/${record.id}`, { status: newStatus });
    } catch {}
    setItems((prev) => prev.map((i) => (i.id === record.id ? { ...i, status: newStatus } : i)));
    message.success(newStatus === 1 ? '已上架' : '已下架');
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload = {
        ...values,
        status: values.status ? 1 : 0,
        categoryName: categoryOptions.find((c) => c.value === values.categoryId)?.label || '',
      };

      if (editingRecord) {
        try {
          await put(`/api/admin/services/items/${editingRecord.id}`, payload);
        } catch {}
        setItems((prev) => prev.map((i) => (i.id === editingRecord.id ? { ...i, ...payload } : i)));
        message.success('编辑成功');
      } else {
        try {
          const res = await post('/api/admin/services/items', payload);
          payload.id = res?.id || Date.now();
        } catch {
          payload.id = Date.now();
        }
        payload.sales = 0;
        payload.image = '';
        payload.createdAt = new Date().toISOString().split('T')[0];
        setItems((prev) => [...prev, payload]);
        message.success('新增成功');
      }
      setModalVisible(false);
    } catch {}
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '服务名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '分类', dataIndex: 'categoryName', key: 'categoryName', width: 110, render: (v: string) => <Tag color="cyan">{v}</Tag> },
    { title: '价格', dataIndex: 'price', key: 'price', width: 90, render: (v: number) => <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{v}</span> },
    { title: '原价', dataIndex: 'originalPrice', key: 'originalPrice', width: 90, render: (v: number) => <span style={{ textDecoration: 'line-through', color: '#999' }}>¥{v}</span> },
    { title: '库存', dataIndex: 'stock', key: 'stock', width: 70 },
    { title: '销量', dataIndex: 'sales', key: 'sales', width: 70 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: number) => <Tag color={v === 1 ? 'green' : 'red'}>{v === 1 ? '上架' : '下架'}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: any, record: ServiceItem) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm title={record.status === 1 ? '确定下架？' : '确定上架？'} onConfirm={() => handleToggleStatus(record)}>
            <Button type="link" size="small" icon={record.status === 1 ? <ArrowDownOutlined /> : <ArrowUpOutlined />}>
              {record.status === 1 ? '下架' : '上架'}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>服务项目管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增服务</Button>
      </div>

      <Table
        columns={columns}
        dataSource={items}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1000 }}
      />

      <Modal
        title={editingRecord ? '编辑服务' : '新增服务'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="服务名称" name="name" rules={[{ required: true, message: '请输入服务名称' }]}>
            <Input placeholder="请输入服务名称" />
          </Form.Item>
          <Form.Item label="服务分类" name="categoryId" rules={[{ required: true, message: '请选择分类' }]}>
            <Select options={categoryOptions} placeholder="请选择分类" />
          </Form.Item>
          <Space style={{ width: '100%' }} size={16}>
            <Form.Item label="售价 (元)" name="price" rules={[{ required: true, message: '请输入价格' }]} style={{ flex: 1 }}>
              <InputNumber min={0} step={0.01} style={{ width: '100%' }} placeholder="0.00" />
            </Form.Item>
            <Form.Item label="原价 (元)" name="originalPrice" style={{ flex: 1 }}>
              <InputNumber min={0} step={0.01} style={{ width: '100%' }} placeholder="0.00" />
            </Form.Item>
          </Space>
          <Form.Item label="库存" name="stock" rules={[{ required: true, message: '请输入库存' }]}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="服务图片" name="image">
            <Upload listType="picture-card" maxCount={1} beforeUpload={() => false}>
              <div>
                <UploadOutlined />
                <div style={{ marginTop: 8 }}>上传图片</div>
              </div>
            </Upload>
          </Form.Item>
          <Form.Item label="服务描述" name="description">
            <TextArea rows={4} placeholder="请输入服务描述" />
          </Form.Item>
          <Form.Item label="上架" name="status" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
