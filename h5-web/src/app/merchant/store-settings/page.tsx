'use client';

// [PRD V1.0 §F2/F3] 商家 PC - 店铺信息（老板可编辑，员工只读）
// [2026-05-03 营业时间/营业范围保存 Bug 修复方案] 营业时间改为 30 分钟时间选择器；新增营业范围编辑
// 数据来源：GET /api/merchant/shop/info  ；保存：PUT /api/merchant/shop/info

import React, { useEffect, useState } from 'react';
import {
  Card,
  Descriptions,
  Typography,
  Spin,
  Alert,
  message,
  Button,
  Form,
  Input,
  Space,
  Tag,
  Select,
} from 'antd';
import { EditOutlined } from '@ant-design/icons';
import api from '@/lib/api';

const { Title } = Typography;

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
  // [2026-05-03 营业时间/营业范围 Bug 修复]
  business_start?: string | null;
  business_end?: string | null;
  business_scope?: number[] | null;
  affected_appointments?: number;
}

interface ProductCategoryItem {
  id: number;
  name: string;
  level?: number;
  children?: ProductCategoryItem[];
}

const BUSINESS_TIME_OPTIONS = (() => {
  const out: { label: string; value: string }[] = [];
  for (let h = 7; h <= 22; h++) {
    for (const m of [0, 30]) {
      if (h === 22 && m === 30) break;
      const v = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
      out.push({ label: v, value: v });
    }
  }
  return out;
})();

const BUSINESS_END_OPTIONS = (() => {
  const out: { label: string; value: string }[] = [];
  for (let h = 7; h <= 22; h++) {
    for (const m of [0, 30]) {
      if (h === 7 && m === 0) continue;
      if (h === 22 && m === 30) break;
      const v = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
      out.push({ label: v, value: v });
    }
  }
  out.push({ label: '22:00', value: '22:00' });
  return out;
})();

function flattenCategories(items: ProductCategoryItem[]): ProductCategoryItem[] {
  const out: ProductCategoryItem[] = [];
  const walk = (list: ProductCategoryItem[]) => {
    list.forEach((c) => {
      out.push(c);
      if (Array.isArray(c.children) && c.children.length > 0) walk(c.children);
    });
  };
  walk(items);
  return out;
}

