'use client';

import React, { useEffect, useState } from 'react';
import { Card, Form, Switch, Button, Typography, message, Spin } from 'antd';
import { get, put } from '@/lib/api';

const { Title } = Typography;

interface TcmConfig {
  tongue_diagnosis_enabled: boolean;
  face_diagnosis_enabled: boolean;
  constitution_test_enabled: boolean;
}

export default function TcmConfigPage() {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const res = await get<TcmConfig>('/api/admin/tcm/config');
      if (res) {
        form.setFieldsValue({
          tongue_diagnosis_enabled: res.tongue_diagnosis_enabled ?? false,
          face_diagnosis_enabled: res.face_diagnosis_enabled ?? false,
          constitution_test_enabled: res.constitution_test_enabled ?? true,
        });
      }
    } catch {
      message.error('获取中医养生配置失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await put('/api/admin/tcm/config', {
        tongue_diagnosis_enabled: values.tongue_diagnosis_enabled ?? false,
        face_diagnosis_enabled: values.face_diagnosis_enabled ?? false,
        constitution_test_enabled: values.constitution_test_enabled ?? true,
      });
      message.success('保存成功');
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>中医养生配置</Title>
      <Spin spinning={loading}>
        <Card style={{ maxWidth: 600 }}>
          <Form
            form={form}
            layout="horizontal"
            labelCol={{ span: 8 }}
            wrapperCol={{ span: 16 }}
            initialValues={{
              tongue_diagnosis_enabled: false,
              face_diagnosis_enabled: false,
              constitution_test_enabled: true,
            }}
          >
            <Form.Item
              label="舌诊-是否显示"
              name="tongue_diagnosis_enabled"
              valuePropName="checked"
            >
              <Switch checkedChildren="开启" unCheckedChildren="关闭" />
            </Form.Item>
            <Form.Item
              label="面诊-是否显示"
              name="face_diagnosis_enabled"
              valuePropName="checked"
            >
              <Switch checkedChildren="开启" unCheckedChildren="关闭" />
            </Form.Item>
            <Form.Item
              label="体质测评-是否显示"
              name="constitution_test_enabled"
              valuePropName="checked"
            >
              <Switch checkedChildren="开启" unCheckedChildren="关闭" />
            </Form.Item>
            <Form.Item wrapperCol={{ offset: 8, span: 16 }}>
              <Button type="primary" loading={saving} onClick={handleSave}>
                保存配置
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </Spin>
    </div>
  );
}
