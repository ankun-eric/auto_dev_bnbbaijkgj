'use client';

// [PRD V1.0 §M5 / §M6] 商家端 H5 - 强制修改密码
// 用于「首次登录」或「被重置密码」的员工。表单：新密码 + 确认新密码，无原密码。
// POST /api/auth/force-change-password 成功后跳回 /merchant/m/login。

import React, { useState } from 'react';
import { Form, Input, Button, Toast, NavBar } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { PASSWORD_REGEX, PASSWORD_HINT } from '@/lib/captcha';

export default function ForceChangePasswordPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();

  const submit = async () => {
    try {
      const values = await form.validateFields();
      if (values.new_password !== values.confirm_password) {
        Toast.show({ icon: 'fail', content: '两次输入的新密码不一致' });
        return;
      }
      setLoading(true);
      await api.post('/api/auth/force-change-password', {
        new_password: values.new_password,
        confirm_password: values.confirm_password,
      });
      Toast.show({ icon: 'success', content: '密码修改成功，请重新登录' });
      try {
        localStorage.removeItem('merchant_token');
        localStorage.removeItem('token');
        localStorage.removeItem('merchant_profile');
        localStorage.removeItem('merchant_current_store');
      } catch {}
      setTimeout(() => router.push('/merchant/m/login'), 800);
    } catch (e: any) {
      if (e?.errorFields) return;
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '修改失败' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f7f8fa' }}>
      <NavBar back={null}>设置新密码</NavBar>
      <div style={{ padding: '20px 16px' }}>
        <div
          style={{
            background: '#fffbe6',
            border: '1px solid #ffe58f',
            color: '#ad8b00',
            borderRadius: 8,
            padding: 12,
            fontSize: 13,
            marginBottom: 16,
          }}
        >
          为了您的账号安全，首次登录或密码被重置后必须先修改密码再继续使用。
        </div>

        <div
          style={{
            background: '#fff',
            borderRadius: 12,
            padding: 16,
            boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
          }}
        >
          <Form form={form} layout="vertical" mode="card" style={{ background: 'transparent' }}>
            <Form.Item
              name="new_password"
              label="新密码"
              rules={[
                { required: true, message: '请输入新密码' },
                { pattern: PASSWORD_REGEX, message: PASSWORD_HINT },
              ]}
              extra={PASSWORD_HINT}
            >
              <Input placeholder="请输入新密码" type="password" clearable />
            </Form.Item>
            <Form.Item
              name="confirm_password"
              label="确认新密码"
              rules={[{ required: true, message: '请再次输入新密码' }]}
            >
              <Input placeholder="请再次输入新密码" type="password" clearable />
            </Form.Item>
          </Form>

          <Button
            block
            color="primary"
            size="large"
            loading={loading}
            onClick={submit}
            style={{ marginTop: 16, height: 48, fontSize: 16 }}
          >
            提交并重新登录
          </Button>
        </div>
      </div>
    </div>
  );
}
