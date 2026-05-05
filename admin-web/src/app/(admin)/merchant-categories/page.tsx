'use client';

import React, { useEffect, useState } from 'react';
import {
  Button, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Switch, Table, Tag, Typography, message,
} from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title } = Typography;

interface Category {
  id: number;
  code: string;
  name: string;
  icon?: string;
  description?: string;
  allowed_attachment_types?: string[];
  sort?: number;
  status: 'active' | 'disabled';
}

export default function MerchantCategoriesPage() {
  const [rows, setRows] = useState<Category[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      const data = await get<Category[]>('/api/admin/merchant-categories');
      setRows(data || []);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载失败');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const onAdd = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ status: 'active', sort: 0, allowed_attachment_types: ['image', 'pdf'] });
    setOpen(true);
  };

  const onEdit = (row: Category) => {
    setEditing(row);
    form.setFieldsValue(row);
    setOpen(true);
  };

  const onSubmit = async (values: any) => {
    try {
      if (editing) {
        await put(`/api/admin/merchant-categories/${editing.id}`, values);
      } else {
        await post('/api/admin/merchant-categories', values);
      }
      message.success('已保存');
      setOpen(false);
      load();
    } catch (e: any) { message.error(e?.response?.data?.detail || '保存失败'); }
  };

  const onDelete = async (id: number) => {
    try {
      await del(`/api/admin/merchant-categories/${id}`);
      message.success('已删除');
      load();
    } catch (e: any) { message.error(e?.response?.data?.detail || '删除失败'); }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>机构类别管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={onAdd}>新建</Button>
      </div>
      {/* [2026-05-05 表格布局 Bug 修复] 全列显式 width + scroll.x 兜底，操作列统一 200px */}
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        pagination={false}
        scroll={{ x: 1100 }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: '编码', dataIndex: 'code', width: 120 },
          { title: '名称', dataIndex: 'name', width: 160 },
          { title: '描述', dataIndex: 'description', width: 240, ellipsis: true },
          {
            title: '允许附件',
            dataIndex: 'allowed_attachment_types',
            width: 160,
            render: (v: string[]) => (v || []).map(t => <Tag key={t}>{t}</Tag>),
          },
          { title: '排序', dataIndex: 'sort', width: 80 },
          {
            title: '状态', dataIndex: 'status', width: 100,
            render: (v: string) => <Tag color={v === 'active' ? 'green' : 'default'}>{v}</Tag>,
          },
          {
            title: '操作', width: 200,
            render: (_: any, row: Category) => (
              <Space size={4}>
                <a onClick={() => onEdit(row)}>编辑</a>
                <Popconfirm title="确定删除?" onConfirm={() => onDelete(row.id)}>
                  <a style={{ color: '#ff4d4f' }}>删除</a>
                </Popconfirm>
              </Space>
            ),
          },
        ] as any}
      />
      <Modal
        title={editing ? '编辑类别' : '新建类别'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={onSubmit}>
          <Form.Item name="code" label="编码" rules={[{ required: true }]}>
            <Input placeholder="如 medical / homeservice" disabled={!!editing} />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如 体检机构" />
          </Form.Item>
          <Form.Item name="icon" label="图标URL">
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="allowed_attachment_types" label="允许的附件类型">
            <Select
              mode="multiple"
              options={[{ label: '图片', value: 'image' }, { label: 'PDF', value: 'pdf' }]}
            />
          </Form.Item>
          <Form.Item name="sort" label="排序" initialValue={0}>
            <InputNumber min={0} />
          </Form.Item>
          <Form.Item name="status" label="状态" initialValue="active">
            <Select options={[{ label: '启用', value: 'active' }, { label: '禁用', value: 'disabled' }]} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
