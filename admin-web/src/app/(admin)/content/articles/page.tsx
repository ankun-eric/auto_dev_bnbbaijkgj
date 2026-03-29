'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Modal, Form, Input, Select, Switch, Tag, message, Typography, Popconfirm } from 'antd';
import { PlusOutlined, EditOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import { get, post, put } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { TextArea } = Input;

interface Article {
  id: number;
  title: string;
  category: string;
  authorId: number | null;
  views: number;
  likes: number;
  status: string;
  content: string;
  summary: string;
  createdAt: string;
}

const categoryOptions = [
  { label: '健康科普', value: '健康科普' },
  { label: '营养饮食', value: '营养饮食' },
  { label: '运动健身', value: '运动健身' },
  { label: '心理健康', value: '心理健康' },
  { label: '中医养生', value: '中医养生' },
  { label: '疾病预防', value: '疾病预防' },
];

function mapArticleFromApi(raw: Record<string, unknown>): Article {
  return {
    id: Number(raw.id),
    title: String(raw.title ?? ''),
    category: String(raw.category ?? ''),
    authorId: raw.author_id != null ? Number(raw.author_id) : null,
    views: Number(raw.view_count ?? 0),
    likes: Number(raw.like_count ?? 0),
    status: String(raw.status ?? 'archived'),
    content: String(raw.content ?? ''),
    summary: String((raw as { summary?: string }).summary ?? ''),
    createdAt: String(raw.created_at ?? ''),
  };
}

function isArticlePublished(status: string) {
  return status === 'published';
}

function articleStatusLabel(status: string) {
  if (status === 'published') return '已发布';
  if (status === 'draft') return '草稿';
  return '已下架';
}

export default function ArticlesPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<Article | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [form] = Form.useForm();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const res = await get('/api/admin/content/articles', { page, page_size: pageSize });
      if (res) {
        const items = res.items || res.list || res;
        const rawList = Array.isArray(items) ? items : [];
        setArticles(rawList.map((r: Record<string, unknown>) => mapArticleFromApi(r)));
        setPagination((prev) => ({ ...prev, current: page, total: res.total ?? rawList.length }));
      }
    } catch {
      setArticles([]);
      setPagination((prev) => ({ ...prev, current: page, total: 0 }));
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({ status: true });
    setModalVisible(true);
  };

  const handleEdit = (record: Article) => {
    setEditingRecord(record);
    form.setFieldsValue({
      title: record.title,
      category: record.category,
      author: record.authorId != null ? String(record.authorId) : '',
      summary: record.summary,
      content: record.content,
      status: isArticlePublished(record.status),
    });
    setModalVisible(true);
  };

  const handleToggleStatus = async (record: Article) => {
    const newStatus = isArticlePublished(record.status) ? 'archived' : 'published';
    try {
      await put(`/api/admin/content/articles/${record.id}`, { status: newStatus });
    } catch {}
    setArticles((prev) => prev.map((a) => (a.id === record.id ? { ...a, status: newStatus } : a)));
    message.success(isArticlePublished(newStatus) ? '已上架' : '已下架');
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const statusStr = values.status ? 'published' : 'archived';
      const payload = {
        title: values.title,
        category: values.category,
        content: values.content,
        summary: values.summary,
        status: statusStr,
        author_id: values.author ? Number(values.author) : undefined,
      };

      if (editingRecord) {
        try {
          await put(`/api/admin/content/articles/${editingRecord.id}`, payload);
        } catch {}
        setArticles((prev) =>
          prev.map((a) =>
            a.id === editingRecord.id
              ? {
                  ...a,
                  ...values,
                  authorId: payload.author_id ?? a.authorId,
                  status: statusStr,
                  views: a.views,
                  likes: a.likes,
                  createdAt: a.createdAt,
                }
              : a
          )
        );
        message.success('编辑成功');
      } else {
        try {
          const res = await post('/api/admin/content/articles', payload);
          const newId = res?.id ?? Date.now();
          setArticles((prev) => [
            ...prev,
            {
              id: newId,
              title: values.title,
              category: values.category,
              content: values.content,
              summary: values.summary ?? '',
              authorId: payload.author_id ?? null,
              status: statusStr,
              views: 0,
              likes: 0,
              createdAt: new Date().toISOString(),
            },
          ]);
        } catch {
          setArticles((prev) => [
            ...prev,
            {
              id: Date.now(),
              title: values.title,
              category: values.category,
              content: values.content,
              summary: values.summary ?? '',
              authorId: payload.author_id ?? null,
              status: statusStr,
              views: 0,
              likes: 0,
              createdAt: new Date().toISOString(),
            },
          ]);
        }
        message.success('新增成功');
      }
      setModalVisible(false);
    } catch {}
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
    { title: '分类', dataIndex: 'category', key: 'category', width: 100, render: (v: string) => <Tag color="cyan">{v}</Tag> },
    {
      title: '作者',
      dataIndex: 'authorId',
      key: 'authorId',
      width: 110,
      render: (v: number | null) => (v != null ? `ID ${v}` : '—'),
    },
    { title: '浏览量', dataIndex: 'views', key: 'views', width: 80 },
    { title: '点赞', dataIndex: 'likes', key: 'likes', width: 70 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: string) => (
        <Tag color={isArticlePublished(v) ? 'green' : v === 'draft' ? 'default' : 'red'}>{articleStatusLabel(v)}</Tag>
      ),
    },
    {
      title: '发布时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 170,
      render: (v: string) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '—'),
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: unknown, record: Article) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title={isArticlePublished(record.status) ? '确定下架？' : '确定上架？'}
            onConfirm={() => handleToggleStatus(record)}
          >
            <Button type="link" size="small" icon={isArticlePublished(record.status) ? <ArrowDownOutlined /> : <ArrowUpOutlined />}>
              {isArticlePublished(record.status) ? '下架' : '上架'}
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
          文章管理
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          新增文章
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={articles}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1000 }}
      />

      <Modal
        title={editingRecord ? '编辑文章' : '新增文章'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={720}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="文章标题" name="title" rules={[{ required: true, message: '请输入文章标题' }]}>
            <Input placeholder="请输入文章标题" />
          </Form.Item>
          <Space style={{ width: '100%' }} size={16}>
            <Form.Item label="分类" name="category" rules={[{ required: true, message: '请选择分类' }]} style={{ flex: 1 }}>
              <Select options={categoryOptions} placeholder="请选择分类" />
            </Form.Item>
            <Form.Item label="作者" name="author" rules={[{ required: true, message: '请输入作者' }]} style={{ flex: 1 }}>
              <Input placeholder="作者用户 ID" />
            </Form.Item>
          </Space>
          <Form.Item label="文章摘要" name="summary">
            <TextArea rows={2} placeholder="请输入文章摘要" />
          </Form.Item>
          <Form.Item label="文章内容" name="content" rules={[{ required: true, message: '请输入文章内容' }]}>
            <TextArea rows={10} placeholder="请输入文章内容（支持Markdown）" />
          </Form.Item>
          <Form.Item label="发布" name="status" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
