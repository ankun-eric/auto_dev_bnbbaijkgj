'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, MedicineBoxOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title } = Typography;

type Category = 'chronic' | 'allergy' | 'genetic';

const CATEGORY_MAP: Record<Category, string> = {
  chronic: '慢性病史',
  allergy: '过敏史',
  genetic: '家族遗传病史',
};

const CATEGORY_OPTIONS = Object.entries(CATEGORY_MAP).map(([value, label]) => ({ value, label }));

interface DiseasePresetItem {
  id: number;
  name: string;
  category: Category;
  sort_order: number;
  is_active: boolean;
  created_at: string | null;
}

function getIsSuperuser(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const raw = localStorage.getItem('admin_user');
    if (!raw) return false;
    const user = JSON.parse(raw);
    return user?.is_superuser === true;
  } catch {
    return false;
  }
}

export default function DiseasePresetsPage() {
  const [category, setCategory] = useState<string>('');
  const [data, setData] = useState<DiseasePresetItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [editingItem, setEditingItem] = useState<DiseasePresetItem | null>(null);
  const [isSuperuser, setIsSuperuser] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    setIsSuperuser(getIsSuperuser());
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (category) params.category = category;
      const res = await get<{ items: DiseasePresetItem[] }>('/api/admin/disease-presets', params);
      setData(res.items ?? []);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const openCreate = () => {
    setEditingItem(null);
    form.resetFields();
    form.setFieldsValue({ sort_order: 0, is_active: true });
    setModalOpen(true);
  };

  const openEdit = (item: DiseasePresetItem) => {
    setEditingItem(item);
    form.setFieldsValue({
      name: item.name,
      category: item.category,
      sort_order: item.sort_order,
      is_active: item.is_active,
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setModalLoading(true);
      if (editingItem) {
        await put(`/api/admin/disease-presets/${editingItem.id}`, values);
        message.success('更新成功');
      } else {
        await post('/api/admin/disease-presets', values);
        message.success('创建成功');
      }
      setModalOpen(false);
      fetchData();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      if (err?.response) {
        message.error(err?.response?.data?.detail || '操作失败');
      }
    } finally {
      setModalLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/disease-presets/${id}`);
      message.success('删除成功');
      fetchData();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '删除失败');
    }
  };

  const columns = useMemo(() => {
    const cols = [
      { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
      { title: '病种名称', dataIndex: 'name', key: 'name' },
      {
        title: '分类',
        dataIndex: 'category',
        key: 'category',
        width: 140,
        render: (v: Category) => CATEGORY_MAP[v] || v,
      },
      { title: '排序值', dataIndex: 'sort_order', key: 'sort_order', width: 100 },
      {
        title: '状态',
        dataIndex: 'is_active',
        key: 'is_active',
        width: 100,
        render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '禁用'}</Tag>,
      },
    ];

    if (isSuperuser) {
      cols.push({
        title: '操作',
        key: 'action',
        width: 140,
        dataIndex: '' as any,
        render: ((_: unknown, record: DiseasePresetItem) => (
          <Space>
            <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
              编辑
            </Button>
            <Popconfirm title="确定删除该预设？" onConfirm={() => handleDelete(record.id)}>
              <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        )) as any,
      });
    }

    return cols;
  }, [isSuperuser]);

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>
        <MedicineBoxOutlined style={{ marginRight: 8, color: '#52c41a' }} />
        预设列表管理
      </Title>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Select
          value={category}
          onChange={setCategory}
          style={{ width: 200 }}
          options={[{ value: '', label: '全部' }, ...CATEGORY_OPTIONS]}
        />
        {isSuperuser && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新增预设
          </Button>
        )}
      </div>

      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        pagination={false}
        scroll={{ x: 600 }}
      />

      <Modal
        title={editingItem ? '编辑预设' : '新增预设'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={modalLoading}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="分类"
            name="category"
            rules={[{ required: true, message: '请选择分类' }]}
          >
            <Select placeholder="请选择分类" options={CATEGORY_OPTIONS} />
          </Form.Item>
          <Form.Item
            label="病种名称"
            name="name"
            rules={[{ required: true, message: '请输入病种名称' }]}
          >
            <Input placeholder="如：高血压、糖尿病..." maxLength={100} />
          </Form.Item>
          <Form.Item label="排序值" name="sort_order">
            <InputNumber min={0} max={9999} style={{ width: '100%' }} placeholder="数字越小越靠前" />
          </Form.Item>
          <Form.Item label="状态" name="is_active" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
