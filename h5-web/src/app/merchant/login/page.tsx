'use client';

// [PRD V1.0 §M7] 商家 PC 登录页：手机号 + 密码 + 图形验证码
// 已删除「短信验证码」Tab 和「忘记密码」入口。
// 登录成功若返回 must_change_password=true，跳转 /merchant/m/profile/force-change-password。

import React, { useEffect, useState } from 'react';
import { Card, Form, Input, Button, message, Typography, Row, Col } from 'antd';
import { UserOutlined, LockOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { fetchCaptchaImage } from '@/lib/captcha';
import { saveLogin } from '../lib';

const { Title, Text } = Typography;

export default function MerchantLoginPage() {
  const [loading, setLoading] = useState(false);
  const [captchaId, setCaptchaId] = useState('');
  const [captchaImg, setCaptchaImg] = useState('');
  const [captchaLoading, setCaptchaLoading] = useState(false);
  const router = useRouter();

  const refreshCaptcha = async () => {
    setCaptchaLoading(true);
    try {
      const data = await fetchCaptchaImage();
      setCaptchaId(data.captcha_id);
      setCaptchaImg(data.image_base64);
    } catch {
      message.error('图形验证码加载失败，请稍后重试');
    } finally {
      setCaptchaLoading(false);
    }
  };

  useEffect(() => {
    refreshCaptcha();
  }, []);

  const submit = async (values: { phone: string; password: string; captcha_code: string }) => {
    setLoading(true);
    try {
      const res: any = await api.post('/api/merchant/auth/login', {
        phone: values.phone,
        password: values.password,
        captcha_id: captchaId,
        captcha_code: values.captcha_code,
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
      refreshCaptcha();
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
          <Form.Item label="图形验证码" required>
            <Row gutter={8} align="middle">
              <Col span={14}>
                <Form.Item
                  name="captcha_code"
                  noStyle
                  rules={[{ required: true, message: '请输入图形验证码' }]}
                >
                  <Input
                    prefix={<SafetyCertificateOutlined />}
                    size="large"
                    placeholder="请输入验证码"
                    maxLength={6}
                  />
                </Form.Item>
              </Col>
              <Col span={10}>
                <div
                  onClick={refreshCaptcha}
                  title="点击刷新"
                  style={{
                    height: 40,
                    borderRadius: 6,
                    border: '1px solid #d9d9d9',
                    overflow: 'hidden',
                    cursor: 'pointer',
                    background: '#fafafa',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    opacity: captchaLoading ? 0.5 : 1,
                  }}
                >
                  {captchaImg ? (
                    <img
                      src={captchaImg}
                      alt="图形验证码"
                      style={{ height: '100%', width: '100%', objectFit: 'cover' }}
                    />
                  ) : (
                    <Text type="secondary" style={{ fontSize: 12 }}>加载中...</Text>
                  )}
                </div>
              </Col>
            </Row>
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
