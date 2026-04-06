'use client';

import React, { useEffect, useState, useRef } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, Select, Switch, Tag, message,
  Typography, Popconfirm, Upload, Row, Col,
} from 'antd';
import {
  PlusOutlined, EditOutlined, ArrowUpOutlined, ArrowDownOutlined,
  SearchOutlined, UploadOutlined, PushpinOutlined,
} from '@ant-design/icons';
import { get, post, put, upload as uploadFile } from '@/lib/api';
import dayjs from 'dayjs';
import type { RcFile } from 'antd/es/upload/interface';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface Article {
  id: number;
  title: string;
  category: string;
  tags: string[];
  authorId: number | null;
  views: number;
  likes: number;
  status: string;
  content: string;
  summary: string;
  coverImage: string;
  isTop: boolean;
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

const statusConfig: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  published: { color: 'green', text: '已发布' },
  archived: { color: 'red', text: '已下架' },
};

function mapArticleFromApi(raw: Record<string, unknown>): Article {
  let tags: string[] = [];
  if (Array.isArray(raw.tags)) tags = raw.tags.map(String);
  else if (typeof raw.tags === 'string' && raw.tags) tags = (raw.tags as string).split(',').map(s => s.trim()).filter(Boolean);

  return {
    id: Number(raw.id),
    title: String(raw.title ?? ''),
    category: String(raw.category ?? ''),
    tags,
    authorId: raw.author_id != null ? Number(raw.author_id) : null,
    views: Number(raw.view_count ?? 0),
    likes: Number(raw.like_count ?? 0),
    status: String(raw.status ?? 'draft'),
    content: String(raw.content ?? ''),
    summary: String(raw.summary ?? ''),
    coverImage: String(raw.cover_image ?? ''),
    isTop: Boolean(raw.is_top ?? false),
    createdAt: String(raw.created_at ?? ''),
  };
}

