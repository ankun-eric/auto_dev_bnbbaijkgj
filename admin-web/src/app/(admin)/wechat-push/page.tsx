'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Form, Input, Switch, Button, Card, Spin, message, Typography } from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import { get, put } from '@/lib/api';

const { Title } = Typography;

interface WechatPushConfig {
  enable_wechat_push: boolean;
  wechat_app_id: string;
  has_wechat_app_secret: boolean;
  order_notify_template: string;
  service_notify_template: string;
}

export default function WechatPushPage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [hasAppSecret, setHasAppSecret] = useState(false);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<WechatPushConfig>('/api/admin/wechat-push/config');
      setHasAppSecret(!!res.has_wechat_app_secret);
      form.setFieldsValue({
        enable_wechat_push: !!res.enable_wechat_push,
        wechat_app_id: res.wechat_app_id || '',
        order_notify_template: res.order_notify_template || '',
        service_notify_template: res.service_notify_template || '',
      });
    } catch {
      // config not yet set
    } finally {
      setLoading(false);
    }
  }, [form]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload: Record<string, any> = {};
      for (const [k, v] of Object.entries(values)) {
        if (v !== undefined && v !== '') payload[k] = v;
      }
      payload.enable_wechat_push = !!values.enable_wechat_push;
      await put('/api/admin/wechat-push/config', payload);
      message.success('微信推送配置保存成功');
      fetchConfig();
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>微信推送管理</Title>
      <Spin spinning={loading}>
        <Card style={{ borderRadius: 12, maxWidth: 640 }}>
          <Form form={form} layout="vertical" initialValues={{ enable_wechat_push: false }}>
            <Form.Item label="启用微信推送" name="enable_wechat_push" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item label="微信AppID" name="wechat_app_id" rules={[{ required: true, message: '请输入微信AppID' }]}>
              <Input placeholder="请输入微信AppID" />
            </Form.Item>
            <Form.Item label="微信AppSecret" name="wechat_app_secret">
              <Input.Password placeholder={hasAppSecret ? '已设置（重新输入将覆盖）' : '请输入微信AppSecret'} />
            </Form.Item>
            <Form.Item label="订单通知模板ID" name="order_notify_template">
              <Input placeholder="请输入订单通知模板ID" />
            </Form.Item>
            <Form.Item label="服务通知模板ID" name="service_notify_template">
              <Input placeholder="请输入服务通知模板ID" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
                保存配置
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </Spin>
    </div>
  );
}
