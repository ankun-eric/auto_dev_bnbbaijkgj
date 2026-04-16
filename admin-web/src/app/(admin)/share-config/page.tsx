'use client';

import React, { useEffect, useState } from 'react';
import { Form, Input, Button, Card, Space, message, Typography, Upload, Radio, ColorPicker, Divider } from 'antd';
import { SaveOutlined, ShareAltOutlined, UploadOutlined, PlusOutlined } from '@ant-design/icons';
import { get, put, upload as apiUpload } from '@/lib/api';
import type { UploadFile } from 'antd';
import type { Color } from 'antd/es/color-picker';

const { Title, Text } = Typography;

type PosterTemplate = 'simple_white' | 'gradient_green' | 'dark_business';

interface ShareConfig {
  logo_url: string;
  product_name: string;
  slogan: string;
  qr_code_url: string;
  background_color: string;
  template: PosterTemplate;
}

const templateLabels: Record<PosterTemplate, string> = {
  simple_white: '简约白',
  gradient_green: '渐变绿',
  dark_business: '深色商务',
};

const templateStyles: Record<PosterTemplate, React.CSSProperties> = {
  simple_white: { background: '#ffffff', color: '#333333' },
  gradient_green: { background: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)', color: '#ffffff' },
  dark_business: { background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)', color: '#ffffff' },
};

