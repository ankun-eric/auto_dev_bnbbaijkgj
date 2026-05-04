'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Table, Input, Button, Space, Select, DatePicker, Tag, Card,
  Statistic, Row, Col, Tooltip, Drawer, Avatar, Image, Descriptions, message,
} from 'antd';
import {
  SearchOutlined, ReloadOutlined, MedicineBoxOutlined, PlusCircleOutlined,
  ExperimentOutlined, CalendarOutlined, MessageOutlined,
} from '@ant-design/icons';
import { get } from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const DRUG_CATEGORY_OPTIONS = [
  { label: '处方药', value: '处方药' },
  { label: '非处方药', value: '非处方药' },
  { label: '中成药', value: '中成药' },
  { label: '保健品', value: '保健品' },
];

const DRUG_CATEGORY_COLORS: Record<string, string> = {
  '处方药': 'red',
  '非处方药': 'green',
  '中成药': 'orange',
  '保健品': 'blue',
};

interface DrugDetail {
  id: number;
  created_at: string;
  user_nickname: string;
  user_phone: string;
  user_avatar: string;
  drug_name: string;
  drug_category: string;
  dosage: string;
  precautions: string;
  provider_name: string;
  original_image_url: string;
  ocr_raw_text: string;
  ai_structured_result: any;
  session_id?: number;
}

interface ListResponse {
  items: DrugDetail[];
  total: number;
  page: number;
  page_size: number;
}

interface StatsData {
  total_drugs: number;
  today_new: number;
  drug_categories: number;
  month_drugs: number;
}

interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
  content_type?: 'text' | 'image';
  image_urls?: string[];
  created_at?: string;
  disclaimer?: string;
}

interface ConversationData {
  session_id: number;
  messages: ConversationMessage[];
  drug_name?: string;
}

const msgBubbleStyle = (isUser: boolean): React.CSSProperties => ({
  maxWidth: '80%',
  padding: '10px 14px',
  borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
  background: isUser ? '#1677ff' : '#f5f5f5',
  color: isUser ? '#fff' : '#333',
  wordBreak: 'break-word',
  lineHeight: 1.6,
});

function maskPhone(phone: string): string {
  if (!phone || phone.length < 7) return phone || '-';
  return phone.slice(0, 3) + '****' + phone.slice(-4);
}

