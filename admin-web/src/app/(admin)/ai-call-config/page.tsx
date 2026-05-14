'use client';

/**
 * [PRD-HEALTH-OPT-V1 2026-05-14 R5] AI 外呼配置 — admin 后台。
 *
 * 5 项配置：
 *  1. 会员等级与额度
 *  2. 默认勿扰时段
 *  3. 默认外呼话术模板
 *  4. 重拨次数和间隔
 *  5. 扣减规则 A/B
 */
import React, { useEffect, useState } from 'react';
import {
  Card, Form, Input, InputNumber, Button, Space, message, Typography,
  Table, Tag, Popconfirm, Modal, Switch, TimePicker, Tabs,
} from 'antd';
import { SaveOutlined, PlusOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { get, post, put, del } from '@/lib/api';

const { Title, Text } = Typography;

interface MembershipLevel {
  id: number;
  level_code: string;
  display_name: string;
  monthly_quota: number;
  sort_order: number;
  is_active: boolean;
}

interface GlobalConfig {
  default_dnd_start: string;
  default_dnd_end: string;
  default_script_template: string;
  retry_max: number;
  retry_interval_minutes: number;
  rule_a_per_plan_once: boolean;
  rule_b_charge_on_answer: boolean;
}

export default function AiCallConfigPage() {
  const [levels, setLevels] = useState<MembershipLevel[]>([]);
  const [config, setConfig] = useState<GlobalConfig | null>(null);
  const [levelModal, setLevelModal] = useState<MembershipLevel | null>(null);
  const [levelModalOpen, setLevelModalOpen] = useState(false);
  const [levelForm] = Form.useForm();
  const [configForm] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const ls: any = await get('/api/admin/ai-call/membership-levels');
      setLevels(Array.isArray(ls) ? ls : (ls?.data || []));
    } catch (e) {
      message.error('加载会员等级失败');
    }
    try {
      const cfg: any = await get('/api/admin/ai-call/config');
      const data = cfg?.data || cfg;
      setConfig(data);
      configForm.setFieldsValue({
        default_dnd_start: data?.default_dnd_start ? dayjs(data.default_dnd_start, 'HH:mm') : null,
        default_dnd_end: data?.default_dnd_end ? dayjs(data.default_dnd_end, 'HH:mm') : null,
        default_script_template: data?.default_script_template,
        retry_max: data?.retry_max,
        retry_interval_minutes: data?.retry_interval_minutes,
        rule_a_per_plan_once: !!data?.rule_a_per_plan_once,
        rule_b_charge_on_answer: !!data?.rule_b_charge_on_answer,
      });
    } catch (e) {
      message.error('加载全局配置失败');
    }
    setLoading(false);
  };

  useEffect(() => { refresh(); }, []);

  const openLevelModal = (item: MembershipLevel | null) => {
    setLevelModal(item);
    setLevelModalOpen(true);
    if (item) {
      levelForm.setFieldsValue(item);
    } else {
      levelForm.resetFields();
      levelForm.setFieldsValue({ monthly_quota: 30, sort_order: 100, is_active: true });
    }
  };

  const submitLevel = async () => {
    const values = await levelForm.validateFields();
    try {
      if (levelModal) {
        await put(`/api/admin/ai-call/membership-levels/${levelModal.id}`, values);
        message.success('已更新');
      } else {
        await post('/api/admin/ai-call/membership-levels', values);
        message.success('已新增');
      }
      setLevelModalOpen(false);
      refresh();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    }
  };

  const removeLevel = async (id: number) => {
    try {
      await del(`/api/admin/ai-call/membership-levels/${id}`);
      message.success('已删除');
      refresh();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  const saveConfig = async () => {
    const v = await configForm.validateFields();
    const payload = {
      default_dnd_start: v.default_dnd_start ? dayjs(v.default_dnd_start).format('HH:mm') : undefined,
      default_dnd_end: v.default_dnd_end ? dayjs(v.default_dnd_end).format('HH:mm') : undefined,
      default_script_template: v.default_script_template,
      retry_max: v.retry_max,
      retry_interval_minutes: v.retry_interval_minutes,
      rule_a_per_plan_once: !!v.rule_a_per_plan_once,
      rule_b_charge_on_answer: !!v.rule_b_charge_on_answer,
    };
    try {
      await put('/api/admin/ai-call/config', payload);
      message.success('已保存');
      refresh();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    }
  };

  const columns = [
    { title: 'Code', dataIndex: 'level_code' },
    { title: '显示名称', dataIndex: 'display_name' },
    { title: '月额度', dataIndex: 'monthly_quota', render: (n: number) => <Tag color="blue">{n} 次/月</Tag> },
    { title: '排序', dataIndex: 'sort_order' },
    {
      title: '状态', dataIndex: 'is_active',
      render: (v: boolean) => v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>,
    },
    {
      title: '操作',
      render: (_: any, r: MembershipLevel) => (
        <Space>
          <Button size="small" onClick={() => openLevelModal(r)}>编辑</Button>
          <Popconfirm title="确认删除该等级？" onConfirm={() => removeLevel(r.id)} disabled={['normal', 'health'].includes(r.level_code)}>
            <Button size="small" danger disabled={['normal', 'health'].includes(r.level_code)}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 20 }}>
      <Title level={3}>AI 外呼配置</Title>
      <Text type="secondary">每项变更对新呼叫即刻生效，已用额度不回退。</Text>

      <Tabs
        style={{ marginTop: 16 }}
        items={[
          {
            key: 'levels',
            label: '会员等级与额度',
            children: (
              <Card
                extra={
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => openLevelModal(null)}>
                    新增等级
                  </Button>
                }
                loading={loading}
              >
                <Table
                  rowKey="id"
                  columns={columns as any}
                  dataSource={levels}
                  pagination={false}
                  data-testid="bh-admin-levels-table"
                />
              </Card>
            ),
          },
          {
            key: 'global',
            label: '全局配置（勿扰 / 话术 / 重拨 / 扣减规则）',
            children: (
              <Card loading={loading}>
                <Form form={configForm} layout="vertical">
                  <Space wrap>
                    <Form.Item name="default_dnd_start" label="默认勿扰开始" rules={[{ required: true }]}>
                      <TimePicker format="HH:mm" minuteStep={5} />
                    </Form.Item>
                    <Form.Item name="default_dnd_end" label="默认勿扰结束" rules={[{ required: true }]}>
                      <TimePicker format="HH:mm" minuteStep={5} />
                    </Form.Item>
                  </Space>
                  <Form.Item
                    name="default_script_template"
                    label="默认外呼话术模板（支持变量 {药物名} {用户姓名} {时间}）"
                    rules={[{ required: true }]}
                  >
                    <Input.TextArea rows={4} maxLength={500} showCount />
                  </Form.Item>
                  <Space wrap>
                    <Form.Item name="retry_max" label="最大重拨次数" rules={[{ required: true }]}>
                      <InputNumber min={0} max={10} />
                    </Form.Item>
                    <Form.Item name="retry_interval_minutes" label="重拨间隔(分钟)" rules={[{ required: true }]}>
                      <InputNumber min={1} max={60} />
                    </Form.Item>
                  </Space>
                  <Form.Item name="rule_a_per_plan_once" label="规则A：每条用药提醒最多扣 1 次" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                  <Form.Item name="rule_b_charge_on_answer" label="规则B：接通才扣（关闭则发起即扣）" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                  <Button type="primary" icon={<SaveOutlined />} onClick={saveConfig}>保存</Button>
                </Form>
              </Card>
            ),
          },
        ]}
      />

      <Modal
        open={levelModalOpen}
        title={levelModal ? '编辑会员等级' : '新增会员等级'}
        onCancel={() => setLevelModalOpen(false)}
        onOk={submitLevel}
        destroyOnClose
      >
        <Form form={levelForm} layout="vertical">
          <Form.Item name="level_code" label="Code（英文，唯一）" rules={[{ required: true }]}>
            <Input disabled={!!levelModal} />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="monthly_quota" label="月额度（次/月）" rules={[{ required: true }]}>
            <InputNumber min={0} max={100000} />
          </Form.Item>
          <Form.Item name="sort_order" label="排序" initialValue={100}>
            <InputNumber min={0} max={9999} />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
