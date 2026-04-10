'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Table,
  Typography,
  message,
  Breadcrumb,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ArrowLeftOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';
import { useRouter, useParams } from 'next/navigation';

const { Title } = Typography;

interface TaskItem {
  id: number;
  plan_id: number;
  task_name: string;
  target_value: number | null;
  target_unit: string | null;
  sort_order: number;
  created_at: string | null;
}

interface PlanInfo {
  id: number;
  name: string;
}

export default function PlanTasksPage() {
  const router = useRouter();
  const params = useParams();
  const planId = params.planId as string;

  const [planInfo, setPlanInfo] = useState<PlanInfo | null>(null);
  const [data, setData] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [editingItem, setEditingItem] = useState<TaskItem | null>(null);
  const [form] = Form.useForm();

  const fetchPlanInfo = useCallback(async () => {
    try {
      const res = await get<{
        items?: PlanInfo[];
        list?: PlanInfo[];
        id?: number;
        name?: string;
      }>(`/api/admin/health-plan/recommended-plans`, { page: 1, page_size: 100 });
      const items = res.items ?? res.list ?? [];
      const plan = items.find((p) => String(p.id) === planId);
      if (plan) setPlanInfo(plan);
    } catch {
      /* ignore */
    }
  }, [planId]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<{ items?: TaskItem[]; list?: TaskItem[] }>(
        `/api/admin/health-plan/recommended-plans/${planId}/tasks`
      );
      const items = res.items ?? res.list ?? [];
      items.sort((a, b) => a.sort_order - b.sort_order);
      setData(items);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '加载任务列表失败');
    } finally {
      setLoading(false);
    }
  }, [planId]);

  useEffect(() => {
    fetchPlanInfo();
    fetchData();
  }, [fetchPlanInfo, fetchData]);

  const openCreate = () => {
    setEditingItem(null);
    form.resetFields();
    form.setFieldsValue({ sort_order: data.length });
    setModalOpen(true);
  };

  const openEdit = (item: TaskItem) => {
    setEditingItem(item);
    form.setFieldsValue({
      task_name: item.task_name,
      target_value: item.target_value,
      target_unit: item.target_unit,
      sort_order: item.sort_order,
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setModalLoading(true);
      if (editingItem) {
        await put(`/api/admin/health-plan/recommended-plans/tasks/${editingItem.id}`, values);
        message.success('更新成功');
      } else {
        await post(`/api/admin/health-plan/recommended-plans/${planId}/tasks`, values);
        message.success('创建成功');
      }
      setModalOpen(false);
      fetchData();
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
      await del(`/api/admin/health-plan/recommended-plans/tasks/${id}`);
      message.success('删除成功');
      fetchData();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '删除失败');
    }
  };

  const handleMoveUp = async (index: number) => {
    if (index <= 0) return;
    const item = data[index];
    const prev = data[index - 1];
    try {
      await put(`/api/admin/health-plan/recommended-plans/tasks/${item.id}`, {
        sort_order: prev.sort_order,
      });
      await put(`/api/admin/health-plan/recommended-plans/tasks/${prev.id}`, {
        sort_order: item.sort_order,
      });
      fetchData();
    } catch {
      message.error('排序操作失败');
    }
  };

  const handleMoveDown = async (index: number) => {
    if (index >= data.length - 1) return;
    const item = data[index];
    const next = data[index + 1];
    try {
      await put(`/api/admin/health-plan/recommended-plans/tasks/${item.id}`, {
        sort_order: next.sort_order,
      });
      await put(`/api/admin/health-plan/recommended-plans/tasks/${next.id}`, {
        sort_order: item.sort_order,
      });
      fetchData();
    } catch {
      message.error('排序操作失败');
    }
  };

  const columns = [
    { title: '排序', dataIndex: 'sort_order', key: 'sort_order', width: 70 },
    { title: '任务名称', dataIndex: 'task_name', key: 'task_name' },
    {
      title: '目标值',
      dataIndex: 'target_value',
      key: 'target_value',
      width: 100,
      render: (v: number | null) => v ?? '-',
    },
    {
      title: '单位',
      dataIndex: 'target_unit',
      key: 'target_unit',
      width: 80,
      render: (v: string | null) => v || '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 260,
      render: (_: unknown, record: TaskItem, index: number) => (
        <Space>
          <Button
            type="link"
            size="small"
            disabled={index === 0}
            onClick={() => handleMoveUp(index)}
          >
            上移
          </Button>
          <Button
            type="link"
            size="small"
            disabled={index === data.length - 1}
            onClick={() => handleMoveDown(index)}
          >
            下移
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除该任务？" onConfirm={() => handleDelete(record.id)}>
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
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          { title: <a onClick={() => router.push('/health-plan/recommended')}>推荐计划管理</a> },
          { title: planInfo?.name || `计划 #${planId}` },
          { title: '每日任务' },
        ]}
      />

      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 24, gap: 12 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => router.push('/health-plan/recommended')}
        >
          返回
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          <UnorderedListOutlined style={{ marginRight: 8, color: '#52c41a' }} />
          {planInfo?.name || `计划 #${planId}`} - 每日任务管理
        </Title>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增任务
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        pagination={false}
        scroll={{ x: 700 }}
      />

      <Modal
        title={editingItem ? '编辑任务' : '新增任务'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={modalLoading}
        destroyOnClose
        width={500}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="任务名称"
            name="task_name"
            rules={[{ required: true, message: '请输入任务名称' }]}
          >
            <Input placeholder="如：步行30分钟、喝水8杯" maxLength={200} />
          </Form.Item>
          <Form.Item label="目标值" name="target_value">
            <InputNumber min={0} style={{ width: '100%' }} placeholder="如：8000" />
          </Form.Item>
          <Form.Item label="单位" name="target_unit">
            <Input placeholder="如：步、杯、分钟" maxLength={50} />
          </Form.Item>
          <Form.Item label="排序值" name="sort_order">
            <InputNumber min={0} max={9999} style={{ width: '100%' }} placeholder="数字越小越靠前" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
