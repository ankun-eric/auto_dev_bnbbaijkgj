'use client';

import React, { useEffect, useState } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, Select, Switch, Upload, Tag, message,
  Typography, Popconfirm, Card, Statistic, Row, Col,
} from 'antd';
import {
  PlusOutlined, EditOutlined, UploadOutlined, ArrowUpOutlined, ArrowDownOutlined,
  PlayCircleOutlined, SearchOutlined, VideoCameraOutlined,
} from '@ant-design/icons';
import { get, post, put, upload as uploadFile } from '@/lib/api';
import dayjs from 'dayjs';
import type { RcFile, UploadFile } from 'antd/es/upload/interface';

const { Title } = Typography;
const { TextArea } = Input;

interface VideoRecord {
  id: number;
  title: string;
  category: string;
  duration: number;
  views: number;
  likes: number;
  status: string;
  coverUrl: string;
  videoUrl: string;
  description: string;
  createdAt: string;
}

const categoryOptions = [
  { label: '健康科普', value: '健康科普' },
  { label: '运动教学', value: '运动教学' },
  { label: '营养课堂', value: '营养课堂' },
  { label: '中医讲堂', value: '中医讲堂' },
  { label: '心理辅导', value: '心理辅导' },
];

const statusConfig: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  published: { color: 'green', text: '已发布' },
  archived: { color: 'red', text: '已下架' },
};

function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return '00:00';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function parseDuration(str: string): number {
  if (!str) return 0;
  const parts = str.split(':');
  if (parts.length === 2) {
    return (parseInt(parts[0], 10) || 0) * 60 + (parseInt(parts[1], 10) || 0);
  }
  return parseInt(str, 10) || 0;
}

function mapVideoFromApi(raw: Record<string, unknown>): VideoRecord {
  return {
    id: Number(raw.id),
    title: String(raw.title ?? ''),
    category: String(raw.category ?? ''),
    duration: Number(raw.duration ?? 0),
    views: Number(raw.view_count ?? 0),
    likes: Number(raw.like_count ?? 0),
    status: String(raw.status ?? 'draft'),
    coverUrl: String(raw.cover_image ?? ''),
    videoUrl: String(raw.video_url ?? ''),
    description: String(raw.description ?? ''),
    createdAt: String(raw.created_at ?? ''),
  };
}

