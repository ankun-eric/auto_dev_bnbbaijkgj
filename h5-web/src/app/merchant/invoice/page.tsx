'use client';

import React, { useEffect } from 'react';
import { Card, Form, Input, Button, Typography, message } from 'antd';
import api from '@/lib/api';

const { Title } = Typography;

export default function InvoicePage() {
  const [form] = Form.useForm();

  useEffect(() => {
    api.get('/api/merchant/v1/invoice-profile').then((d: any) => { if (d) form.setFieldsValue(d); }).catch(() => {});
  }, [form]);

  const onSubmit = async (values: any) => {
    try {
      await api.put('/api/merchant/v1/invoice-profile', values);
      message.success('已保存');
    } catch (e: any) { message.error(e?.response?.data?.detail || '保存失败'); }
  };

  return (
    <div>
      <Title level={4}>发票信息</Title>
      <Card>
        <Form form={form} layout="vertical" onFinish={onSubmit} style={{ maxWidth: 640 }}>
          <Form.Item name="title" label="发票抬头" rules={[{ required: true }]}>
            <Input placeholder="公司全称" />
          </Form.Item>
          <Form.Item name="tax_no" label="税号" rules={[{ required: true }]}>
            <Input placeholder="统一社会信用代码" />
          </Form.Item>
          <Form.Item name="bank_name" label="开户行"><Input /></Form.Item>
          <Form.Item name="bank_account" label="开户账号"><Input /></Form.Item>
          <Form.Item name="register_address" label="注册地址"><Input /></Form.Item>
          <Form.Item name="register_phone" label="注册电话"><Input /></Form.Item>
          <Form.Item name="receive_address" label="收票地址"><Input /></Form.Item>
          <Form.Item name="receive_email" label="收票邮箱"><Input /></Form.Item>
          <Button type="primary" htmlType="submit">保存</Button>
        </Form>
      </Card>
    </div>
  );
}
