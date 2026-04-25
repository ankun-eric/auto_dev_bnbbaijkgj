'use client';

// [PRD V1.0 §M4] 商家 PC 端 - 修改密码
// PUT /api/merchant/password 成功后清除 token 并跳回登录页。

import React, { useState } from 'react';
import { Card, Form, Input, Button, message, Typography } from 'antd';
import { LockOutlined } from '@ant-design/icons';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { PASSWORD_REGEX, PASSWORD_HINT } from '@/lib/captcha';

const { Title } = Typography;

export default function MerchantChangePasswordPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();

  const submit = async (values: { old_password: string; new_password: string; confirm_password: string }) => {
    if (values.new_password !== values.confirm_password) {
      message.error('两次输入的新密码不一致');
      return;
    }
    setLoading(true);
    try {
      await api.put('/api/merchant/password', {
        old_password: values.old_password,
        new_password: values.new_password,
        confirm_password: values.confirm_password,
      });
      message.success('密码修改成功，请重新登录');
      // 清 token 并跳登录页
      try {
        localStorage.removeItem('merchant_token');
        localStorage.removeItem('token');
        localStorage.removeItem('merchant_profile');
        localStorage.removeItem('merchant_current_store');
      } catch {}
      setTimeout(() => router.push('/merchant/login'), 800);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '修改失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Title level={4}>修改密码</Title>
      <Card style={{ maxWidth: 520 }}>
        <Form form={form} layout="vertical" onFinish={submit} autoComplete="off">
          <Form.Item
            name="old_password"
            label="原密码"
            rules={[{ required: true, message: '请输入原密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} size="large" placeholder="请输入原密码" />
          </Form.Item>
          <Form.Item
            name="new_password"
            label="新密码"
            extra={PASSWORD_HINT}
            rules={[
              { required: true, message: '请输入新密码' },
              { pattern: PASSWORD_REGEX, message: PASSWORD_HINT },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} size="large" placeholder="请输入新密码" />
          </Form.Item>
          <Form.Item
            name="confirm_password"
            label="确认新密码"
            dependencies={['new_password']}
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_, v) {
                  if (!v || v === getFieldValue('new_password')) return Promise.resolve();
                  return Promise.reject(new Error('两次输入的新密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} size="large" placeholder="请再次输入新密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" size="large" loading={loading} block>
              提交
            </Button>
          </Form.Item>
          <div style={{ color: '#999', fontSize: 12 }}>
            修改成功后，您将自动退出登录，请使用新密码重新登录。
          </div>
        </Form>
      </Card>
    </div>
  );
}
