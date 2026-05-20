'use client';

/**
 * [商品标签体系重构 v1.0 2026-05-20] 标签管理后台
 *
 * 6 大分类：
 * - 体质类 constitution（预置 9 体质，锁定不可删除）
 * - 症状类 symptom（运营自维护）
 * - 人群类 crowd（运营自维护）
 * - 功效类 effect（运营自维护）
 * - 场景类 scene（运营自维护）
 * - 禁忌类 contraindication（运营自维护）
 *
 * 功能：6 Tab + CRUD + 合并 + 启停 + 查看关联商品数；
 * 体质类标签锁定（is_locked=1）：禁止删除/改名/改分类，仅允许启停。
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Typography,
  message,
  Tag as AntTag,
  Tooltip,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  MergeCellsOutlined,
  ReloadOutlined,
  LockOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title } = Typography;

interface TagItem {
  id: number;
  name: string;
  category: string;
  status: number;
  goods_count: number;
  is_locked?: number;
  sort_order?: number;
}

const CATEGORY_OPTIONS = [
  { value: 'constitution', label: '🧬 体质类', color: 'green' },
  { value: 'symptom', label: '🤒 症状类', color: 'red' },
  { value: 'crowd', label: '👥 人群类', color: 'blue' },
  { value: 'effect', label: '💊 功效类', color: 'orange' },
  { value: 'scene', label: '🌅 场景类', color: 'magenta' },
  { value: 'contraindication', label: '⚠️ 禁忌类', color: 'volcano' },
];

function categoryColor(c: string): string {
  const o = CATEGORY_OPTIONS.find((x) => x.value === c);
  return o?.color || 'default';
}

export default function TagsManagementPage() {
  const [activeCategory, setActiveCategory] = useState<string>('constitution');
  const [items, setItems] = useState<TagItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<TagItem | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [mergeOpen, setMergeOpen] = useState(false);
  const [mergeSource, setMergeSource] = useState<TagItem | null>(null);
  const [mergeTargetId, setMergeTargetId] = useState<number | null>(null);
  const [form] = Form.useForm();

  const fetchData = useCallback(async (category: string) => {
    setLoading(true);
    try {
      const res = await get<any>('/api/admin/tags', { category, page: 1, page_size: 500 });
      setItems(res.items || []);
    } catch (e: any) {
      message.error('加载标签失败');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData(activeCategory);
  }, [activeCategory, fetchData]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ category: activeCategory, status: 1, sort_order: 0 });
    setModalOpen(true);
  };

  const openEdit = (record: TagItem) => {
    setEditing(record);
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (editing) {
        await put(`/api/admin/tags/${editing.id}`, values);
        message.success('已更新');
      } else {
        await post('/api/admin/tags', values);
        message.success('已新增');
      }
      setModalOpen(false);
      fetchData(activeCategory);
    } catch (e: any) {
      if (e?.response?.data?.detail) {
        message.error(e.response.data.detail);
      } else if (e?.errorFields) {
        // 表单校验失败
      } else {
        message.error('保存失败');
      }
    }
  };

  const handleDelete = async (record: TagItem) => {
    try {
      await del(`/api/admin/tags/${record.id}`);
      message.success('已删除');
      fetchData(activeCategory);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  const handleToggle = async (record: TagItem, checked: boolean) => {
    try {
      await put(`/api/admin/tags/${record.id}`, { status: checked ? 1 : 0 });
      message.success(checked ? '已启用' : '已停用');
      fetchData(activeCategory);
    } catch {
      message.error('操作失败');
    }
  };

  const openMerge = (record: TagItem) => {
    setMergeSource(record);
    setMergeTargetId(null);
    setMergeOpen(true);
  };

  const handleMerge = async () => {
    if (!mergeSource || !mergeTargetId) {
      message.warning('请选择合并目标');
      return;
    }
    try {
      const res: any = await post(`/api/admin/tags/${mergeSource.id}/merge`, { target_id: mergeTargetId });
      message.success(`合并完成，共迁移 ${res?.merged_goods || 0} 个商品关联`);
      setMergeOpen(false);
      fetchData(activeCategory);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '合并失败');
    }
  };

  const mergeCandidates = useMemo(
    () => items.filter((t) => mergeSource && t.id !== mergeSource.id),
    [items, mergeSource],
  );

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    {
      title: '标签名',
      dataIndex: 'name',
      render: (v: string, r: TagItem) => (
        <Space>
          <AntTag color={categoryColor(r.category)}>{v}</AntTag>
          {Number(r.is_locked) === 1 && (
            <Tooltip title="系统预置（仅允许启停，不可删除/改名/合并）">
              <LockOutlined style={{ color: '#999' }} />
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: '关联商品数',
      dataIndex: 'goods_count',
      width: 110,
    },
    {
      title: '排序',
      dataIndex: 'sort_order',
      width: 80,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (v: number, r: TagItem) => (
        <Switch
          checked={v === 1}
          onChange={(c) => handleToggle(r, c)}
          checkedChildren="启用"
          unCheckedChildren="停用"
        />
      ),
    },
    {
      title: '操作',
      width: 240,
      render: (_: any, r: TagItem) => {
        const locked = Number(r.is_locked) === 1;
        return (
          <Space>
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>编辑</Button>
            <Button size="small" icon={<MergeCellsOutlined />} onClick={() => openMerge(r)} disabled={locked}>
              合并
            </Button>
            {!locked && (
              <Popconfirm title="确认删除？关联商品的此标签将一并移除" onConfirm={() => handleDelete(r)}>
                <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
              </Popconfirm>
            )}
          </Space>
        );
      },
    },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Title level={4}>标签管理</Title>
      <div style={{ color: '#666', marginBottom: 16, fontSize: 13 }}>
        商品标签体系（6 大类）：体质类、症状类、人群类、功效类、场景类、禁忌类。运营自维护，用于商品筛选、相关推荐、问卷推荐。
      </div>
      <Tabs
        activeKey={activeCategory}
        onChange={setActiveCategory}
        items={CATEGORY_OPTIONS.map((c) => ({ key: c.value, label: c.label }))}
        tabBarExtraContent={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => fetchData(activeCategory)}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} data-testid="tag-create-btn">
              新增标签
            </Button>
          </Space>
        }
      />
      <Table
        rowKey="id"
        loading={loading}
        dataSource={items}
        columns={columns as any}
        pagination={false}
        data-testid="tag-table"
      />

      {/* 新建/编辑弹窗 */}
      <Modal
        title={editing ? '编辑标签' : '新增标签'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="category" label="分类" rules={[{ required: true }]}>
            <Select
              options={CATEGORY_OPTIONS.map((c) => ({ value: c.value, label: c.label }))}
              disabled={Number(editing?.is_locked) === 1}
            />
          </Form.Item>
          <Form.Item name="name" label="标签名" rules={[{ required: true, max: 64 }]}>
            <Input placeholder="如：补气、气虚质" data-testid="tag-name-input" disabled={Number(editing?.is_locked) === 1} />
          </Form.Item>
          <Form.Item name="sort_order" label="排序" initialValue={0}>
            <Input type="number" placeholder="数值越小越靠前" />
          </Form.Item>
          <Form.Item name="status" label="状态" initialValue={1}>
            <Select
              options={[
                { value: 1, label: '启用' },
                { value: 0, label: '停用' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 合并弹窗 */}
      <Modal
        title={`将「${mergeSource?.name || ''}」合并到...`}
        open={mergeOpen}
        onOk={handleMerge}
        onCancel={() => setMergeOpen(false)}
        destroyOnClose
      >
        <div style={{ marginBottom: 12, color: '#666' }}>
          合并后，所有关联到「{mergeSource?.name}」的商品将自动改为关联目标标签。源标签会被删除。
        </div>
        <Select
          style={{ width: '100%' }}
          placeholder="请选择合并目标"
          showSearch
          optionFilterProp="label"
          value={mergeTargetId ?? undefined}
          onChange={setMergeTargetId}
          options={mergeCandidates.map((t) => ({ value: t.id, label: t.name }))}
          data-testid="tag-merge-target-select"
        />
      </Modal>
    </div>
  );
}
