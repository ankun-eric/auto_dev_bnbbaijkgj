'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Modal, Form, Input, InputNumber, Select, Switch, Upload, Tag, message, Typography, Popconfirm } from 'antd';
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
  status: string;
  image: string;
  description: string;
  createdAt: string;
}

const TYPE_LABELS: Record<string, string> = {
  virtual: '虚拟商品',
  physical: '实物商品',
  service: '体验服务',
  third_party: '第三方商品',
};

const categoryOptions = [
  { label: '虚拟商品', value: 'virtual' },
  { label: '实物商品', value: 'physical' },
  { label: '体验服务', value: 'service' },
  { label: '第三方商品', value: 'third_party' },
];

function firstImage(images: unknown): string {
  if (Array.isArray(images) && images.length > 0) return String(images[0]);
  if (typeof images === 'string') return images;
  return '';
}

function mapMallItemFromApi(raw: Record<string, unknown>): MallGoods {
  const typeKey = String(raw.type ?? '');
  return {
    id: Number(raw.id),
    name: String(raw.name ?? ''),
    category: typeKey,
    points: Number(raw.price_points ?? 0),
    stock: Number(raw.stock ?? 0),
    status: String(raw.status ?? ''),
    image: firstImage(raw.images),
    description: String(raw.description ?? ''),
    createdAt: String(raw.created_at ?? ''),
  };
}

function isMallOnShelf(status: string) {
  return status === 'active';
}

export default function PointsMallPage() {
  const [goods, setGoods] = useState<MallGoods[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<MallGoods | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [form] = Form.useForm();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const res = await get('/api/admin/points/mall', { page, page_size: pageSize });
      if (res) {
        const items = res.items || res.list || res;
        const rawList = Array.isArray(items) ? items : [];
        setGoods(rawList.map((r: Record<string, unknown>) => mapMallItemFromApi(r)));
        setPagination((prev) => ({ ...prev, current: page, total: res.total ?? rawList.length }));
      }
    } catch {
      setGoods([]);
      setPagination((prev) => ({ ...prev, current: page, total: 0 }));
    } finally {
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
    form.setFieldsValue({
      name: record.name,
      category: categoryOptions.some((o) => o.value === record.category) ? record.category : 'virtual',
      points: record.points,
      stock: record.stock,
      image: record.image,
      description: record.description,
      status: isMallOnShelf(record.status),
    });
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
      const onShelf = Boolean(values.status);
      const statusStr = onShelf ? 'active' : 'inactive';
      const payload = {
        name: values.name,
        type: values.category,
        price_points: values.points,
        stock: values.stock,
        description: values.description,
        status: statusStr,
        images: values.image ? [values.image] : [],
      };

      if (editingRecord) {
        try {
          await put(`/api/admin/points/mall/${editingRecord.id}`, payload);
        } catch {}
        setGoods((prev) =>
          prev.map((g) =>
            g.id === editingRecord.id
              ? {
                  ...g,
                  name: values.name,
                  category: values.category,
                  points: values.points,
                  stock: values.stock,
                  description: values.description ?? g.description,
                  status: statusStr,
                  image: typeof values.image === 'string' ? values.image : g.image,
                  createdAt: g.createdAt,
                }
              : g
          )
        );
        message.success('编辑成功');
      } else {
        const localRow: MallGoods = {
          id: Date.now(),
          name: values.name,
          category: values.category,
          points: values.points,
          stock: values.stock,
          status: statusStr,
          image: typeof values.image === 'string' ? values.image : '',
          description: values.description ?? '',
          createdAt: new Date().toISOString().split('T')[0],
        };
        try {
          const res = await post('/api/admin/points/mall', payload);
          if (res?.id != null) localRow.id = res.id;
        } catch {}
        setGoods((prev) => [...prev, localRow]);
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
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: (v: string) => <Tag color="orange">{TYPE_LABELS[v] ?? v}</Tag>,
    },
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
    {
      title: '已兑换',
      dataIndex: 'exchangeCount',
      key: 'exchangeCount',
      width: 80,
      render: () => '—',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: string) => (
        <Tag color={isMallOnShelf(v) ? 'green' : 'red'}>{isMallOnShelf(v) ? '上架' : '下架'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: unknown, record: MallGoods) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除该商品？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>
          积分商城管理
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          新增商品
        </Button>
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
