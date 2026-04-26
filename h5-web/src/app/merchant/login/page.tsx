'use client';

import React, { useState } from 'react';
import { Card, Form, Input, Button, message, Typography, Alert } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { saveLogin } from '../lib';

const { Title, Text } = Typography;

interface LoginFormValues {
  phone: string;
  password: string;
}

export default function MerchantLoginPage() {
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string>('');
  const router = useRouter();
  const [form] = Form.useForm<LoginFormValues>();

  const submit = async (values: LoginFormValues) => {
    setErrorMsg('');
    setLoading(true);
    try {
      const res: any = await api.post('/api/merchant/auth/login', {
        phone: values.phone,
        password: values.password,
      });
      saveLogin(res.access_token, {
        merchant_id: res.user_id,
        merchant_name: res.nickname || '商家',
        role: res.merchant_role,
        store_ids: (res.stores || []).map((s: any) => s.id),
        stores: (res.stores || []).map((s: any) => ({ id: s.id, name: s.store_name })),
      });
      message.success('登录成功');
      if (res.must_change_password) {
        router.push('/merchant/m/profile/force-change-password');
        return;
      }
      if ((res.stores || []).length <= 1) {
        router.push('/merchant/dashboard');
      } else {
        router.push('/merchant/select-store');
      }
    } catch (e: any) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;
      const remainingAttempts =
        typeof detail === 'object' ? detail?.remaining_attempts : undefined;

      if (status === 429) {
        setErrorMsg('账号已被锁定，请 10 分钟后再试');
      } else if (remainingAttempts !== undefined && remainingAttempts <= 0) {
        setErrorMsg('账号已被锁定，请 10 分钟后再试');
      } else if (remainingAttempts !== undefined && remainingAttempts > 0) {
        setErrorMsg(`密码错误，还剩 ${remainingAttempts} 次尝试机会`);
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
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #e6fffb 0%, #f6ffed 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Card style={{ width: 420, boxShadow: '0 6px 24px rgba(0,0,0,0.08)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Title level={3} style={{ color: '#52c41a', marginBottom: 4 }}>
            商家/机构工作台
          </Title>
          <Text type="secondary">宾尼小康 · 合作机构/商家登录</Text>
        </div>
        <Form form={form} layout="vertical" onFinish={submit} autoComplete="off">
          <Form.Item
            name="phone"
            label="手机号"
            rules={[
              { required: true, message: '请输入手机号' },
              { pattern: /^1\d{10}$/, message: '手机号格式错误' },
            ]}
          >
            <Input prefix={<UserOutlined />} size="large" placeholder="请输入手机号" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} size="large" placeholder="请输入密码" />
          </Form.Item>
          {errorMsg && (
            <Form.Item style={{ marginBottom: 8 }}>
              <Alert message={errorMsg} type="error" showIcon />
            </Form.Item>
          )}
          <Form.Item style={{ marginTop: 12 }}>
            <Button block size="large" type="primary" htmlType="submit" loading={loading}>
              登录
            </Button>
          </Form.Item>
        </Form>
        <div style={{ textAlign: 'center', color: '#999', fontSize: 12 }}>
          非商家账号请前往 C 端小程序使用普通功能。
        </div>
      </Card>
    </div>
  );
}
