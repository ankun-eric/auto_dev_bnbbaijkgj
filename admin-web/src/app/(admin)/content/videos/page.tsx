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
  status: number;
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

const mockVideos: VideoRecord[] = [
  { id: 1, title: '每日5分钟颈椎操', category: '运动教学', duration: '05:32', views: 8920, likes: 456, status: 1, coverUrl: '', videoUrl: '', description: '简单有效的颈椎锻炼方法', createdAt: '2026-03-25 10:00:00' },
  { id: 2, title: '春季养肝食疗方', category: '营养课堂', duration: '12:15', views: 5430, likes: 287, status: 1, coverUrl: '', videoUrl: '', description: '中医推荐的春季养肝食谱', createdAt: '2026-03-24 14:30:00' },
  { id: 3, title: '正念冥想入门教程', category: '心理辅导', duration: '18:40', views: 3210, likes: 198, status: 1, coverUrl: '', videoUrl: '', description: '零基础学习正念冥想', createdAt: '2026-03-23 09:00:00' },
  { id: 4, title: '高血压预防知识', category: '健康科普', duration: '08:55', views: 6780, likes: 345, status: 1, coverUrl: '', videoUrl: '', description: '了解高血压的预防与管理', createdAt: '2026-03-22 16:00:00' },
  { id: 5, title: '艾灸养生入门', category: '中医讲堂', duration: '15:20', views: 4150, likes: 223, status: 0, coverUrl: '', videoUrl: '', description: '家庭艾灸的基础知识', createdAt: '2026-03-20 11:30:00' },
];

export default function VideosPage() {
  const [videos, setVideos] = useState<VideoRecord[]>(mockVideos);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<VideoRecord | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: mockVideos.length });
  const [form] = Form.useForm();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const res = await get('/api/admin/content/videos', { page, pageSize });
      if (res) {
        const items = res.items || res.list || res;
        setVideos(Array.isArray(items) ? items : []);
        setPagination((prev) => ({ ...prev, current: page, total: res.total ?? (Array.isArray(items) ? items.length : 0) }));
      }
    } catch {} finally {
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
    form.setFieldsValue({ ...record, status: record.status === 1 });
    setModalVisible(true);
  };

  const handleToggleStatus = async (record: VideoRecord) => {
    const newStatus = record.status === 1 ? 0 : 1;
    try {
      await put(`/api/admin/content/videos/${record.id}`, { status: newStatus });
    } catch {}
    setVideos((prev) => prev.map((v) => (v.id === record.id ? { ...v, status: newStatus } : v)));
    message.success(newStatus === 1 ? '已上架' : '已下架');
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload = { ...values, status: values.status ? 1 : 0 };

      if (editingRecord) {
        try {
          await put(`/api/admin/content/videos/${editingRecord.id}`, payload);
        } catch {}
        setVideos((prev) => prev.map((v) => (v.id === editingRecord.id ? { ...v, ...payload } : v)));
        message.success('编辑成功');
      } else {
        try {
          const res = await post('/api/admin/content/videos', payload);
          payload.id = res?.id || Date.now();
        } catch {
          payload.id = Date.now();
        }
        payload.views = 0;
        payload.likes = 0;
        payload.coverUrl = '';
        payload.videoUrl = '';
        payload.createdAt = new Date().toISOString();
        setVideos((prev) => [...prev, payload]);
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
      render: (v: number) => <Tag color={v === 1 ? 'green' : 'red'}>{v === 1 ? '已发布' : '已下架'}</Tag>,
    },
    {
      title: '发布时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 170,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: VideoRecord) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm title={record.status === 1 ? '确定下架？' : '确定上架？'} onConfirm={() => handleToggleStatus(record)}>
            <Button type="link" size="small" icon={record.status === 1 ? <ArrowDownOutlined /> : <ArrowUpOutlined />}>
              {record.status === 1 ? '下架' : '上架'}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>视频管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增视频</Button>
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
