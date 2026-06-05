'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Table, Button, Modal, Input, InputNumber, Switch, Space, Popconfirm, message, Card, Tag } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';

interface SceneGroup {
  id: number;
  name: string;
  sort_order: number;
  is_enabled: boolean;
  device_count: number;
}

export default function SceneGroupsPage() {
  const [groups, setGroups] = useState<SceneGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<SceneGroup | null>(null);
  const [formName, setFormName] = useState('');
  const [formSort, setFormSort] = useState(0);
  const [formEnabled, setFormEnabled] = useState(true);
  const [saving, setSaving] = useState(false);

  const token = typeof window !== 'undefined' ? localStorage.getItem('token') || '' : '';

  const fetchGroups = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/devices/scene-groups?include_disabled=true', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setGroups(data.items || []);
    } catch (e) {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchGroups(); }, [fetchGroups]);

  const openCreate = () => {
    setEditing(null);
    setFormName('');
    setFormSort(groups.length > 0 ? groups[groups.length - 1].sort_order + 1 : 1);
    setFormEnabled(true);
    setModalOpen(true);
  };

  const openEdit = (g: SceneGroup) => {
    setEditing(g);
    setFormName(g.name);
    setFormSort(g.sort_order);
    setFormEnabled(g.is_enabled);
    setModalOpen(true);
  };

  const handleSave = async () => {
    if (!formName.trim()) { message.warning('请输入分类名称'); return; }
    setSaving(true);
    try {
      const url = editing
        ? `/api/devices/scene-groups/${editing.id}`
        : '/api/devices/scene-groups';
      const method = editing ? 'PUT' : 'POST';
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: formName.trim(), sort_order: formSort, is_enabled: formEnabled }),
      });
      if (!res.ok) {
        const err = await res.json();
        message.error(err.detail || '保存失败');
        return;
      }
      message.success(editing ? '已更新' : '已创建');
      setModalOpen(false);
      fetchGroups();
    } catch (e) {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (g: SceneGroup) => {
    try {
      const res = await fetch(`/api/devices/scene-groups/${g.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json();
        message.error(err.detail || '删除失败');
        return;
      }
      message.success('已删除');
      fetchGroups();
    } catch (e) {
      message.error('删除失败');
    }
  };

  const handleToggle = async (g: SceneGroup) => {
    try {
      const res = await fetch(`/api/devices/scene-groups/${g.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ is_enabled: !g.is_enabled }),
      });
      if (!res.ok) { message.error('操作失败'); return; }
      message.success(g.is_enabled ? '已禁用' : '已启用');
      fetchGroups();
    } catch (e) {
      message.error('操作失败');
    }
  };

  const handleMove = async (g: SceneGroup, direction: 'up' | 'down') => {
    const idx = groups.findIndex(x => x.id === g.id);
    if (idx < 0) return;
    const targetIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (targetIdx < 0 || targetIdx >= groups.length) return;
    const target = groups[targetIdx];
    try {
      await Promise.all([
        fetch(`/api/devices/scene-groups/${g.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ sort_order: target.sort_order }),
        }),
        fetch(`/api/devices/scene-groups/${target.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ sort_order: g.sort_order }),
        }),
      ]);
      message.success('排序已调整');
      fetchGroups();
    } catch (e) {
      message.error('调整失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '分类名称', dataIndex: 'name', width: 150 },
    { title: '排序', dataIndex: 'sort_order', width: 60 },
    {
      title: '启用状态', dataIndex: 'is_enabled', width: 100,
      render: (v: boolean, record: SceneGroup) => (
        <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '禁用'}</Tag>
      ),
    },
    {
      title: '设备数量', dataIndex: 'device_count', width: 80,
      render: (v: number) => <span style={{ fontWeight: 500 }}>{v}</span>,
    },
    {
      title: '操作', key: 'actions', width: 240,
      render: (_: any, record: SceneGroup) => (
        <Space>
          <Button size="small" icon={<ArrowUpOutlined />} onClick={() => handleMove(record, 'up')} />
          <Button size="small" icon={<ArrowDownOutlined />} onClick={() => handleMove(record, 'down')} />
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>编辑</Button>
          <Button size="small" onClick={() => handleToggle(record)}>
            {record.is_enabled ? '禁用' : '启用'}
          </Button>
          <Popconfirm title="确认删除？" description="仅当分类下无设备时可删除" onConfirm={() => handleDelete(record)}>
            <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card title="设备场景分类管理" extra={<Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增分类</Button>}>
      <Table rowKey="id" columns={columns} dataSource={groups} loading={loading} pagination={false} size="middle" />

      <Modal
        title={editing ? '编辑分类' : '新增分类'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 12 }}>
          <div>
            <div style={{ marginBottom: 4 }}>分类名称</div>
            <Input value={formName} onChange={(e) => setFormName(e.target.value)} maxLength={50} placeholder="如：安全守护" />
          </div>
          <div>
            <div style={{ marginBottom: 4 }}>排序序号</div>
            <InputNumber value={formSort} onChange={(v) => setFormSort(v || 0)} min={0} style={{ width: '100%' }} />
          </div>
          <div>
            <div style={{ marginBottom: 4 }}>启用</div>
            <Switch checked={formEnabled} onChange={setFormEnabled} />
          </div>
        </div>
      </Modal>
    </Card>
  );
}
