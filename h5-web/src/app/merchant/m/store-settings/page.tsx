'use client';

// [PRD V1.0 §F2/F3/F4] 商家 H5 - 店铺信息（老板可编辑，员工只读）
// 数据来源：GET /api/merchant/shop/info  ；保存：PUT /api/merchant/shop/info

import React, { useEffect, useState } from 'react';
import { NavBar, Form, Input, TextArea, Button, Toast, List, Tag, Image } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

interface ShopInfo {
  store_id: number;
  merchant_id: number;
  merchant_no: string;
  store_name: string;
  logo_url?: string | null;
  description?: string | null;
  address?: string | null;
  contact_phone?: string | null;
  business_hours?: string | null;
  license_no?: string | null;
  legal_person?: string | null;
  is_owner: boolean;
  can_edit: boolean;
  updated_at?: string | null;
}

export default function StoreSettingsMobilePage() {
  const router = useRouter();
  const [form] = Form.useForm();
  const [info, setInfo] = useState<ShopInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get<ShopInfo, ShopInfo>('/api/merchant/shop/info');
      setInfo(res);
      form.setFieldsValue(res);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : detail?.msg || '加载失败';
      Toast.show({ icon: 'fail', content: msg });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    if (!info?.can_edit) {
      Toast.show({ content: '仅老板可修改店铺信息' });
      return;
    }
    try {
      const values = await form.validateFields();
      setSaving(true);
      const updated = await api.put<ShopInfo, ShopInfo>('/api/merchant/shop/info', values);
      setInfo(updated);
      form.setFieldsValue(updated);
      setEditing(false);
      Toast.show({ icon: 'success', content: '保存成功' });
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : detail?.msg || '保存失败';
      Toast.show({ icon: 'fail', content: msg });
    } finally {
      setSaving(false);
    }
  };

  const cancel = () => {
    setEditing(false);
    if (info) form.setFieldsValue(info);
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f7f8fa', paddingBottom: editing ? 80 : 24 }}>
      <NavBar
        onBack={() => router.back()}
        right={
          info?.can_edit && !editing ? (
            <span
              style={{ color: '#1677ff', fontSize: 14 }}
              onClick={() => setEditing(true)}
            >
              编辑
            </span>
          ) : null
        }
      >
        店铺信息
      </NavBar>

      {!info?.can_edit && (
        <div style={{ margin: 12, padding: 12, background: '#fff7e6', borderRadius: 8, color: '#ad6800', fontSize: 13 }}>
          员工角色仅可查看店铺信息，如需修改请联系老板。
        </div>
      )}

      {!editing ? (
        <>
          {info?.logo_url && (
            <div style={{ textAlign: 'center', padding: 16, background: '#fff', margin: 12, borderRadius: 10 }}>
              <Image src={info.logo_url} width={80} height={80} fit="cover" style={{ borderRadius: '50%' }} />
            </div>
          )}
          <List style={{ margin: 12, borderRadius: 10, overflow: 'hidden' }}>
            <List.Item extra={info?.store_name || '—'}>店铺名称</List.Item>
            <List.Item
              extra={
                <span style={{ maxWidth: 220, textAlign: 'right', display: 'inline-block', whiteSpace: 'normal' }}>
                  {info?.description || '—'}
                </span>
              }
            >
              店铺简介
            </List.Item>
            <List.Item
              extra={
                <span style={{ maxWidth: 220, textAlign: 'right', display: 'inline-block', whiteSpace: 'normal' }}>
                  {info?.address || '—'}
                </span>
              }
            >
              店铺地址
            </List.Item>
            <List.Item extra={info?.contact_phone || '—'}>联系电话</List.Item>
            <List.Item extra={info?.business_hours || '—'}>营业时间</List.Item>
          </List>

          <List header="以下字段不可修改（敏感字段）" style={{ margin: 12, borderRadius: 10, overflow: 'hidden' }}>
            <List.Item extra={info?.license_no || '—'}>营业执照号</List.Item>
            <List.Item extra={info?.legal_person || '—'}>法人姓名</List.Item>
            <List.Item extra={info?.merchant_no || '—'}>商家 ID</List.Item>
          </List>
        </>
      ) : (
        <div style={{ margin: 12, background: '#fff', borderRadius: 10, overflow: 'hidden' }}>
          <Form form={form} layout="vertical" mode="card" style={{ background: 'transparent' }}>
            <Form.Header>可编辑信息</Form.Header>
            <Form.Item
              name="store_name"
              label="店铺名称"
              rules={[
                { required: true, message: '店铺名称不可为空' },
                { min: 2, max: 30, message: '请输入 2-30 个字符' },
              ]}
            >
              <Input placeholder="店铺名称" maxLength={30} clearable />
            </Form.Item>
            <Form.Item name="logo_url" label="店铺 Logo URL">
              <Input placeholder="图片链接" maxLength={500} clearable />
            </Form.Item>
            <Form.Item name="description" label="店铺简介">
              <TextArea placeholder="店铺简介，最多 200 字" rows={3} maxLength={200} />
            </Form.Item>
            <Form.Item name="address" label="店铺地址" rules={[{ required: true, message: '店铺地址不可为空' }]}>
              <Input placeholder="店铺地址" clearable />
            </Form.Item>
            <Form.Item
              name="contact_phone"
              label="联系电话"
              rules={[
                {
                  pattern: /^(1\d{10}|0\d{2,3}-?\d{7,8})?$/,
                  message: '请输入合法的手机号或固话',
                },
              ]}
            >
              <Input placeholder="11 位手机号或固话" clearable />
            </Form.Item>
            <Form.Item name="business_hours" label="营业时间">
              <Input placeholder="例：00:00 - 24:00" maxLength={100} clearable />
            </Form.Item>
          </Form>
        </div>
      )}

      {editing && (
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
            display: 'flex',
            gap: 12,
            zIndex: 100,
          }}
        >
          <Button block onClick={cancel} disabled={saving}>
            取消
          </Button>
          <Button block color="primary" onClick={save} loading={saving}>
            保存
          </Button>
        </div>
      )}
    </div>
  );
}
