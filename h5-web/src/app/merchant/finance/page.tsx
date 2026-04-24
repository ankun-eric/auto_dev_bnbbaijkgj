'use client';

import React from 'react';
import { Card, Col, Row, Space, Typography, Button } from 'antd';
import { AccountBookOutlined, FileTextOutlined, DownloadOutlined } from '@ant-design/icons';
import { useRouter } from 'next/navigation';

const { Title, Paragraph } = Typography;

export default function MerchantFinancePage() {
  const router = useRouter();
  return (
    <div>
      <Title level={3}>财务对账</Title>
      <Paragraph type="secondary">
        查看营业流水、对账结算、发票信息和财务导出。
      </Paragraph>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={8}>
          <Card hoverable onClick={() => router.push('/merchant/settlement')}>
            <Space align="start" size={16}>
              <AccountBookOutlined style={{ fontSize: 32, color: '#52c41a' }} />
              <div>
                <Title level={5} style={{ margin: 0 }}>对账结算</Title>
                <Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
                  查看对账单、确认账期
                </Paragraph>
              </div>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card hoverable onClick={() => router.push('/merchant/invoice')}>
            <Space align="start" size={16}>
              <FileTextOutlined style={{ fontSize: 32, color: '#1677ff' }} />
              <div>
                <Title level={5} style={{ margin: 0 }}>发票信息</Title>
                <Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
                  管理发票抬头与记录
                </Paragraph>
              </div>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card hoverable onClick={() => router.push('/merchant/downloads')}>
            <Space align="start" size={16}>
              <DownloadOutlined style={{ fontSize: 32, color: '#fa8c16' }} />
              <div>
                <Title level={5} style={{ margin: 0 }}>财务导出</Title>
                <Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
                  下载核销流水、财务报表
                </Paragraph>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>
      <div style={{ marginTop: 24 }}>
        <Button onClick={() => router.push('/merchant/reports')}>查看报表分析</Button>
      </div>
    </div>
  );
}
