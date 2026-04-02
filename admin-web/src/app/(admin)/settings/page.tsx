'use client';

import React, { useEffect, useState } from 'react';
import { Tabs, Form, Input, Switch, Button, InputNumber, Card, Space, message, Typography, Select, Divider, Radio, Modal, Tooltip } from 'antd';
import { SaveOutlined, SettingOutlined, BellOutlined, FileProtectOutlined, UserAddOutlined, QuestionCircleOutlined } from '@ant-design/icons';
import { get, post } from '@/lib/api';

const { Title, Text, Link } = Typography;
const { TextArea } = Input;

export default function SettingsPage() {
  const [basicForm] = Form.useForm();
  const [pushForm] = Form.useForm();
  const [protocolForm] = Form.useForm();
  const [registerForm] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [exampleModal, setExampleModal] = useState<{ open: boolean; title: string; content: React.ReactNode }>({ open: false, title: '', content: null });

  const enableSelfRegistration = Form.useWatch('enable_self_registration', registerForm);
  const memberCardNoRule = Form.useWatch('member_card_no_rule', registerForm);

  const showExample = (title: string, content: React.ReactNode) => {
    setExampleModal({ open: true, title, content });
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

  const handleSavePush = async () => {
    try {
      const values = await pushForm.validateFields();
      setSaving(true);
      try {
        await post('/api/admin/settings/push', values);
      } catch {}
      message.success('推送配置保存成功');
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

  const tabItems = [
    {
      key: 'basic',
      label: (
        <Space><SettingOutlined />基础配置</Space>
      ),
      children: (
        <Card style={{ borderRadius: 12 }}>
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
      key: 'push',
      label: (
        <Space><BellOutlined />推送管理</Space>
      ),
      children: (
        <Card style={{ borderRadius: 12 }}>
          <Form
            form={pushForm}
            layout="vertical"
            initialValues={{
              enableSMS: true,
              smsProvider: 'aliyun',
              smsAccessKey: '',
              smsSecret: '',
              smsSign: '宾尼小康',
              enableWechatPush: true,
              wechatAppId: '',
              wechatAppSecret: '',
              orderNotifyTemplate: '',
              serviceNotifyTemplate: '',
              enableEmailNotify: false,
              smtpHost: '',
              smtpPort: 465,
              smtpUser: '',
              smtpPassword: '',
            }}
          >
            <Title level={5}>短信配置</Title>
            <Form.Item label="启用短信通知" name="enableSMS" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item label="短信服务商" name="smsProvider">
              <Select options={[{ label: '阿里云', value: 'aliyun' }, { label: '腾讯云', value: 'tencent' }, { label: '华为云', value: 'huawei' }]} style={{ width: 200 }} />
            </Form.Item>
            <Space style={{ width: '100%' }} size={16}>
              <Form.Item label="Access Key" name="smsAccessKey" style={{ flex: 1 }}>
                <Input placeholder="Access Key" />
              </Form.Item>
              <Form.Item label="Secret" name="smsSecret" style={{ flex: 1 }}>
                <Input.Password placeholder="Secret" />
              </Form.Item>
            </Space>
            <Form.Item label="短信签名" name="smsSign">
              <Input placeholder="短信签名" style={{ width: 200 }} />
            </Form.Item>

            <Divider />

            <Title level={5}>微信推送</Title>
            <Form.Item label="启用微信推送" name="enableWechatPush" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Space style={{ width: '100%' }} size={16}>
              <Form.Item label="微信 AppID" name="wechatAppId" style={{ flex: 1 }}>
                <Input placeholder="AppID" />
              </Form.Item>
              <Form.Item label="微信 AppSecret" name="wechatAppSecret" style={{ flex: 1 }}>
                <Input.Password placeholder="AppSecret" />
              </Form.Item>
            </Space>
            <Form.Item label="订单通知模板ID" name="orderNotifyTemplate">
              <Input placeholder="模板ID" />
            </Form.Item>
            <Form.Item label="服务通知模板ID" name="serviceNotifyTemplate">
              <Input placeholder="模板ID" />
            </Form.Item>

            <Divider />

            <Title level={5}>邮件通知</Title>
            <Form.Item label="启用邮件通知" name="enableEmailNotify" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Space style={{ width: '100%' }} size={16}>
              <Form.Item label="SMTP服务器" name="smtpHost" style={{ flex: 1 }}>
                <Input placeholder="smtp.example.com" />
              </Form.Item>
              <Form.Item label="端口" name="smtpPort" style={{ width: 120 }}>
                <InputNumber min={1} max={65535} style={{ width: '100%' }} />
              </Form.Item>
            </Space>
            <Space style={{ width: '100%' }} size={16}>
              <Form.Item label="用户名" name="smtpUser" style={{ flex: 1 }}>
                <Input placeholder="邮箱用户名" />
              </Form.Item>
              <Form.Item label="密码" name="smtpPassword" style={{ flex: 1 }}>
                <Input.Password placeholder="邮箱密码" />
              </Form.Item>
            </Space>

            <Form.Item>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSavePush} loading={saving}>保存推送配置</Button>
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
