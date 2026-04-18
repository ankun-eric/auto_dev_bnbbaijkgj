'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, InputNumber, Switch, message,
  Typography, Popconfirm, Tag, Select,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, MenuOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title } = Typography;

interface Category {
  id: number;
  name: string;
  parent_id: number | null;
  icon: string;
  description: string;
  sort_order: number;
  status: string;
  level: number;
  created_at: string;
  children?: Category[];
}

function mapCategory(raw: Record<string, unknown>): Category {
  return {
    id: Number(raw.id),
    name: String(raw.name ?? ''),
    parent_id: raw.parent_id != null ? Number(raw.parent_id) : null,
    icon: String(raw.icon ?? ''),
    description: String(raw.description ?? ''),
    sort_order: Number(raw.sort_order ?? 0),
    status: String(raw.status ?? 'active'),
    level: Number(raw.level ?? 1),
    created_at: String(raw.created_at ?? ''),
  };
}

function buildTree(flatList: Category[]): Category[] {
  const map = new Map<number, Category>();
  const roots: Category[] = [];

  flatList.forEach(c => {
    map.set(c.id, { ...c, children: [] });
  });

  flatList.forEach(c => {
    const node = map.get(c.id)!;
    if (c.parent_id && map.has(c.parent_id)) {
      map.get(c.parent_id)!.children!.push(node);
    } else {
      roots.push(node);
    }
  });

  roots.forEach(r => {
    if (r.children && r.children.length === 0) delete r.children;
  });
  map.forEach(node => {
    if (node.children && node.children.length === 0) delete node.children;
  });

  return roots;
}