export default function DrugDetailsPage() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<DrugDetail[]>([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [stats, setStats] = useState<StatsData>({ total_drugs: 0, today_new: 0, drug_categories: 0, month_drugs: 0 });

  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [keyword, setKeyword] = useState('');
  const [drugName, setDrugName] = useState('');
  const [drugCategory, setDrugCategory] = useState<string | undefined>(undefined);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [detail, setDetail] = useState<DrugDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [convDrawerOpen, setConvDrawerOpen] = useState(false);
  const [convLoading, setConvLoading] = useState(false);
  const [conversation, setConversation] = useState<ConversationData | null>(null);
  const [convDrugName, setConvDrugName] = useState('');

  const fetchStats = useCallback(async () => {
    try {
      const res = await get<any>('/api/admin/drug-details/statistics');
      setStats({
        total_drugs: res.total ?? res.total_drugs ?? 0,
        today_new: res.today_count ?? res.today_new ?? 0,
        drug_categories: res.drug_types_count ?? res.drug_categories ?? 0,
        month_drugs: res.month_count ?? res.month_drugs ?? 0,
      });
    } catch {
      // ignore
    }
  }, []);

  const fetchData = useCallback(async (page = 1, pageSize = 20) => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (dateRange?.[0]) params.start_date = dateRange[0].format('YYYY-MM-DD');
      if (dateRange?.[1]) params.end_date = dateRange[1].format('YYYY-MM-DD');
      if (keyword) params.keyword = keyword;
      if (drugName) params.drug_name = drugName;
      if (drugCategory) params.drug_category = drugCategory;

      const res = await get<ListResponse>('/api/admin/drug-details', params);
      setData(res.items || []);
      setPagination({ current: res.page, pageSize: res.page_size, total: res.total });
    } catch {
      message.error('获取拍照识药记录明细失败');
    } finally {
      setLoading(false);
    }
  }, [dateRange, keyword, drugName, drugCategory]);

  useEffect(() => {
    fetchData();
    fetchStats();
  }, [fetchData, fetchStats]);

  const handleSearch = () => {
    fetchData(1, pagination.pageSize);
  };

  const handleReset = () => {
    setDateRange(null);
    setKeyword('');
    setDrugName('');
    setDrugCategory(undefined);
  };

  const handleViewDetail = async (record: DrugDetail) => {
    setDrawerOpen(true);
    setDetailLoading(true);
    try {
      const res = await get<DrugDetail>(`/api/admin/drug-details/${record.id}`);
      setDetail(res);
    } catch {
      message.error('获取详情失败');
      setDetail(record);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleViewConversation = async (record: DrugDetail) => {
    setConvDrugName(record.drug_name || '未知药品');
    setConvDrawerOpen(true);
    setConvLoading(true);
    try {
      const res = await get<ConversationData>(`/api/admin/drug-details/${record.id}/conversation`);
      setConversation(res);
    } catch {
      message.error('获取对话记录失败');
      setConversation(null);
    } finally {
      setConvLoading(false);
    }
  };

  const columns = [
    {
      title: '识别时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: '关联用户',
      key: 'user',
      width: 160,
      render: (_: any, record: DrugDetail) => (
        <Space>
          <span>{record.user_nickname || '-'}</span>
          <Text type="secondary">{maskPhone(record.user_phone)}</Text>
        </Space>
      ),
    },
    {
      title: '药品名称',
      dataIndex: 'drug_name',
      key: 'drug_name',
      width: 140,
    },
    {
      title: '药品分类',
      dataIndex: 'drug_category',
      key: 'drug_category',
      width: 100,
      render: (v: string) => <Tag color={DRUG_CATEGORY_COLORS[v] || 'default'}>{v || '-'}</Tag>,
    },
    {
      title: '用法用量',
      dataIndex: 'dosage',
      key: 'dosage',
      ellipsis: true,
      render: (v: string) => (
        <Tooltip title={v}>
          <span>{v && v.length > 20 ? v.slice(0, 20) + '...' : v || '-'}</span>
        </Tooltip>
      ),
    },
    {
      title: '注意事项/禁忌',
      dataIndex: 'precautions',
      key: 'precautions',
      ellipsis: true,
      render: (v: string) => (
        <Tooltip title={v}>
          <span>{v && v.length > 20 ? v.slice(0, 20) + '...' : v || '-'}</span>
        </Tooltip>
      ),
    },
    {
      title: '使用厂商',
      dataIndex: 'provider_name',
      key: 'provider_name',
      width: 100,
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: DrugDetail) => (
        <Space size={0}>
          <Button type="link" size="small" onClick={() => handleViewDetail(record)}>
            详情
          </Button>
          <Button
            type="link"
            size="small"
            icon={<MessageOutlined />}
            disabled={!record.session_id}
            onClick={() => handleViewConversation(record)}
          >
            查看对话
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>拍照识药记录明细</Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="总识药数"
              value={stats.total_drugs}
              prefix={<MedicineBoxOutlined style={{ color: '#1890ff' }} />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="今日新增"
              value={stats.today_new}
              prefix={<PlusCircleOutlined style={{ color: '#52c41a' }} />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="药品种类数"
              value={stats.drug_categories}
              prefix={<ExperimentOutlined style={{ color: '#fa8c16' }} />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="本月识别数"
              value={stats.month_drugs}
              prefix={<CalendarOutlined style={{ color: '#722ed1' }} />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col>
          <RangePicker
            value={dateRange as any}
            onChange={(dates) => setDateRange(dates as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null)}
          />
        </Col>
        <Col>
          <Input
            placeholder="用户搜索"
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 180 }}
            allowClear
          />
        </Col>
        <Col>
          <Input
            placeholder="药品名称搜索"
            value={drugName}
            onChange={(e) => setDrugName(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 180 }}
            allowClear
          />
        </Col>
        <Col>
          <Select
            placeholder="药品分类"
            value={drugCategory}
            onChange={(v) => setDrugCategory(v)}
            allowClear
            style={{ width: 130 }}
            options={DRUG_CATEGORY_OPTIONS}
          />
        </Col>
        <Col>
          <Space>
            <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>搜索</Button>
            <Button icon={<ReloadOutlined />} onClick={() => { handleReset(); setTimeout(() => fetchData(1, pagination.pageSize), 0); }}>重置</Button>
          </Space>
        </Col>
      </Row>

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
        scroll={{ x: 1100 }}
      />

      <Drawer
        title="拍照识药详情"
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setDetail(null); }}
        width={700}
        loading={detailLoading}
      >
        {detail && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <Card size="small" title="用户信息">
              <Space>
                <Avatar src={resolveAssetUrl(detail.user_avatar)} size={48}>{detail.user_nickname?.[0]}</Avatar>
                <div>
                  <div><Text strong>{detail.user_nickname || '-'}</Text></div>
                  <div><Text type="secondary">{detail.user_phone || '-'}</Text></div>
                </div>
              </Space>
            </Card>

            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="识别时间">
                {detail.created_at ? dayjs(detail.created_at).format('YYYY-MM-DD HH:mm:ss') : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="使用厂商">{detail.provider_name || '-'}</Descriptions.Item>
            </Descriptions>

            {detail.original_image_url && (
              <Card size="small" title="原始药品图片">
                <Image
                  src={detail.original_image_url}
                  style={{ maxWidth: '100%', maxHeight: 300 }}
                  fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN8/+F/PQAJpAN4kNMRdQAAAABJRU5ErkJggg=="
                />
              </Card>
            )}

            <Card size="small" title="OCR原始文字">
              <pre style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: 12, borderRadius: 6, maxHeight: 200, overflow: 'auto', margin: 0 }}>
                {detail.ocr_raw_text || '暂无'}
              </pre>
            </Card>

            <Card size="small" title="AI结构化结果">
              {detail.ai_structured_result ? (
                <Descriptions column={1} size="small" bordered>
                  <Descriptions.Item label="药品名称">
                    {detail.ai_structured_result.drug_name || detail.drug_name || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="药品分类">
                    <Tag color={DRUG_CATEGORY_COLORS[detail.ai_structured_result.drug_category || detail.drug_category] || 'default'}>
                      {detail.ai_structured_result.drug_category || detail.drug_category || '-'}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="用法用量">
                    {detail.ai_structured_result.dosage || detail.dosage || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="注意事项">
                    {detail.ai_structured_result.precautions || detail.precautions || '-'}
                  </Descriptions.Item>
                </Descriptions>
              ) : (
                <pre style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: 12, borderRadius: 6, margin: 0 }}>
                  暂无
                </pre>
              )}
            </Card>

            {detail.ai_structured_result && (
              <Card size="small" title="完整AI分析数据">
                <pre style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: 12, borderRadius: 6, maxHeight: 300, overflow: 'auto', margin: 0 }}>
                  {JSON.stringify(detail.ai_structured_result, null, 2)}
                </pre>
              </Card>
            )}
          </div>
        )}
      </Drawer>

      <Drawer
        title={`对话记录 - ${convDrugName}`}
        open={convDrawerOpen}
        onClose={() => { setConvDrawerOpen(false); setConversation(null); }}
        width={600}
        loading={convLoading}
      >
        {conversation && conversation.messages && conversation.messages.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: '8px 0' }}>
            {conversation.messages.map((msg, idx) => {
              const isUser = msg.role === 'user';
              return (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    justifyContent: isUser ? 'flex-end' : 'flex-start',
                  }}
                >
                  <div style={{ maxWidth: '80%' }}>
                    <div style={msgBubbleStyle(isUser)}>
                      {msg.image_urls && msg.image_urls.length > 0 ? (
                        <Space direction="vertical" size={4}>
                          {msg.image_urls.map((url, imgIdx) => (
                            <Image
                              key={imgIdx}
                              src={url}
                              style={{ maxWidth: '100%', maxHeight: 200, borderRadius: 8 }}
                              fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN8/+F/PQAJpAN4kNMRdQAAAABJRU5ErkJggg=="
                            />
                          ))}
                          {msg.content && <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>}
                        </Space>
                      ) : (
                        <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
                      )}
                    </div>
                    {msg.disclaimer && (
                      <div style={{ color: '#999', fontSize: 12, fontStyle: 'italic', marginTop: 4, padding: '0 4px' }}>
                        {msg.disclaimer}
                      </div>
                    )}
                    {msg.created_at && (
                      <div style={{ color: '#bbb', fontSize: 11, marginTop: 4, textAlign: isUser ? 'right' : 'left', padding: '0 4px' }}>
                        {dayjs(msg.created_at).format('YYYY-MM-DD HH:mm:ss')}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          !convLoading && (
            <div style={{ textAlign: 'center', color: '#999', padding: '60px 0' }}>
              暂无对话记录
            </div>
          )
        )}
      </Drawer>
    </div>
  );
}
