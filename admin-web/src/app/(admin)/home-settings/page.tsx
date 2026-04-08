'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Form, Input, Button, Switch, Select, InputNumber, Typography, Spin, message,
} from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import { get, put } from '@/lib/api';

const { Title } = Typography;

interface HomeConfig {
  [key: string]: any;
}

export default function HomeSettingsPage() {
  const [loading, setLoading] = useState(false);
  const [savingSearch, setSavingSearch] = useState(false);
  const [savingGrid, setSavingGrid] = useState(false);
  const [savingFont, setSavingFont] = useState(false);

  const [searchForm] = Form.useForm();
  const [gridForm] = Form.useForm();
  const [fontForm] = Form.useForm();

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<HomeConfig>('/api/admin/home-config');
      searchForm.setFieldsValue({
        search_visible: res.search_visible ?? true,
        search_placeholder: res.search_placeholder ?? '',
      });
      gridForm.setFieldsValue({
        grid_columns: res.grid_columns ?? 3,
      });
      fontForm.setFieldsValue({
        font_switch_enabled: res.font_switch_enabled ?? false,
        font_default_level: res.font_default_level ?? 'standard',
        font_standard_size: res.font_standard_size ?? 14,
        font_large_size: res.font_large_size ?? 18,
        font_xlarge_size: res.font_xlarge_size ?? 22,
      });
    } catch {
      message.error('获取首页配置失败');
    } finally {
      setLoading(false);
    }
  }, [searchForm, gridForm, fontForm]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleSaveSearch = async () => {
    try {
      const values = await searchForm.validateFields();
      setSavingSearch(true);
      await put('/api/admin/home-config', values);
      message.success('搜索框配置保存成功');
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSavingSearch(false);
    }
  };

  const handleSaveGrid = async () => {
    try {
      const values = await gridForm.validateFields();
      setSavingGrid(true);
      await put('/api/admin/home-config', values);
      message.success('宫格配置保存成功');
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSavingGrid(false);
    }
  };

  const handleSaveFont = async () => {
    try {
      const values = await fontForm.validateFields();
      setSavingFont(true);
      await put('/api/admin/home-config', values);
      message.success('字体切换配置保存成功');
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSavingFont(false);
    }
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>首页基础设置</Title>
      <Spin spinning={loading}>
        <Card title="搜索框配置" style={{ borderRadius: 12, maxWidth: 640, marginBottom: 24 }}>
          <Form form={searchForm} layout="vertical">
            <Form.Item label="搜索框显示" name="search_visible" valuePropName="checked">
              <Switch checkedChildren="显示" unCheckedChildren="隐藏" />
            </Form.Item>
            <Form.Item label="提示文字" name="search_placeholder">
              <Input placeholder="请输入搜索框提示文字" maxLength={50} />
            </Form.Item>
            <Form.Item>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveSearch} loading={savingSearch}>
                保存
              </Button>
            </Form.Item>
          </Form>
        </Card>

        <Card title="宫格配置" style={{ borderRadius: 12, maxWidth: 640, marginBottom: 24 }}>
          <Form form={gridForm} layout="vertical">
            <Form.Item label="菜单列数" name="grid_columns" rules={[{ required: true, message: '请选择菜单列数' }]}>
              <Select
                options={[
                  { label: '3列', value: 3 },
                  { label: '4列', value: 4 },
                  { label: '5列', value: 5 },
                ]}
              />
            </Form.Item>
            <Form.Item>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveGrid} loading={savingGrid}>
                保存
              </Button>
            </Form.Item>
          </Form>
        </Card>

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
