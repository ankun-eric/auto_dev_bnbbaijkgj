'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Table, Button, Space, Modal, Form, Input, InputNumber, Select, Switch, Upload, message, Typography, Tag, Popconfirm } from 'antd';
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
  status: string;
  image: string;
  description: string;
  serviceType: string;
  createdAt: string;
}

interface CategoryOption {
  label: string;
  value: number;
}

function firstImage(images: unknown): string {
  if (Array.isArray(images) && images.length > 0) return String(images[0]);
  if (typeof images === 'string') return images;
  return '';
}

function mapServiceItemFromApi(raw: Record<string, unknown>, categoryMap: Map<number, string>): ServiceItem {
  const categoryId = Number(raw.category_id ?? 0);
  const categoryName = categoryMap.get(categoryId) ?? '未分类';
  return {
    id: Number(raw.id),
    name: String(raw.name ?? ''),
    categoryId,
    categoryName,
    price: Number(raw.price ?? 0),
    originalPrice: Number(raw.original_price ?? 0),
    stock: Number(raw.stock ?? 0),
    sales: Number(raw.sales_count ?? 0),
    status: String(raw.status ?? 'deleted'),
    image: firstImage(raw.images),
    description: String(raw.description ?? ''),
    serviceType: String(raw.service_type ?? 'online'),
    createdAt: String(raw.created_at ?? raw.updated_at ?? ''),
  };
}

function isServiceActive(status: string) {
  return status === 'active';
}

export default function ServiceItemsPage() {
  const [items, setItems] = useState<ServiceItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<ServiceItem | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [categoryOptions, setCategoryOptions] = useState<CategoryOption[]>([]);
  const [categoryMap, setCategoryMap] = useState<Map<number, string>>(new Map());
  const [form] = Form.useForm();

  const fetchCategories = useCallback(async () => {
    try {
      const res = await get('/api/admin/services/categories');
      if (res) {
        const rawList = res.items || res.list || res;
        if (Array.isArray(rawList)) {
          const opts: CategoryOption[] = rawList
            .filter((c: Record<string, unknown>) => c.status === 'active')
            .map((c: Record<string, unknown>) => ({
              label: String(c.name ?? ''),
              value: Number(c.id),
            }));
          const map = new Map<number, string>();
          rawList.forEach((c: Record<string, unknown>) => {
            map.set(Number(c.id), String(c.name ?? ''));
          });
          setCategoryOptions(opts);
          setCategoryMap(map);
          return map;
        }
      }
    } catch {}
    return new Map<number, string>();
  }, []);

  const fetchData = useCallback(async (page = 1, pageSize = 10, catMap?: Map<number, string>) => {
    setLoading(true);
    const usedMap = catMap ?? categoryMap;
    try {
      const res = await get('/api/admin/services/items', { page, page_size: pageSize });
      if (res) {
        const itemsRaw = res.items || res.list || res;
        const rawList = Array.isArray(itemsRaw) ? itemsRaw : [];
        setItems(rawList.map((r: Record<string, unknown>) => mapServiceItemFromApi(r, usedMap)));
        setPagination((prev) => ({ ...prev, current: page, total: res.total ?? rawList.length }));
      }
    } catch {
      setItems([]);
      setPagination((prev) => ({ ...prev, current: page, total: 0 }));
    } finally {
      setLoading(false);
    }
  }, [categoryMap]);

  useEffect(() => {
    (async () => {
      const catMap = await fetchCategories();
      await fetchData(1, 10, catMap);
    })();
  }, []);

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({ status: true, stock: 999, serviceType: 'online' });
    setModalVisible(true);
  };

  const handleEdit = (record: ServiceItem) => {
    setEditingRecord(record);
    form.setFieldsValue({
      name: record.name,
      categoryId: record.categoryId,
      price: record.price,
      originalPrice: record.originalPrice,
      stock: record.stock,
      image: record.image,
      description: record.description,
      serviceType: record.serviceType,
      status: isServiceActive(record.status),
    });
    setModalVisible(true);
  };

  const handleToggleStatus = async (record: ServiceItem) => {
    const newStatus = isServiceActive(record.status) ? 'deleted' : 'active';
    try {
      await put(`/api/admin/services/items/${record.id}`, { status: newStatus });
      message.success(isServiceActive(newStatus) ? '已上架' : '已下架');
      fetchData(pagination.current, pagination.pageSize);
    } catch {
      message.error('操作失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const statusStr = values.status ? 'active' : 'deleted';
      const payload = {
        name: values.name,
        category_id: values.categoryId,
        price: values.price,
        original_price: values.originalPrice,
        stock: values.stock,
        description: values.description,
        service_type: values.serviceType || 'online',
        status: statusStr,
        images: values.image ? [values.image] : [],
      };

      if (editingRecord) {
        await put(`/api/admin/services/items/${editingRecord.id}`, payload);
        message.success('编辑成功');
      } else {
        await post('/api/admin/services/items', payload);
        message.success('新增成功');
      }
      setModalVisible(false);
      fetchData(pagination.current, pagination.pageSize);
    } catch {
      message.error('操作失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '服务名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '分类', dataIndex: 'categoryName', key: 'categoryName', width: 110, render: (v: string) => <Tag color="cyan">{v}</Tag> },
    { title: '价格', dataIndex: 'price', key: 'price', width: 90, render: (v: number) => <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{v}</span> },
    {
      title: '原价',
      dataIndex: 'originalPrice',
      key: 'originalPrice',
      width: 90,
      render: (v: number) => v ? <span style={{ textDecoration: 'line-through', color: '#999' }}>¥{v}</span> : '—',
    },
    { title: '库存', dataIndex: 'stock', key: 'stock', width: 70 },
    { title: '销量', dataIndex: 'sales', key: 'sales', width: 70 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: string) => (
        <Tag color={isServiceActive(v) ? 'green' : 'red'}>{isServiceActive(v) ? '上架' : '下架'}</Tag>
      ),
    },
    { title: '创建时间', dataIndex: 'createdAt', key: 'createdAt', width: 160, render: (v: string) => v ? v.slice(0, 19).replace('T', ' ') : '' },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: unknown, record: ServiceItem) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title={isServiceActive(record.status) ? '确定下架？' : '确定上架？'}
            onConfirm={() => handleToggleStatus(record)}
          >
            <Button type="link" size="small" icon={isServiceActive(record.status) ? <ArrowDownOutlined /> : <ArrowUpOutlined />}>
              {isServiceActive(record.status) ? '下架' : '上架'}
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
          服务项目管理
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          新增服务
        </Button>
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
        scroll={{ x: 1100 }}
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
          <Form.Item label="服务类型" name="serviceType">
            <Select
              options={[
                { label: '线上服务', value: 'online' },
                { label: '线下服务', value: 'offline' },
              ]}
              placeholder="请选择服务类型"
            />
          </Form.Item>
          <Form.Item label="服务图片URL" name="image">
            <Input placeholder="请输入图片URL地址" />
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
