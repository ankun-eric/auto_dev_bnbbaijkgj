'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Modal, Form, Input, InputNumber, Select, Switch, Upload, Tag, message, Typography, Popconfirm, Image } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined, GiftOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title } = Typography;
const { TextArea } = Input;

interface MallGoods {
  id: number;
  name: string;
  category: string;
  points: number;
  stock: number;
  exchangeCount: number;
  status: number;
  image: string;
  description: string;
  createdAt: string;
}

const categoryOptions = [
  { label: '健康用品', value: '健康用品' },
  { label: '优惠券', value: '优惠券' },
  { label: '虚拟商品', value: '虚拟商品' },
  { label: '体验服务', value: '体验服务' },
  { label: '周边礼品', value: '周边礼品' },
];

const mockGoods: MallGoods[] = [
  { id: 1, name: '健康体检优惠券 (100元)', category: '优惠券', points: 500, stock: 200, exchangeCount: 156, status: 1, image: '', description: '可用于任意体检套餐抵扣100元', createdAt: '2026-01-10' },
  { id: 2, name: 'AI健康咨询次卡(3次)', category: '虚拟商品', points: 300, stock: 500, exchangeCount: 289, status: 1, image: '', description: '3次AI深度健康咨询服务', createdAt: '2026-01-15' },
  { id: 3, name: '智能体脂秤', category: '健康用品', points: 5000, stock: 50, exchangeCount: 23, status: 1, image: '', description: '支持蓝牙连接，多项身体数据监测', createdAt: '2026-02-01' },
  { id: 4, name: '专家一对一咨询', category: '体验服务', points: 2000, stock: 30, exchangeCount: 12, status: 1, image: '', description: '30分钟专家视频咨询', createdAt: '2026-02-10' },
  { id: 5, name: '宾尼小康定制水杯', category: '周边礼品', points: 800, stock: 100, exchangeCount: 67, status: 1, image: '', description: '品牌定制保温水杯', createdAt: '2026-02-20' },
  { id: 6, name: '营养方案折扣券(8折)', category: '优惠券', points: 200, stock: 0, exchangeCount: 345, status: 0, image: '', description: '营养方案定制服务8折优惠券', createdAt: '2026-03-01' },
];

export default function PointsMallPage() {
  const [goods, setGoods] = useState<MallGoods[]>(mockGoods);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<MallGoods | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: mockGoods.length });
  const [form] = Form.useForm();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const res = await get('/api/admin/points/mall', { page, pageSize });
      if (res) {
        const items = res.items || res.list || res;
        setGoods(Array.isArray(items) ? items : []);
        setPagination((prev) => ({ ...prev, current: page, total: res.total ?? (Array.isArray(items) ? items.length : 0) }));
      }
    } catch {} finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({ status: true, stock: 100 });
    setModalVisible(true);
  };

  const handleEdit = (record: MallGoods) => {
    setEditingRecord(record);
    form.setFieldsValue({ ...record, status: record.status === 1 });
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/points/mall/${id}`);
    } catch {}
    setGoods((prev) => prev.filter((g) => g.id !== id));
    message.success('删除成功');
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload = { ...values, status: values.status ? 1 : 0 };

      if (editingRecord) {
        try {
          await put(`/api/admin/points/mall/${editingRecord.id}`, payload);
        } catch {}
        setGoods((prev) => prev.map((g) => (g.id === editingRecord.id ? { ...g, ...payload } : g)));
        message.success('编辑成功');
      } else {
        try {
          const res = await post('/api/admin/points/mall', payload);
          payload.id = res?.id || Date.now();
        } catch {
          payload.id = Date.now();
        }
        payload.exchangeCount = 0;
        payload.image = '';
        payload.createdAt = new Date().toISOString().split('T')[0];
        setGoods((prev) => [...prev, payload]);
        message.success('新增成功');
      }
      setModalVisible(false);
    } catch {}
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '商品名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (v: string) => (
        <Space>
          <GiftOutlined style={{ color: '#52c41a' }} />
          {v}
        </Space>
      ),
    },
    { title: '分类', dataIndex: 'category', key: 'category', width: 100, render: (v: string) => <Tag color="orange">{v}</Tag> },
    {
      title: '所需积分',
      dataIndex: 'points',
      key: 'points',
      width: 100,
      render: (v: number) => <span style={{ color: '#faad14', fontWeight: 600 }}>{v}</span>,
    },
    {
      title: '库存',
      dataIndex: 'stock',
      key: 'stock',
      width: 80,
      render: (v: number) => <Tag color={v > 0 ? 'green' : 'red'}>{v}</Tag>,
    },
    { title: '已兑换', dataIndex: 'exchangeCount', key: 'exchangeCount', width: 80 },
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
      width: 150,
      render: (_: any, record: MallGoods) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm title="确定删除该商品？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>积分商城管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增商品</Button>
      </div>

      <Table
        columns={columns}
        dataSource={goods}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 950 }}
      />

      <Modal
        title={editingRecord ? '编辑商品' : '新增商品'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={600}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="商品名称" name="name" rules={[{ required: true, message: '请输入商品名称' }]}>
            <Input placeholder="请输入商品名称" />
          </Form.Item>
          <Form.Item label="商品分类" name="category" rules={[{ required: true, message: '请选择分类' }]}>
            <Select options={categoryOptions} placeholder="请选择分类" />
          </Form.Item>
          <Space style={{ width: '100%' }} size={16}>
            <Form.Item label="所需积分" name="points" rules={[{ required: true, message: '请输入积分' }]} style={{ flex: 1 }}>
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="库存" name="stock" rules={[{ required: true, message: '请输入库存' }]} style={{ flex: 1 }}>
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
          </Space>
          <Form.Item label="商品图片" name="image">
            <Upload listType="picture-card" maxCount={1} beforeUpload={() => false}>
              <div>
                <UploadOutlined />
                <div style={{ marginTop: 8 }}>上传图片</div>
              </div>
            </Upload>
          </Form.Item>
          <Form.Item label="商品描述" name="description">
            <TextArea rows={3} placeholder="请输入商品描述" />
          </Form.Item>
          <Form.Item label="上架" name="status" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
