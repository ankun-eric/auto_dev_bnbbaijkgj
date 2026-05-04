'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Dropdown,
  Button,
  Modal,
  Input,
  Checkbox,
  message,
  List,
  Tag,
  Popconfirm,
  Space,
} from 'antd';
import {
  StarOutlined,
  StarFilled,
  PlusOutlined,
  DeleteOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import api from '@/lib/api';
import type { CalendarFilters, CalendarView, MyView } from './types';

interface MyViewsManagerProps {
  storeId: number | null;
  currentFilters: CalendarFilters;
  currentView: CalendarView;
  onApplyView: (v: MyView) => void;
}

export default function MyViewsManager({
  storeId,
  currentFilters,
  currentView,
  onApplyView,
}: MyViewsManagerProps) {
  const [views, setViews] = useState<MyView[]>([]);
  const [loading, setLoading] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saveAsDefault, setSaveAsDefault] = useState(false);

  const load = useCallback(async () => {
    if (!storeId) return;
    setLoading(true);
    try {
      const res: any = await api.get('/api/merchant/calendar/views', {
        params: { store_id: storeId },
      });
      setViews(res?.items || []);
    } catch {
      setViews([]);
    } finally {
      setLoading(false);
    }
  }, [storeId]);

  useEffect(() => {
    load();
  }, [load]);

  const submitSave = async () => {
    if (!storeId) return;
    if (!saveName.trim()) {
      message.warning('请填写视图名称');
      return;
    }
    try {
      await api.post(
        '/api/merchant/calendar/views',
        {
          name: saveName.trim(),
          view_type: currentView,
          filter_payload: currentFilters,
          is_default: saveAsDefault,
        },
        { params: { store_id: storeId } }
      );
      message.success('保存成功');
      setSaveOpen(false);
      setSaveName('');
      setSaveAsDefault(false);
      await load();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '保存失败');
    }
  };

  const removeView = async (id: number) => {
    if (!storeId) return;
    try {
      await api.delete(`/api/merchant/calendar/views/${id}`, {
        params: { store_id: storeId },
      });
      message.success('已删除');
      await load();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除失败');
    }
  };

  const setDefault = async (v: MyView) => {
    if (!storeId) return;
    try {
      await api.put(
        `/api/merchant/calendar/views/${v.id}`,
        { is_default: !v.is_default },
        { params: { store_id: storeId } }
      );
      await load();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const menuItems = [
    ...views.map((v) => ({
      key: `view-${v.id}`,
      label: (
        <Space>
          {v.is_default ? (
            <StarFilled style={{ color: '#faad14' }} />
          ) : (
            <StarOutlined />
          )}
          {v.name}
          <Tag>{v.view_type}</Tag>
        </Space>
      ),
      onClick: () => onApplyView(v),
    })),
    { type: 'divider' as const },
    {
      key: 'save-as',
      label: (
        <Space>
          <PlusOutlined />
          保存当前为我的视图
        </Space>
      ),
      onClick: () => setSaveOpen(true),
    },
    {
      key: 'manage',
      label: (
        <Space>
          <SettingOutlined />
          管理我的视图
        </Space>
      ),
      onClick: () => setManageOpen(true),
    },
  ];

  return (
    <>
      <Dropdown
        menu={{ items: menuItems }}
        trigger={['click']}
        placement="bottomRight"
      >
        <Button size="small" loading={loading}>
          我的视图 {views.length > 0 ? `(${views.length})` : ''}
        </Button>
      </Dropdown>

      <Modal
        title="保存当前为我的视图"
        open={saveOpen}
        onOk={submitSave}
        onCancel={() => setSaveOpen(false)}
        okText="保存"
        cancelText="取消"
      >
        <div style={{ marginBottom: 12 }}>
          <Input
            placeholder="视图名称（最长 40 字）"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            maxLength={40}
          />
        </div>
        <Checkbox
          checked={saveAsDefault}
          onChange={(e) => setSaveAsDefault(e.target.checked)}
        >
          设为默认（打开页面时自动应用）
        </Checkbox>
        <div style={{ marginTop: 12, color: '#8c8c8c', fontSize: 12 }}>
          每账号每门店最多保存 10 个视图，超出请先删除旧视图。
        </div>
      </Modal>

      <Modal
        title="管理我的视图"
        open={manageOpen}
        onCancel={() => setManageOpen(false)}
        footer={null}
        width={520}
      >
        <List
          loading={loading}
          dataSource={views}
          locale={{ emptyText: '暂无视图' }}
          renderItem={(v) => (
            <List.Item
              actions={[
                <Button
                  key="default"
                  type="text"
                  icon={
                    v.is_default ? (
                      <StarFilled style={{ color: '#faad14' }} />
                    ) : (
                      <StarOutlined />
                    )
                  }
                  onClick={() => setDefault(v)}
                  size="small"
                >
                  {v.is_default ? '默认' : '设为默认'}
                </Button>,
                <Popconfirm
                  key="del"
                  title="确认删除该视图？"
                  onConfirm={() => removeView(v.id)}
                >
                  <Button type="text" danger icon={<DeleteOutlined />} size="small">
                    删除
                  </Button>
                </Popconfirm>,
              ]}
            >
              <List.Item.Meta
                title={
                  <Space>
                    {v.name}
                    <Tag>{v.view_type}</Tag>
                  </Space>
                }
                description={
                  v.filter_payload
                    ? `筛选：${Object.keys(v.filter_payload).filter((k) => (v.filter_payload as any)[k]?.length || (v.filter_payload as any)[k]).join('、') || '无'}`
                    : '无筛选'
                }
              />
            </List.Item>
          )}
        />
      </Modal>
    </>
  );
}
