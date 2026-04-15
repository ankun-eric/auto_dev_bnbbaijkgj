'use client';

import React, { useEffect, useState } from 'react';
import { Table, Card, Row, Col, Statistic, Typography, message } from 'antd';
import { TeamOutlined, UserAddOutlined, CalendarOutlined } from '@ant-design/icons';
import { get } from '@/lib/api';

const { Title } = Typography;

interface RankingItem {
  user_no: string;
  nickname: string;
  phone: string;
  referral_count: number;
}

interface ReferralStats {
  total_referrals: number;
  today_referrals: number;
  month_referrals: number;
  ranking: RankingItem[];
  total: number;
  page: number;
  page_size: number;
}

export default function ReferralPage() {
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState({ total: 0, today: 0, month: 0 });
  const [ranking, setRanking] = useState<RankingItem[]>([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const res = await get<ReferralStats>('/api/admin/referral/stats', { page, page_size: pageSize });
      setStats({
        total: res.total_referrals ?? 0,
        today: res.today_referrals ?? 0,
        month: res.month_referrals ?? 0,
      });
      const items = res.ranking ?? [];
      setRanking(items);
      setPagination({
        current: res.page ?? page,
        pageSize: res.page_size ?? pageSize,
        total: res.total ?? items.length,
      });
    } catch (e: unknown) {
      const err = e as { response?: { data?: { message?: string } }; message?: string };
      message.error(err?.response?.data?.message || err?.message || '加载推荐统计失败');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: '排名',
      key: 'rank',
      width: 80,
      render: (_: unknown, __: unknown, index: number) =>
        (pagination.current - 1) * pagination.pageSize + index + 1,
    },
    { title: '用户编号', dataIndex: 'user_no', key: 'user_no', width: 140 },
    { title: '昵称', dataIndex: 'nickname', key: 'nickname', width: 140 },
    { title: '手机号', dataIndex: 'phone', key: 'phone', width: 140 },
    {
      title: '推荐人数',
      dataIndex: 'referral_count',
      key: 'referral_count',
      width: 120,
      sorter: (a: RankingItem, b: RankingItem) => a.referral_count - b.referral_count,
      defaultSortOrder: 'descend' as const,
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>推荐管理</Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Statistic
              title="总推荐用户数"
              value={stats.total}
              prefix={<TeamOutlined />}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="今日新增"
              value={stats.today}
              prefix={<UserAddOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="本月新增"
              value={stats.month}
              prefix={<CalendarOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
      </Row>

      <Title level={5} style={{ marginBottom: 16 }}>推荐排行榜</Title>

      <Table
        columns={columns}
        dataSource={ranking}
        rowKey="user_no"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
      />
    </div>
  );
}
