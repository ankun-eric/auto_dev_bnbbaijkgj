'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Form, Button, Switch, Select, InputNumber, Typography, Spin, message,
} from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import { get, put } from '@/lib/api';

const { Title } = Typography;

interface HomeConfig {
  [key: string]: any;
}

// [PRD-LEGACY-HOME-CLEANUP-V1.1 2026-05-19]
// 原「首页基础设置」改名「字体配置」并瘦身：
// - 仅保留 5 个 font_* 字段（font_switch_enabled / font_default_level /
//   font_standard_size / font_large_size / font_xlarge_size）
// - 移除 search_visible / search_placeholder / grid_columns 等旧 /home 专用字段
export default function HomeSettingsPage() {
  const [loading, setLoading] = useState(false);
  const [savingFont, setSavingFont] = useState(false);

  const [fontForm] = Form.useForm();

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<HomeConfig>('/api/admin/home-config');
      fontForm.setFieldsValue({
        font_switch_enabled: res.font_switch_enabled ?? false,
        font_default_level: res.font_default_level ?? 'standard',
        font_standard_size: res.font_standard_size ?? 14,
        font_large_size: res.font_large_size ?? 18,
        font_xlarge_size: res.font_xlarge_size ?? 22,
      });
    } catch {
      message.error('获取字体配置失败');
    } finally {
      setLoading(false);
    }
  }, [fontForm]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleSaveFont = async () => {
    try {
      const values = await fontForm.validateFields();
      setSavingFont(true);
      // 仅提交 font_* 5 个字段，后端其它 KV 保持不变
      await put('/api/admin/home-config', {
        font_switch_enabled: values.font_switch_enabled,
        font_default_level: values.font_default_level,
        font_standard_size: values.font_standard_size,
        font_large_size: values.font_large_size,
        font_xlarge_size: values.font_xlarge_size,
      });
      message.success('字体配置保存成功');
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSavingFont(false);
    }
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>字体配置</Title>
      <Spin spinning={loading}>
        <Card title="字体切换配置" style={{ borderRadius: 12, maxWidth: 640 }}>
          <Form form={fontForm} layout="vertical">
            <Form.Item label="字体切换功能" name="font_switch_enabled" valuePropName="checked">
              <Switch checkedChildren="开启" unCheckedChildren="关闭" />
            </Form.Item>
            <Form.Item label="新用户默认档位" name="font_default_level" rules={[{ required: true, message: '请选择默认档位' }]}>
              <Select
                options={[
                  { label: '标准', value: 'standard' },
                  { label: '大', value: 'large' },
                  { label: '超大', value: 'xlarge' },
                ]}
              />
            </Form.Item>
            <Form.Item label="标准档基础字号" name="font_standard_size" rules={[{ required: true, message: '请输入字号' }]}>
              <InputNumber min={12} max={16} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="大档基础字号" name="font_large_size" rules={[{ required: true, message: '请输入字号' }]}>
              <InputNumber min={16} max={22} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="超大档基础字号" name="font_xlarge_size" rules={[{ required: true, message: '请输入字号' }]}>
              <InputNumber min={20} max={28} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveFont} loading={savingFont}>
                保存
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </Spin>
    </div>
  );
}
