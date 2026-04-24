'use client';

import React, { useState } from 'react';
import { Card, Form, Input, Button, Tabs, message, Typography } from 'antd';
import { UserOutlined, LockOutlined, MessageOutlined } from '@ant-design/icons';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { saveLogin } from '../lib';

const { Title, Text } = Typography;

export default function MerchantLoginPage() {
  const [mode, setMode] = useState<'password' | 'sms'>('password');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const submit = async (values: { phone: string; password?: string; sms_code?: string }) => {
    setLoading(true);
    try {
      const res: any = await api.post('/api/merchant/auth/login', {
        phone: values.phone,
        password: mode === 'password' ? values.password : undefined,
        sms_code: mode === 'sms' ? values.sms_code : undefined,
      });
      saveLogin(res.access_token, {
        merchant_id: res.user_id,
        merchant_name: res.nickname || '商家',
        role: res.merchant_role,
        store_ids: res.stores.map((s: any) => s.id),
        stores: res.stores.map((s: any) => ({ id: s.id, name: s.store_name })),
      });
      message.success('登录成功');
      if (res.stores.length <= 1) {
        router.push('/merchant/dashboard');
      } else {
        router.push('/merchant/select-store');
      }
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '登录失败';
      message.error(detail);
    } finally {
      setLoading(false);
    }
  };

  const sendSms = async () => {
    message.info('测试环境：万能验证码 8888');
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
        <Tabs
          activeKey={mode}
          onChange={k => setMode(k as any)}
          centered
          items={[
            { key: 'password', label: '密码登录' },
            { key: 'sms', label: '验证码登录' },
          ]}
        />
        <Form layout="vertical" onFinish={submit} autoComplete="off">
          <Form.Item
            name="phone"
            label="手机号"
            rules={[{ required: true, message: '请输入手机号' }, { pattern: /^1\d{10}$/, message: '手机号格式错误' }]}
          >
            <Input prefix={<UserOutlined />} size="large" placeholder="请输入手机号" />
          </Form.Item>
          {mode === 'password' ? (
            <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
              <Input.Password prefix={<LockOutlined />} size="large" placeholder="请输入密码" />
            </Form.Item>
          ) : (
            <Form.Item name="sms_code" label="验证码" rules={[{ required: true, message: '请输入验证码' }]}>
              <Input
                prefix={<MessageOutlined />}
                size="large"
                placeholder="测试环境：8888"
                suffix={
                  <Button type="link" size="small" onClick={sendSms}>
                    获取验证码
                  </Button>
                }
              />
            </Form.Item>
          )}
          <Form.Item>
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
