'use client';

// [PRD V1.0 §M4] 商家 H5 - 修改密码（与 PC 逻辑一致）
// PUT /api/merchant/password 成功后清除 token 并跳回 /merchant/m/login

import React, { useState } from 'react';
import { Form, Input, Button, Toast, NavBar } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { PASSWORD_REGEX, PASSWORD_HINT } from '@/lib/captcha';

export default function MerchantMobileChangePasswordPage() {
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
      await api.put('/api/merchant/password', {
        old_password: values.old_password,
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
      <NavBar onBack={() => router.back()}>修改密码</NavBar>
      <div style={{ padding: 16 }}>
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
              name="old_password"
              label="原密码"
              rules={[{ required: true, message: '请输入原密码' }]}
            >
              <Input placeholder="请输入原密码" type="password" clearable />
            </Form.Item>
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
            提交
          </Button>
          <div style={{ color: '#999', fontSize: 12, marginTop: 12 }}>
            修改成功后将自动退出，请使用新密码重新登录。
          </div>
        </div>
      </div>
    </div>
  );
}
