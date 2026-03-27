'use client';

import React, { useState } from 'react';
import { Form, Input, Button, Card, message, Typography } from 'antd';
import { UserOutlined, LockOutlined, MedicineBoxOutlined } from '@ant-design/icons';
import { post } from '@/lib/api';
import { useRouter } from 'next/navigation';

const { Title, Text } = Typography;

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const onFinish = async (values: { phone: string; password: string }) => {
    setLoading(true);
    try {
      const res = await post('/api/admin/login', values);
      if (res.code === 0 || res.token) {
        localStorage.setItem('admin_token', res.token || res.data?.token);
        localStorage.setItem(
          'admin_user',
          JSON.stringify(res.user || res.data?.user || { name: '管理员' })
        );
        message.success('登录成功');
        router.push('/dashboard');
      } else {
        message.error(res.message || '登录失败');
      }
    } catch (err: any) {
      message.error(err?.response?.data?.message || '登录失败，请检查账号密码');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-bg" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <Card
        style={{
          width: 420,
          borderRadius: 16,
          boxShadow: '0 8px 32px rgba(82,196,26,0.12)',
          border: 'none',
        }}
        bodyStyle={{ padding: '48px 40px 36px' }}
      >
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 16,
            }}
          >
            <MedicineBoxOutlined style={{ fontSize: 32, color: '#fff' }} />
          </div>
          <Title level={3} style={{ marginBottom: 4, color: '#333' }}>
            宾尼小康
          </Title>
          <Text type="secondary">AI健康管家 · 管理后台</Text>
        </div>

        <Form name="login" onFinish={onFinish} size="large" autoComplete="off">
          <Form.Item name="phone" rules={[{ required: true, message: '请输入手机号' }, { pattern: /^1\d{10}$/, message: '请输入正确的手机号' }]}>
            <Input prefix={<UserOutlined />} placeholder="请输入手机号" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" loading={loading} block style={{ height: 44, borderRadius: 8, fontSize: 16 }}>
              登 录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
