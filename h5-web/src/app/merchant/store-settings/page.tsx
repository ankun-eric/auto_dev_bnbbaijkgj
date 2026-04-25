'use client';

// [PRD V1.0 §F2/F3] 商家 PC - 店铺信息（老板可编辑，员工只读）
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
}

export default function StoreSettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [info, setInfo] = useState<ShopInfo | null>(null);
  const [form] = Form.useForm();

  const load = () => {
    setLoading(true);
    api
      .get<ShopInfo, ShopInfo>('/api/merchant/shop/info')
      .then((d) => {
        setInfo(d);
        form.setFieldsValue(d);
      })
      .catch((e: any) => message.error(e?.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const onSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const updated = await api.put<ShopInfo, ShopInfo>('/api/merchant/shop/info', values);
      setInfo(updated);
      form.setFieldsValue(updated);
      setEditing(false);
      message.success('保存成功');
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : detail?.msg || '保存失败';
      message.error(msg);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <Spin />;

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
          <Form form={form} layout="vertical" initialValues={info || {}}>
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
            <Form.Item label="营业时间" name="business_hours">
              <Input placeholder="例：00:00 - 24:00" maxLength={100} />
            </Form.Item>
            <Space>
              <Button type="primary" loading={saving} onClick={onSave}>
                保存
              </Button>
              <Button
                onClick={() => {
                  setEditing(false);
                  if (info) form.setFieldsValue(info);
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
            <Descriptions.Item label="营业时间">{info?.business_hours || '—'}</Descriptions.Item>
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
