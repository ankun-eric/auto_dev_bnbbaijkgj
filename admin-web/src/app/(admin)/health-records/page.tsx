'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Descriptions,
  Drawer,
  Input,
  Progress,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { EyeOutlined, HeartOutlined, SearchOutlined, UserOutlined } from '@ant-design/icons';
import { get } from '@/lib/api';

const { Title, Text } = Typography;

interface HealthUserItem {
  user_id: number;
  phone: string;
  nickname: string;
  member_count: number;
  avg_completeness: number;
}

interface HealthProfile {
  id: number;
  name: string | null;
  gender: string | null;
  birthday: string | null;
  height: number | null;
  weight: number | null;
  blood_type: string | null;
  smoking: string | null;
  drinking: string | null;
  exercise_habit: string | null;
  sleep_habit: string | null;
  diet_habit: string | null;
  chronic_diseases: string[] | null;
  medical_histories: string[] | null;
  genetic_diseases: string[] | null;
  allergies: string[] | null;
  completeness: number;
}

interface MemberItem {
  member_id: number;
  is_self: boolean;
  nickname: string;
  relationship_type: string;
  health_profile: HealthProfile | null;
}

function CompletenessBar({ value }: { value: number }) {
  const color = value >= 80 ? '#52c41a' : value >= 50 ? '#faad14' : '#ff4d4f';
  return (
    <Space>
      <Progress percent={value} size="small" strokeColor={color} style={{ width: 100 }} showInfo={false} />
      <Text style={{ color, minWidth: 40 }}>{value}%</Text>
    </Space>
  );
}

function HealthProfileCard({ member }: { member: MemberItem }) {
  const hp = member.health_profile;
  const genderLabel = (g: string | null) => (g === 'male' ? '男' : g === 'female' ? '女' : g || '-');

  return (
    <Card
      size="small"
      style={{ marginBottom: 12 }}
      title={
        <Space>
          <span style={{ fontSize: 20 }}>{member.is_self ? '👤' : '👨‍👩‍👧'}</span>
          <Text strong>{member.nickname || '未命名'}</Text>
          <Tag color="blue">{member.relationship_type || '-'}</Tag>
          {member.is_self && <Tag color="green">本人</Tag>}
        </Space>
      }
      extra={
        hp ? (
          <Space>
            <Text type="secondary">完整度</Text>
            <CompletenessBar value={hp.completeness} />
          </Space>
        ) : (
          <Tag color="default">暂无档案</Tag>
        )
      }
    >
      {hp ? (
        <Descriptions size="small" column={3} bordered>
          <Descriptions.Item label="姓名">{hp.name || '-'}</Descriptions.Item>
          <Descriptions.Item label="性别">{genderLabel(hp.gender)}</Descriptions.Item>
          <Descriptions.Item label="生日">{hp.birthday || '-'}</Descriptions.Item>
          <Descriptions.Item label="身高">{hp.height != null ? `${hp.height} cm` : '-'}</Descriptions.Item>
          <Descriptions.Item label="体重">{hp.weight != null ? `${hp.weight} kg` : '-'}</Descriptions.Item>
          <Descriptions.Item label="血型">{hp.blood_type || '-'}</Descriptions.Item>
          <Descriptions.Item label="吸烟">{hp.smoking || '-'}</Descriptions.Item>
          <Descriptions.Item label="饮酒">{hp.drinking || '-'}</Descriptions.Item>
          <Descriptions.Item label="运动习惯">{hp.exercise_habit || '-'}</Descriptions.Item>
          <Descriptions.Item label="慢性病" span={3}>
            {hp.chronic_diseases?.length ? hp.chronic_diseases.join('、') : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="既往病史" span={3}>
            {hp.medical_histories?.length ? hp.medical_histories.join('、') : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="家族遗传病" span={3}>
            {hp.genetic_diseases?.length ? hp.genetic_diseases.join('、') : '-'}
          </Descriptions.Item>
        </Descriptions>
      ) : (
        <Text type="secondary">该成员尚未填写健康档案</Text>
      )}
    </Card>
  );
}

export default function HealthRecordsPage() {
  const [data, setData] = useState<HealthUserItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [selectedUser, setSelectedUser] = useState<HealthUserItem | null>(null);
  const [members, setMembers] = useState<MemberItem[]>([]);

  const fetchData = useCallback(async (page = 1, pageSize = 20) => {
    setLoading(true);
    try {
      const res = await get<{ items: HealthUserItem[]; total: number; page: number; page_size: number }>(
        '/api/admin/health/users',
        { page, page_size: pageSize, ...(keyword ? { keyword } : {}) }
      );
      setData(res.items ?? []);
      setPagination({ current: res.page ?? page, pageSize: res.page_size ?? pageSize, total: res.total ?? 0 });
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [keyword]);

  useEffect(() => {
    fetchData();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openDrawer = async (user: HealthUserItem) => {
    setSelectedUser(user);
    setDrawerOpen(true);
    setDrawerLoading(true);
    try {
      const res = await get<{ items: MemberItem[] }>(`/api/admin/health/users/${user.user_id}/members`);
      setMembers(res.items ?? []);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '加载成员失败');
      setMembers([]);
    } finally {
      setDrawerLoading(false);
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'user_id', key: 'user_id', width: 70 },
    { title: '手机号', dataIndex: 'phone', key: 'phone', width: 140 },
    {
      title: '昵称',
      dataIndex: 'nickname',
      key: 'nickname',
      width: 140,
      render: (v: string) => (
        <Space>
          <UserOutlined style={{ color: '#52c41a' }} />
          {v || '-'}
        </Space>
      ),
    },
    {
      title: '家庭成员数',
      dataIndex: 'member_count',
      key: 'member_count',
      width: 110,
      render: (v: number) => <Tag color="blue">{v} 人</Tag>,
    },
    {
      title: '平均档案完整度',
      dataIndex: 'avg_completeness',
      key: 'avg_completeness',
      width: 200,
      render: (v: number) => <CompletenessBar value={v} />,
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, record: HealthUserItem) => (
        <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => openDrawer(record)}>
          查看详情
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>
        <HeartOutlined style={{ marginRight: 8, color: '#ff4d4f' }} />
        用户健康档案
      </Title>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索手机号/昵称"
          prefix={<SearchOutlined />}
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onPressEnter={() => fetchData(1)}
          style={{ width: 240 }}
          allowClear
        />
        <Button type="primary" onClick={() => fetchData(1)}>
          搜索
        </Button>
        <Button
          onClick={() => {
            setKeyword('');
            setTimeout(() => fetchData(1), 0);
          }}
        >
          重置
        </Button>
      </Space>

      <Table
        columns={columns}
        dataSource={data}
        rowKey="user_id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 800 }}
      />

      <Drawer
        title={
          selectedUser ? (
            <Space>
              <UserOutlined />
              {selectedUser.nickname || selectedUser.phone} 的健康档案
            </Space>
          ) : '健康档案详情'
        }
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={780}
        bodyStyle={{ padding: 16 }}
      >
        {drawerLoading ? (
          <div style={{ textAlign: 'center', padding: 60 }}>
            <Spin size="large" />
          </div>
        ) : members.length === 0 ? (
          <Text type="secondary">该用户暂无家庭成员记录</Text>
        ) : (
          members.map((m) => <HealthProfileCard key={m.member_id} member={m} />)
        )}
      </Drawer>
    </div>
  );
}