export default function ProductCategoriesPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [flatCategories, setFlatCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<Category | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await get('/api/admin/products/categories');
      if (res) {
        const items = res.items || res.list || res;
        const rawList = Array.isArray(items) ? items : [];
        const flat = rawList.map((r: Record<string, unknown>) => mapCategory(r));
        setFlatCategories(flat);
        setCategories(buildTree(flat));
      }
    } catch {
      setCategories([]);
      setFlatCategories([]);
    } finally {
      setLoading(false);
    }
  };

  const parentOptions = flatCategories
    .filter(c => c.level === 1)
    .map(c => ({ label: c.name, value: c.id }));

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({ sort_order: 0, status: true });
    setModalVisible(true);
  };

  const handleEdit = (record: Category) => {
    setEditingRecord(record);
    form.setFieldsValue({
      name: record.name,
      parent_id: record.parent_id,
      icon: record.icon,
      description: record.description,
      sort_order: record.sort_order,
      status: record.status === 'active',
    });
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/products/categories/${id}`);
      message.success('删除成功');
      fetchData();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload = {
        name: values.name,
        parent_id: values.parent_id || null,
        icon: values.icon || '',
        description: values.description || '',
        sort_order: values.sort_order ?? 0,
        status: values.status ? 'active' : 'inactive',
      };

      if (editingRecord) {
        await put(`/api/admin/products/categories/${editingRecord.id}`, payload);
        message.success('编辑成功');
      } else {
        await post('/api/admin/products/categories', payload);
        message.success('新增成功');
      }
      setModalVisible(false);
      fetchData();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const handleReorder = async (parentId: number | null, orderedIds: number[]) => {
    try {
      await post('/api/admin/products/categories/reorder', {
        parent_id: parentId,
        ordered_ids: orderedIds,
      });
      message.success('排序已更新');
      fetchData();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '排序更新失败');
    }
  };

  const onDragRow = (
    sourceId: number,
    targetId: number,
    parentId: number | null,
    siblings: Category[]
  ) => {
    if (sourceId === targetId) return;
    const ids = siblings.map(s => s.id);
    const sIdx = ids.indexOf(sourceId);
    const tIdx = ids.indexOf(targetId);
    if (sIdx === -1 || tIdx === -1) return;
    const next = [...ids];
    next.splice(sIdx, 1);
    next.splice(tIdx, 0, sourceId);
    handleReorder(parentId, next);
  };

  // 拖拽行组件
  const dragRowProps = (record: Category, siblings: Category[]) => ({
    draggable: true,
    onDragStart: (e: React.DragEvent) => {
      e.dataTransfer.setData('text/plain', JSON.stringify({
        id: record.id,
        parentId: record.parent_id,
      }));
    },
    onDragOver: (e: React.DragEvent) => {
      e.preventDefault();
    },
    onDrop: (e: React.DragEvent) => {
      e.preventDefault();
      try {
        const raw = e.dataTransfer.getData('text/plain');
        if (!raw) return;
        const { id: srcId, parentId: srcParent } = JSON.parse(raw);
        if (srcParent !== record.parent_id) {
          message.warning('仅支持同级分类间拖拽排序，跨级请使用「编辑」修改上级分类');
          return;
        }
        onDragRow(srcId, record.id, record.parent_id, siblings);
      } catch {}
    },
    style: { cursor: 'move' as const },
  });

  const getSiblings = (record: Category): Category[] => {
    if (record.parent_id == null) {
      return categories.filter(c => c.parent_id == null);
    }
    const parent = flatCategories.find(c => c.id === record.parent_id);
    if (!parent) return [];
    return flatCategories
      .filter(c => c.parent_id === record.parent_id)
      .sort((a, b) => a.sort_order - b.sort_order);
  };

  const components = {
    body: {
      row: (props: any) => {
        const record: Category | undefined = props['data-row-key'] != null
          ? flatCategories.find(c => c.id === Number(props['data-row-key']))
          : undefined;
        if (!record) return <tr {...props} />;
        const siblings = getSiblings(record);
        const dp = dragRowProps(record, siblings);
        return <tr {...props} {...dp} />;
      },
    },
  };

  const columns = [
    {
      title: '',
      key: 'drag',
      width: 36,
      render: () => <MenuOutlined style={{ color: '#999', cursor: 'move' }} />,
    },
    { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
    {
      title: '图标',
      dataIndex: 'icon',
      key: 'icon',
      width: 60,
      render: (v: string) => <span style={{ fontSize: 20 }}>{v || '-'}</span>,
    },
    { title: '分类名称', dataIndex: 'name', key: 'name', width: 180 },
    {
      title: '层级',
      dataIndex: 'level',
      key: 'level',
      width: 80,
      render: (v: number) => <Tag color={v === 1 ? 'blue' : 'cyan'}>{v === 1 ? '一级' : '二级'}</Tag>,
    },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '排序', dataIndex: 'sort_order', key: 'sort_order', width: 70 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: string) => <Tag color={v === 'active' ? 'green' : 'red'}>{v === 'active' ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (v: string) => v ? v.slice(0, 19).replace('T', ' ') : '',
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: unknown, record: Category) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm title="确定删除该分类？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>商品分类管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增分类</Button>
      </div>

      <div style={{ marginBottom: 8, color: '#999', fontSize: 12 }}>
        💡 提示：拖拽行可调整同级分类顺序；跨级移动请使用「编辑」修改上级分类。
      </div>
      <Table
        columns={columns}
        dataSource={categories}
        rowKey="id"
        loading={loading}
        pagination={false}
        expandable={{ childrenColumnName: 'children' }}
        components={components}
      />

      <Modal
        title={editingRecord ? '编辑分类' : '新增分类'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="分类名称" name="name" rules={[{ required: true, message: '请输入分类名称' }]}>
            <Input placeholder="请输入分类名称" />
          </Form.Item>
          <Form.Item label="上级分类" name="parent_id">
            <Select
              placeholder="不选则为一级分类"
              allowClear
              options={parentOptions}
            />
          </Form.Item>
          <Form.Item label="图标 (Emoji)" name="icon">
            <Input placeholder="请输入Emoji图标，如 💊" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea placeholder="请输入分类描述" rows={3} />
          </Form.Item>
          <Form.Item label="排序" name="sort_order">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="启用" name="status" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
