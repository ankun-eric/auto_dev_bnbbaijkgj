'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, InputNumber, Switch, Tag, message,
  Typography, Popconfirm,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title } = Typography;

interface ArticleCategory {
  id: number;
  name: string;
  sort_order: number;
  is_enabled: boolean;
  created_at: string;
}

export default function CategoryPage() {
  const [list, setList] = useState<ArticleCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<ArticleCategory | null>(null);
  const [form] = Form.useForm();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await get('/api/admin/article-categories');
      setList(res?.items || []);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({ is_enabled: true, sort_order: 0 });
    setModalVisible(true);
  };

  const handleEdit = (record: ArticleCategory) => {
    setEditingRecord(record);
    form.setFieldsValue({
      name: record.name,
      sort_order: record.sort_order,
      is_enabled: record.is_enabled,
    });
    setModalVisible(true);
  };

  const handleDelete = async (record: ArticleCategory) => {
    try {
      await del(`/api/admin/article-categories/${record.id}`);
      message.success('删除成功');
      fetchData();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除失败');
    }
  };

  const handleToggleEnabled = async (record: ArticleCategory) => {
    try {
      await put(`/api/admin/article-categories/${record.id}`, { is_enabled: !record.is_enabled });
      message.success('操作成功');
      fetchData();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingRecord) {
        await put(`/api/admin/article-categories/${editingRecord.id}`, values);
        message.success('编辑成功');
      } else {
        await post('/api/admin/article-categories', values);
        message.success('新增成功');
      }
      setModalVisible(false);
      fetchData();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '分类名称', dataIndex: 'name', key: 'name' },
    { title: '排序', dataIndex: 'sort_order', key: 'sort_order', width: 80 },
    {
      title: '状态', dataIndex: 'is_enabled', key: 'is_enabled', width: 100,
      render: (v: boolean) => v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>,
    },
    {
      title: '操作', key: 'action', width: 260,
      render: (_: unknown, record: ArticleCategory) => (
        <Space size={0} wrap>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" size="small" onClick={() => handleToggleEnabled(record)}>
            {record.is_enabled ? '停用' : '启用'}
          </Button>
          <Popconfirm title="确定删除？删除前请确保该分类下无文章" onConfirm={() => handleDelete(record)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>文章分类管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增分类</Button>
      </div>

      <Table
        columns={columns}
        dataSource={list}
        rowKey="id"
        loading={loading}
        pagination={false}
      />

      <Modal
        title={editingRecord ? '编辑分类' : '新增分类'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="分类名称" name="name" rules={[{ required: true, message: '请输入分类名称' }]}>
            <Input placeholder="例如：健康科普" maxLength={50} />
          </Form.Item>
          <Form.Item label="排序（数字越小越靠前）" name="sort_order">
            <InputNumber min={0} max={9999} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="启用" name="is_enabled" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
