'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Switch, Modal, Form, Input, InputNumber,
  Typography, message, Popconfirm, DatePicker,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { get, post, put, del, patch } from '@/lib/api';

const { Title } = Typography;
const { TextArea } = Input;

interface Notice {
  id: number;
  content: string;
  link_url?: string;
  start_time: string;
  end_time: string;
  is_enabled: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

interface NoticeListResponse {
  items: Notice[];
  total: number;
  page: number;
  page_size: number;
}

export default function NoticesPage() {
  const [notices, setNotices] = useState<Notice[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<Notice | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const fetchData = useCallback(async (currentPage = 1) => {
    setLoading(true);
    try {
      const res = await get<NoticeListResponse | Notice[]>(
        `/api/admin/notices?page=${currentPage}&page_size=${pageSize}`
      );
      if (Array.isArray(res)) {
        setNotices(res);
        setTotal(res.length);
      } else {
        setNotices((res as NoticeListResponse).items || []);
        setTotal((res as NoticeListResponse).total || 0);
      }
    } catch {
      message.error('获取公告列表失败');
    } finally {
      setLoading(false);
    }
  }, [pageSize]);

  useEffect(() => {
    fetchData(page);
  }, [fetchData, page]);

  const handleToggleEnabled = async (record: Notice, checked: boolean) => {
    try {
      await patch(`/api/admin/notices/${record.id}/status`, { is_enabled: checked });
      message.success('状态更新成功');
      fetchData(page);
    } catch {
      message.error('状态更新失败');
    }
  };

  const handleOpenModal = (record?: Notice) => {
    setEditingItem(record || null);
    form.resetFields();
    if (record) {
      form.setFieldsValue({
        content: record.content,
        link_url: record.link_url,
        start_time: record.start_time ? dayjs(record.start_time) : null,
        end_time: record.end_time ? dayjs(record.end_time) : null,
        is_enabled: record.is_enabled,
        sort_order: record.sort_order,
      });
    } else {
      form.setFieldsValue({ is_enabled: true, sort_order: 0 });
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = {
        content: values.content,
        link_url: values.link_url || undefined,
        start_time: values.start_time ? values.start_time.toISOString() : undefined,
        end_time: values.end_time ? values.end_time.toISOString() : undefined,
        is_enabled: values.is_enabled,
        sort_order: values.sort_order ?? 0,
      };
      if (editingItem) {
        await put(`/api/admin/notices/${editingItem.id}`, payload);
        message.success('公告更新成功');
      } else {
        await post('/api/admin/notices', payload);
        message.success('公告创建成功');
      }
      setModalOpen(false);
      fetchData(page);
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/notices/${id}`);
      message.success('公告删除成功');
      fetchData(page);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  const columns = [
    {
      title: '序号',
      key: 'index',
      width: 70,
      render: (_: any, __: Notice, index: number) => (page - 1) * pageSize + index + 1,
    },
    {
      title: '公告内容',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
      render: (val: string) => (
        <span title={val}>{val.length > 40 ? val.slice(0, 40) + '...' : val}</span>
      ),
    },
    {
      title: '跳转路径',
      dataIndex: 'link_url',
      key: 'link_url',
      width: 180,
      ellipsis: true,
      render: (val: string) => val || '-',
    },
    {
      title: '生效开始时间',
      dataIndex: 'start_time',
      key: 'start_time',
      width: 180,
      render: (val: string) => val ? dayjs(val).format('YYYY-MM-DD HH:mm') : '-',
    },
    {
      title: '生效结束时间',
      dataIndex: 'end_time',
      key: 'end_time',
      width: 180,
      render: (val: string) => val ? dayjs(val).format('YYYY-MM-DD HH:mm') : '-',
    },
    {
      title: '启用状态',
      dataIndex: 'is_enabled',
      key: 'is_enabled',
      width: 100,
      render: (val: boolean, record: Notice) => (
        <Switch
          checked={val}
          checkedChildren="启用"
          unCheckedChildren="禁用"
          onChange={(checked) => handleToggleEnabled(record, checked)}
        />
      ),
    },
    {
      title: '排序权重',
      dataIndex: 'sort_order',
      key: 'sort_order',
      width: 100,
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: any, record: Notice) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除此公告？" onConfirm={() => handleDelete(record.id)} okText="确定" cancelText="取消">
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
      <Title level={4} style={{ marginBottom: 24 }}>公告管理</Title>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>
          新增公告
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={notices}
        rowKey="id"
        loading={loading}
        scroll={{ x: 1000 }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: false,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p) => setPage(p),
        }}
      />
      <Modal
        title={editingItem ? '编辑公告' : '新增公告'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        destroyOnClose
        width={560}
      >
        <Form form={form} layout="vertical" initialValues={{ is_enabled: true, sort_order: 0 }}>
          <Form.Item label="公告文字" name="content" rules={[{ required: true, message: '请输入公告内容' }]}>
            <TextArea placeholder="请输入公告内容" rows={3} maxLength={500} showCount />
          </Form.Item>
          <Form.Item label="跳转路径" name="link_url">
            <Input placeholder="/health-profile" />
          </Form.Item>
          <Form.Item label="生效开始时间" name="start_time" rules={[{ required: true, message: '请选择生效开始时间' }]}>
            <DatePicker showTime style={{ width: '100%' }} placeholder="请选择生效开始时间" />
          </Form.Item>
          <Form.Item label="生效结束时间" name="end_time" rules={[{ required: true, message: '请选择生效结束时间' }]}>
            <DatePicker showTime style={{ width: '100%' }} placeholder="请选择生效结束时间" />
          </Form.Item>
          <Form.Item label="启用状态" name="is_enabled" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
          <Form.Item label="排序权重" name="sort_order" extra="数值越小越靠前">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
