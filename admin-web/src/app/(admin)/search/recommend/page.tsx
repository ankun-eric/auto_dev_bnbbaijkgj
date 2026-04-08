'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Table, Input, Button, Space, Modal, Form, message, Tag, Switch,
  InputNumber, Select, Popconfirm,
} from 'antd';
import { SearchOutlined, PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;

interface RecommendWord {
  id: number;
  keyword: string;
  sort_order: number;
  category_hint: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface ListResponse {
  items: RecommendWord[];
  total: number;
  page: number;
  page_size: number;
}

const CATEGORY_OPTIONS = [
  { label: '文章', value: 'article' },
  { label: '视频', value: 'video' },
  { label: '服务', value: 'service' },
  { label: '积分商品', value: 'points_mall' },
];

const categoryLabel = (val: string | null) => {
  if (!val) return '-';
  const found = CATEGORY_OPTIONS.find((o) => o.value === val);
  return found ? found.label : val;
};

export default function RecommendWordsPage() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<RecommendWord[]>([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [keyword, setKeyword] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<RecommendWord | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const fetchData = useCallback(async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const res = await get<ListResponse>('/api/admin/search/recommend-words', {
        page,
        page_size: pageSize,
        keyword: keyword || undefined,
      });
      setData(res.items || []);
      setPagination({ current: res.page, pageSize: res.page_size, total: res.total });
    } catch {
      message.error('获取推荐搜索词列表失败');
    } finally {
      setLoading(false);
    }
  }, [keyword]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSearch = () => {
    fetchData(1, pagination.pageSize);
  };

  const handleOpenModal = (record?: RecommendWord) => {
    setEditing(record || null);
    form.resetFields();
    if (record) {
      form.setFieldsValue({
        keyword: record.keyword,
        sort_order: record.sort_order,
        category_hint: record.category_hint || undefined,
        is_active: record.is_active,
      });
    } else {
      form.setFieldsValue({ sort_order: 0, is_active: true });
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = {
        ...values,
        category_hint: values.category_hint || null,
      };
      if (editing) {
        await put(`/api/admin/search/recommend-words/${editing.id}`, payload);
        message.success('更新成功');
      } else {
        await post('/api/admin/search/recommend-words', payload);
        message.success('新增成功');
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

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/search/recommend-words/${id}`);
      message.success('删除成功');
      fetchData(pagination.current, pagination.pageSize);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '删除失败';
      message.error(typeof detail === 'string' ? detail : '删除失败');
    }
  };

  const columns = [
    {
      title: '词条',
      dataIndex: 'keyword',
      key: 'keyword',
    },
    {
      title: '排序值',
      dataIndex: 'sort_order',
      key: 'sort_order',
      width: 100,
      sorter: (a: RecommendWord, b: RecommendWord) => a.sort_order - b.sort_order,
    },
    {
      title: '关联类别',
      dataIndex: 'category_hint',
      key: 'category_hint',
      width: 120,
      render: (v: string | null) => categoryLabel(v),
    },
    {
      title: '启用状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: any, record: RecommendWord) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除该推荐词？" onConfirm={() => handleDelete(record.id)} okText="确定" cancelText="取消">
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
      <Title level={4} style={{ marginBottom: 24 }}>推荐搜索词管理</Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索词条"
          prefix={<SearchOutlined />}
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onPressEnter={handleSearch}
          style={{ width: 240 }}
          allowClear
        />
        <Button type="primary" onClick={handleSearch}>搜索</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>
          新增推荐词
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
      />
      <Modal
        title={editing ? '编辑推荐搜索词' : '新增推荐搜索词'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="词条"
            name="keyword"
            rules={[{ required: true, message: '请输入词条' }]}
          >
            <Input placeholder="请输入推荐搜索词" />
          </Form.Item>
          <Form.Item label="排序值" name="sort_order">
            <InputNumber
              min={0}
              style={{ width: '100%' }}
              placeholder="越小越靠前，默认0"
            />
          </Form.Item>
          <Form.Item label="关联类别" name="category_hint">
            <Select
              placeholder="可不选"
              allowClear
              options={CATEGORY_OPTIONS}
            />
          </Form.Item>
          <Form.Item label="启用状态" name="is_active" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
