'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table,
  Button,
  Space,
  Tag,
  Modal,
  Card,
  Statistic,
  Input,
  Select,
  DatePicker,
  Typography,
  Descriptions,
  Row,
  Col,
  message,
} from 'antd';
import {
  EyeOutlined,
  MailOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  MessageOutlined,
} from '@ant-design/icons';
import { get } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

const MESSAGE_TYPE_MAP: Record<string, { label: string; color: string }> = {
  system_notice: { label: '系统通知', color: 'blue' },
  operation_activity: { label: '运营活动', color: 'orange' },
  maintenance: { label: '维护通知', color: 'red' },
};

interface MessageRecord {
  id: number;
  message_type: string;
  recipient_user_id: number;
  recipient_nickname?: string;
  recipient_phone?: string;
  sender_user_id?: number;
  sender_nickname?: string;
  title: string;
  content: string;
  is_read: boolean;
  read_at?: string;
  created_at: string;
}

interface MessageStats {
  total: number;
  unread: number;
  type_counts: Record<string, number>;
}

export default function SystemMessagesPage() {
  const [records, setRecords] = useState<MessageRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [detailVisible, setDetailVisible] = useState(false);
  const [currentRecord, setCurrentRecord] = useState<MessageRecord | null>(null);
  const [stats, setStats] = useState<MessageStats | null>(null);

  const [messageType, setMessageType] = useState<string | undefined>(undefined);
  const [readStatus, setReadStatus] = useState<string | undefined>(undefined);
  const [keyword, setKeyword] = useState('');
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);

  const fetchStats = useCallback(async () => {
    try {
      const res = await get<MessageStats>('/api/admin/messages/stats');
      setStats(res);
    } catch {
      setStats(null);
    }
  }, []);

  const fetchData = useCallback(async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (messageType) params.message_type = messageType;
      if (readStatus === 'read') params.is_read = true;
      if (readStatus === 'unread') params.is_read = false;
      if (keyword) params.keyword = keyword;
      if (dateRange?.[0]) params.start_date = dateRange[0].format('YYYY-MM-DD');
      if (dateRange?.[1]) params.end_date = dateRange[1].format('YYYY-MM-DD');

      const res = await get<{
        items?: MessageRecord[];
        list?: MessageRecord[];
        total?: number;
        page?: number;
        page_size?: number;
      }>('/api/admin/messages', params);

      const items = res.items ?? res.list ?? [];
      setRecords(Array.isArray(items) ? items : []);
      setPagination((prev) => ({
        ...prev,
        current: res.page ?? page,
        pageSize: res.page_size ?? pageSize,
        total: res.total ?? items.length,
      }));
    } catch {
      setRecords([]);
      setPagination((prev) => ({ ...prev, current: page, pageSize, total: 0 }));
    } finally {
      setLoading(false);
    }
  }, [messageType, readStatus, keyword, dateRange]);

  useEffect(() => {
    fetchData();
    fetchStats();
  }, []);

  const handleSearch = () => {
    fetchData(1, pagination.pageSize);
  };

  const handleReset = () => {
    setMessageType(undefined);
    setReadStatus(undefined);
    setKeyword('');
    setDateRange(null);
    setTimeout(() => fetchData(1, pagination.pageSize), 0);
  };

  const typeTag = (type: string) => {
    const cfg = MESSAGE_TYPE_MAP[type];
    return cfg ? <Tag color={cfg.color}>{cfg.label}</Tag> : <Tag>{type}</Tag>;
  };

  const columns = [
    { title: '消息ID', dataIndex: 'id', key: 'id', width: 80 },
    {
      title: '消息类型',
      dataIndex: 'message_type',
      key: 'message_type',
      width: 120,
      render: (v: string) => typeTag(v),
    },
    {
      title: '发送对象',
      key: 'recipient',
      width: 160,
      render: (_: unknown, record: MessageRecord) => (
        <div>
          <div>{record.recipient_nickname || '-'}</div>
          <div style={{ fontSize: 12, color: '#999' }}>{record.recipient_phone || '-'}</div>
        </div>
      ),
    },
    {
      title: '消息标题',
      dataIndex: 'title',
      key: 'title',
      width: 200,
      ellipsis: true,
    },
    {
      title: '消息内容',
      dataIndex: 'content',
      key: 'content',
      width: 250,
      ellipsis: true,
      render: (v: string) => (v && v.length > 40 ? `${v.substring(0, 40)}...` : v || '-'),
    },
    {
      title: '发送时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (v: string) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'),
    },
    {
      title: '阅读状态',
      dataIndex: 'is_read',
      key: 'is_read',
      width: 100,
      render: (v: boolean) =>
        v ? (
          <Tag icon={<CheckCircleOutlined />} color="success">已读</Tag>
        ) : (
          <Tag icon={<ClockCircleOutlined />} color="warning">未读</Tag>
        ),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, record: MessageRecord) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => {
            setCurrentRecord(record);
            setDetailVisible(true);
          }}
        >
          详情
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>系统消息管理</Title>

      {stats && (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={6}>
            <Card bordered={false} style={{ background: '#f6ffed' }}>
              <Statistic
                title="消息总数"
                value={stats.total}
                prefix={<MessageOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card bordered={false} style={{ background: '#fff7e6' }}>
              <Statistic
                title="未读消息"
                value={stats.unread}
                prefix={<ClockCircleOutlined />}
                valueStyle={{ color: '#fa8c16' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card bordered={false} style={{ background: '#e6f7ff' }}>
              <Statistic
                title="已读消息"
                value={stats.total - stats.unread}
                prefix={<CheckCircleOutlined />}
                valueStyle={{ color: '#1890ff' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card bordered={false} style={{ background: '#f9f0ff' }}>
              <Statistic
                title="消息类型数"
                value={Object.keys(stats.type_counts).length}
                prefix={<MailOutlined />}
                valueStyle={{ color: '#722ed1' }}
              />
            </Card>
          </Col>
        </Row>
      )}

      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          placeholder="消息类型"
          allowClear
          style={{ width: 160 }}
          value={messageType}
          onChange={setMessageType}
          options={[
            { label: '系统通知', value: 'system_notice' },
            { label: '运营活动', value: 'operation_activity' },
            { label: '维护通知', value: 'maintenance' },
          ]}
        />
        <Select
          placeholder="阅读状态"
          allowClear
          style={{ width: 120 }}
          value={readStatus}
          onChange={setReadStatus}
          options={[
            { label: '已读', value: 'read' },
            { label: '未读', value: 'unread' },
          ]}
        />
        <Input
          placeholder="用户手机号/姓名"
          style={{ width: 180 }}
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          allowClear
        />
        <RangePicker
          value={dateRange as [dayjs.Dayjs, dayjs.Dayjs] | null}
          onChange={(dates) => setDateRange(dates as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null)}
        />
        <Button type="primary" onClick={handleSearch}>查询</Button>
        <Button onClick={handleReset}>重置</Button>
      </Space>

      <Table
        columns={columns}
        dataSource={records}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1200 }}
      />

      <Modal
        title="消息详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={640}
      >
        {currentRecord && (
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="消息ID">{currentRecord.id}</Descriptions.Item>
            <Descriptions.Item label="消息类型">{typeTag(currentRecord.message_type)}</Descriptions.Item>
            <Descriptions.Item label="接收用户">{currentRecord.recipient_nickname || '-'}</Descriptions.Item>
            <Descriptions.Item label="用户手机号">{currentRecord.recipient_phone || '-'}</Descriptions.Item>
            <Descriptions.Item label="发送者">{currentRecord.sender_nickname || '系统'}</Descriptions.Item>
            <Descriptions.Item label="阅读状态">
              {currentRecord.is_read ? (
                <Tag icon={<CheckCircleOutlined />} color="success">已读</Tag>
              ) : (
                <Tag icon={<ClockCircleOutlined />} color="warning">未读</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="消息标题" span={2}>{currentRecord.title}</Descriptions.Item>
            <Descriptions.Item label="消息内容" span={2}>
              <div style={{ whiteSpace: 'pre-wrap', maxHeight: 300, overflowY: 'auto' }}>
                {currentRecord.content}
              </div>
            </Descriptions.Item>
            <Descriptions.Item label="发送时间">
              {currentRecord.created_at ? dayjs(currentRecord.created_at).format('YYYY-MM-DD HH:mm:ss') : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="阅读时间">
              {currentRecord.read_at ? dayjs(currentRecord.read_at).format('YYYY-MM-DD HH:mm:ss') : '-'}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
}
