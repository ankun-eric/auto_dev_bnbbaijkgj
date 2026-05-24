'use client';

/**
 * [付费会员体系 PRD v1.1] 免费会员额度配置页
 *
 * 路径：/membership/free-quota
 * 功能：维护一份"默认免费会员额度"系统级常量配置（单行 id=1）。
 */

import React, { useEffect, useState } from 'react';
import { Button, Card, Form, Input, InputNumber, Space, Typography, message } from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import Link from 'next/link';
import { get, put } from '@/lib/api';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

export default function FreeQuotaPage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await get('/api/admin/membership/free-quota');
      if (res) {
        form.setFieldsValue({
          ai_call_quota: res.ai_call_quota || 0,
          ai_alert_quota: res.ai_alert_quota || 0,
          ai_remind_quota: res.ai_remind_quota || 0,
          max_guardians: res.max_guardians || 1,
          benefits_desc: res.benefits_desc || '',
        });
      }
    } catch (e) {
      message.error('加载免费会员额度失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const onSave = async () => {
    setSaving(true);
    try {
      const values = await form.validateFields();
      await put('/api/admin/membership/free-quota', values);
      message.success('已保存');
    } catch (e: any) {
      if (!e?.errorFields) message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 720 }}>
      <Title level={3}>免费会员额度配置</Title>
      <Paragraph type="secondary">
        系统级常量。所有未购买付费套餐的用户默认享有以下额度。修改后立即对所有免费会员生效。
        <Link href="/membership/plans" style={{ marginLeft: 12 }}>
          ← 返回付费会员套餐配置
        </Link>
      </Paragraph>

      <Card loading={loading}>
        <Form form={form} layout="vertical">
          <Form.Item label="AI 电话告警额度（次/月）" name="ai_call_quota">
            <InputNumber min={0} style={{ width: 240 }} />
          </Form.Item>
          <Form.Item
            label="AI 异常告警额度（次/月）"
            name="ai_alert_quota"
            tooltip="PRD § 七：异常告警电话完全免费、平台兜底，本字段仅控制 App 内告警次数限制"
          >
            <InputNumber min={0} style={{ width: 240 }} />
          </Form.Item>
          <Form.Item label="AI 外呼提醒额度（次/月）" name="ai_remind_quota">
            <InputNumber min={0} style={{ width: 240 }} />
          </Form.Item>
          <Form.Item label="守护人数量上限" name="max_guardians" rules={[{ required: true }]}>
            <InputNumber min={1} style={{ width: 240 }} />
          </Form.Item>
          <Form.Item label="免费会员权益说明" name="benefits_desc">
            <TextArea rows={4} placeholder="将展示在用户端的会员卡片/权益页" />
          </Form.Item>
          <Space>
            <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={onSave}>
              保存
            </Button>
          </Space>
        </Form>
      </Card>
    </div>
  );
}
