'use client';

import React, { useState } from 'react';
import { Button, Card, DatePicker, Form, Input, InputNumber, Modal, Space, Typography, message } from 'antd';
import { get, post } from '@/lib/api';
import dayjs from 'dayjs';

const { Title, Paragraph } = Typography;

export default function AdminSettlementsPage() {
  const [genOpen, setGenOpen] = useState(false);
  const [proofOpen, setProofOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [genForm] = Form.useForm();
  const [proofForm] = Form.useForm();

  const doGenerate = async (values: any) => {
    setLoading(true);
    try {
      const body: any = {};
      if (values.range) {
        body.period_start = values.range[0].format('YYYY-MM-DD');
        body.period_end = values.range[1].format('YYYY-MM-DD');
      }
      if (values.merchant_profile_id) body.merchant_profile_id = values.merchant_profile_id;
      const res: any = await post('/api/admin/settlements/generate-monthly', body);
      message.success(`已生成 ${res?.generated_count ?? 0} 张对账单`);
      setGenOpen(false);
      genForm.resetFields();
    } catch (e: any) { message.error(e?.response?.data?.detail || '生成失败'); } finally { setLoading(false); }
  };

  const doUploadProof = async (values: any) => {
    setLoading(true);
    try {
      await post(`/api/admin/settlements/${values.settlement_id}/payment-proof`, {
        file_url: values.file_url,
        file_name: values.file_name,
        amount: values.amount,
        paid_at: values.paid_at ? values.paid_at.toISOString() : undefined,
      });
      message.success('凭证已上传，对账单标记为已结清');
      setProofOpen(false);
      proofForm.resetFields();
    } catch (e: any) { message.error(e?.response?.data?.detail || '上传失败'); } finally { setLoading(false); }
  };

  return (
    <div>
      <Title level={4}>对账单管理</Title>
      <Paragraph type="secondary">
        系统每月 1 号自动出上月对账单。管理员可手动补出对账单、查看状态、上传打款凭证。
      </Paragraph>
      <Space size="large">
        <Card style={{ width: 320 }}>
          <Title level={5}>生成月度对账单</Title>
          <Paragraph type="secondary" style={{ fontSize: 12 }}>
            默认针对上一自然月所有已启用的机构生成对账单。
          </Paragraph>
          <Button type="primary" onClick={() => setGenOpen(true)}>生成对账单</Button>
        </Card>
        <Card style={{ width: 320 }}>
          <Title level={5}>上传打款凭证</Title>
          <Paragraph type="secondary" style={{ fontSize: 12 }}>
            线下对公转账完成后，按对账单ID上传凭证。
          </Paragraph>
          <Button onClick={() => setProofOpen(true)}>上传凭证</Button>
        </Card>
      </Space>

      <Modal title="生成月度对账单" open={genOpen} onCancel={() => setGenOpen(false)} onOk={() => genForm.submit()} confirmLoading={loading}>
        <Form form={genForm} layout="vertical" onFinish={doGenerate}>
          <Form.Item name="range" label="账单周期（可选，默认上月）">
            <DatePicker.RangePicker />
          </Form.Item>
          <Form.Item name="merchant_profile_id" label="指定机构ID（可选，默认全部）">
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="上传打款凭证" open={proofOpen} onCancel={() => setProofOpen(false)} onOk={() => proofForm.submit()} confirmLoading={loading}>
        <Form form={proofForm} layout="vertical" onFinish={doUploadProof}>
          <Form.Item name="settlement_id" label="对账单ID" rules={[{ required: true }]}>
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="file_url" label="凭证文件URL" rules={[{ required: true }]}>
            <Input placeholder="OSS/COS URL" />
          </Form.Item>
          <Form.Item name="file_name" label="文件名">
            <Input />
          </Form.Item>
          <Form.Item name="amount" label="打款金额" rules={[{ required: true }]}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="paid_at" label="打款时间" initialValue={dayjs()}>
            <DatePicker showTime style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