export default function StoreSettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [info, setInfo] = useState<ShopInfo | null>(null);
  const [categories, setCategories] = useState<ProductCategoryItem[]>([]);
  const [form] = Form.useForm();

  const load = () => {
    setLoading(true);
    api
      .get<ShopInfo, ShopInfo>('/api/merchant/shop/info')
      .then((d) => {
        setInfo(d);
        form.setFieldsValue({
          ...d,
          business_scope: Array.isArray(d.business_scope) ? d.business_scope : [],
        });
      })
      .catch((e: any) => message.error(e?.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false));
  };

  const loadCategories = () => {
    api
      .get<any, any>('/api/products/categories')
      .then((res: any) => {
        const list: ProductCategoryItem[] = res?.items || res?.list || res || [];
        setCategories(flattenCategories(Array.isArray(list) ? list : []));
      })
      .catch(() => setCategories([]));
  };

  useEffect(() => {
    load();
    loadCategories();
  }, []);

  const onSave = async () => {
    let values: any;
    try {
      values = await form.validateFields();
    } catch (e: any) {
      return;
    }

    // [2026-05-03 营业时间 Bug 修复] 前端拦截
    if (!values.business_start || !values.business_end) {
      message.error('请选择营业开始时间和结束时间');
      return;
    }
    if (values.business_end <= values.business_start) {
      message.error('营业结束时间必须晚于营业开始时间');
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
        business_start: values.business_start,
        business_end: values.business_end,
        business_scope: Array.isArray(values.business_scope) ? values.business_scope : [],
      };
      const updated = await api.put<ShopInfo, ShopInfo>('/api/merchant/shop/info', payload);
      setInfo(updated);
      form.setFieldsValue({
        ...updated,
        business_scope: Array.isArray(updated.business_scope) ? updated.business_scope : [],
      });
      setEditing(false);
      message.success('保存成功');
      const affected = Number(updated?.affected_appointments || 0);
      if (affected > 0) {
        message.info(`您有 ${affected} 单预约时间已不在新营业范围内，建议联系客户`, 6);
      }
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : detail?.msg || '保存失败';
      message.error(msg);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <Spin />;

  const renderBusinessHoursDisplay = () => {
    if (info?.business_start && info?.business_end) {
      return `${info.business_start} - ${info.business_end}`;
    }
    return info?.business_hours || '—';
  };

  const renderBusinessScopeDisplay = () => {
    const ids = Array.isArray(info?.business_scope) ? info!.business_scope! : [];
    if (!ids || ids.length === 0) return '—';
    const map = new Map(categories.map((c) => [c.id, c.name]));
    const names = ids.map((id) => map.get(id) || `#${id}`);
    return names.join(' / ');
  };

  return (
    <div>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }}>
        <Title level={4} style={{ margin: 0 }}>店铺信息</Title>
        {info?.can_edit && !editing && (
          <Button type="primary" icon={<EditOutlined />} onClick={() => setEditing(true)}>
            编辑
          </Button>
        )}
      </Space>

      {!info?.can_edit && (
        <Alert
          type="info"
          showIcon
          message="员工角色仅可查看店铺信息，如需修改请联系老板。"
          style={{ marginBottom: 16 }}
        />
      )}

      <Card>
        {editing ? (
          <Form
            form={form}
            layout="vertical"
            initialValues={{
              ...(info || {}),
              business_scope: Array.isArray(info?.business_scope) ? info!.business_scope! : [],
            }}
          >
            <Form.Item
              label="店铺名称"
              name="store_name"
              rules={[
                { required: true, message: '店铺名称不可为空' },
                { min: 2, max: 30, message: '请输入 2-30 个字符' },
              ]}
            >
              <Input placeholder="店铺名称" maxLength={30} />
            </Form.Item>
            <Form.Item label="店铺 Logo URL" name="logo_url">
              <Input placeholder="图片链接（≤ 500 字符）" maxLength={500} />
            </Form.Item>
            <Form.Item label="店铺简介" name="description" rules={[{ max: 200, message: '不超过 200 字' }]}>
              <Input.TextArea rows={3} placeholder="店铺简介，最多 200 字" maxLength={200} />
            </Form.Item>
            <Form.Item label="店铺地址" name="address" rules={[{ required: true, message: '店铺地址不可为空' }]}>
              <Input placeholder="店铺地址" />
            </Form.Item>
            <Form.Item
              label="联系电话"
              name="contact_phone"
              rules={[
                {
                  pattern: /^(1\d{10}|0\d{2,3}-?\d{7,8})?$/,
                  message: '请输入合法的手机号或固话',
                },
              ]}
            >
              <Input placeholder="11 位手机号或固话" />
            </Form.Item>
            {/* [2026-05-03] 营业时间：30 分钟粒度时间选择器 */}
            <Form.Item
              label="营业时间"
              required
              tooltip="30 分钟粒度，可选范围 07:00 – 22:00；结束时间必须晚于开始时间"
              shouldUpdate={(prev, cur) =>
                prev.business_start !== cur.business_start || prev.business_end !== cur.business_end
              }
            >
              {({ getFieldValue }) => {
                const bs: string | undefined = getFieldValue('business_start');
                const be: string | undefined = getFieldValue('business_end');
                const invalid = !!bs && !!be && be <= bs;
                return (
                  <>
                    <Space>
                      <Form.Item
                        name="business_start"
                        noStyle
                        rules={[{ required: true, message: '请选择开始时间' }]}
                      >
                        <Select
                          placeholder="开始时间"
                          style={{ width: 140 }}
                          options={BUSINESS_TIME_OPTIONS}
                        />
                      </Form.Item>
                      <span>至</span>
                      <Form.Item
                        name="business_end"
                        noStyle
                        rules={[{ required: true, message: '请选择结束时间' }]}
                      >
                        <Select
                          placeholder="结束时间"
                          style={{ width: 140 }}
                          options={BUSINESS_END_OPTIONS}
                        />
                      </Form.Item>
                    </Space>
                    {invalid && (
                      <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4 }}>
                        结束时间必须晚于开始时间
                      </div>
                    )}
                  </>
                );
              }}
            </Form.Item>
            {/* [2026-05-03] 新增：营业范围 */}
            <Form.Item
              label="营业范围"
              name="business_scope"
              tooltip="选填；选择本店经营的商品分类"
            >
              <Select
                mode="multiple"
                placeholder="请选择经营的商品分类（选填）"
                showSearch
                optionFilterProp="label"
                options={categories.map((c) => ({
                  label: `${c.level === 2 ? '  └ ' : ''}${c.name}`,
                  value: c.id,
                }))}
                maxTagCount="responsive"
                allowClear
              />
            </Form.Item>
            <Space>
              <Button type="primary" loading={saving} onClick={onSave}>
                保存
              </Button>
              <Button
                onClick={() => {
                  setEditing(false);
                  if (info) {
                    form.setFieldsValue({
                      ...info,
                      business_scope: Array.isArray(info.business_scope) ? info.business_scope : [],
                    });
                  }
                }}
              >
                取消
              </Button>
            </Space>
          </Form>
        ) : (
          <Descriptions bordered column={1} labelStyle={{ width: 140 }}>
            <Descriptions.Item label="店铺名称">{info?.store_name || '—'}</Descriptions.Item>
            <Descriptions.Item label="店铺 Logo">
              {info?.logo_url ? (
                <img src={info.logo_url} alt="logo" style={{ height: 60, borderRadius: 8 }} />
              ) : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="店铺简介">{info?.description || '—'}</Descriptions.Item>
            <Descriptions.Item label="店铺地址">{info?.address || '—'}</Descriptions.Item>
            <Descriptions.Item label="联系电话">{info?.contact_phone || '—'}</Descriptions.Item>
            <Descriptions.Item label="营业时间">{renderBusinessHoursDisplay()}</Descriptions.Item>
            <Descriptions.Item label="营业范围">{renderBusinessScopeDisplay()}</Descriptions.Item>
            <Descriptions.Item label="营业执照号">
              <Tag color="default">{info?.license_no || '—'}</Tag>
              <span style={{ color: '#999', marginLeft: 8, fontSize: 12 }}>敏感字段，仅平台可改</span>
            </Descriptions.Item>
            <Descriptions.Item label="法人姓名">
              <Tag color="default">{info?.legal_person || '—'}</Tag>
              <span style={{ color: '#999', marginLeft: 8, fontSize: 12 }}>敏感字段，仅平台可改</span>
            </Descriptions.Item>
            <Descriptions.Item label="商家 ID">{info?.merchant_no}</Descriptions.Item>
            {info?.updated_at && (
              <Descriptions.Item label="最近更新">{info.updated_at}</Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Card>
    </div>
  );
}