export default function ArticlesPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<Article | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [filterCategory, setFilterCategory] = useState<string | undefined>(undefined);
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined);
  const [searchText, setSearchText] = useState('');
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewContent, setPreviewContent] = useState('');
  const [form] = Form.useForm();
  const editorRef = useRef<HTMLDivElement>(null);

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (filterCategory) params.category = filterCategory;
      if (filterStatus) params.status = filterStatus;
      if (searchText) params.keyword = searchText;
      const res = await get('/api/admin/content/articles', params);
      if (res) {
        const items = res.items || res.list || res;
        const rawList = Array.isArray(items) ? items : [];
        setArticles(rawList.map((r: Record<string, unknown>) => mapArticleFromApi(r)));
        setPagination(prev => ({ ...prev, current: page, total: res.total ?? rawList.length }));
      }
    } catch (err: any) {
      setArticles([]);
      setPagination(prev => ({ ...prev, current: page, total: 0 }));
      message.error('加载文章失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleSearch = () => fetchData(1, pagination.pageSize);

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({ status: 'draft', is_top: false });
    setModalVisible(true);
  };

  const handleEdit = (record: Article) => {
    setEditingRecord(record);
    form.setFieldsValue({
      title: record.title,
      category: record.category,
      tags: record.tags,
      summary: record.summary,
      content: record.content,
      status: record.status,
      cover_image: record.coverImage,
      is_top: record.isTop,
    });
    setModalVisible(true);
  };

  const handleToggleStatus = async (record: Article, targetStatus: string) => {
    try {
      await put(`/api/admin/content/articles/${record.id}`, { status: targetStatus });
      message.success(targetStatus === 'published' ? '已发布' : '已下架');
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const handleToggleTop = async (record: Article) => {
    try {
      await put(`/api/admin/content/articles/${record.id}`, { is_top: !record.isTop });
      message.success(record.isTop ? '已取消置顶' : '已置顶');
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload: Record<string, unknown> = {
        title: values.title,
        category: values.category,
        tags: values.tags || [],
        content: values.content,
        summary: values.summary || '',
        status: values.status || 'draft',
        cover_image: values.cover_image || '',
        is_top: values.is_top || false,
      };

      if (editingRecord) {
        await put(`/api/admin/content/articles/${editingRecord.id}`, payload);
        message.success('编辑成功');
      } else {
        await post('/api/admin/content/articles', payload);
        message.success('新增成功');
      }
      setModalVisible(false);
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const handleCoverUpload = async (file: RcFile) => {
    try {
      const res = await uploadFile('/api/admin/upload', file);
      const url = (res as any)?.url || (res as any)?.data?.url || '';
      if (url) {
        form.setFieldsValue({ cover_image: url });
        message.success('封面上传成功');
      }
    } catch {
      message.error('封面上传失败');
    }
    return false;
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '标题', dataIndex: 'title', key: 'title', ellipsis: true,
      render: (v: string, record: Article) => (
        <Space>
          {record.isTop && <span title="置顶">📌</span>}
          {v}
        </Space>
      ),
    },
    {
      title: '分类', dataIndex: 'category', key: 'category', width: 100,
      render: (v: string) => <Tag color="cyan">{v || '-'}</Tag>,
    },
    {
      title: '标签', dataIndex: 'tags', key: 'tags', width: 150,
      render: (tags: string[]) => tags?.length ? tags.map(t => <Tag key={t} color="blue">{t}</Tag>) : '-',
    },
    { title: '浏览量', dataIndex: 'views', key: 'views', width: 80 },
    { title: '点赞', dataIndex: 'likes', key: 'likes', width: 70 },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 90,
      render: (v: string) => {
        const c = statusConfig[v] || { color: 'default', text: v };
        return <Tag color={c.color}>{c.text}</Tag>;
      },
    },
    {
      title: '发布时间', dataIndex: 'createdAt', key: 'createdAt', width: 170,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '—',
    },
    {
      title: '操作', key: 'action', width: 260, fixed: 'right' as const,
      render: (_: unknown, record: Article) => (
        <Space size={0} wrap>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" size="small" icon={<PushpinOutlined />} onClick={() => handleToggleTop(record)}>
            {record.isTop ? '取消置顶' : '置顶'}
          </Button>
          {record.status !== 'published' && (
            <Popconfirm title="确定发布？" onConfirm={() => handleToggleStatus(record, 'published')}>
              <Button type="link" size="small" icon={<ArrowUpOutlined />}>发布</Button>
            </Popconfirm>
          )}
          {record.status === 'published' && (
            <Popconfirm title="确定下架？" onConfirm={() => handleToggleStatus(record, 'archived')}>
              <Button type="link" size="small" danger icon={<ArrowDownOutlined />}>下架</Button>
            </Popconfirm>
          )}
          <Button type="link" size="small" onClick={() => { setPreviewContent(record.content); setPreviewVisible(true); }}>预览</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>文章管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增文章</Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col>
          <Select placeholder="按分类筛选" allowClear style={{ width: 140 }} options={categoryOptions}
            value={filterCategory} onChange={v => setFilterCategory(v)} />
        </Col>
        <Col>
          <Select placeholder="按状态筛选" allowClear style={{ width: 120 }}
            options={[{ label: '草稿', value: 'draft' }, { label: '已发布', value: 'published' }, { label: '已下架', value: 'archived' }]}
            value={filterStatus} onChange={v => setFilterStatus(v)} />
        </Col>
        <Col>
          <Input placeholder="搜索标题" prefix={<SearchOutlined />} value={searchText}
            onChange={e => setSearchText(e.target.value)} onPressEnter={handleSearch}
            style={{ width: 220 }} allowClear />
        </Col>
        <Col>
          <Button type="primary" onClick={handleSearch}>搜索</Button>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={articles}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: total => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1200 }}
      />

      <Modal
        title={editingRecord ? '编辑文章' : '新增文章'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={800}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="文章标题" name="title" rules={[{ required: true, message: '请输入文章标题' }]}>
            <Input placeholder="请输入文章标题" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="分类" name="category" rules={[{ required: true, message: '请选择分类' }]}>
                <Select options={categoryOptions} placeholder="请选择分类" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="标签" name="tags">
                <Select mode="tags" placeholder="输入标签后回车" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="状态" name="status">
                <Select options={[
                  { label: '草稿', value: 'draft' },
                  { label: '已发布', value: 'published' },
                  { label: '已下架', value: 'archived' },
                ]} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="封面图" name="cover_image">
            <Input placeholder="封面图URL" addonAfter={
              <Upload showUploadList={false} beforeUpload={handleCoverUpload as any} accept="image/*">
                <Button size="small" type="link" icon={<UploadOutlined />}>上传</Button>
              </Upload>
            } />
          </Form.Item>
          <Form.Item label="文章摘要" name="summary">
            <TextArea rows={2} placeholder="请输入文章摘要" />
          </Form.Item>
          <Form.Item label="文章内容" name="content" rules={[{ required: true, message: '请输入文章内容' }]}>
            <TextArea rows={12} placeholder="请输入文章内容（支持HTML）" />
          </Form.Item>
          <Form.Item label="置顶" name="is_top" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="内容预览" open={previewVisible} onCancel={() => setPreviewVisible(false)} footer={null} width={700}>
        <div style={{ maxHeight: 500, overflow: 'auto', padding: 16 }}>
          <div dangerouslySetInnerHTML={{ __html: previewContent }} />
        </div>
      </Modal>
    </div>
  );
}
