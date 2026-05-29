'use client';

/**
 * [会员中心 PRD v1.0 终稿对齐 2026-05-26] 免费会员额度配置页
 *
 * 路径：/membership/free-quota
 * 字段：max_managed / ai_outbound_call_count / emergency_ai_call_count / max_managed_by
 */

import React, { useEffect, useState } from 'react';
import { Button, Card, Form, InputNumber, Space, Typography, message, Alert } from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import Link from 'next/link';
import { get, put } from '@/lib/api';

const { Title, Paragraph } = Typography;

export default function FreeQuotaPage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await get<any>('/api/admin/membership/free-quota');
      if (res) {
        form.setFieldsValue({
          max_managed: res.max_managed ?? 3,
          ai_outbound_call_count: res.ai_outbound_call_count ?? 5,
          emergency_ai_call_count: res.emergency_ai_call_count ?? 3,
          max_managed_by: res.max_managed_by ?? 3,
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
      message.success('已保存：所有免费会员的额度立即按新配置生效');
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
        系统级常量。保存后所有免费会员（未购买付费套餐的用户）的额度立即按新配置生效。
        <Link href="/membership/plans" style={{ marginLeft: 12 }}>
          ← 返回付费会员套餐管理
        </Link>
      </Paragraph>

      <Alert
        type="info"
        showIcon
        message="字段值填 -1 表示不限"
        style={{ marginBottom: 16 }}
      />

      <Card loading={loading}>
        <Form form={form} layout="vertical">
          <Form.Item label="可管理健康档案数（不含本人）" name="max_managed" rules={[{ required: true }]}
            tooltip="[PRD-HEALTH-ARCHIVE-MGR-V1 2026-05-29] 字段名保留 max_managed；填写「可管理家人健康档案数」，用户端展示时自动 +1 含本人。-1 表示不限。">
            <InputNumber min={-1} style={{ width: 240 }} />
          </Form.Item>
          <Form.Item label="AI 外呼提醒（次/月）" name="ai_outbound_call_count" rules={[{ required: true }]}
            tooltip="-1 表示不限">
            <InputNumber min={-1} style={{ width: 240 }} />
          </Form.Item>
          <Form.Item label="紧急 AI 呼叫（次/月）" name="emergency_ai_call_count" rules={[{ required: true }]}
            tooltip="-1 表示不限">
            <InputNumber min={-1} style={{ width: 240 }} />
          </Form.Item>
          <Form.Item label="被管理人数上限" name="max_managed_by" rules={[{ required: true }]}
            tooltip="免费用户可被多少守护人管理（-1 表示不限）">
            <InputNumber min={-1} style={{ width: 240 }} />
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
