'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  UnorderedListOutlined,
  ScheduleOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';
import { useRouter } from 'next/navigation';

const { Title } = Typography;
const { TextArea } = Input;

interface CategoryItem {
  id: number;
  name: string;
}

interface RecommendedPlanItem {
  id: number;
  name: string;
  description: string | null;
  category_id: number;
  category_name?: string;
  category?: { id: number; name: string };
  target_audience: string | null;
  duration_days: number | null;
  cover_image: string | null;
  is_published: boolean;
  sort_order: number;
  created_at: string | null;
}

export default function RecommendedPlansPage() {
  const router = useRouter();
  const [data, setData] = useState<RecommendedPlanItem[]>([]);
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [filterCategoryId, setFilterCategoryId] = useState<number | undefined>(undefined);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [editingItem, setEditingItem] = useState<RecommendedPlanItem | null>(null);
  const [form] = Form.useForm();

  const fetchCategories = useCallback(async () => {
    try {
      const res = await get<{ items?: CategoryItem[]; list?: CategoryItem[] }>(
        '/api/admin/health-plan/template-categories'
      );
      setCategories(res.items ?? res.list ?? []);
    } catch {
      /* ignore */
    }
  }, []);

  const fetchData = useCallback(
    async (page = 1, pageSize = 10) => {
      setLoading(true);
      try {
        const res = await get<{
          items?: RecommendedPlanItem[];
          list?: RecommendedPlanItem[];
          total?: number;
          page?: number;
          page_size?: number;
        }>('/api/admin/health-plan/recommended-plans', {
          page,
          page_size: pageSize,
          ...(filterCategoryId ? { category_id: filterCategoryId } : {}),
        });
        const items = res.items ?? res.list ?? [];
        setData(items);
        setPagination((prev) => ({
          ...prev,
          current: res.page ?? page,
          pageSize: res.page_size ?? pageSize,
          total: res.total ?? items.length,
        }));
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string } }; message?: string };
        message.error(err?.response?.data?.detail || err?.message || '加载推荐计划列表失败');
      } finally {
        setLoading(false);
      }
    },
    [filterCategoryId]
  );

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const openCreate = () => {
    setEditingItem(null);
    form.resetFields();
    form.setFieldsValue({ sort_order: 0, is_published: true });
    setModalOpen(true);
  };

  const openEdit = (item: RecommendedPlanItem) => {
    setEditingItem(item);
    form.setFieldsValue({
      name: item.name,
      description: item.description,
      category_id: item.category_id,
      target_audience: item.target_audience,
      duration_days: item.duration_days,
      cover_image: item.cover_image,
      sort_order: item.sort_order,
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setModalLoading(true);
      if (editingItem) {
        await put(`/api/admin/health-plan/recommended-plans/${editingItem.id}`, values);
        message.success('更新成功');
      } else {
        await post('/api/admin/health-plan/recommended-plans', values);
        message.success('创建成功');
      }
      setModalOpen(false);
      fetchData(pagination.current, pagination.pageSize);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      if (err?.response) {
        message.error(err?.response?.data?.detail || '操作失败');
      }
    } finally {
      setModalLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/health-plan/recommended-plans/${id}`);
      message.success('删除成功');
      fetchData(pagination.current, pagination.pageSize);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '删除失败');
    }
  };

  const handleTogglePublish = async (record: RecommendedPlanItem) => {
    try {
      await put(`/api/admin/health-plan/recommended-plans/${record.id}/publish`, {
        is_published: !record.is_published,
      });
      message.success(record.is_published ? '已下架' : '已上架');
      fetchData(pagination.current, pagination.pageSize);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '操作失败');
    }
  };

  const getCategoryName = (record: RecommendedPlanItem) => {
    if (record.category_name) return record.category_name;
    if (record.category?.name) return record.category.name;
    const cat = categories.find((c) => c.id === record.category_id);
    return cat?.name || '-';
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
    {
      title: '计划名称',
      dataIndex: 'name',
      key: 'name',
      render: (v: string, record: RecommendedPlanItem) => (
        <a onClick={() => router.push(`/health-plan/recommended/${record.id}/tasks`)}>{v}</a>
      ),
    },
    {
      title: '所属分类',
      key: 'category',
      width: 130,
      render: (_: unknown, record: RecommendedPlanItem) => getCategoryName(record),
    },
    {
      title: '适用人群',
      dataIndex: 'target_audience',
      key: 'target_audience',
      width: 150,
      render: (v: string | null) =>
        v
          ? v.split(/[,，]/).map((tag, i) => (
              <Tag key={i} color="blue">
                {tag.trim()}
              </Tag>
            ))
          : '-',
    },
    { title: '周期(天)', dataIndex: 'duration_days', key: 'duration_days', width: 90 },
    {
      title: '状态',
      dataIndex: 'is_published',
      key: 'is_published',
      width: 90,
      render: (v: boolean, record: RecommendedPlanItem) => (
        <Switch
          checked={v}
          checkedChildren="上架"
          unCheckedChildren="下架"
          onChange={() => handleTogglePublish(record)}
        />
      ),
    },
    { title: '排序', dataIndex: 'sort_order', key: 'sort_order', width: 80 },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: unknown, record: RecommendedPlanItem) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<UnorderedListOutlined />}
            onClick={() => router.push(`/health-plan/recommended/${record.id}/tasks`)}
          >
            任务
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除该推荐计划？" onConfirm={() => handleDelete(record.id)}>
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
      <Title level={4} style={{ marginBottom: 24 }}>
        <ScheduleOutlined style={{ marginRight: 8, color: '#52c41a' }} />
        推荐计划管理
      </Title>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Select
            placeholder="按分类筛选"
            allowClear
            style={{ width: 200 }}
            value={filterCategoryId}
            onChange={(v) => setFilterCategoryId(v)}
            options={categories.map((c) => ({ label: c.name, value: c.id }))}
          />
          <Button type="primary" onClick={() => fetchData(1)}>
            查询
          </Button>
        </Space>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增推荐计划
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1000 }}
      />

      <Modal
        title={editingItem ? '编辑推荐计划' : '新增推荐计划'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={modalLoading}
        destroyOnClose
        width={600}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="计划名称"
            name="name"
            rules={[{ required: true, message: '请输入计划名称' }]}
          >
            <Input placeholder="请输入计划名称" maxLength={200} />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <TextArea placeholder="请输入计划描述" rows={3} maxLength={500} />
          </Form.Item>
          <Form.Item
            label="所属分类"
            name="category_id"
            rules={[{ required: true, message: '请选择所属分类' }]}
          >
            <Select
              placeholder="请选择分类"
              options={categories.map((c) => ({ label: c.name, value: c.id }))}
            />
          </Form.Item>
          <Form.Item label="适用人群标签" name="target_audience">
            <Input placeholder="多个标签用逗号分隔，如：高血压,糖尿病" maxLength={200} />
          </Form.Item>
          <Form.Item label="周期天数" name="duration_days">
            <InputNumber min={1} max={365} style={{ width: '100%' }} placeholder="请输入周期天数" />
          </Form.Item>
          <Form.Item label="封面图URL" name="cover_image">
            <Input placeholder="请输入封面图片URL" maxLength={500} />
          </Form.Item>
          <Form.Item label="排序值" name="sort_order">
            <InputNumber min={0} max={9999} style={{ width: '100%' }} placeholder="数字越小越靠前" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
