'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Table, Input, Button, Space, Tag, Modal, Form, Switch,
  message, Popconfirm,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined,
  FolderOpenOutlined, BarChartOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';
import { useRouter } from 'next/navigation';
import dayjs from 'dayjs';

const { Title } = Typography;

interface KnowledgeBase {
  id: number;
  name: string;
  description: string;
  status: string;
  is_global: boolean;
  entry_count: number;
  active_entry_count: number;
  created_at: string;
  updated_at?: string;
}

interface ListResponse {
  items: KnowledgeBase[];
  total: number;
  page: number;
  page_size: number;
}

export default function KnowledgePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<KnowledgeBase[]>([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<KnowledgeBase | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const fetchData = useCallback(async (page = 1, pageSize = 20) => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (search) params.keyword = search;
      const res = await get<ListResponse>('/api/admin/knowledge-bases', params);
      setData(res.items || []);
      setPagination({ current: res.page, pageSize: res.page_size, total: res.total });
    } catch {
      message.error('获取知识库列表失败');
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleOpenModal = (record?: KnowledgeBase) => {
    setEditing(record || null);
    form.resetFields();
    if (record) {
      form.setFieldsValue({
        name: record.name,
        description: record.description,
        is_global: record.is_global,
      });
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      if (editing) {
        await put(`/api/admin/knowledge-bases/${editing.id}`, values);
        message.success('知识库更新成功');
      } else {
        await post('/api/admin/knowledge-bases', values);
        message.success('知识库创建成功');
      }
      setModalOpen(false);
      fetchData(pagination.current, pagination.pageSize);
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleStatus = async (record: KnowledgeBase) => {
    try {
      const newStatus = record.status === 'active' ? 'inactive' : 'active';
      await put(`/api/admin/knowledge-bases/${record.id}`, {
        status: newStatus,
      });
      message.success(newStatus === 'active' ? '已启用' : '已禁用');
      fetchData(pagination.current, pagination.pageSize);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '操作失败';
      message.error(typeof detail === 'string' ? detail : '操作失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/knowledge-bases/${id}?confirm=true`);
      message.success('知识库删除成功');
      fetchData(pagination.current, pagination.pageSize);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '删除失败';
      message.error(typeof detail === 'string' ? detail : '删除失败');
    }
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 180,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v: string, record: KnowledgeBase) => (
        <Space>
          <Tag color={v === 'active' ? 'green' : 'default'}>{v === 'active' ? '启用' : '禁用'}</Tag>
          {record.is_global && <Tag color="blue">通用</Tag>}
        </Space>
      ),
    },
    {
      title: '条目数量',
      dataIndex: 'entry_count',
      key: 'entry_count',
      width: 100,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '操作',
      key: 'action',
      width: 280,
      render: (_: any, record: KnowledgeBase) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)}>
            编辑
          </Button>
          <Button type="link" size="small" onClick={() => handleToggleStatus(record)}>
            {record.status === 'active' ? '禁用' : '启用'}
          </Button>
          <Button
            type="link"
            size="small"
            icon={<FolderOpenOutlined />}
            onClick={() => router.push(`/knowledge/${record.id}`)}
          >
            条目管理
          </Button>
          <Popconfirm title="确定删除此知识库？" onConfirm={() => handleDelete(record.id)} okText="确定" cancelText="取消">
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>知识库管理</Title>
        <Button
          type="link"
          icon={<BarChartOutlined />}
          onClick={() => router.push('/knowledge/stats')}
        >
          数据统计
        </Button>
      </div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索知识库名称"
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onPressEnter={() => fetchData(1, pagination.pageSize)}
          style={{ width: 240 }}
          allowClear
        />
        <Button type="primary" onClick={() => fetchData(1, pagination.pageSize)}>搜索</Button>
        <Button onClick={() => { setSearch(''); setTimeout(() => fetchData(1, pagination.pageSize), 0); }}>重置</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>
          创建知识库
        </Button>
      </Space>
      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total: pagination.total,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 900 }}
      />
      <Modal
        title={editing ? '编辑知识库' : '创建知识库'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        destroyOnClose
        width={520}
      >
        <Form form={form} layout="vertical" initialValues={{ is_global: false }}>
          <Form.Item label="知识库名称" name="name" rules={[{ required: true, message: '请输入知识库名称' }]}>
            <Input placeholder="请输入知识库名称" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} placeholder="请输入知识库描述" />
          </Form.Item>
          <Form.Item label="设为通用知识库" name="is_global" valuePropName="checked">
            <Switch checkedChildren="是" unCheckedChildren="否" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
