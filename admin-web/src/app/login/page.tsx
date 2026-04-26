'use client';

import React, { useState } from 'react';
import { Form, Input, Button, Card, message, Typography, Alert } from 'antd';
import { UserOutlined, LockOutlined, MedicineBoxOutlined } from '@ant-design/icons';
import { post } from '@/lib/api';
import { useRouter } from 'next/navigation';

const { Title, Text } = Typography;

interface LoginFormValues {
  phone: string;
  password: string;
}

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string>('');
  const router = useRouter();
  const [form] = Form.useForm<LoginFormValues>();

  const onFinish = async (values: LoginFormValues) => {
    setLoading(true);
    setErrorMsg('');
    try {
      const res = await post('/api/admin/login', {
        phone: values.phone,
        password: values.password,
      });
      if (res.token || res.access_token) {
        localStorage.setItem('admin_token', res.token || res.access_token);
        localStorage.setItem(
          'admin_user',
          JSON.stringify(res.user || { name: '管理员' })
        );
        setErrorMsg('');
        message.success('登录成功');
        if (res.must_change_password || res.user?.must_change_password) {
          router.push('/profile/change-password?force=1');
        } else {
          router.push('/dashboard');
        }
      } else {
        message.error(res.message || res.msg || '登录失败');
      }
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;

      if (status === 429) {
        setErrorMsg('账号已被锁定，请 10 分钟后再试');
      } else if (status === 400 && detail && typeof detail === 'object' && detail.remaining_attempts != null) {
        if (detail.remaining_attempts === 0) {
          setErrorMsg('账号已被锁定，请 10 分钟后再试');
        } else {
          setErrorMsg(`密码错误，还剩 ${detail.remaining_attempts} 次尝试机会`);
        }
      } else {
        let msgText = '账号或密码错误';
        if (detail && typeof detail === 'object') {
          msgText = detail.msg || msgText;
        } else if (typeof detail === 'string') {
          msgText = detail;
        }
        setErrorMsg(msgText);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-bg" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <Card
        style={{
          width: 460,
          borderRadius: 16,
          boxShadow: '0 8px 32px rgba(82,196,26,0.12)',
          border: 'none',
        }}
        bodyStyle={{ padding: '40px 36px 32px' }}
      >
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
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
          <Text type="secondary">AI健康管家 · 平台管理后台</Text>
        </div>

        <Form form={form} name="login" onFinish={onFinish} size="large" autoComplete="off">
          <Form.Item
            name="phone"
            rules={[
              { required: true, message: '请输入手机号' },
              { pattern: /^1\d{10}$/, message: '请输入正确的手机号' },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="请输入手机号" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" />
          </Form.Item>
          {errorMsg && (
            <Form.Item style={{ marginBottom: 12 }}>
              <Alert message={errorMsg} type="error" showIcon />
            </Form.Item>
          )}
          <Form.Item style={{ marginBottom: 0 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{ height: 44, borderRadius: 8, fontSize: 16 }}
            >
              登 录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
