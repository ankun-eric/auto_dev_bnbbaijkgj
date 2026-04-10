'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Table, Button, Space, Modal, Input, Typography, message, Popconfirm, Empty,
} from 'antd';
import {
  PlusOutlined, ArrowUpOutlined, ArrowDownOutlined, DeleteOutlined, SaveOutlined, SearchOutlined,
} from '@ant-design/icons';
import { get, post, del } from '@/lib/api';

const { Title } = Typography;

interface City {
  id: number;
  name: string;
  province: string;
}

interface CityListResponse {
  items: City[];
  total: number;
  page: number;
  page_size: number;
}

export default function CityManagementPage() {
  const [hotCities, setHotCities] = useState<City[]>([]);
  const [loading, setLoading] = useState(false);
  const [sortChanged, setSortChanged] = useState(false);
  const [savingSort, setSavingSort] = useState(false);

  const [modalOpen, setModalOpen] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [searchResults, setSearchResults] = useState<City[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchTotal, setSearchTotal] = useState(0);
  const [searchPage, setSearchPage] = useState(1);
  const searchPageSize = 20;

  const hotCityIdsRef = useRef<Set<number>>(new Set());

  const fetchHotCities = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<any>('/api/admin/cities/hot');
      const list = Array.isArray(res)
        ? res
        : res?.cities ?? res?.items ?? [];
      setHotCities(list);
      hotCityIdsRef.current = new Set(list.map((c) => c.id));
    } catch {
      message.error('获取热门城市列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHotCities();
  }, [fetchHotCities]);

  const handleMoveUp = (index: number) => {
    if (index <= 0) return;
    const next = [...hotCities];
    [next[index - 1], next[index]] = [next[index], next[index - 1]];
    setHotCities(next);
    setSortChanged(true);
  };

  const handleMoveDown = (index: number) => {
    if (index >= hotCities.length - 1) return;
    const next = [...hotCities];
    [next[index], next[index + 1]] = [next[index + 1], next[index]];
    setHotCities(next);
    setSortChanged(true);
  };

  const handleRemove = async (cityId: number) => {
    try {
      await del(`/api/admin/cities/hot/${cityId}`);
      message.success('已移除热门城市');
      setSortChanged(false);
      fetchHotCities();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '移除失败');
    }
  };

  const handleSaveSort = async () => {
    setSavingSort(true);
    try {
      await post('/api/admin/cities/hot', { city_ids: hotCities.map((c) => c.id) });
      message.success('排序保存成功');
      setSortChanged(false);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存排序失败');
    } finally {
      setSavingSort(false);
    }
  };

  const handleSearchCities = useCallback(async (keyword: string, page = 1) => {
    if (!keyword.trim()) {
      setSearchResults([]);
      setSearchTotal(0);
      return;
    }
    setSearchLoading(true);
    try {
      const res = await get<CityListResponse | City[]>(
        `/api/admin/cities/list?keyword=${encodeURIComponent(keyword)}&page=${page}&page_size=${searchPageSize}`
      );
      if (Array.isArray(res)) {
        setSearchResults(res);
        setSearchTotal(res.length);
      } else {
        setSearchResults(res.items || []);
        setSearchTotal(res.total || 0);
      }
    } catch {
      message.error('搜索城市失败');
    } finally {
      setSearchLoading(false);
    }
  }, []);

  const handleOpenModal = () => {
    setSearchKeyword('');
    setSearchResults([]);
    setSearchTotal(0);
    setSearchPage(1);
    setModalOpen(true);
  };

  const handleAddHotCity = async (city: City) => {
    const newList = [...hotCities, city];
    try {
      await post('/api/admin/cities/hot', { city_ids: newList.map((c) => c.id) });
      message.success(`已添加「${city.name}」为热门城市`);
      hotCityIdsRef.current.add(city.id);
      fetchHotCities();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '添加失败');
    }
  };

  const columns = [
    {
      title: '序号',
      key: 'index',
      width: 80,
      render: (_: any, __: City, index: number) => index + 1,
    },
    {
      title: '城市名',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '省份',
      dataIndex: 'province',
      key: 'province',
    },
    {
      title: '操作',
      key: 'action',
      width: 220,
      render: (_: any, record: City, index: number) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<ArrowUpOutlined />}
            disabled={index === 0}
            onClick={() => handleMoveUp(index)}
          >
            上移
          </Button>
          <Button
            type="link"
            size="small"
            icon={<ArrowDownOutlined />}
            disabled={index === hotCities.length - 1}
            onClick={() => handleMoveDown(index)}
          >
            下移
          </Button>
          <Popconfirm
            title="确定移除该热门城市？"
            onConfirm={() => handleRemove(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              移除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const searchColumns = [
    {
      title: '城市名',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '省份',
      dataIndex: 'province',
      key: 'province',
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, record: City) => {
        const isHot = hotCityIdsRef.current.has(record.id);
        return (
          <Button
            type="link"
            size="small"
            disabled={isHot}
            onClick={() => handleAddHotCity(record)}
          >
            {isHot ? '已添加' : '添加'}
          </Button>
        );
      },
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>热门城市管理</Title>
      <div style={{ marginBottom: 16, display: 'flex', gap: 12 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenModal}>
          添加热门城市
        </Button>
        <Button
          icon={<SaveOutlined />}
          disabled={!sortChanged}
          loading={savingSort}
          onClick={handleSaveSort}
        >
          保存排序
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={hotCities}
        rowKey="id"
        loading={loading}
        pagination={false}
        scroll={{ x: 600 }}
      />
      <Modal
        title="添加热门城市"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        destroyOnClose
        width={600}
      >
        <Input.Search
          placeholder="输入城市名搜索"
          allowClear
          enterButton={<><SearchOutlined /> 搜索</>}
          value={searchKeyword}
          onChange={(e) => setSearchKeyword(e.target.value)}
          onSearch={(val) => {
            setSearchPage(1);
            handleSearchCities(val, 1);
          }}
          style={{ marginBottom: 16 }}
        />
        {searchResults.length > 0 ? (
          <Table
            columns={searchColumns}
            dataSource={searchResults}
            rowKey="id"
            size="small"
            loading={searchLoading}
            pagination={{
              current: searchPage,
              pageSize: searchPageSize,
              total: searchTotal,
              showSizeChanger: false,
              showTotal: (t) => `共 ${t} 条`,
              onChange: (p) => {
                setSearchPage(p);
                handleSearchCities(searchKeyword, p);
              },
            }}
          />
        ) : (
          <Empty description={searchKeyword ? '未找到匹配城市' : '请输入城市名进行搜索'} />
        )}
      </Modal>
    </div>
  );
}
