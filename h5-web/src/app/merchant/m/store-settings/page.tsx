'use client';

// [PRD V1.0 §F2/F3/F4] 商家 H5 - 店铺信息（老板可编辑，员工只读）
// [2026-05-03 营业时间/营业范围保存 Bug 修复方案] 营业时间改为时间选择器；新增营业范围编辑
// 数据来源：GET /api/merchant/shop/info  ；保存：PUT /api/merchant/shop/info

import React, { useEffect, useState } from 'react';
import {
  NavBar,
  Form,
  Input,
  TextArea,
  Button,
  Toast,
  List,
  Tag,
  Image,
  Picker,
  Selector,
} from 'antd-mobile';
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
  business_start?: string | null;
  business_end?: string | null;
  business_scope?: number[] | null;
  affected_appointments?: number;
}

interface CategoryItem {
  id: number;
  name: string;
  level?: number;
  children?: CategoryItem[];
}

const TIME_START_OPTIONS = (() => {
  const out: string[] = [];
  for (let h = 7; h <= 22; h++) {
    for (const m of [0, 30]) {
      if (h === 22 && m === 30) break;
      out.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`);
    }
  }
  return out;
})();

const TIME_END_OPTIONS = (() => {
  const out: string[] = [];
  for (let h = 7; h <= 22; h++) {
    for (const m of [0, 30]) {
      if (h === 7 && m === 0) continue;
      if (h === 22 && m === 30) break;
      out.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`);
    }
  }
  out.push('22:00');
  return out;
})();

function flattenCategories(items: CategoryItem[]): CategoryItem[] {
  const out: CategoryItem[] = [];
  const walk = (list: CategoryItem[]) => {
    list.forEach((c) => {
      out.push(c);
      if (Array.isArray(c.children) && c.children.length > 0) walk(c.children);
    });
  };
  walk(items);
  return out;
}

