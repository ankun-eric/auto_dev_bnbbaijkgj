'use client';

// [PRD V1.0 §M7 + Bug 修复 V1.0 / 2026-04-25]
// 商家 PC 登录页：手机号 + 密码 + 滑块拼图验证码
// 旧字符验证码 captcha_id/captcha_code 已替换为 captcha_token（滑块通过后下发）。
// 登录成功若返回 must_change_password=true，跳转 /merchant/m/profile/force-change-password。

import React, { useState } from 'react';
import { Card, Form, Input, Button, message, Typography } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import SliderCaptcha from '@/components/SliderCaptcha';
import { saveLogin } from '../lib';

const { Title, Text } = Typography;

export default function MerchantLoginPage() {
  const [loading, setLoading] = useState(false);
  const [captchaToken, setCaptchaToken] = useState<string>('');
  const [captchaResetKey, setCaptchaResetKey] = useState<number>(0);
  const router = useRouter();

  const submit = async (values: { phone: string; password: string }) => {
    if (!captchaToken) {
      message.warning('请先完成滑块验证');
      return;
    }
    setLoading(true);
    try {
      const res: any = await api.post('/api/merchant/auth/login', {
        phone: values.phone,
        password: values.password,
        captcha_token: captchaToken,
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
      const detail = e?.response?.data?.detail || e?.message || '登录失败';
      message.error(detail);
      // 登录失败 token 已被服务端销毁，前端清空并刷新滑块
      setCaptchaToken('');
      setCaptchaResetKey((k) => k + 1);
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
        <Form layout="vertical" onFinish={submit} autoComplete="off">
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
          <Form.Item label="滑块验证" required>
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <SliderCaptcha
                key={captchaResetKey}
                apiClient={api as any}
                mode="pc"
                onSuccess={(tok) => setCaptchaToken(tok)}
                onReset={() => setCaptchaToken('')}
              />
            </div>
          </Form.Item>
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
