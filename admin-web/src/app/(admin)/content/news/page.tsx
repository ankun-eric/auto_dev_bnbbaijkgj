'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, Select, Switch, Tag, message,
  Typography, Popconfirm, Upload, Row, Col, AutoComplete, DatePicker,
} from 'antd';
import {
  PlusOutlined, EditOutlined, ArrowUpOutlined, ArrowDownOutlined,
  SearchOutlined, UploadOutlined, PushpinOutlined, DeleteOutlined,
} from '@ant-design/icons';
import { get, post, put, del, upload as uploadFile } from '@/lib/api';
import dayjs from 'dayjs';
import type { RcFile } from 'antd/es/upload/interface';

const { Title } = Typography;
const { TextArea } = Input;

interface NewsItem {
  id: number;
  title: string;
  coverImage: string;
  summary: string;
  contentHtml: string;
  tags: string[];
  source: string;
  status: string;
  isTop: boolean;
  viewCount: number;
  likeCount: number;
  commentCount: number;
  publishedAt: string | null;
  createdAt: string;
}

const statusConfig: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  published: { color: 'green', text: '已发布' },
  archived: { color: 'red', text: '已下架' },
};

function mapNews(raw: any): NewsItem {
  return {
    id: Number(raw.id),
    title: String(raw.title ?? ''),
    coverImage: String(raw.cover_image ?? ''),
    summary: String(raw.summary ?? ''),
    contentHtml: String(raw.content_html ?? ''),
    tags: Array.isArray(raw.tags) ? raw.tags.map(String) : [],
    source: String(raw.source ?? ''),
    status: String(raw.status ?? 'draft'),
    isTop: Boolean(raw.is_top),
    viewCount: Number(raw.view_count ?? 0),
    likeCount: Number(raw.like_count ?? 0),
    commentCount: Number(raw.comment_count ?? 0),
    publishedAt: raw.published_at ?? null,
    createdAt: String(raw.created_at ?? ''),
  };
}

