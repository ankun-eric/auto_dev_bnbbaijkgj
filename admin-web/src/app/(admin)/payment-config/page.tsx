'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  Tabs, Card, Tag, Button, Switch, Space, Drawer, Form, Input, Select,
  Typography, Descriptions, message, Spin, Alert, Upload, Popconfirm,
  InputNumber,
} from 'antd';
import {
  CreditCardOutlined,
  EditOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { get, put, patch, post } from '@/lib/api';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

interface PaymentChannel {
  id: number;
  channel_code: string;
  channel_name: string;
  display_name: string;
  platform: string;
  provider: string;
  is_enabled: boolean;
  is_complete: boolean;
  notify_url: string | null;
  return_url: string | null;
  sort_order: number;
  config_masked: Record<string, string>;
  last_test_at: string | null;
  last_test_ok: boolean | null;
  last_test_message: string | null;
  created_at: string;
  updated_at: string;
}

const CHANNEL_TAB_LABEL: Record<string, string> = {
  wechat_miniprogram: '微信小程序支付',
  wechat_app: '微信APP支付',
  alipay_h5: '支付宝H5支付',
  alipay_app: '支付宝APP支付',
};

const TAB_ORDER = ['wechat_miniprogram', 'wechat_app', 'alipay_h5', 'alipay_app'];

// 字段元定义（与后端 CHANNEL_FIELD_SPEC 对齐）
interface FieldDef {
  key: string;
  label: string;
  isSecret: boolean;
  multiline?: boolean;
  uploadable?: boolean; // .pem 文件上传
  enum?: { value: string; label: string }[];
  visibleWhen?: { key: string; equals: string };
  required?: boolean;
}

const WECHAT_COMMON: FieldDef[] = [
  { key: 'mch_id', label: '商户号 MchID', isSecret: false, required: true },
  { key: 'api_v3_key', label: 'API V3 密钥', isSecret: true, required: true },
  { key: 'cert_serial_no', label: '商户证书序列号', isSecret: false, required: true },
  { key: 'private_key', label: '商户私钥（PEM）', isSecret: true, multiline: true, uploadable: true, required: true },
];

const FIELDS_BY_CHANNEL: Record<string, FieldDef[]> = {
  wechat_miniprogram: [
    { key: 'appid', label: '小程序 AppID', isSecret: false, required: true },
    ...WECHAT_COMMON,
  ],
  wechat_app: [
    { key: 'app_id', label: '开放平台 AppID', isSecret: false, required: true },
    ...WECHAT_COMMON,
  ],
  alipay_h5: [
    { key: 'app_id', label: '应用 AppID', isSecret: false, required: true },
    {
      key: 'access_mode', label: '接入模式', isSecret: false, required: true,
      enum: [
        { value: 'public_key', label: '公钥模式' },
        { value: 'cert', label: '公钥证书模式' },
      ],
    },
    { key: 'app_private_key', label: '应用私钥（PEM）', isSecret: true, multiline: true, uploadable: true, required: true },
    {
      key: 'alipay_public_key', label: '支付宝公钥', isSecret: true, multiline: true,
      visibleWhen: { key: 'access_mode', equals: 'public_key' },
    },
    {
      key: 'app_public_cert', label: '应用公钥证书', isSecret: true, multiline: true, uploadable: true,
      visibleWhen: { key: 'access_mode', equals: 'cert' },
    },
    {
      key: 'alipay_root_cert', label: '支付宝根证书', isSecret: true, multiline: true, uploadable: true,
      visibleWhen: { key: 'access_mode', equals: 'cert' },
    },
    {
      key: 'alipay_public_cert', label: '支付宝公钥证书', isSecret: true, multiline: true, uploadable: true,
      visibleWhen: { key: 'access_mode', equals: 'cert' },
    },
  ],
  alipay_app: [
    { key: 'app_id', label: '应用 AppID', isSecret: false, required: true },
    {
      key: 'access_mode', label: '接入模式', isSecret: false, required: true,
      enum: [
        { value: 'public_key', label: '公钥模式' },
        { value: 'cert', label: '公钥证书模式' },
      ],
    },
    { key: 'app_private_key', label: '应用私钥（PEM）', isSecret: true, multiline: true, uploadable: true, required: true },
    {
      key: 'alipay_public_key', label: '支付宝公钥', isSecret: true, multiline: true,
      visibleWhen: { key: 'access_mode', equals: 'public_key' },
    },
    {
      key: 'app_public_cert', label: '应用公钥证书', isSecret: true, multiline: true, uploadable: true,
      visibleWhen: { key: 'access_mode', equals: 'cert' },
    },
    {
      key: 'alipay_root_cert', label: '支付宝根证书', isSecret: true, multiline: true, uploadable: true,
      visibleWhen: { key: 'access_mode', equals: 'cert' },
    },
    {
      key: 'alipay_public_cert', label: '支付宝公钥证书', isSecret: true, multiline: true, uploadable: true,
      visibleWhen: { key: 'access_mode', equals: 'cert' },
    },
  ],
};


export default function PaymentConfigPage() {
  const [loading, setLoading] = useState(false);
  const [channels, setChannels] = useState<PaymentChannel[]>([]);
  const [activeKey, setActiveKey] = useState<string>('wechat_miniprogram');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerCode, setDrawerCode] = useState<string>('');
  const [form] = Form.useForm();
  const [accessMode, setAccessMode] = useState<string>('public_key');
  const [saving, setSaving] = useState(false);
  const [roleAllowed, setRoleAllowed] = useState<boolean>(true);
  // [Bug 修复] 加载错误信息透传，方便用户/运维一眼看到根因
  const [loadError, setLoadError] = useState<string>('');

  useEffect(() => {
    // 仅 admin / super_admin 可见（项目当前没有 super_admin，因此放宽到 admin）
    if (typeof window !== 'undefined') {
      try {
        const stored = localStorage.getItem('admin_user');
        const user = stored ? JSON.parse(stored) : null;
        const role = user?.role || '';
        if (role && role !== 'admin' && role !== 'super_admin') {
          setRoleAllowed(false);
        }
      } catch {}
    }
    void loadAll();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    setLoadError('');
    try {
      const data = await get<PaymentChannel[]>('/api/admin/payment-channels');
      setChannels(data);
    } catch (e: any) {
      // [Bug 修复 FIX-6] 把后端 detail 透传到提示文案，
      // 没有 detail（如 502/网络异常）则提示"网络异常或服务器无响应"。
      const detail = e?.response?.data?.detail;
      const status = e?.response?.status;
      let msg = '';
      if (typeof detail === 'string' && detail) {
        msg = `加载失败：${detail}`;
      } else if (status) {
        msg = `加载失败：HTTP ${status}（请联系管理员排查后端日志）`;
      } else {
        msg = '加载失败：网络异常或服务器无响应，请检查网络后重试';
      }
      setLoadError(msg);
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const channelMap = useMemo(() => {
    const m = new Map<string, PaymentChannel>();
    channels.forEach((ch) => m.set(ch.channel_code, ch));
    return m;
  }, [channels]);

  const openEdit = async (code: string) => {
    setDrawerCode(code);
    try {
      const ch = await get<PaymentChannel>(`/api/admin/payment-channels/${code}`);
      // 表单初值：display_name / notify_url / return_url / sort_order + 显示掩码字段（只读）+ access_mode
      form.resetFields();
      form.setFieldsValue({
        display_name: ch.display_name,
        notify_url: ch.notify_url || '',
        return_url: ch.return_url || '',
        sort_order: ch.sort_order ?? 0,
        access_mode: ch.config_masked?.access_mode || 'public_key',
      });
      setAccessMode(ch.config_masked?.access_mode || 'public_key');
      setDrawerOpen(true);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载失败');
    }
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    form.resetFields();
  };

  const buildConfig = (values: any): Record<string, any> => {
    const fields = FIELDS_BY_CHANNEL[drawerCode] || [];
    const out: Record<string, any> = {};
    for (const f of fields) {
      const v = values[f.key];
      if (v === undefined) continue;
      // 空字符串：敏感字段表示"保留旧值"，非敏感字段表示"清空"
      // 后端处理逻辑统一：把值传上去，由后端按 is_secret 区分
      out[f.key] = v;
    }
    return out;
  };

  const onSubmit = async (alsoTest: boolean) => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      const body = {
        display_name: values.display_name,
        notify_url: values.notify_url || null,
        return_url: values.return_url || null,
        sort_order: values.sort_order ?? 0,
        config: buildConfig(values),
      };
      const updated = await put<PaymentChannel>(`/api/admin/payment-channels/${drawerCode}`, body);
      message.success('已保存');
      // 同步本地缓存
      setChannels((prev) =>
        prev.map((c) => (c.channel_code === drawerCode ? updated : c))
      );
      if (alsoTest) {
        await onTest(drawerCode, false);
      }
      closeDrawer();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const onTest = async (code: string, withReload = true) => {
    try {
      const r = await post<{ success: boolean; message: string }>(
        `/api/admin/payment-channels/${code}/test`,
      );
      if (r.success) {
        message.success(`测试连接成功：${r.message}`);
      } else {
        message.warning(r.message);
      }
      if (withReload) await loadAll();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      message.error(`测试失败：${typeof detail === 'string' ? detail : '配置不完整'}`);
    }
  };

  const onToggle = async (code: string, enabled: boolean) => {
    try {
      const updated = await patch<PaymentChannel>(
        `/api/admin/payment-channels/${code}/toggle`,
        { enabled },
      );
      setChannels((prev) =>
        prev.map((c) => (c.channel_code === code ? updated : c))
      );
      message.success(enabled ? '已启用' : '已禁用');
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : '操作失败');
    }
  };

  const onRestoreNotifyUrl = async () => {
    try {
      const r = await get<{ notify_url: string }>(
        `/api/admin/payment-channels/${drawerCode}/default-notify-url`,
      );
      form.setFieldsValue({ notify_url: r.notify_url });
      message.success('已填入默认 notify URL');
    } catch (e: any) {
      message.error('获取默认 URL 失败');
    }
  };

  const renderTabContent = (code: string) => {
    const ch = channelMap.get(code);
    if (!ch) return <Spin />;
    const fields = FIELDS_BY_CHANNEL[code] || [];
    const accessModeVal = ch.config_masked?.access_mode || '';

    return (
      <Card
        title={
          <Space>
            <CreditCardOutlined />
            <span>{ch.channel_name}</span>
            <Tag color={ch.is_enabled ? 'green' : 'default'}>
              {ch.is_enabled ? '已启用' : '未启用'}
            </Tag>
            <Tag color={ch.is_complete ? 'blue' : 'orange'}>
              {ch.is_complete ? '配置完整' : '配置未完整'}
            </Tag>
          </Space>
        }
        extra={
          <Space>
            <Button icon={<ThunderboltOutlined />} onClick={() => onTest(code)}>
              测试连接
            </Button>
            <Button type="primary" icon={<EditOutlined />} onClick={() => openEdit(code)}>
              编辑
            </Button>
            <Switch
              checked={ch.is_enabled}
              onChange={(v) => onToggle(code, v)}
              checkedChildren="启用"
              unCheckedChildren="停用"
            />
          </Space>
        }
      >
        <Descriptions column={2} bordered size="small">
          <Descriptions.Item label="显示名称">{ch.display_name}</Descriptions.Item>
          <Descriptions.Item label="服务商">{ch.provider}</Descriptions.Item>
          <Descriptions.Item label="目标端">{ch.platform}</Descriptions.Item>
          <Descriptions.Item label="排序">{ch.sort_order}</Descriptions.Item>
          <Descriptions.Item label="notify_url" span={2}>
            <Text copyable={!!ch.notify_url}>{ch.notify_url || '（未配置）'}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="return_url" span={2}>
            <Text copyable={!!ch.return_url}>{ch.return_url || '（未配置）'}</Text>
          </Descriptions.Item>
          {fields
            .filter((f) =>
              !f.visibleWhen || (accessModeVal && accessModeVal === f.visibleWhen.equals)
            )
            .map((f) => (
              <Descriptions.Item key={f.key} label={f.label} span={f.multiline ? 2 : 1}>
                <Text type="secondary">
                  {ch.config_masked?.[f.key] || '（未填写）'}
                </Text>
              </Descriptions.Item>
            ))}
          <Descriptions.Item label="最近测试" span={2}>
            {ch.last_test_at ? (
              <Space>
                <Tag color={ch.last_test_ok ? 'green' : 'red'}>
                  {ch.last_test_ok ? '成功' : '失败'}
                </Tag>
                <Text type="secondary">{ch.last_test_at}</Text>
                <Text type="secondary">{ch.last_test_message || ''}</Text>
              </Space>
            ) : (
              <Text type="secondary">尚未测试</Text>
            )}
          </Descriptions.Item>
        </Descriptions>
      </Card>
    );
  };

  if (!roleAllowed) {
    return (
      <div style={{ padding: 24 }}>
        <Title level={4}>支付配置</Title>
        <Alert
          type="warning"
          showIcon
          message="您的账号没有访问支付配置的权限"
          description="此页面仅对超级管理员（super_admin）/管理员（admin）开放。"
        />
      </div>
    );
  }

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>
        <CreditCardOutlined /> 支付配置
      </Title>
      <Paragraph type="secondary">
        集中管理 4 个支付通道（微信小程序 / 微信APP / 支付宝H5 / 支付宝APP）。所有敏感字段以
        AES-256-GCM 加密存储；测试连接通过且已启用的通道才会在 C 端展示。
      </Paragraph>
      {loadError && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message={loadError}
          description="若提示与加密密钥/通道初始数据相关，请联系部署人员设置环境变量 PAYMENT_CONFIG_ENCRYPTION_KEY 后重启后端服务，或重新启动后端以触发自动初始化。"
          action={
            <Button
              size="small"
              type="primary"
              icon={<ReloadOutlined />}
              onClick={loadAll}
            >
              重试
            </Button>
          }
        />
      )}
      <Spin spinning={loading}>
        <Tabs
          activeKey={activeKey}
          onChange={setActiveKey}
          items={TAB_ORDER.map((code) => ({
            key: code,
            label: CHANNEL_TAB_LABEL[code],
            children: channels.length === 0 && !loading ? (
              <div style={{ padding: 24, textAlign: 'center', color: '#999' }}>
                暂无通道数据。
                <Button
                  type="link"
                  icon={<ReloadOutlined />}
                  onClick={loadAll}
                >
                  点此重试
                </Button>
              </div>
            ) : renderTabContent(code),
          }))}
        />
      </Spin>

      <Drawer
        title={`编辑 - ${CHANNEL_TAB_LABEL[drawerCode] || drawerCode}`}
        width={720}
        open={drawerOpen}
        onClose={closeDrawer}
        footer={
          <div style={{ textAlign: 'right' }}>
            <Space>
              <Button onClick={closeDrawer}>取消</Button>
              <Button type="primary" loading={saving} onClick={() => onSubmit(false)}>
                仅保存
              </Button>
              <Button type="primary" loading={saving} icon={<ThunderboltOutlined />}
                      onClick={() => onSubmit(true)}>
                保存并测试连接
              </Button>
            </Space>
          </div>
        }
      >
        <Alert
          showIcon
          type="info"
          message="敏感字段（密钥、证书等）留空表示不修改原值；填写新值则会以 AES-256-GCM 加密后保存。"
          style={{ marginBottom: 16 }}
        />
        <Form
          form={form}
          layout="vertical"
          onValuesChange={(changed, all) => {
            if ('access_mode' in changed) {
              setAccessMode(changed.access_mode);
            }
          }}
        >
          <Form.Item
            label="显示名称"
            name="display_name"
            rules={[
              { required: true, message: '显示名称必填' },
              { whitespace: true, message: '显示名称不能为空白' },
            ]}
          >
            <Input maxLength={100} placeholder="C 端显示名称（如：微信支付 / 支付宝）" />
          </Form.Item>
          <Form.Item
            label={
              <Space>
                <span>notify_url（异步通知地址）</span>
                <Button size="small" icon={<ReloadOutlined />} onClick={onRestoreNotifyUrl}>
                  还原默认
                </Button>
              </Space>
            }
            name="notify_url"
          >
            <Input placeholder="https://.../api/pay/notify/<channel_code>" />
          </Form.Item>
          <Form.Item label="return_url（同步跳转，仅 H5/APP 需要）" name="return_url">
            <Input placeholder="可选" />
          </Form.Item>
          <Form.Item label="排序（数字越小越靠前）" name="sort_order">
            <InputNumber min={0} max={9999} />
          </Form.Item>

          {(FIELDS_BY_CHANNEL[drawerCode] || []).map((f) => {
            if (f.visibleWhen && accessMode !== f.visibleWhen.equals) return null;

            if (f.enum) {
              return (
                <Form.Item
                  key={f.key}
                  label={f.label}
                  name={f.key}
                  rules={f.required ? [{ required: true, message: `${f.label}必填` }] : []}
                >
                  <Select options={f.enum.map((e) => ({ value: e.value, label: e.label }))} />
                </Form.Item>
              );
            }

            const placeholder = f.isSecret
              ? '留空表示不修改原值；填写新值则会加密保存'
              : `请输入${f.label}`;

            return (
              <Form.Item
                key={f.key}
                label={
                  f.uploadable ? (
                    <Space>
                      <span>{f.label}</span>
                      <Upload
                        accept=".pem,.key,.crt,.cer,.txt"
                        showUploadList={false}
                        beforeUpload={(file) => {
                          const reader = new FileReader();
                          reader.onload = () => {
                            form.setFieldValue(f.key, String(reader.result || ''));
                            message.success(`已读取 ${file.name}`);
                          };
                          reader.readAsText(file);
                          return false;
                        }}
                      >
                        <Button size="small" icon={<UploadOutlined />}>
                          上传 .pem
                        </Button>
                      </Upload>
                    </Space>
                  ) : (
                    f.label
                  )
                }
                name={f.key}
                rules={(!f.isSecret && f.required) ? [{ required: true, message: `${f.label}必填` }] : []}
              >
                {f.multiline ? (
                  <TextArea rows={6} placeholder={placeholder} />
                ) : (
                  <Input placeholder={placeholder} />
                )}
              </Form.Item>
            );
          })}
        </Form>
      </Drawer>
    </div>
  );
}
