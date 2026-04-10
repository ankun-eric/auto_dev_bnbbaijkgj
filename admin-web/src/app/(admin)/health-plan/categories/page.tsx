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
  Tag,
  Typography,
  message,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  AppstoreOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title } = Typography;
const { TextArea } = Input;

interface CategoryItem {
  id: number;
  name: string;
  description: string | null;
  icon: string | null;
  sort_order: number;
  preset_tasks: unknown[] | null;
  status: string;
  created_at: string | null;
}

export default function TemplateCategoriesPage() {
  const [data, setData] = useState<CategoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [editingItem, setEditingItem] = useState<CategoryItem | null>(null);
  const [form] = Form.useForm();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<{ items?: CategoryItem[]; list?: CategoryItem[] }>(
        '/api/admin/health-plan/template-categories'
      );
      setData(res.items ?? res.list ?? []);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '加载分类列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const openCreate = () => {
    setEditingItem(null);
    form.resetFields();
    form.setFieldsValue({ sort_order: 0 });
    setModalOpen(true);
  };

  const openEdit = (item: CategoryItem) => {
    setEditingItem(item);
    const tasks = Array.isArray(item.preset_tasks)
      ? item.preset_tasks.map((t: any) => ({
          name: t.name ?? '',
          target_value: t.target_value ?? null,
          target_unit: t.target_unit ?? '',
        }))
      : [];
    form.setFieldsValue({
      name: item.name,
      description: item.description,
      icon: item.icon,
      sort_order: item.sort_order,
      preset_tasks_list: tasks.length > 0 ? tasks : undefined,
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setModalLoading(true);

      const preset_tasks =
        values.preset_tasks_list && values.preset_tasks_list.length > 0
          ? values.preset_tasks_list.map((t: any) => ({
              name: t.name,
              target_value: t.target_value ?? null,
              target_unit: t.target_unit ?? null,
            }))
          : null;

      const payload = {
        name: values.name,
        description: values.description,
        icon: values.icon,
        sort_order: values.sort_order,
        preset_tasks,
      };

      if (editingItem) {
        await put(`/api/admin/health-plan/template-categories/${editingItem.id}`, payload);
        message.success('更新成功');
      } else {
        await post('/api/admin/health-plan/template-categories', payload);
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
      await del(`/api/admin/health-plan/template-categories/${id}`);
      message.success('删除成功');
      fetchData();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '删除失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
    {
      title: '图标',
      dataIndex: 'icon',
      key: 'icon',
      width: 70,
      render: (v: string | null) => (v ? <span style={{ fontSize: 24 }}>{v}</span> : '-'),
    },
    { title: '分类名称', dataIndex: 'name', key: 'name' },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (v: string | null) => v || '-',
    },
    { title: '排序', dataIndex: 'sort_order', key: 'sort_order', width: 80 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: string) => (
        <Tag color={v === 'active' ? 'green' : 'default'}>{v === 'active' ? '启用' : '禁用'}</Tag>
      ),
    },
    {
      title: '预设任务数',
      key: 'preset_count',
      width: 100,
      render: (_: unknown, record: CategoryItem) => {
        const count = Array.isArray(record.preset_tasks) ? record.preset_tasks.length : 0;
        return <Tag color="blue">{count} 项</Tag>;
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: unknown, record: CategoryItem) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title="确定删除该分类？"
            description="删除后不影响已创建的用户计划"
            onConfirm={() => handleDelete(record.id)}
          >
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
        <AppstoreOutlined style={{ marginRight: 8, color: '#52c41a' }} />
        模板分类管理
      </Title>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增分类
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        pagination={false}
        scroll={{ x: 800 }}
      />

      <Modal
        title={editingItem ? '编辑分类' : '新增分类'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={modalLoading}
        destroyOnClose
        width={600}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="分类名称"
            name="name"
            rules={[{ required: true, message: '请输入分类名称' }]}
          >
            <Input placeholder="如：运动健身、饮食管理" maxLength={100} />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <TextArea placeholder="请输入分类描述" rows={2} maxLength={500} />
          </Form.Item>
          <Form.Item label="图标/Emoji" name="icon">
            <Input placeholder="请输入图标或Emoji，如：🏃‍♂️" maxLength={50} />
          </Form.Item>
          <Form.Item label="排序值" name="sort_order">
            <InputNumber min={0} max={9999} style={{ width: '100%' }} placeholder="数字越小越靠前" />
          </Form.Item>
          <Form.Item label="预设建议任务">
            <Form.List name="preset_tasks_list">
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name, ...restField }) => (
                    <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                      <Form.Item
                        {...restField}
                        name={[name, 'name']}
                        rules={[{ required: true, message: '请输入任务名' }]}
                        style={{ marginBottom: 0 }}
                      >
                        <Input placeholder="任务名称" style={{ width: 150 }} />
                      </Form.Item>
                      <Form.Item {...restField} name={[name, 'target_value']} style={{ marginBottom: 0 }}>
                        <InputNumber placeholder="目标值" style={{ width: 100 }} />
                      </Form.Item>
                      <Form.Item {...restField} name={[name, 'target_unit']} style={{ marginBottom: 0 }}>
                        <Input placeholder="单位" style={{ width: 80 }} />
                      </Form.Item>
                      <MinusCircleOutlined onClick={() => remove(name)} style={{ color: '#ff4d4f' }} />
                    </Space>
                  ))}
                  <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                    添加预设任务
                  </Button>
                </>
              )}
            </Form.List>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
