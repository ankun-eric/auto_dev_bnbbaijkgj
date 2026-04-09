'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Form,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  Input,
  message,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, TeamOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title } = Typography;

interface RelationTypeItem {
  id: number;
  name: string;
  sort_order: number;
  is_active: boolean;
  created_at: string | null;
}

export default function RelationTypesPage() {
  const [data, setData] = useState<RelationTypeItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [editingItem, setEditingItem] = useState<RelationTypeItem | null>(null);
  const [form] = Form.useForm();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<{ items: RelationTypeItem[] }>('/api/admin/relation-types');
      setData(res.items ?? []);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '加载失败');
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

  const openEdit = (item: RelationTypeItem) => {
    setEditingItem(item);
    form.setFieldsValue({ name: item.name, sort_order: item.sort_order, is_active: item.is_active });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setModalLoading(true);
      if (editingItem) {
        await put(`/api/admin/relation-types/${editingItem.id}`, values);
        message.success('更新成功');
      } else {
        await post('/api/admin/relation-types', values);
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
      await del(`/api/admin/relation-types/${id}`);
      message.success('删除成功');
      fetchData();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '删除失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
    { title: '关系名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '排序值', dataIndex: 'sort_order', key: 'sort_order', width: 100 },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: unknown, record: RelationTypeItem) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除该关系类型？" onConfirm={() => handleDelete(record.id)}>
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
          <TeamOutlined style={{ marginRight: 8 }} />
          关系类型配置
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增关系类型
        </Button>
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
        title={editingItem ? '编辑关系类型' : '新增关系类型'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={modalLoading}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="关系名称"
            name="name"
            rules={[{ required: true, message: '请输入关系名称' }]}
          >
            <Input placeholder="如：父亲、母亲、配偶..." maxLength={50} />
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