export default function VideosPage() {
  const [videos, setVideos] = useState<VideoRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<VideoRecord | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [filterCategory, setFilterCategory] = useState<string | undefined>(undefined);
  const [searchText, setSearchText] = useState('');
  const [coverFileList, setCoverFileList] = useState<UploadFile[]>([]);
  const [videoFileList, setVideoFileList] = useState<UploadFile[]>([]);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewUrl, setPreviewUrl] = useState('');
  const [form] = Form.useForm();

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (filterCategory) params.category = filterCategory;
      if (searchText) params.keyword = searchText;
      const res = await get('/api/admin/content/videos', params);
      if (res) {
        const items = res.items || res.list || res;
        const rawList = Array.isArray(items) ? items : [];
        setVideos(rawList.map((r: Record<string, unknown>) => mapVideoFromApi(r)));
        setPagination(prev => ({ ...prev, current: page, total: res.total ?? rawList.length }));
      }
    } catch (err: any) {
      setVideos([]);
      setPagination(prev => ({ ...prev, current: page, total: 0 }));
      message.error('加载视频失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleSearch = () => fetchData(1, pagination.pageSize);

  const totalVideos = pagination.total;
  const totalViews = videos.reduce((sum, v) => sum + v.views, 0);
  const todayVideos = videos.filter(v => v.createdAt && dayjs(v.createdAt).isSame(dayjs(), 'day')).length;

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({ status: 'draft' });
    setCoverFileList([]);
    setVideoFileList([]);
    setModalVisible(true);
  };

  const handleEdit = (record: VideoRecord) => {
    setEditingRecord(record);
    form.setFieldsValue({
      title: record.title,
      category: record.category,
      duration: formatDuration(record.duration),
      coverUrl: record.coverUrl,
      videoUrl: record.videoUrl,
      description: record.description,
      status: record.status,
    });
    setCoverFileList(record.coverUrl ? [{ uid: '-1', name: 'cover', status: 'done', url: record.coverUrl }] : []);
    setVideoFileList(record.videoUrl ? [{ uid: '-1', name: 'video', status: 'done', url: record.videoUrl }] : []);
    setModalVisible(true);
  };

  const handleToggleStatus = async (record: VideoRecord, targetStatus: string) => {
    try {
      await put(`/api/admin/content/videos/${record.id}`, { status: targetStatus });
      message.success(targetStatus === 'published' ? '已发布' : '已下架');
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const doUpload = async (file: RcFile): Promise<string> => {
    try {
      const res = await uploadFile('/api/admin/upload', file);
      return (res as any)?.url || (res as any)?.data?.url || '';
    } catch {
      message.error('上传失败');
      return '';
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const durationSeconds = parseDuration(values.duration || '');

      let coverUrl = values.coverUrl || '';
      if (coverFileList.length > 0 && coverFileList[0].originFileObj) {
        coverUrl = await doUpload(coverFileList[0].originFileObj as RcFile);
        if (!coverUrl) return;
      } else if (coverFileList.length > 0 && coverFileList[0].url) {
        coverUrl = coverFileList[0].url;
      }

      let videoUrl = values.videoUrl || '';
      if (videoFileList.length > 0 && videoFileList[0].originFileObj) {
        videoUrl = await doUpload(videoFileList[0].originFileObj as RcFile);
        if (!videoUrl) return;
      } else if (videoFileList.length > 0 && videoFileList[0].url) {
        videoUrl = videoFileList[0].url;
      }

      const payload = {
        title: values.title,
        category: values.category,
        duration: durationSeconds,
        description: values.description || '',
        cover_image: coverUrl,
        video_url: videoUrl,
        status: values.status || 'draft',
      };

      if (editingRecord) {
        await put(`/api/admin/content/videos/${editingRecord.id}`, payload);
        message.success('编辑成功');
      } else {
        await post('/api/admin/content/videos', payload);
        message.success('新增成功');
      }
      setModalVisible(false);
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '标题', dataIndex: 'title', key: 'title', ellipsis: true,
      render: (v: string) => <Space><PlayCircleOutlined style={{ color: '#52c41a' }} />{v}</Space>,
    },
    {
      title: '分类', dataIndex: 'category', key: 'category', width: 100,
      render: (v: string) => <Tag color="purple">{v || '-'}</Tag>,
    },
    {
      title: '时长', dataIndex: 'duration', key: 'duration', width: 80,
      render: (v: number) => formatDuration(v),
    },
    { title: '播放量', dataIndex: 'views', key: 'views', width: 80 },
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
      title: '操作', key: 'action', width: 240, fixed: 'right' as const,
      render: (_: unknown, record: VideoRecord) => (
        <Space size={0} wrap>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          {record.videoUrl && (
            <Button type="link" size="small" icon={<PlayCircleOutlined />}
              onClick={() => { setPreviewUrl(record.videoUrl); setPreviewVisible(true); }}>播放</Button>
          )}
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
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>视频管理</Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}><Card size="small"><Statistic title="视频总数" value={totalVideos} prefix={<VideoCameraOutlined />} /></Card></Col>
        <Col span={8}><Card size="small"><Statistic title="总播放量" value={totalViews} prefix={<PlayCircleOutlined />} /></Card></Col>
        <Col span={8}><Card size="small"><Statistic title="今日新增" value={todayVideos} prefix={<PlusOutlined />} /></Card></Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col>
          <Select placeholder="按分类筛选" allowClear style={{ width: 140 }} options={categoryOptions}
            value={filterCategory} onChange={v => setFilterCategory(v)} />
        </Col>
        <Col>
          <Input placeholder="搜索视频名称" prefix={<SearchOutlined />} value={searchText}
            onChange={e => setSearchText(e.target.value)} onPressEnter={handleSearch}
            style={{ width: 220 }} allowClear />
        </Col>
        <Col><Button type="primary" onClick={handleSearch}>搜索</Button></Col>
        <Col flex="auto" style={{ textAlign: 'right' }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增视频</Button>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={videos}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: total => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1100 }}
      />

      <Modal
        title={editingRecord ? '编辑视频' : '新增视频'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="视频标题" name="title" rules={[{ required: true, message: '请输入视频标题' }]}>
            <Input placeholder="请输入视频标题" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="分类" name="category" rules={[{ required: true, message: '请选择分类' }]}>
                <Select options={categoryOptions} placeholder="请选择分类" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="时长 (分:秒)" name="duration">
                <Input placeholder="例如: 05:30" />
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
          <Form.Item label="封面图" name="coverUrl">
            <div>
              <Upload
                listType="picture-card"
                maxCount={1}
                fileList={coverFileList}
                beforeUpload={() => false}
                onChange={({ fileList }) => setCoverFileList(fileList)}
                onRemove={() => { setCoverFileList([]); form.setFieldsValue({ coverUrl: '' }); }}
                accept="image/*"
              >
                {coverFileList.length === 0 && (
                  <div><UploadOutlined /><div style={{ marginTop: 8 }}>上传封面</div></div>
                )}
              </Upload>
            </div>
          </Form.Item>
          <Form.Item label="视频文件" name="videoUrl">
            <div>
              <Upload
                maxCount={1}
                fileList={videoFileList}
                beforeUpload={() => false}
                onChange={({ fileList }) => setVideoFileList(fileList)}
                onRemove={() => { setVideoFileList([]); form.setFieldsValue({ videoUrl: '' }); }}
                accept="video/*"
              >
                {videoFileList.length === 0 && <Button icon={<UploadOutlined />}>上传视频</Button>}
              </Upload>
            </div>
          </Form.Item>
          <Form.Item label="视频描述" name="description">
            <TextArea rows={3} placeholder="请输入视频描述" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="视频预览" open={previewVisible} onCancel={() => { setPreviewVisible(false); setPreviewUrl(''); }} footer={null} width={700} destroyOnClose>
        {previewUrl && (
          <video src={previewUrl} controls autoPlay style={{ width: '100%', maxHeight: 400 }} />
        )}
      </Modal>
    </div>
  );
}
