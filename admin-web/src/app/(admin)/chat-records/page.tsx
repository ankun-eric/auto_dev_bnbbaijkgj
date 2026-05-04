'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Table, Input, Button, Space, Select, DatePicker, InputNumber, Avatar, message,
} from 'antd';
import { SearchOutlined, ReloadOutlined, EyeOutlined, DownloadOutlined } from '@ant-design/icons';
import { get } from '@/lib/api';
import api from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';
import { useRouter } from 'next/navigation';
import dayjs from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

interface ChatSession {
  id: number;
  user_id: number;
  user_nickname: string;
  user_avatar: string;
  title: string;
  model_name: string;
  message_count: number;
  first_message: string;
  created_at: string;
  updated_at: string;
}

interface ListResponse {
  items: ChatSession[];
  total: number;
  page: number;
  page_size: number;
}

export default function ChatRecordsPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<ChatSession[]>([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const [userSearch, setUserSearch] = useState('');
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [keyword, setKeyword] = useState('');
  const [modelName, setModelName] = useState<string | undefined>(undefined);
  const [minRounds, setMinRounds] = useState<number | null>(null);
  const [maxRounds, setMaxRounds] = useState<number | null>(null);

  const [modelOptions, setModelOptions] = useState<{ label: string; value: string }[]>([]);

  const fetchData = useCallback(async (page = 1, pageSize = 20) => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (userSearch) params.user_search = userSearch;
      if (dateRange?.[0]) params.start_date = dateRange[0].format('YYYY-MM-DD');
      if (dateRange?.[1]) params.end_date = dateRange[1].format('YYYY-MM-DD');
      if (keyword) params.keyword = keyword;
      if (modelName) params.model_name = modelName;
      if (minRounds !== null) params.min_rounds = minRounds;
      if (maxRounds !== null) params.max_rounds = maxRounds;

      const res = await get<ListResponse>('/api/admin/chat-sessions', params);
      setData(res.items || []);
      setPagination({ current: res.page, pageSize: res.page_size, total: res.total });

      const models = new Set<string>();
      (res.items || []).forEach((item) => {
        if (item.model_name) models.add(item.model_name);
      });
      setModelOptions((prev) => {
        const existing = new Set(prev.map((o) => o.value));
        models.forEach((m) => existing.add(m));
        return Array.from(existing).map((m) => ({ label: m, value: m }));
      });
    } catch {
      message.error('获取对话记录失败');
    } finally {
      setLoading(false);
    }
  }, [userSearch, dateRange, keyword, modelName, minRounds, maxRounds]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSearch = () => {
    fetchData(1, pagination.pageSize);
  };

  const handleReset = () => {
    setUserSearch('');
    setDateRange(null);
    setKeyword('');
    setModelName(undefined);
    setMinRounds(null);
    setMaxRounds(null);
  };

  const handleExport = async (id: number, format: 'xlsx' | 'csv') => {
    try {
      const res = await api.get(`/api/admin/chat-sessions/${id}/export`, {
        params: { format },
        responseType: 'blob',
      });
      const blob = new Blob([res.data]);
      const disposition = res.headers['content-disposition'];
      let filename = `chat_${id}.${format}`;
      if (disposition) {
        const match = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';\n]+)/i);
        if (match) filename = decodeURIComponent(match[1]);
      }
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      message.error('导出失败');
    }
  };

  const columns = [
    {
      title: '对话ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '用户信息',
      key: 'user',
      width: 160,
      render: (_: any, record: ChatSession) => (
        <Space>
          <Avatar src={resolveAssetUrl(record.user_avatar)} size="small">
            {record.user_nickname?.[0] || '?'}
          </Avatar>
          <span>{record.user_nickname || '-'}</span>
        </Space>
      ),
    },
    {
      title: '首条消息摘要',
      key: 'first_message',
      ellipsis: true,
      render: (_: any, record: ChatSession) => {
        const text = record.first_message || record.title || '-';
        return text.length > 30 ? text.slice(0, 30) + '...' : text;
      },
    },
    {
      title: '对话轮数',
      dataIndex: 'message_count',
      key: 'message_count',
      width: 90,
    },
    {
      title: 'AI模型',
      dataIndex: 'model_name',
      key: 'model_name',
      width: 140,
    },
    {
      title: '对话时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '操作',
      key: 'action',
      width: 240,
      render: (_: any, record: ChatSession) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => router.push(`/chat-records/${record.id}`)}>
            查看详情
          </Button>
          <Button type="link" size="small" icon={<DownloadOutlined />} onClick={() => handleExport(record.id, 'xlsx')}>
            Excel
          </Button>
          <Button type="link" size="small" icon={<DownloadOutlined />} onClick={() => handleExport(record.id, 'csv')}>
            CSV
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>AI对话记录管理</Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索用户昵称/手机号"
          prefix={<SearchOutlined />}
          value={userSearch}
          onChange={(e) => setUserSearch(e.target.value)}
          onPressEnter={handleSearch}
          style={{ width: 200 }}
          allowClear
        />
        <RangePicker
          value={dateRange as any}
          onChange={(dates) => setDateRange(dates as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null)}
        />
        <Input
          placeholder="在对话内容中搜索"
          prefix={<SearchOutlined />}
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onPressEnter={handleSearch}
          style={{ width: 200 }}
          allowClear
        />
        <Select
          placeholder="全部模型"
          value={modelName}
          onChange={(v) => setModelName(v)}
          allowClear
          style={{ width: 160 }}
          options={modelOptions}
        />
        <Space>
          <InputNumber
            placeholder="最小轮数"
            min={0}
            value={minRounds}
            onChange={(v) => setMinRounds(v)}
            style={{ width: 110 }}
          />
          <span>~</span>
          <InputNumber
            placeholder="最大轮数"
            min={0}
            value={maxRounds}
            onChange={(v) => setMaxRounds(v)}
            style={{ width: 110 }}
          />
        </Space>
        <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>搜索</Button>
        <Button icon={<ReloadOutlined />} onClick={() => { handleReset(); setTimeout(() => fetchData(1, pagination.pageSize), 0); }}>重置</Button>
      </Space>
      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total: pagination.total,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1000 }}
      />
    </div>
  );
}