export default function StoreSettingsMobilePage() {
  const router = useRouter();
  const [form] = Form.useForm();
  const [info, setInfo] = useState<ShopInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [categories, setCategories] = useState<CategoryItem[]>([]);

  const [bsStart, setBsStart] = useState<string>('09:00');
  const [bsEnd, setBsEnd] = useState<string>('22:00');
  const [scope, setScope] = useState<number[]>([]);
  const [pickerStartVisible, setPickerStartVisible] = useState(false);
  const [pickerEndVisible, setPickerEndVisible] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get<ShopInfo, ShopInfo>('/api/merchant/shop/info');
      setInfo(res);
      form.setFieldsValue(res);
      setBsStart(res.business_start || '09:00');
      setBsEnd(res.business_end || '22:00');
      setScope(Array.isArray(res.business_scope) ? res.business_scope : []);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : detail?.msg || '加载失败';
      Toast.show({ icon: 'fail', content: msg });
    } finally {
      setLoading(false);
    }
  };

  const loadCategories = async () => {
    try {
      const res: any = await api.get<any, any>('/api/products/categories');
      const list: CategoryItem[] = res?.items || res?.list || res || [];
      setCategories(flattenCategories(Array.isArray(list) ? list : []));
    } catch {
      setCategories([]);
    }
  };

  useEffect(() => {
    load();
    loadCategories();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    if (!info?.can_edit) {
      Toast.show({ content: '仅老板可修改店铺信息' });
      return;
    }
    let values: any;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    if (!bsStart || !bsEnd) {
      Toast.show({ icon: 'fail', content: '请选择营业开始 / 结束时间' });
      return;
    }
    if (bsEnd <= bsStart) {
      Toast.show({ icon: 'fail', content: '结束时间必须晚于开始时间' });
      return;
    }
    try {
      setSaving(true);
      const payload = {
        store_name: values.store_name,
        logo_url: values.logo_url,
        description: values.description,
        address: values.address,
        contact_phone: values.contact_phone,
        business_start: bsStart,
        business_end: bsEnd,
        business_scope: scope,
      };
      const updated = await api.put<ShopInfo, ShopInfo>('/api/merchant/shop/info', payload);
      setInfo(updated);
      form.setFieldsValue(updated);
      setBsStart(updated.business_start || bsStart);
      setBsEnd(updated.business_end || bsEnd);
      setScope(Array.isArray(updated.business_scope) ? updated.business_scope : []);
      setEditing(false);
      Toast.show({ icon: 'success', content: '保存成功' });
      const affected = Number(updated?.affected_appointments || 0);
      if (affected > 0) {
        setTimeout(() => {
          Toast.show({
            content: `您有 ${affected} 单预约时间已不在新营业范围内，建议联系客户`,
            duration: 5000,
          });
        }, 600);
      }
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : detail?.msg || '保存失败';
      Toast.show({ icon: 'fail', content: msg });
    } finally {
      setSaving(false);
    }
  };

  const cancel = () => {
    setEditing(false);
    if (info) {
      form.setFieldsValue(info);
      setBsStart(info.business_start || '09:00');
      setBsEnd(info.business_end || '22:00');
      setScope(Array.isArray(info.business_scope) ? info.business_scope : []);
    }
  };

  const businessHoursDisplay = (() => {
    if (info?.business_start && info?.business_end) {
      return `${info.business_start} - ${info.business_end}`;
    }
    return info?.business_hours || '—';
  })();

  const businessScopeDisplay = (() => {
    const ids = Array.isArray(info?.business_scope) ? info!.business_scope! : [];
    if (!ids || ids.length === 0) return '—';
    const map = new Map(categories.map((c) => [c.id, c.name]));
    return ids.map((id) => map.get(id) || `#${id}`).join(' / ');
  })();

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
            <List.Item extra={businessHoursDisplay}>营业时间</List.Item>
            <List.Item
              extra={
                <span style={{ maxWidth: 220, textAlign: 'right', display: 'inline-block', whiteSpace: 'normal' }}>
                  {businessScopeDisplay}
                </span>
              }
            >
              营业范围
            </List.Item>
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
            {/* [2026-05-03] 营业时间：30 分钟粒度 */}
            <Form.Item label="营业时间">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div
                  onClick={() => setPickerStartVisible(true)}
                  style={{
                    flex: 1,
                    border: '1px solid #ddd',
                    borderRadius: 4,
                    padding: '6px 10px',
                    minHeight: 32,
                    color: bsStart ? '#000' : '#999',
                  }}
                >
                  {bsStart || '开始时间'}
                </div>
                <span>至</span>
                <div
                  onClick={() => setPickerEndVisible(true)}
                  style={{
                    flex: 1,
                    border: '1px solid #ddd',
                    borderRadius: 4,
                    padding: '6px 10px',
                    minHeight: 32,
                    color: bsEnd ? '#000' : '#999',
                  }}
                >
                  {bsEnd || '结束时间'}
                </div>
              </div>
              <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>
                30 分钟一档，范围 07:00 – 22:00；结束时间必须晚于开始时间
              </div>
              {bsStart && bsEnd && bsEnd <= bsStart && (
                <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4 }}>
                  结束时间必须晚于开始时间
                </div>
              )}
              <Picker
                columns={[TIME_START_OPTIONS.map((t) => ({ label: t, value: t }))]}
                visible={pickerStartVisible}
                onClose={() => setPickerStartVisible(false)}
                value={[bsStart]}
                onConfirm={(v) => {
                  if (v && v[0]) setBsStart(String(v[0]));
                }}
              />
              <Picker
                columns={[TIME_END_OPTIONS.map((t) => ({ label: t, value: t }))]}
                visible={pickerEndVisible}
                onClose={() => setPickerEndVisible(false)}
                value={[bsEnd]}
                onConfirm={(v) => {
                  if (v && v[0]) setBsEnd(String(v[0]));
                }}
              />
            </Form.Item>
            {/* [2026-05-03] 营业范围（多选商品分类） */}
            <Form.Item label="营业范围">
              <Selector
                multiple
                options={categories.map((c) => ({
                  label: `${c.level === 2 ? '└ ' : ''}${c.name}`,
                  value: c.id,
                }))}
                value={scope}
                onChange={(v) => setScope((v as number[]) || [])}
              />
              <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>
                选填；不填不影响下单链路
              </div>
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
