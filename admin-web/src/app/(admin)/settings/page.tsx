'use client';

import React, { useEffect, useState } from 'react';
import { Tabs, Form, Input, Switch, Button, InputNumber, Card, Space, message, Typography, Divider, Radio, Modal, Tooltip, Upload, Select } from 'antd';
import { SaveOutlined, SettingOutlined, FileProtectOutlined, UserAddOutlined, QuestionCircleOutlined, UploadOutlined, DeleteOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { get, post, put, del, upload as apiUpload } from '@/lib/api';

const { Title, Text, Link } = Typography;
const { TextArea } = Input;

const timeoutHandlingOptions = [
  { label: '自动取消订单并退款', value: 'auto_cancel' },
  { label: '自动确认接单', value: 'auto_confirm' },
  { label: '升级通知管理员', value: 'escalate' },
];

export default function SettingsPage() {
  const [basicForm] = Form.useForm();
  const [protocolForm] = Form.useForm();
  const [registerForm] = Form.useForm();
  const [timeoutForm] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [exampleModal, setExampleModal] = useState<{ open: boolean; title: string; content: React.ReactNode }>({ open: false, title: '', content: null });
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [logoLoading, setLogoLoading] = useState(false);
  const [logoUploading, setLogoUploading] = useState(false);

  const enableSelfRegistration = Form.useWatch('enable_self_registration', registerForm);
  const memberCardNoRule = Form.useWatch('member_card_no_rule', registerForm);

  const showExample = (title: string, content: React.ReactNode) => {
    setExampleModal({ open: true, title, content });
  };

  useEffect(() => {
    const loadLogo = async () => {
      setLogoLoading(true);
      try {
        const res = await get<{ code: number; data: { logo_url: string } }>('/api/settings/logo');
        if (res?.data?.logo_url) {
          setLogoUrl(res.data.logo_url);
        }
      } catch {
        // ignore
      } finally {
        setLogoLoading(false);
      }
    };
    loadLogo();
  }, []);

  const handleLogoUpload = async (file: File) => {
    setLogoUploading(true);
    try {
      const res = await apiUpload<{ code: number; data: { logo_url: string } }>('/api/admin/settings/logo', file, 'file');
      if (res?.data?.logo_url) {
        setLogoUrl(res.data.logo_url);
        message.success('LOGO上传成功');
      }
    } catch {
      message.error('LOGO上传失败，请稍后重试');
    } finally {
      setLogoUploading(false);
    }
  };

  const handleLogoDelete = async () => {
    try {
      await del('/api/admin/settings/logo');
      setLogoUrl(null);
      message.success('LOGO已删除');
    } catch {
      message.error('LOGO删除失败，请稍后重试');
    }
  };

  useEffect(() => {
    const loadRegisterSettings = async () => {
      try {
        const values = await get('/api/admin/settings/register');
        registerForm.setFieldsValue(values);
      } catch {
        message.warning('注册设置加载失败，已显示页面默认值');
      }
    };
    loadRegisterSettings();
  }, [registerForm]);

  useEffect(() => {
    const loadTimeoutPolicy = async () => {
      try {
        const [policyRes, reminderRes] = await Promise.all([
          get('/api/admin/settings/timeout-policy'),
          get('/api/admin/settings/reminder-advance'),
        ]);
        const merged: Record<string, any> = {};
        if (policyRes) {
          merged.urge_minutes = policyRes.urge_minutes ?? 15;
          merged.timeout_minutes = policyRes.timeout_minutes ?? 30;
          merged.timeout_action = policyRes.timeout_action ?? 'auto_cancel';
        }
        if (reminderRes) {
          merged.reminder_advance_hours = reminderRes.reminder_advance_hours ?? 2;
        }
        timeoutForm.setFieldsValue(merged);
      } catch {
        // use defaults
      }
    };
    loadTimeoutPolicy();
  }, [timeoutForm]);

  const handleSaveBasic = async () => {
    try {
      const values = await basicForm.validateFields();
      setSaving(true);
      try {
        await post('/api/admin/settings/basic', values);
      } catch {}
      message.success('基础配置保存成功');
    } catch {} finally {
      setSaving(false);
    }
  };

  const handleSaveProtocol = async () => {
    try {
      const values = await protocolForm.validateFields();
      setSaving(true);
      try {
        await post('/api/admin/settings/protocol', values);
      } catch {}
      message.success('协议保存成功');
    } catch {} finally {
      setSaving(false);
    }
  };

  const handleSaveRegister = async () => {
    try {
      const values = await registerForm.validateFields();
      setSaving(true);
      await post('/api/admin/settings/register', values);
      message.success('注册设置保存成功');
    } catch (e: unknown) {
      if ((e as { errorFields?: unknown })?.errorFields) return;
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : '注册设置保存失败，请稍后重试');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveTimeoutPolicy = async () => {
    try {
      const values = await timeoutForm.validateFields();
      setSaving(true);
      await Promise.all([
        put('/api/admin/settings/timeout-policy', {
          urge_minutes: values.urge_minutes,
          timeout_minutes: values.timeout_minutes,
          timeout_action: values.timeout_action,
        }),
        put('/api/admin/settings/reminder-advance', {
          reminder_advance_hours: values.reminder_advance_hours,
        }),
      ]);
      message.success('超时策略保存成功');
    } catch (e: unknown) {
      if ((e as { errorFields?: unknown })?.errorFields) return;
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : '超时策略保存失败');
    } finally {
      setSaving(false);
    }
  };

  const tabItems = [
    {
      key: 'basic',
      label: (
        <Space><SettingOutlined />基础配置</Space>
      ),
      children: (
        <Card style={{ borderRadius: 12 }}>
          <Title level={5}>品牌LOGO</Title>
          <div style={{ marginBottom: 24 }}>
            <Space align="start" size={16}>
              {logoUrl && (
                <img
                  src={logoUrl}
                  alt="品牌LOGO"
                  style={{ width: 80, height: 80, objectFit: 'contain', borderRadius: 8, border: '1px solid #f0f0f0' }}
                />
              )}
              <Space direction="vertical" size={8}>
                <Upload
                  accept=".png,.jpg,.jpeg"
                  showUploadList={false}
                  beforeUpload={(file) => {
                    const isValid = file.type === 'image/png' || file.type === 'image/jpeg';
                    if (!isValid) {
                      message.error('仅支持 PNG/JPG 格式');
                      return false;
                    }
                    const isLt2M = file.size / 1024 / 1024 < 2;
                    if (!isLt2M) {
                      message.error('图片大小不能超过 2MB');
                      return false;
                    }
                    handleLogoUpload(file);
                    return false;
                  }}
                >
                  <Button icon={<UploadOutlined />} loading={logoUploading}>
                    {logoUrl ? '更换LOGO' : '上传LOGO'}
                  </Button>
                </Upload>
                {logoUrl && (
                  <Button icon={<DeleteOutlined />} danger onClick={handleLogoDelete}>
                    删除
                  </Button>
                )}
                <Text type="secondary" style={{ fontSize: 12 }}>
                  支持 PNG/JPG 格式，建议正方形（如 512×512），大小不超过 2MB
                </Text>
              </Space>
            </Space>
          </div>
          <Divider style={{ margin: '0 0 16px' }} />
          <Form
            form={basicForm}
            layout="vertical"
            initialValues={{
              appName: '宾尼小康',
              appSlogan: 'AI健康管家，守护您的健康',
              contactPhone: '400-888-9999',
              contactEmail: 'support@bini-health.com',
              serviceHours: '09:00-21:00',
              enableRegister: true,
              enableAIChat: true,
              enablePointsMall: true,
              maintenanceMode: false,
              maintenanceMessage: '系统正在升级维护中，请稍后再试',
              maxDailyAICalls: 50,
              defaultAvatar: '',
              shareTitle: '宾尼小康 - 您的AI健康管家',
              shareDescription: '智能健康咨询，专业营养方案，中医养生指导',
            }}
          >
            <Title level={5}>应用信息</Title>
            <Space style={{ width: '100%' }} size={16}>
              <Form.Item label="应用名称" name="appName" rules={[{ required: true }]} style={{ flex: 1 }}>
                <Input placeholder="应用名称" />
              </Form.Item>
              <Form.Item label="应用标语" name="appSlogan" style={{ flex: 2 }}>
                <Input placeholder="应用标语" />
              </Form.Item>
            </Space>

            <Title level={5} style={{ marginTop: 8 }}>联系方式</Title>
            <Space style={{ width: '100%' }} size={16}>
              <Form.Item label="客服电话" name="contactPhone" style={{ flex: 1 }}>
                <Input placeholder="400-xxx-xxxx" />
              </Form.Item>
              <Form.Item label="客服邮箱" name="contactEmail" style={{ flex: 1 }}>
                <Input placeholder="support@example.com" />
              </Form.Item>
              <Form.Item label="服务时间" name="serviceHours" style={{ flex: 1 }}>
                <Input placeholder="09:00-21:00" />
              </Form.Item>
            </Space>

            <Title level={5} style={{ marginTop: 8 }}>功能开关</Title>
            <Space size={32} wrap>
              <Form.Item label="开放注册" name="enableRegister" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item label="AI对话" name="enableAIChat" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item label="积分商城" name="enablePointsMall" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item label="维护模式" name="maintenanceMode" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Space>

            <Form.Item label="维护公告" name="maintenanceMessage">
              <TextArea rows={2} placeholder="维护模式下显示的公告内容" />
            </Form.Item>

            <Title level={5} style={{ marginTop: 8 }}>AI配额</Title>
            <Form.Item label="每日AI调用上限(每用户)" name="maxDailyAICalls">
              <InputNumber min={1} style={{ width: 200 }} addonAfter="次" />
            </Form.Item>

            <Title level={5} style={{ marginTop: 8 }}>分享设置</Title>
            <Form.Item label="分享标题" name="shareTitle">
              <Input placeholder="分享标题" />
            </Form.Item>
            <Form.Item label="分享描述" name="shareDescription">
              <TextArea rows={2} placeholder="分享描述" />
            </Form.Item>

            <Form.Item>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveBasic} loading={saving}>保存基础配置</Button>
            </Form.Item>
          </Form>
        </Card>
      ),
    },
    {
      key: 'register',
      label: (
        <Space><UserAddOutlined />注册设置</Space>
      ),
      children: (
        <Card style={{ borderRadius: 12 }}>
          <Form
            form={registerForm}
            layout="vertical"
            initialValues={{
              enable_self_registration: true,
              wechat_register_mode: 'authorize_member',
              register_page_layout: 'vertical',
              show_profile_completion_prompt: true,
              member_card_no_rule: 'incremental',
            }}
          >
            <Form.Item label="自助注册会员" name="enable_self_registration">
              <Radio.Group
                options={[
                  { label: '关闭', value: false },
                  { label: '开启', value: true },
                ]}
                optionType="default"
              />
            </Form.Item>
            <div style={{ marginTop: -16, marginBottom: 16, paddingLeft: 12 }}>
              <Text type="secondary">
                {enableSelfRegistration
                  ? '开启后，未注册手机号或授权用户可按配置自动成为会员。'
                  : '关闭后，新用户无法自助开通会员，以下渠道注册方式仅保留配置，不会对外开放。'}
              </Text>
            </div>

            <Form.Item
              label={
                <Space>
                  微信端注册方式
                  <Link onClick={() => showExample('微信端注册方式说明', (
                    <div>
                      <Title level={5}>授权即会员</Title>
                      <Text>用户通过微信授权登录后，系统自动将其注册为会员，无需填写任何额外信息。适合追求快速转化、降低注册门槛的场景。</Text>
                      <Divider />
                      <Title level={5}>填写注册信息</Title>
                      <Text>用户授权登录后，需要填写手机号、姓名等注册信息才能成为会员。适合需要收集用户详细资料的场景。</Text>
                    </div>
                  ))}>示例</Link>
                </Space>
              }
              name="wechat_register_mode"
              style={{ paddingLeft: 24 }}
            >
              <Radio.Group disabled={!enableSelfRegistration}>
                <Radio value="authorize_member">
                  <Space>
                    授权即会员
                    <Tooltip title="微信授权后直接成为会员，无需填写额外信息">
                      <QuestionCircleOutlined style={{ color: '#999' }} />
                    </Tooltip>
                  </Space>
                </Radio>
                <Radio value="fill_profile">填写注册信息</Radio>
              </Radio.Group>
            </Form.Item>

            <Form.Item
              label={
                <Space>
                  注册页布局
                  <Link onClick={() => showExample('注册页布局说明', (
                    <div>
                      <Title level={5}>上下结构</Title>
                      <Text>Logo/品牌图在上方，注册表单在下方，适合移动端竖屏浏览，视觉流程自上而下。</Text>
                      <Divider />
                      <Title level={5}>左右结构</Title>
                      <Text>品牌展示区在左侧，注册表单在右侧，适合PC端或平板横屏，充分利用宽屏空间。</Text>
                    </div>
                  ))}>示例</Link>
                </Space>
              }
              name="register_page_layout"
            >
              <Radio.Group>
                <Radio value="vertical">上下结构</Radio>
                <Radio value="horizontal">左右结构</Radio>
              </Radio.Group>
            </Form.Item>

            <Form.Item
              label={
                <Space>
                  会员信息补充提醒
                  <Link onClick={() => showExample('会员信息补充提醒说明', (
                    <div>
                      <Text>开启后，当会员资料不完整（如缺少手机号、姓名等关键信息）时，系统会在用户登录后弹出提醒，引导用户补充完善个人信息。</Text>
                    </div>
                  ))}>示例</Link>
                </Space>
              }
              name="show_profile_completion_prompt"
            >
              <Radio.Group
                options={[
                  { label: '关闭', value: false },
                  { label: '开启', value: true },
                ]}
              />
            </Form.Item>

            <Form.Item label="会员卡号生成规则" name="member_card_no_rule">
              <Radio.Group>
                <Radio value="incremental">默认（递增）</Radio>
                <Radio value="random">随机生成</Radio>
              </Radio.Group>
            </Form.Item>
            <div style={{ marginTop: -16, marginBottom: 16, paddingLeft: 12 }}>
              <Text type="secondary">
                {memberCardNoRule === 'random' ? '随机生成8位数字卡号' : '按顺序递增生成卡号，如1、2、3'}
              </Text>
            </div>

            <Form.Item>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveRegister} loading={saving}>保存注册设置</Button>
            </Form.Item>
          </Form>
        </Card>
      ),
    },
    {
      key: 'protocol',
      label: (
        <Space><FileProtectOutlined />协议管理</Space>
      ),
      children: (
        <Card style={{ borderRadius: 12 }}>
          <Form
            form={protocolForm}
            layout="vertical"
            initialValues={{
              userAgreement: '《宾尼小康用户服务协议》\n\n第一条 总则\n本协议是用户与宾尼小康AI健康管家平台之间关于使用平台服务的法律协议...\n\n第二条 服务内容\n宾尼小康提供AI健康咨询、营养管理、专家问诊等健康管理服务...\n\n第三条 用户权利与义务\n用户有权享受平台提供的各项服务，同时应遵守平台规则...',
              privacyPolicy: '《宾尼小康隐私政策》\n\n一、信息收集\n我们可能收集您的以下信息：\n1. 注册信息：手机号、昵称等\n2. 健康信息：您主动提供的健康数据\n3. 使用信息：浏览记录、使用偏好等\n\n二、信息使用\n我们将收集的信息用于：\n1. 提供和改善健康管理服务\n2. 个性化推荐\n3. 安全保障...',
              healthDisclaimer: '《健康免责声明》\n\n宾尼小康AI健康管家提供的所有健康建议、营养方案、体检报告解读等内容仅供参考，不构成医疗诊断或治疗建议。\n\n如有健康问题，请及时就医。\n\n本平台不对因使用AI建议而导致的任何健康问题承担责任。',
            }}
          >
            <Form.Item label="用户服务协议" name="userAgreement" rules={[{ required: true, message: '请输入用户服务协议' }]}>
              <TextArea rows={10} placeholder="请输入用户服务协议内容" />
            </Form.Item>
            <Form.Item label="隐私政策" name="privacyPolicy" rules={[{ required: true, message: '请输入隐私政策' }]}>
              <TextArea rows={10} placeholder="请输入隐私政策内容" />
            </Form.Item>
            <Form.Item label="健康免责声明" name="healthDisclaimer">
              <TextArea rows={6} placeholder="请输入健康免责声明" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveProtocol} loading={saving}>保存协议</Button>
            </Form.Item>
          </Form>
        </Card>
      ),
    },
    {
      key: 'timeout',
      label: (
        <Space><ClockCircleOutlined />超时策略</Space>
      ),
      children: (
        <Card style={{ borderRadius: 12 }}>
          <Form
            form={timeoutForm}
            layout="vertical"
            initialValues={{
              urge_minutes: 15,
              timeout_minutes: 30,
              timeout_action: 'auto_cancel',
              reminder_advance_hours: 2,
            }}
          >
            <Title level={5}>订单超时策略</Title>
            <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
              配置商家未接单时的催促提醒与超时处理规则，以及预约订单的提前提醒时长。
            </Text>

            <Space style={{ width: '100%' }} size={16}>
              <Form.Item
                label="催促提醒时间"
                name="urge_minutes"
                rules={[{ required: true, message: '请输入催促提醒时间' }]}
                tooltip="下单后多少分钟内商家未接单，系统向商家发送催促提醒"
                style={{ flex: 1 }}
              >
                <InputNumber min={1} max={1440} style={{ width: '100%' }} addonAfter="分钟" placeholder="15" />
              </Form.Item>
              <Form.Item
                label="超时时长"
                name="timeout_minutes"
                rules={[{ required: true, message: '请输入超时时长' }]}
                tooltip="下单后多少分钟内商家仍未接单，触发超时处理"
                style={{ flex: 1 }}
              >
                <InputNumber min={1} max={1440} style={{ width: '100%' }} addonAfter="分钟" placeholder="30" />
              </Form.Item>
            </Space>

            <Form.Item
              label="超时处理方式"
              name="timeout_action"
              rules={[{ required: true, message: '请选择超时处理方式' }]}
              tooltip="商家超时未接单后系统自动执行的操作"
            >
              <Select options={timeoutHandlingOptions} style={{ width: 300 }} />
            </Form.Item>

            <Divider style={{ margin: '8px 0 16px' }} />

            <Title level={5}>预约提醒设置</Title>
            <Form.Item
              label="预约提前提醒时长"
              name="reminder_advance_hours"
              rules={[{ required: true, message: '请输入提前提醒时长' }]}
              tooltip="在预约时间前多少小时向用户和商家发送提醒"
            >
              <InputNumber min={0.5} max={72} step={0.5} style={{ width: 200 }} addonAfter="小时" placeholder="2" />
            </Form.Item>

            <Form.Item>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveTimeoutPolicy} loading={saving}>保存超时策略</Button>
            </Form.Item>
          </Form>
        </Card>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>系统设置</Title>
      <Tabs items={tabItems} />
      <Modal
        title={exampleModal.title}
        open={exampleModal.open}
        footer={null}
        onCancel={() => setExampleModal((s) => ({ ...s, open: false }))}
        destroyOnClose
        width={560}
      >
        {exampleModal.content}
      </Modal>
    </div>
  );
}