export default function ShareConfigPage() {
  const [form] = Form.useForm<ShareConfig>();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [logoUrl, setLogoUrl] = useState<string>('');
  const [qrUrl, setQrUrl] = useState<string>('');
  const [logoUploading, setLogoUploading] = useState(false);
  const [qrUploading, setQrUploading] = useState(false);

  const productName = Form.useWatch('product_name', form);
  const slogan = Form.useWatch('slogan', form);
  const bgColor = Form.useWatch('background_color', form);
  const template = Form.useWatch('template', form);

  useEffect(() => {
    const loadConfig = async () => {
      setLoading(true);
      try {
        const res = await get<{ code: number; data: ShareConfig }>('/api/admin/settings/share-config');
        if (res?.data) {
          form.setFieldsValue(res.data);
          if (res.data.logo_url) setLogoUrl(res.data.logo_url);
          if (res.data.qr_code_url) setQrUrl(res.data.qr_code_url);
        }
      } catch {
        // use defaults
      } finally {
        setLoading(false);
      }
    };
    loadConfig();
  }, [form]);

  const handleUploadLogo = async (file: File) => {
    setLogoUploading(true);
    try {
      const res = await apiUpload<{ code: number; data: { url: string } }>('/api/admin/settings/share-config/upload', file, 'file');
      if (res?.data?.url) {
        setLogoUrl(res.data.url);
        form.setFieldsValue({ logo_url: res.data.url });
        message.success('Logo上传成功');
      }
    } catch {
      message.error('Logo上传失败');
    } finally {
      setLogoUploading(false);
    }
  };

  const handleUploadQr = async (file: File) => {
    setQrUploading(true);
    try {
      const res = await apiUpload<{ code: number; data: { url: string } }>('/api/admin/settings/share-config/upload', file, 'file');
      if (res?.data?.url) {
        setQrUrl(res.data.url);
        form.setFieldsValue({ qr_code_url: res.data.url });
        message.success('二维码上传成功');
      }
    } catch {
      message.error('二维码上传失败');
    } finally {
      setQrUploading(false);
    }
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = {
        ...values,
        background_color: typeof values.background_color === 'string' ? values.background_color : (values.background_color as unknown as Color)?.toHexString?.() || '#ffffff',
        logo_url: logoUrl,
        qr_code_url: qrUrl,
      };
      await put('/api/admin/settings/share-config', payload);
      message.success('保存成功');
    } catch (e: unknown) {
      if ((e as { errorFields?: unknown })?.errorFields) return;
      message.error('保存失败，请稍后重试');
    } finally {
      setSaving(false);
    }
  };

  const currentTemplate = template || 'simple_white';
  const currentBgColor = typeof bgColor === 'string'
    ? bgColor
    : (bgColor as unknown as Color)?.toHexString?.() || '#ffffff';

  const previewBg = currentBgColor !== '#ffffff'
    ? currentBgColor
    : templateStyles[currentTemplate]?.background || '#ffffff';
  const previewColor = currentTemplate === 'simple_white' && currentBgColor === '#ffffff'
    ? '#333333'
    : templateStyles[currentTemplate]?.color || '#333333';

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>
        <Space>
          <ShareAltOutlined />
          分享海报配置
        </Space>
      </Title>

      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <Card style={{ borderRadius: 12, flex: 1, minWidth: 420 }} loading={loading}>
          <Form
            form={form}
            layout="vertical"
            initialValues={{
              logo_url: '',
              product_name: '宾尼小康',
              slogan: 'AI健康管家',
              qr_code_url: '',
              background_color: '#ffffff',
              template: 'simple_white' as PosterTemplate,
            }}
          >
            <Title level={5}>品牌信息</Title>

            <Form.Item label="品牌Logo" name="logo_url">
              <Space align="start" size={16}>
                {logoUrl && (
                  <img
                    src={logoUrl}
                    alt="品牌Logo"
                    style={{ width: 80, height: 80, objectFit: 'contain', borderRadius: 8, border: '1px solid #f0f0f0' }}
                  />
                )}
                <Upload
                  accept=".png,.jpg,.jpeg"
                  showUploadList={false}
                  beforeUpload={(file) => {
                    const isValid = file.type === 'image/png' || file.type === 'image/jpeg';
                    if (!isValid) { message.error('仅支持 PNG/JPG 格式'); return false; }
                    if (file.size / 1024 / 1024 > 2) { message.error('图片不超过 2MB'); return false; }
                    handleUploadLogo(file);
                    return false;
                  }}
                >
                  <Button icon={<UploadOutlined />} loading={logoUploading}>
                    {logoUrl ? '更换Logo' : '上传Logo'}
                  </Button>
                </Upload>
              </Space>
            </Form.Item>

            <Form.Item label="产品名称" name="product_name" rules={[{ required: true, message: '请输入产品名称' }]}>
              <Input placeholder="请输入产品名称" />
            </Form.Item>

            <Form.Item label="Slogan宣传语" name="slogan">
              <Input placeholder="请输入宣传语" />
            </Form.Item>

            <Form.Item label="小程序码/二维码" name="qr_code_url">
              <Space align="start" size={16}>
                {qrUrl && (
                  <img
                    src={qrUrl}
                    alt="二维码"
                    style={{ width: 80, height: 80, objectFit: 'contain', borderRadius: 8, border: '1px solid #f0f0f0' }}
                  />
                )}
                <Upload
                  accept=".png,.jpg,.jpeg"
                  showUploadList={false}
                  beforeUpload={(file) => {
                    const isValid = file.type === 'image/png' || file.type === 'image/jpeg';
                    if (!isValid) { message.error('仅支持 PNG/JPG 格式'); return false; }
                    if (file.size / 1024 / 1024 > 2) { message.error('图片不超过 2MB'); return false; }
                    handleUploadQr(file);
                    return false;
                  }}
                >
                  <Button icon={<UploadOutlined />} loading={qrUploading}>
                    {qrUrl ? '更换二维码' : '上传二维码'}
                  </Button>
                </Upload>
              </Space>
            </Form.Item>

            <Divider />
            <Title level={5}>海报样式</Title>

            <Form.Item label="海报背景色" name="background_color">
              <ColorPicker showText />
            </Form.Item>

            <Form.Item label="海报模板" name="template">
              <Radio.Group>
                <Radio value="simple_white">简约白</Radio>
                <Radio value="gradient_green">渐变绿</Radio>
                <Radio value="dark_business">深色商务</Radio>
              </Radio.Group>
            </Form.Item>

            <Divider />
            <Form.Item>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
                保存配置
              </Button>
            </Form.Item>
          </Form>
        </Card>

        {/* 海报预览 */}
        <Card
          title="海报预览"
          style={{ borderRadius: 12, width: 320, flexShrink: 0 }}
          styles={{ body: { padding: 0 } }}
        >
          <div
            style={{
              width: '100%',
              minHeight: 460,
              background: previewBg,
              color: previewColor,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              padding: '32px 24px',
              borderRadius: '0 0 12px 12px',
              transition: 'all 0.3s ease',
            }}
          >
            {logoUrl ? (
              <img
                src={logoUrl}
                alt="Logo"
                style={{ width: 64, height: 64, borderRadius: 12, objectFit: 'contain', marginBottom: 16 }}
              />
            ) : (
              <div
                style={{
                  width: 64,
                  height: 64,
                  borderRadius: 12,
                  background: 'rgba(128,128,128,0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: 16,
                  fontSize: 12,
                  color: previewColor,
                  opacity: 0.5,
                }}
              >
                LOGO
              </div>
            )}

            <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 8, textAlign: 'center' }}>
              {productName || '产品名称'}
            </div>
            <div style={{ fontSize: 13, opacity: 0.75, marginBottom: 32, textAlign: 'center' }}>
              {slogan || '宣传语'}
            </div>

            <div style={{ flex: 1 }} />

            {qrUrl ? (
              <img
                src={qrUrl}
                alt="二维码"
                style={{ width: 100, height: 100, borderRadius: 8, objectFit: 'contain', marginBottom: 12 }}
              />
            ) : (
              <div
                style={{
                  width: 100,
                  height: 100,
                  borderRadius: 8,
                  background: 'rgba(128,128,128,0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: 12,
                  fontSize: 12,
                  color: previewColor,
                  opacity: 0.5,
                }}
              >
                二维码
              </div>
            )}
            <div style={{ fontSize: 12, opacity: 0.6 }}>长按识别，立即体验</div>
          </div>
        </Card>
      </div>
    </div>
  );
}
