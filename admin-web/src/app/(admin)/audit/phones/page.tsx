'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Switch, message, Space, Tag, Popconfirm, Typography } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title, Paragraph } = Typography;

interface Phone {
  id: number;
  phone: string;
  notes: string | null;
  enabled: boolean;
  created_at: string;
}

export default function AuditPhonesPage() {
  const [items, setItems] = useState<Phone[]>([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState<Phone | null>(null);
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res: any = await get('/api/admin/audit/phones');
      setItems(res?.items || []);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleAdd = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ enabled: true });
    setModal(true);
  };
  const handleEdit = (r: Phone) => {
    setEditing(r);
    form.setFieldsValue(r);
    setModal(true);
  };
  const handleSubmit = async () => {
    try {
      const v = await form.validateFields();
      if (editing) {
        await put(`/api/admin/audit/phones/${editing.id}`, v);
        message.success('更新成功');
      } else {
        await post('/api/admin/audit/phones', v);
        message.success('添加成功');
      }
      setModal(false);
      fetchData();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };
  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/audit/phones/${id}`);
      message.success('删除成功');
      fetchData();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除失败');
    }
  };

  return (
    <div>
      <Title level={4}>审核手机号配置</Title>
      <Paragraph type="secondary">审核操作（如券回收、批量发放等高风险操作）将向以下手机号发送 6 位短信验证码</Paragraph>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>添加审核手机号</Button>
      </div>
      <Table rowKey="id" loading={loading} dataSource={items}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 70 },
          { title: '手机号', dataIndex: 'phone', width: 160 },
          { title: '备注', dataIndex: 'notes', render: (v: string) => v || '-' },
          { title: '状态', dataIndex: 'enabled', width: 100,
            render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? '启用' : '停用'}</Tag> },
          { title: '操作', key: 'a', width: 180,
            render: (_: any, r: Phone) => (
              <Space>
                <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(r)}>编辑</Button>
                <Popconfirm title="删除该审核手机号？" onConfirm={() => handleDelete(r.id)}>
                  <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
                </Popconfirm>
              </Space>
            ) },
        ]} />

      <Modal title={editing ? '编辑审核手机号' : '添加审核手机号'} open={modal}
        onOk={handleSubmit} onCancel={() => setModal(false)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item label="手机号" name="phone" rules={[
            { required: true, message: '请输入手机号' },
            { pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确' },
          ]}>
            <Input maxLength={11} />
          </Form.Item>
          <Form.Item label="备注" name="notes"><Input placeholder="如：财务总监 / 老板" /></Form.Item>
          <Form.Item label="启用" name="enabled" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
