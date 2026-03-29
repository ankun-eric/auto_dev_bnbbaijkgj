'use client';

import React, { useEffect, useState } from 'react';
import { Button, Form, Input, Modal, Popconfirm, Space, Table, Tag, Typography, message } from 'antd';
import { get, post, put } from '@/lib/api';

const { Title } = Typography;

interface StoreItem {
  id: number;
  store_name: string;
  store_code: string;
  contact_name?: string;
  contact_phone?: string;
  address?: string;
  status: string;
}

export default function MerchantStoresPage() {
  const [items, setItems] = useState<StoreItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<StoreItem | null>(null);
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await get('/api/admin/merchant/stores');
      setItems(res.items || []);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '门店列表加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ status: 'active' });
    setOpen(true);
  };

  const openEdit = (item: StoreItem) => {
    setEditing(item);
    form.setFieldsValue(item);
    setOpen(true);
  };

  const submit = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        await put(`/api/admin/merchant/stores/${editing.id}`, values);
        message.success('门店更新成功');
      } else {
        await post('/api/admin/merchant/stores', values);
        message.success('门店创建成功');
      }
      setOpen(false);
      fetchData();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '保存失败');
    }
  };

  const toggleStatus = async (item: StoreItem) => {
    try {
      await put(`/api/admin/merchant/stores/${item.id}`, {
        status: item.status === 'active' ? 'disabled' : 'active',
      });
      message.success('状态已更新');
      fetchData();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '状态更新失败');
    }
  };

  return (
    <div>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>门店管理</Title>
        <Button type="primary" onClick={openCreate}>新建门店</Button>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={items}
        columns={[
          { title: '门店名称', dataIndex: 'store_name' },
          { title: '门店编码', dataIndex: 'store_code' },
          { title: '联系人', dataIndex: 'contact_name' },
          { title: '联系电话', dataIndex: 'contact_phone' },
          { title: '地址', dataIndex: 'address', ellipsis: true },
          {
            title: '状态',
            dataIndex: 'status',
            render: (value: string) => (
              <Tag color={value === 'active' ? 'green' : 'red'}>
                {value === 'active' ? '启用' : '停用'}
              </Tag>
            ),
          },
          {
            title: '操作',
            render: (_: any, item: StoreItem) => (
              <Space>
                <Button type="link" onClick={() => openEdit(item)}>编辑</Button>
                <Popconfirm
                  title={item.status === 'active' ? '确认停用该门店？' : '确认启用该门店？'}
                  onConfirm={() => toggleStatus(item)}
                >
                  <Button type="link">{item.status === 'active' ? '停用' : '启用'}</Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editing ? '编辑门店' : '新建门店'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={submit}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="store_name" label="门店名称" rules={[{ required: true, message: '请输入门店名称' }]}>
            <Input placeholder="请输入门店名称" />
          </Form.Item>
          <Form.Item name="store_code" label="门店编码" rules={[{ required: true, message: '请输入门店编码' }]}>
            <Input placeholder="请输入唯一门店编码" disabled={!!editing} />
          </Form.Item>
          <Form.Item name="contact_name" label="联系人">
            <Input placeholder="请输入联系人" />
          </Form.Item>
          <Form.Item name="contact_phone" label="联系电话">
            <Input placeholder="请输入联系电话" />
          </Form.Item>
          <Form.Item name="address" label="门店地址">
            <Input.TextArea rows={3} placeholder="请输入门店地址" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
