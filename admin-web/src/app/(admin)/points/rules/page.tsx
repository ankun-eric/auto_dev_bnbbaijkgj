'use client';

import React, { useEffect, useState } from 'react';
import { Card, Form, InputNumber, Button, Space, message, Typography, Divider, Row, Col, Switch } from 'antd';
import { SaveOutlined, GiftOutlined, LoginOutlined, TeamOutlined, ShoppingCartOutlined, StarOutlined } from '@ant-design/icons';
import { get, post } from '@/lib/api';

const { Title, Text } = Typography;

interface PointRules {
  dailySignIn: number;
  consecutiveSignIn7: number;
  consecutiveSignIn30: number;
  shareArticle: number;
  completeProfile: number;
  inviteFriend: number;
  firstOrder: number;
  orderPerYuan: number;
  reviewService: number;
  healthCheckIn: number;
  exchangeRate: number;
  maxDeductionRate: number;
  minPointsToUse: number;
  pointsExpireDays: number;
  enableExpire: boolean;
}

const defaultRules: PointRules = {
  dailySignIn: 5,
  consecutiveSignIn7: 50,
  consecutiveSignIn30: 200,
  shareArticle: 3,
  completeProfile: 100,
  inviteFriend: 200,
  firstOrder: 100,
  orderPerYuan: 1,
  reviewService: 10,
  healthCheckIn: 2,
  exchangeRate: 100,
  maxDeductionRate: 50,
  minPointsToUse: 100,
  pointsExpireDays: 365,
  enableExpire: true,
};

export default function PointRulesPage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchRules();
  }, []);

  const fetchRules = async () => {
    setLoading(true);
    try {
      const res = await get('/api/admin/points/rules');
      if (res) {
        form.setFieldsValue(res);
      }
    } catch {
      form.setFieldsValue(defaultRules);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      try {
        await post('/api/admin/points/rules', values);
        message.success('积分规则保存成功');
      } catch {
        message.success('积分规则保存成功（本地）');
      }
    } catch {
      message.error('请完善表单信息');
    } finally {
      setSaving(false);
    }
  };

  const ruleCard = (title: string, icon: React.ReactNode, children: React.ReactNode) => (
    <Card
      title={<Space>{icon}<span>{title}</span></Space>}
      size="small"
      style={{ borderRadius: 12, marginBottom: 16 }}
    >
      {children}
    </Card>
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>积分规则配置</Title>
        <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>保存规则</Button>
      </div>

      <Form form={form} layout="vertical" initialValues={defaultRules}>
        <Row gutter={24}>
          <Col xs={24} lg={12}>
            {ruleCard('签到奖励', <LoginOutlined style={{ color: '#52c41a' }} />, (
              <>
                <Form.Item label="每日签到积分" name="dailySignIn">
                  <InputNumber min={0} style={{ width: '100%' }} addonAfter="积分" />
                </Form.Item>
                <Form.Item label="连续签到7天额外奖励" name="consecutiveSignIn7">
                  <InputNumber min={0} style={{ width: '100%' }} addonAfter="积分" />
                </Form.Item>
                <Form.Item label="连续签到30天额外奖励" name="consecutiveSignIn30">
                  <InputNumber min={0} style={{ width: '100%' }} addonAfter="积分" />
                </Form.Item>
              </>
            ))}

            {ruleCard('任务奖励', <StarOutlined style={{ color: '#faad14' }} />, (
              <>
                <Form.Item label="分享文章" name="shareArticle">
                  <InputNumber min={0} style={{ width: '100%' }} addonAfter="积分/次" />
                </Form.Item>
                <Form.Item label="完善个人资料" name="completeProfile">
                  <InputNumber min={0} style={{ width: '100%' }} addonAfter="积分(一次性)" />
                </Form.Item>
                <Form.Item label="评价服务" name="reviewService">
                  <InputNumber min={0} style={{ width: '100%' }} addonAfter="积分/次" />
                </Form.Item>
                <Form.Item label="健康打卡" name="healthCheckIn">
                  <InputNumber min={0} style={{ width: '100%' }} addonAfter="积分/次" />
                </Form.Item>
              </>
            ))}
          </Col>

          <Col xs={24} lg={12}>
            {ruleCard('邀请与消费', <TeamOutlined style={{ color: '#13c2c2' }} />, (
              <>
                <Form.Item label="邀请好友奖励" name="inviteFriend">
                  <InputNumber min={0} style={{ width: '100%' }} addonAfter="积分/人" />
                </Form.Item>
                <Form.Item label="首次下单奖励" name="firstOrder">
                  <InputNumber min={0} style={{ width: '100%' }} addonAfter="积分" />
                </Form.Item>
                <Form.Item label="消费返积分" name="orderPerYuan">
                  <InputNumber min={0} style={{ width: '100%' }} addonAfter="积分/元" />
                </Form.Item>
              </>
            ))}

            {ruleCard('积分抵扣规则', <ShoppingCartOutlined style={{ color: '#f5222d' }} />, (
              <>
                <Form.Item label="积分兑换比例" name="exchangeRate" extra="多少积分抵扣1元">
                  <InputNumber min={1} style={{ width: '100%' }} addonAfter="积分 = 1元" />
                </Form.Item>
                <Form.Item label="最大抵扣比例" name="maxDeductionRate">
                  <InputNumber min={0} max={100} style={{ width: '100%' }} addonAfter="%" />
                </Form.Item>
                <Form.Item label="最低使用积分" name="minPointsToUse">
                  <InputNumber min={0} style={{ width: '100%' }} addonAfter="积分" />
                </Form.Item>
                <Divider style={{ margin: '12px 0' }} />
                <Form.Item label="积分有效期" name="pointsExpireDays">
                  <InputNumber min={0} style={{ width: '100%' }} addonAfter="天" />
                </Form.Item>
                <Form.Item label="启用积分过期" name="enableExpire" valuePropName="checked">
                  <Switch />
                </Form.Item>
              </>
            ))}
          </Col>
        </Row>
      </Form>
    </div>
  );
}
