'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Modal, Form, Input, Select, Switch, Tag, message, Typography, Popconfirm } from 'antd';
import { PlusOutlined, EditOutlined, EyeOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import { get, post, put } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { TextArea } = Input;

interface Article {
  id: number;
  title: string;
  category: string;
  author: string;
  views: number;
  likes: number;
  status: number;
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

const mockArticles: Article[] = [
  { id: 1, title: '春季养生指南：如何提高免疫力', category: '健康科普', author: '健康编辑', views: 3256, likes: 128, status: 1, content: '春季是万物复苏的季节...', summary: '春季养生重点在于提高免疫力', createdAt: '2026-03-25 10:00:00' },
  { id: 2, title: '每日营养搭配：科学饮食从这里开始', category: '营养饮食', author: '营养师小王', views: 2180, likes: 96, status: 1, content: '科学的饮食搭配...', summary: '了解每日营养需求，科学搭配饮食', createdAt: '2026-03-24 14:30:00' },
  { id: 3, title: '办公室简易健身操：缓解久坐疲劳', category: '运动健身', author: '健身教练', views: 4520, likes: 215, status: 1, content: '长时间坐在办公室...', summary: '简单易学的办公室健身操', createdAt: '2026-03-23 09:15:00' },
  { id: 4, title: '如何应对职场焦虑：心理调适技巧', category: '心理健康', author: '心理咨询师', views: 1890, likes: 87, status: 1, content: '现代职场压力...', summary: '职场压力管理与心理调适方法', createdAt: '2026-03-22 16:00:00' },
  { id: 5, title: '中医四季养生之道', category: '中医养生', author: '中医专家', views: 2650, likes: 145, status: 0, content: '中医讲究天人合一...', summary: '遵循自然规律的中医养生方法', createdAt: '2026-03-20 11:30:00' },
];

export default function ArticlesPage() {
  const [articles, setArticles] = useState<Article[]>(mockArticles);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<Article | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: mockArticles.length });
  const [form] = Form.useForm();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const res = await get('/api/admin/content/articles', { page, pageSize });
      if (res.code === 0 && res.data) {
        setArticles(res.data.list || res.data);
        setPagination((prev) => ({ ...prev, current: page, total: res.data.total || res.data.length }));
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

  const handleEdit = (record: Article) => {
    setEditingRecord(record);
    form.setFieldsValue({ ...record, status: record.status === 1 });
    setModalVisible(true);
  };

  const handleToggleStatus = async (record: Article) => {
    const newStatus = record.status === 1 ? 0 : 1;
    try {
      await put(`/api/admin/content/articles/${record.id}`, { status: newStatus });
    } catch {}
    setArticles((prev) => prev.map((a) => (a.id === record.id ? { ...a, status: newStatus } : a)));
    message.success(newStatus === 1 ? '已上架' : '已下架');
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload = { ...values, status: values.status ? 1 : 0 };

      if (editingRecord) {
        try {
          await put(`/api/admin/content/articles/${editingRecord.id}`, payload);
        } catch {}
        setArticles((prev) => prev.map((a) => (a.id === editingRecord.id ? { ...a, ...payload } : a)));
        message.success('编辑成功');
      } else {
        try {
          const res = await post('/api/admin/content/articles', payload);
          payload.id = res?.data?.id || Date.now();
        } catch {
          payload.id = Date.now();
        }
        payload.views = 0;
        payload.likes = 0;
        payload.createdAt = new Date().toISOString();
        setArticles((prev) => [...prev, payload]);
        message.success('新增成功');
      }
      setModalVisible(false);
    } catch {}
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
    { title: '分类', dataIndex: 'category', key: 'category', width: 100, render: (v: string) => <Tag color="cyan">{v}</Tag> },
    { title: '作者', dataIndex: 'author', key: 'author', width: 110 },
    { title: '浏览量', dataIndex: 'views', key: 'views', width: 80 },
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
      width: 160,
      render: (_: any, record: Article) => (
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
        <Title level={4} style={{ margin: 0 }}>文章管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增文章</Button>
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
              <Input placeholder="请输入作者" />
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
