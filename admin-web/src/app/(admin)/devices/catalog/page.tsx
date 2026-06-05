'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Table, Button, Modal, Input, InputNumber, Switch, Select, Space, Popconfirm, message, Card, Tag } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';

interface CatalogItem {
  id: number;
  brand_code: string;
  brand_name: string;
  category_code: string;
  device_name: string;
  icon: string | null;
  icon_url: string | null;
  scene_group_id: number | null;
  jump_url: string | null;
  is_active: boolean;
  is_unique: boolean;
  sort_order: number;
}

interface SceneGroup {
  id: number;
  name: string;
}

export default function CatalogPage() {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [sceneGroups, setSceneGroups] = useState<SceneGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CatalogItem | null>(null);
  const [form, setForm] = useState({
    brand_code: 'other',
    brand_name: '',
    category_code: '',
    device_name: '',
    icon: '',
    icon_url: '',
    scene_group_id: null as number | null,
    jump_url: '',
    is_active: false,
    is_unique: true,
    sort_order: 0,
  });
  const [saving, setSaving] = useState(false);
  const [filterSceneGroup, setFilterSceneGroup] = useState<number | undefined>(undefined);

  const token = typeof window !== 'undefined' ? localStorage.getItem('token') || '' : '';

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      let url = '/api/devices/admin/catalog';
      if (filterSceneGroup != null) url += `?scene_group_id=${filterSceneGroup}`;
      const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      setItems(data.items || []);
    } catch (e) {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  }, [token, filterSceneGroup]);

  const fetchSceneGroups = useCallback(async () => {
    try {
      const res = await fetch('/api/devices/scene-groups?include_disabled=true', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setSceneGroups(data.items || []);
    } catch (e) { /* ignore */ }
  }, [token]);

  useEffect(() => { fetchItems(); fetchSceneGroups(); }, [fetchItems, fetchSceneGroups]);

  const openCreate = () => {
    setEditing(null);
    setForm({
      brand_code: 'other',
      brand_name: '',
      category_code: '',
      device_name: '',
      icon: '',
      icon_url: '',
      scene_group_id: null,
      jump_url: '',
      is_active: false,
      is_unique: true,
      sort_order: 0,
    });
    setModalOpen(true);
  };

  const openEdit = (item: CatalogItem) => {
    setEditing(item);
    setForm({
      brand_code: item.brand_code,
      brand_name: item.brand_name,
      category_code: item.category_code,
      device_name: item.device_name,
      icon: item.icon || '',
      icon_url: item.icon_url || '',
      scene_group_id: item.scene_group_id,
      jump_url: item.jump_url || '',
      is_active: item.is_active,
      is_unique: item.is_unique,
      sort_order: item.sort_order,
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    if (!form.device_name.trim()) { message.warning('请输入设备名称'); return; }
    setSaving(true);
    try {
      const url = editing
        ? `/api/devices/admin/catalog/${editing.id}`
        : '/api/devices/admin/catalog';
      const method = editing ? 'PUT' : 'POST';
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const err = await res.json();
        message.error(err.detail || '保存失败');
        return;
      }
      message.success(editing ? '已更新' : '已创建');
      setModalOpen(false);
      fetchItems();
    } catch (e) {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (item: CatalogItem) => {
    try {
      const res = await fetch(`/api/devices/admin/catalog/${item.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { message.error('删除失败'); return; }
      message.success('已删除');
      fetchItems();
    } catch (e) {
      message.error('删除失败');
    }
  };

  const getSceneGroupName = (id: number | null) => {
    if (id == null) return <Tag>未分类</Tag>;
    const sg = sceneGroups.find(g => g.id === id);
    return sg ? <Tag color="blue">{sg.name}</Tag> : <Tag>未知</Tag>;
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 50 },
    { title: '品牌', dataIndex: 'brand_name', width: 80 },
    { title: '设备名称', dataIndex: 'device_name', width: 160 },
    {
      title: '图标', dataIndex: 'icon', width: 80,
      render: (v: string | null) => v ? <span style={{ fontSize: 20 }}>{v}</span> : '-',
    },
    {
      title: '图标URL', dataIndex: 'icon_url', width: 120,
      render: (v: string | null) => v ? (
        <img src={v} alt="" style={{ width: 32, height: 32, objectFit: 'contain' }} />
      ) : '-',
    },
    {
      title: '场景分类', dataIndex: 'scene_group_id', width: 100,
      render: (v: number | null) => getSceneGroupName(v),
    },
    {
      title: '跳转链接', dataIndex: 'jump_url', width: 150,
      render: (v: string | null) => v ? <a href={v} target="_blank" style={{ fontSize: 12 }}>{v.slice(0, 30)}...</a> : '-',
      ellipsis: true,
    },
    {
      title: '启用', dataIndex: 'is_active', width: 60,
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '是' : '否'}</Tag>,
    },
    {
      title: '操作', key: 'actions', width: 160,
      render: (_: any, record: CatalogItem) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>编辑</Button>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record)}>
            <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="设备目录管理"
      extra={
        <Space>
          <Select
            placeholder="按场景分类筛选"
            allowClear
            style={{ width: 140 }}
            value={filterSceneGroup}
            onChange={(v) => setFilterSceneGroup(v)}
            options={[
              { label: '全部', value: undefined },
              ...sceneGroups.map(sg => ({ label: sg.name, value: sg.id })),
            ]}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增设备</Button>
        </Space>
      }
    >
      <Table rowKey="id" columns={columns} dataSource={items} loading={loading} pagination={{ pageSize: 20 }} size="middle" />

      <Modal
        title={editing ? '编辑设备' : '新增设备'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        width={600}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 12 }}>
          <Space>
            <div>
              <div style={{ marginBottom: 4 }}>品牌编码</div>
              <Input value={form.brand_code} onChange={(e) => setForm({ ...form, brand_code: e.target.value })} style={{ width: 100 }} />
            </div>
            <div>
              <div style={{ marginBottom: 4 }}>品牌名称</div>
              <Input value={form.brand_name} onChange={(e) => setForm({ ...form, brand_name: e.target.value })} style={{ width: 120 }} />
            </div>
          </Space>
          <div>
            <div style={{ marginBottom: 4 }}>设备名称</div>
            <Input value={form.device_name} onChange={(e) => setForm({ ...form, device_name: e.target.value })} maxLength={128} />
          </div>
          <div>
            <div style={{ marginBottom: 4 }}>分类编码</div>
            <Input value={form.category_code} onChange={(e) => setForm({ ...form, category_code: e.target.value })} />
          </div>
          <Space>
            <div>
              <div style={{ marginBottom: 4 }}>图标 (emoji)</div>
              <Input value={form.icon} onChange={(e) => setForm({ ...form, icon: e.target.value })} maxLength={500} style={{ width: 200 }} />
            </div>
            <div>
              <div style={{ marginBottom: 4 }}>图标 URL</div>
              <Input value={form.icon_url} onChange={(e) => setForm({ ...form, icon_url: e.target.value })} maxLength={500} style={{ width: 260 }} placeholder="https://..." />
            </div>
          </Space>
          <div>
            <div style={{ marginBottom: 4 }}>场景分类</div>
            <Select
              value={form.scene_group_id}
              onChange={(v) => setForm({ ...form, scene_group_id: v })}
              allowClear
              placeholder="选择场景分类"
              style={{ width: '100%' }}
              options={sceneGroups.map(sg => ({ label: sg.name, value: sg.id }))}
            />
          </div>
          <div>
            <div style={{ marginBottom: 4 }}>跳转链接</div>
            <Input value={form.jump_url} onChange={(e) => setForm({ ...form, jump_url: e.target.value })} maxLength={500} placeholder="https://..." />
          </div>
          <Space>
            <div>
              <div style={{ marginBottom: 4 }}>排序</div>
              <InputNumber value={form.sort_order} onChange={(v) => setForm({ ...form, sort_order: v || 0 })} min={0} />
            </div>
            <div>
              <div style={{ marginBottom: 4 }}>启用</div>
              <Switch checked={form.is_active} onChange={(v) => setForm({ ...form, is_active: v })} />
            </div>
            <div>
              <div style={{ marginBottom: 4 }}>唯一绑定</div>
              <Switch checked={form.is_unique} onChange={(v) => setForm({ ...form, is_unique: v })} />
            </div>
          </Space>
        </div>
      </Modal>
    </Card>
  );
}