export default function NewsPage() {
  const [list, setList] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<NewsItem | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [filterStatus, setFilterStatus] = useState<string | undefined>();
  const [searchText, setSearchText] = useState('');
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewContent, setPreviewContent] = useState('');
  const [tagOptions, setTagOptions] = useState<{ value: string; label: string }[]>([]);
  const [form] = Form.useForm();

  const fetchData = useCallback(async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (filterStatus) params.status = filterStatus;
      if (searchText) params.keyword = searchText;
      const res: any = await get('/api/admin/news', params);
      const items = res?.items || [];
      setList(items.map(mapNews));
      setPagination(prev => ({ ...prev, current: page, pageSize, total: res?.total ?? items.length }));
    } catch {
      setList([]);
      setPagination(prev => ({ ...prev, current: page, total: 0 }));
      message.error('加载资讯失败');
    } finally {
      setLoading(false);
    }
  }, [filterStatus, searchText]);

  useEffect(() => { fetchData(1, pagination.pageSize); }, []); // 首次加载

  const fetchTagSuggest = useCallback(async (q: string) => {
    try {
      const res: any = await get('/api/admin/news/tags/suggest', { q, limit: 20 });
      const items = res?.items || [];
      setTagOptions(items.map((i: any) => ({ value: i.tag, label: `${i.tag} (${i.use_count ?? 0})` })));
    } catch {
      setTagOptions([]);
    }
  }, []);

  const handleSearch = () => fetchData(1, pagination.pageSize);

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({ status: 'draft', is_top: false, tags: [] });
    fetchTagSuggest('');
    setModalVisible(true);
  };

  const handleEdit = (record: NewsItem) => {
    setEditingRecord(record);
    form.setFieldsValue({
      title: record.title,
      source: record.source,
      tags: record.tags,
      summary: record.summary,
      content_html: record.contentHtml,
      status: record.status,
      cover_image: record.coverImage,
      is_top: record.isTop,
      published_at: record.publishedAt ? dayjs(record.publishedAt) : null,
    });
    fetchTagSuggest('');
    setModalVisible(true);
  };

  const handleDelete = async (record: NewsItem) => {
    try {
      await del(`/api/admin/news/${record.id}`);
      message.success('已删除');
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除失败');
    }
  };

  const handleTogglePublish = async (record: NewsItem, target: 'published' | 'archived') => {
    try {
      await post(`/api/admin/news/${record.id}/publish?target_status=${target}`);
      message.success(target === 'published' ? '已发布' : '已下架');
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const handleToggleTop = async (record: NewsItem) => {
    try {
      await post(`/api/admin/news/${record.id}/top`);
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
        cover_image: values.cover_image || '',
        summary: values.summary || '',
        content_html: values.content_html || '',
        tags: values.tags || [],
        source: values.source || '',
        status: values.status || 'draft',
        is_top: values.is_top || false,
      };
      if (values.published_at) {
        payload.published_at = values.published_at.toISOString();
      }

      if (editingRecord) {
        await put(`/api/admin/news/${editingRecord.id}`, payload);
        message.success('编辑成功');
      } else {
        await post('/api/admin/news', payload);
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
      const res: any = await uploadFile('/api/admin/upload', file);
      const url = res?.url || res?.data?.url || '';
      if (url) {
        form.setFieldsValue({ cover_image: url });
        message.success('封面上传成功');
      }
    } catch {
      message.error('封面上传失败');
    }
    return false;
  };

  const handleMediaInsert = async (type: 'image' | 'video') => {
    // 简易：点击按钮选择文件 → 上传 → 插入到 content_html
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = type === 'image' ? 'image/*' : 'video/*';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      try {
        const res: any = await uploadFile('/api/admin/upload', file);
        const url = res?.url || res?.data?.url || '';
        if (url) {
          const current = form.getFieldValue('content_html') || '';
          const tag = type === 'image'
            ? `<p><img src="${url}" style="max-width:100%" /></p>`
            : `<p><video src="${url}" controls style="max-width:100%"></video></p>`;
          form.setFieldsValue({ content_html: current + '\n' + tag });
          message.success(`${type === 'image' ? '图片' : '视频'}已插入正文`);
        }
      } catch {
        message.error('上传失败');
      }
    };
    input.click();
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '标题', dataIndex: 'title', key: 'title', ellipsis: true,
      render: (v: string, record: NewsItem) => (
        <Space>
          {record.isTop && <span title="置顶">📌</span>}
          <span>{v}</span>
        </Space>
      ),
    },
    {
      title: '摘要', dataIndex: 'summary', key: 'summary', width: 220, ellipsis: true,
    },
    {
      title: '标签', dataIndex: 'tags', key: 'tags', width: 180,
      render: (tags: string[]) => tags?.length ? tags.slice(0, 3).map(t => <Tag key={t} color="blue">{t}</Tag>) : '-',
    },
    { title: '来源', dataIndex: 'source', key: 'source', width: 100 },
    { title: '浏览', dataIndex: 'viewCount', key: 'viewCount', width: 70 },
    { title: '点赞', dataIndex: 'likeCount', key: 'likeCount', width: 70 },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 90,
      render: (v: string) => {
        const c = statusConfig[v] || { color: 'default', text: v };
        return <Tag color={c.color}>{c.text}</Tag>;
      },
    },
    {
      title: '发布时间', dataIndex: 'publishedAt', key: 'publishedAt', width: 150,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '—',
    },
    {
      title: '操作', key: 'action', width: 300, fixed: 'right' as const,
      render: (_: unknown, record: NewsItem) => (
        <Space size={0} wrap>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" size="small" icon={<PushpinOutlined />} onClick={() => handleToggleTop(record)}>
            {record.isTop ? '取消置顶' : '置顶'}
          </Button>
          {record.status !== 'published' && (
            <Popconfirm title="确定发布？" onConfirm={() => handleTogglePublish(record, 'published')}>
              <Button type="link" size="small" icon={<ArrowUpOutlined />}>发布</Button>
            </Popconfirm>
          )}
          {record.status === 'published' && (
            <Popconfirm title="确定下架？" onConfirm={() => handleTogglePublish(record, 'archived')}>
              <Button type="link" size="small" danger icon={<ArrowDownOutlined />}>下架</Button>
            </Popconfirm>
          )}
          <Button type="link" size="small" onClick={() => { setPreviewContent(record.contentHtml); setPreviewVisible(true); }}>预览</Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>资讯管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增资讯</Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col>
          <Select placeholder="按状态筛选" allowClear style={{ width: 120 }}
            options={[{ label: '草稿', value: 'draft' }, { label: '已发布', value: 'published' }, { label: '已下架', value: 'archived' }]}
            value={filterStatus} onChange={v => setFilterStatus(v)} />
        </Col>
        <Col>
          <Input placeholder="搜索标题/摘要" prefix={<SearchOutlined />} value={searchText}
            onChange={e => setSearchText(e.target.value)} onPressEnter={handleSearch}
            style={{ width: 220 }} allowClear />
        </Col>
        <Col>
          <Button type="primary" onClick={handleSearch}>搜索</Button>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={list}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: total => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1400 }}
      />

      <Modal
        title={editingRecord ? '编辑资讯' : '新增资讯'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={900}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="资讯标题" name="title" rules={[{ required: true, message: '请输入资讯标题' }]}>
            <Input placeholder="请输入资讯标题" maxLength={200} />
          </Form.Item>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="来源" name="source">
                <Input placeholder="可填来源或作者" maxLength={100} />
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
            <Col span={8}>
              <Form.Item label="发布时间" name="published_at" tooltip="未填时发布自动记录当前时间">
                <DatePicker showTime style={{ width: '100%' }} format="YYYY-MM-DD HH:mm" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="标签（最多10个，每个≤20字）" name="tags" rules={[{
            validator: async (_, v) => {
              const arr: string[] = v || [];
              if (arr.length > 10) throw new Error('标签最多 10 个');
              for (const t of arr) { if (t && t.length > 20) throw new Error('每个标签不能超过 20 个字'); }
            }
          }]}>
            <Select mode="tags" placeholder="输入标签后回车；下拉显示历史标签"
              onSearch={q => fetchTagSuggest(q || '')}
              options={tagOptions}
              maxTagCount={10}
            />
          </Form.Item>
          <Form.Item label="封面图" name="cover_image">
            <Input placeholder="封面图URL" addonAfter={
              <Upload showUploadList={false} beforeUpload={handleCoverUpload as any} accept="image/*">
                <Button size="small" type="link" icon={<UploadOutlined />}>上传</Button>
              </Upload>
            } />
          </Form.Item>
          <Form.Item label="摘要" name="summary">
            <TextArea rows={2} placeholder="资讯摘要（可选）" maxLength={500} showCount />
          </Form.Item>
          <Form.Item label="正文（富文本 HTML）" name="content_html" rules={[{ required: true, message: '请输入正文' }]}>
            <TextArea rows={10} placeholder="支持 HTML；可用下方按钮插入图片/视频" />
          </Form.Item>
          <Space style={{ marginBottom: 16 }}>
            <Button size="small" onClick={() => handleMediaInsert('image')}>插入图片</Button>
            <Button size="small" onClick={() => handleMediaInsert('video')}>插入视频</Button>
            <Button size="small" onClick={() => { setPreviewContent(form.getFieldValue('content_html') || ''); setPreviewVisible(true); }}>预览正文</Button>
          </Space>
          <Form.Item label="置顶" name="is_top" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="内容预览" open={previewVisible} onCancel={() => setPreviewVisible(false)} footer={null} width={700}>
        <div style={{ maxHeight: 500, overflow: 'auto', padding: 16 }} className="rich-text">
          <div dangerouslySetInnerHTML={{ __html: previewContent }} />
        </div>
      </Modal>
    </div>
  );
}
