'use client';

import React, { useCallback, useEffect, useState } from 'react';
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
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title } = Typography;
const { TextArea } = Input;

interface DefaultTaskItem {
  id: number;
  name: string;
  description: string | null;
  category_type: string | null;
  sort_order: number;
  is_active: boolean;
  created_at: string | null;
}

const categoryTypeOptions = [
  { label: '运动', value: 'exercise' },
  { label: '饮食', value: 'diet' },
  { label: '睡眠', value: 'sleep' },
  { label: '饮水', value: 'water' },
  { label: '用药', value: 'medication' },
  { label: '其他', value: 'other' },
];

export default function DefaultTasksPage() {
  const [data, setData] = useState<DefaultTaskItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [editingItem, setEditingItem] = useState<DefaultTaskItem | null>(null);
  const [form] = Form.useForm();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<{ items?: DefaultTaskItem[]; list?: DefaultTaskItem[] }>(
        '/api/admin/health-plan/default-tasks'
      );
      setData(res.items ?? res.list ?? []);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '加载默认任务列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const openCreate = () => {
    setEditingItem(null);
    form.resetFields();
    form.setFieldsValue({ sort_order: 0, is_active: true });
    setModalOpen(true);
  };

  const openEdit = (item: DefaultTaskItem) => {
    setEditingItem(item);
    form.setFieldsValue({
      name: item.name,
      description: item.description,
      category_type: item.category_type,
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
        await put(`/api/admin/health-plan/default-tasks/${editingItem.id}`, values);
        message.success('更新成功');
      } else {
        await post('/api/admin/health-plan/default-tasks', values);
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
      await del(`/api/admin/health-plan/default-tasks/${id}`);
      message.success('删除成功');
      fetchData();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '删除失败');
    }
  };

  const getCategoryTypeName = (type: string | null) => {
    if (!type) return '-';
    const opt = categoryTypeOptions.find((o) => o.value === type);
    return opt?.label || type;
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
    { title: '任务名称', dataIndex: 'name', key: 'name' },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (v: string | null) => v || '-',
    },
    {
      title: '分类类型',
      dataIndex: 'category_type',
      key: 'category_type',
      width: 100,
      render: (v: string | null) => {
        const name = getCategoryTypeName(v);
        return name !== '-' ? <Tag>{name}</Tag> : '-';
      },
    },
    { title: '排序', dataIndex: 'sort_order', key: 'sort_order', width: 80 },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: unknown, record: DefaultTaskItem) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除该默认任务？" onConfirm={() => handleDelete(record.id)}>
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
      <Title level={4} style={{ marginBottom: 24 }}>
        <ToolOutlined style={{ marginRight: 8, color: '#52c41a' }} />
        通用任务配置
      </Title>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增默认任务
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        pagination={false}
        scroll={{ x: 1000 }}
      />

      <Modal
        title={editingItem ? '编辑默认任务' : '新增默认任务'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={modalLoading}
        destroyOnClose
        width={600}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="任务名称"
            name="name"
            rules={[{ required: true, message: '请输入任务名称' }]}
          >
            <Input placeholder="如：每日步行、喝水" maxLength={200} />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <TextArea placeholder="请输入任务描述" rows={2} maxLength={500} />
          </Form.Item>
          <Form.Item label="分类类型" name="category_type">
            <Select placeholder="请选择分类类型" allowClear options={categoryTypeOptions} />
          </Form.Item>
          <Form.Item label="排序值" name="sort_order">
            <InputNumber min={0} max={9999} style={{ width: '100%' }} placeholder="数字越小越靠前" />
          </Form.Item>
          <Form.Item label="启用状态" name="is_active" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
