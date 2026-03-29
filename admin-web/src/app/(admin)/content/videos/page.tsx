'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Modal, Form, Input, Select, Switch, Upload, Tag, message, Typography, Popconfirm } from 'antd';
import { PlusOutlined, EditOutlined, UploadOutlined, ArrowUpOutlined, ArrowDownOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { get, post, put } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { TextArea } = Input;

interface VideoRecord {
  id: number;
  title: string;
  category: string;
  duration: string;
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

function mapVideoFromApi(raw: Record<string, unknown>): VideoRecord {
  return {
    id: Number(raw.id),
    title: String(raw.title ?? ''),
    category: String(raw.category ?? ''),
    duration: raw.duration != null ? String(raw.duration) : '',
    views: Number(raw.view_count ?? 0),
    likes: Number(raw.like_count ?? 0),
    status: String(raw.status ?? 'archived'),
    coverUrl: String(raw.cover_image ?? ''),
    videoUrl: String(raw.video_url ?? ''),
    description: String(raw.description ?? ''),
    createdAt: String(raw.created_at ?? ''),
  };
}

function isVideoPublished(status: string) {
  return status === 'published';
}

function videoStatusLabel(status: string) {
  if (status === 'published') return '已发布';
  if (status === 'draft') return '草稿';
  return '已下架';
}

export default function VideosPage() {
  const [videos, setVideos] = useState<VideoRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<VideoRecord | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [form] = Form.useForm();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const res = await get('/api/admin/content/videos', { page, page_size: pageSize });
      if (res) {
        const items = res.items || res.list || res;
        const rawList = Array.isArray(items) ? items : [];
        setVideos(rawList.map((r: Record<string, unknown>) => mapVideoFromApi(r)));
        setPagination((prev) => ({ ...prev, current: page, total: res.total ?? rawList.length }));
      }
    } catch {
      setVideos([]);
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

  const handleEdit = (record: VideoRecord) => {
    setEditingRecord(record);
    form.setFieldsValue({
      title: record.title,
      category: record.category,
      duration: record.duration,
      coverUrl: record.coverUrl,
      videoUrl: record.videoUrl,
      description: record.description,
      status: isVideoPublished(record.status),
    });
    setModalVisible(true);
  };

  const handleToggleStatus = async (record: VideoRecord) => {
    const newStatus = isVideoPublished(record.status) ? 'archived' : 'published';
    try {
      await put(`/api/admin/content/videos/${record.id}`, { status: newStatus });
    } catch {}
    setVideos((prev) => prev.map((v) => (v.id === record.id ? { ...v, status: newStatus } : v)));
    message.success(isVideoPublished(newStatus) ? '已上架' : '已下架');
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const statusStr = values.status ? 'published' : 'archived';
      const payload = {
        title: values.title,
        category: values.category,
        duration: values.duration,
        description: values.description,
        cover_image: values.coverUrl,
        video_url: values.videoUrl,
        status: statusStr,
      };

      if (editingRecord) {
        try {
          await put(`/api/admin/content/videos/${editingRecord.id}`, payload);
        } catch {}
        setVideos((prev) =>
          prev.map((v) =>
            v.id === editingRecord.id
              ? {
                  ...v,
                  title: values.title,
                  category: values.category,
                  duration: values.duration ?? v.duration,
                  coverUrl: values.coverUrl ?? v.coverUrl,
                  videoUrl: values.videoUrl ?? v.videoUrl,
                  description: values.description ?? v.description,
                  status: statusStr,
                  views: v.views,
                  likes: v.likes,
                  createdAt: v.createdAt,
                }
              : v
          )
        );
        message.success('编辑成功');
      } else {
        const localRow: VideoRecord = {
          id: Date.now(),
          title: values.title,
          category: values.category,
          duration: values.duration ?? '',
          views: 0,
          likes: 0,
          status: statusStr,
          coverUrl: values.coverUrl ?? '',
          videoUrl: values.videoUrl ?? '',
          description: values.description ?? '',
          createdAt: new Date().toISOString(),
        };
        try {
          const res = await post('/api/admin/content/videos', payload);
          if (res?.id != null) localRow.id = res.id;
        } catch {}
        setVideos((prev) => [...prev, localRow]);
        message.success('新增成功');
      }
      setModalVisible(false);
    } catch {}
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (v: string) => (
        <Space>
          <PlayCircleOutlined style={{ color: '#52c41a' }} />
          {v}
        </Space>
      ),
    },
    { title: '分类', dataIndex: 'category', key: 'category', width: 100, render: (v: string) => <Tag color="purple">{v}</Tag> },
    { title: '时长', dataIndex: 'duration', key: 'duration', width: 80 },
    { title: '播放量', dataIndex: 'views', key: 'views', width: 80 },
    { title: '点赞', dataIndex: 'likes', key: 'likes', width: 70 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: string) => (
        <Tag color={isVideoPublished(v) ? 'green' : v === 'draft' ? 'default' : 'red'}>{videoStatusLabel(v)}</Tag>
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
      width: 150,
      render: (_: unknown, record: VideoRecord) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title={isVideoPublished(record.status) ? '确定下架？' : '确定上架？'}
            onConfirm={() => handleToggleStatus(record)}
          >
            <Button type="link" size="small" icon={isVideoPublished(record.status) ? <ArrowDownOutlined /> : <ArrowUpOutlined />}>
              {isVideoPublished(record.status) ? '下架' : '上架'}
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
          视频管理
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          新增视频
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={videos}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 950 }}
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
          <Space style={{ width: '100%' }} size={16}>
            <Form.Item label="分类" name="category" rules={[{ required: true, message: '请选择分类' }]} style={{ flex: 1 }}>
              <Select options={categoryOptions} placeholder="请选择分类" />
            </Form.Item>
            <Form.Item label="时长" name="duration" style={{ flex: 1 }}>
              <Input placeholder="例如: 05:30" />
            </Form.Item>
          </Space>
          <Form.Item label="封面图" name="coverUrl">
            <Upload listType="picture-card" maxCount={1} beforeUpload={() => false}>
              <div>
                <UploadOutlined />
                <div style={{ marginTop: 8 }}>上传封面</div>
              </div>
            </Upload>
          </Form.Item>
          <Form.Item label="视频文件" name="videoUrl">
            <Upload maxCount={1} beforeUpload={() => false} accept="video/*">
              <Button icon={<UploadOutlined />}>上传视频</Button>
            </Upload>
          </Form.Item>
          <Form.Item label="视频描述" name="description">
            <TextArea rows={3} placeholder="请输入视频描述" />
          </Form.Item>
          <Form.Item label="发布" name="status" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
