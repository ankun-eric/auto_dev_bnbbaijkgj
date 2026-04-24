'use client';

// [2026-04-24] 移动端 - 门店设置 PRD §4.7
// 可编辑：营业时间、联系电话、门店公告；其他字段只读

import React, { useEffect, useState } from 'react';
import { NavBar, Form, Input, TextArea, Button, Toast, List } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { getProfile, getCurrentStoreId } from '../mobile-lib';

export default function StoreSettingsMobilePage() {
  const router = useRouter();
  const [form] = Form.useForm();
  const [store, setStore] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const storeId = getCurrentStoreId() || getProfile()?.stores?.[0]?.id;
  const role = getProfile()?.role;
  const readonly = role === 'finance';

  const load = async () => {
    if (!storeId) return;
    setLoading(true);
    try {
      // 复用 C 端 stores 接口或管理端接口（按实际后端调整）
      const res: any = await api.get(`/api/merchant/v1/stores/${storeId}`).catch(async () => {
        // 兜底：从 profile 构造
        const p = getProfile();
        const s = p?.stores?.find((x) => x.id === storeId);
        return { id: storeId, name: s?.name || '门店', phone: '', business_hours: '', notice: '' };
      });
      setStore(res);
      form.setFieldsValue({
        phone: res.phone || '',
        business_hours: res.business_hours || '',
        notice: res.notice || res.description || '',
      });
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '加载失败' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storeId]);

  const save = async () => {
    if (readonly) {
      Toast.show({ content: '财务角色只读，无法编辑' });
      return;
    }
    try {
      const values = await form.validateFields();
      setSaving(true);
      await api.put(`/api/merchant/v1/stores/${storeId}`, values);
      Toast.show({ icon: 'success', content: '已保存' });
      load();
    } catch (e: any) {
      if (e?.errorFields) return;
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '保存失败' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f7f8fa', paddingBottom: 80 }}>
      <NavBar onBack={() => router.back()}>门店设置</NavBar>

      {/* 只读字段 */}
      <List header="基础信息（只读，请用电脑编辑）" style={{ margin: 12, borderRadius: 10, overflow: 'hidden' }}>
        <List.Item extra={store?.name || '-'}>门店名</List.Item>
        <List.Item extra={store?.address || '-'}>门店地址</List.Item>
        <List.Item extra={store?.category || '-'}>门店类别</List.Item>
      </List>

      {/* 可编辑字段 */}
      <div style={{ margin: 12, background: '#fff', borderRadius: 10, overflow: 'hidden' }}>
        <Form form={form} layout="vertical" mode="card" style={{ background: 'transparent' }}>
          <Form.Header>可编辑信息</Form.Header>
          <Form.Item name="phone" label="联系电话">
            <Input placeholder="请输入联系电话" clearable disabled={readonly} />
          </Form.Item>
          <Form.Item name="business_hours" label="营业时间">
            <Input placeholder="如：09:00-21:00" clearable disabled={readonly} />
          </Form.Item>
          <Form.Item name="notice" label="门店公告">
            <TextArea placeholder="请输入门店公告" rows={3} disabled={readonly} maxLength={200} />
          </Form.Item>
        </Form>
      </div>

      {!readonly && (
        <div
          style={{
            position: 'fixed',
            left: 0,
            right: 0,
            bottom: 0,
            background: '#fff',
            padding: 12,
            borderTop: '1px solid #eee',
            maxWidth: 768,
            margin: '0 auto',
          }}
        >
          <Button block color="primary" onClick={save} loading={saving}>
            保存
          </Button>
        </div>
      )}
    </div>
  );
}
