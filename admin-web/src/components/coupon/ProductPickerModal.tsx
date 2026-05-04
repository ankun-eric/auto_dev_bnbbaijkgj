'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Modal, Tabs, Input, Select, Table, Tag, Image, Button, Space, Alert,
  Typography, Popover, message,
} from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { get } from '@/lib/api';
import { fulfillmentLabel } from '@/utils/fulfillmentLabel';

const { Text } = Typography;

export interface PickerProduct {
  id: number;
  name: string;
  image?: string | null;
  category_id?: number | null;
  category_name?: string | null;
  price: number;
  stock?: number | null;
  fulfillment_type: 'delivery' | 'in_store';
}

interface CategoryOption {
  value: number;
  label: string;
  children?: CategoryOption[];
}

interface Props {
  open: boolean;
  title?: string;
  /** 上限：默认 100；用于"排除商品弹窗"时改为 50 */
  maxCount?: number;
  /** 当达到上限时是否展示"切换为指定分类模式"的快捷按钮（仅适用商品弹窗用，排除商品弹窗不展示） */
  showSwitchToCategory?: boolean;
  initialSelectedIds?: number[];
  onCancel: () => void;
  onConfirm: (selectedIds: number[]) => void;
  /** 当用户在达到上限时点击"切换为指定分类"的快捷按钮 */
  onSwitchToCategory?: () => void;
}

type TabKey = 'all' | 'delivery' | 'in_store';

/**
 * F4：商品弹窗选择器
 * - 3 个 Tab：全部 / 快递配送 / 到店服务
 * - 顶部搜索（商品名/编码） + 分类筛选 + 分页
 * - 跨页 / Tab / 搜索保留勾选
 * - 已选数实时计数 + 顶部提示
 * - F5：达到上限置灰禁用 + 红色横幅 + 「切换为指定分类模式」按钮
 */
export default function ProductPickerModal({
  open,
  title = '选择商品',
  maxCount = 100,
  showSwitchToCategory = true,
  initialSelectedIds = [],
  onCancel,
  onConfirm,
  onSwitchToCategory,
}: Props) {
  const [tab, setTab] = useState<TabKey>('all');
  const [keyword, setKeyword] = useState('');
  const [categoryId, setCategoryId] = useState<number | undefined>(undefined);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [items, setItems] = useState<PickerProduct[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  // 跨 Tab/分页/搜索保留：用 Set<id>
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [selectedDetails, setSelectedDetails] = useState<Record<number, PickerProduct>>({});

  // 分类下拉数据
  const [catTree, setCatTree] = useState<CategoryOption[]>([]);

  // 重置：每次打开
  useEffect(() => {
    if (!open) return;
    setSelected(new Set(initialSelectedIds || []));
    setSelectedDetails({});
    setTab('all');
    setKeyword('');
    setCategoryId(undefined);
    setPage(1);
  }, [open]); // eslint-disable-line

  // 拉分类树
  useEffect(() => {
    if (!open) return;
    get('/api/admin/coupons/category-tree').then((res: any) => {
      const items = res?.items || [];
      const conv = (arr: any[]): CategoryOption[] =>
        arr.map(n => ({
          value: n.id,
          label: n.name,
          children: n.children?.length ? conv(n.children) : undefined,
        }));
      setCatTree(conv(items));
    }).catch(() => setCatTree([]));
  }, [open]);

  // 拉初始已选商品的详情（用于回显已选卡片名称）
  useEffect(() => {
    if (!open || !initialSelectedIds || initialSelectedIds.length === 0) return;
    get(`/api/admin/coupons/product-picker?selected_ids=${initialSelectedIds.join(',')}&page=1&page_size=1`)
      .then((res: any) => {
        const details: Record<number, PickerProduct> = {};
        (res?.selected_items || []).forEach((it: any) => {
          if (!it.missing) {
            details[it.id] = it;
          }
        });
        setSelectedDetails(details);
      })
      .catch(() => {});
  }, [open, initialSelectedIds]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('fulfillment_type', tab);
      if (keyword) params.set('keyword', keyword);
      if (categoryId) params.set('category_id', String(categoryId));
      params.set('page', String(page));
      params.set('page_size', String(pageSize));
      const res: any = await get(`/api/admin/coupons/product-picker?${params.toString()}`);
      setItems(res?.items || []);
      setTotal(res?.total || 0);
      // 收录最新一批的详情，避免 onConfirm 时丢掉新选商品名
      const merged = { ...selectedDetails };
      (res?.items || []).forEach((it: PickerProduct) => {
        merged[it.id] = it;
      });
      setSelectedDetails(merged);
    } catch (e) {
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [tab, keyword, categoryId, page, pageSize, selectedDetails]);

  useEffect(() => {
    if (open) fetchData();
  }, [open, tab, page, categoryId]); // keyword 走手动按钮触发

  const handleSearch = () => {
    setPage(1);
    fetchData();
  };

  const isFull = selected.size >= maxCount;

  const toggleOne = (id: number, on: boolean) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (on) {
        if (next.size >= maxCount) {
          message.warning(`已达上限，单张优惠券最多关联 ${maxCount} 个商品`);
          return next;
        }
        next.add(id);
      } else {
        next.delete(id);
      }
      return next;
    });
  };

  const togglePage = (on: boolean) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (on) {
        for (const it of items) {
          if (next.size >= maxCount) {
            message.warning(`已达上限，单张优惠券最多关联 ${maxCount} 个商品`);
            break;
          }
          next.add(it.id);
        }
      } else {
        items.forEach(it => next.delete(it.id));
      }
      return next;
    });
  };

  const allOnPageChecked = useMemo(
    () => items.length > 0 && items.every(it => selected.has(it.id)),
    [items, selected]
  );

  const switchToCategory = () => {
    Modal.confirm({
      title: '切换将清空当前已选商品，是否继续？',
      okText: '继续切换',
      onOk: () => {
        setSelected(new Set());
        onSwitchToCategory?.();
        onCancel();
      },
    });
  };

  const columns = [
    {
      title: '',
      dataIndex: 'id',
      width: 50,
      render: (_: any, record: PickerProduct) => {
        const checked = selected.has(record.id);
        const disabled = !checked && isFull;
        return (
          <input
            type="checkbox"
            checked={checked}
            disabled={disabled}
            onChange={(e) => toggleOne(record.id, e.target.checked)}
            title={disabled ? `已达 ${maxCount} 上限` : ''}
          />
        );
      },
    },
    {
      title: '图', dataIndex: 'image', width: 56,
      render: (img: string) => img ? (
        <Image src={img} width={32} height={32} fallback="/no-image.png" preview={false} />
      ) : <div style={{ width: 32, height: 32, background: '#f5f5f5' }} />,
    },
    { title: '商品名称', dataIndex: 'name', ellipsis: true },
    { title: '分类', dataIndex: 'category_name', width: 110,
      render: (v: string) => v || <Text type="secondary">-</Text>,
    },
    { title: '价格', dataIndex: 'price', width: 80,
      render: (v: number) => `¥${(v ?? 0).toFixed(2)}`,
    },
    { title: '库存', dataIndex: 'stock', width: 70,
      render: (v: number | null) => v == null ? <Text type="secondary">-</Text> : v,
    },
    { title: '履约方式', dataIndex: 'fulfillment_type', width: 96,
      render: (v: string) => {
        const colorMap: Record<string, string> = {
          delivery: 'blue',
          in_store: 'orange',
          on_site: 'green',
          virtual: 'purple',
        };
        return <Tag color={colorMap[v] || 'default'}>{fulfillmentLabel(v)}</Tag>;
      },
    },
  ];

  return (
    <Modal
      title={
        <span>
          {title}
          <span style={{ marginLeft: 12, color: '#666', fontSize: 13 }}>
            已选 <b style={{ color: isFull ? '#ff4d4f' : '#1677ff' }}>{selected.size}</b> / {maxCount}
          </span>
        </span>
      }
      open={open}
      onCancel={onCancel}
      onOk={() => onConfirm(Array.from(selected))}
      okText="确定"
      cancelText="取消"
      width={1080}
      bodyStyle={{ padding: 16 }}
      destroyOnClose
    >
      {isFull && showSwitchToCategory && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
          message={`已选商品已达 ${maxCount} 上限，建议改用「指定分类」覆盖更多商品。`}
          action={
            <Button size="small" type="primary" onClick={switchToCategory}>
              切换为指定分类模式
            </Button>
          }
        />
      )}
      {isFull && !showSwitchToCategory && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
          message={`已达 ${maxCount} 上限，请取消已选后再继续`}
        />
      )}

      <Tabs
        activeKey={tab}
        onChange={(k) => { setTab(k as TabKey); setPage(1); }}
        items={[
          { key: 'all', label: '全部' },
          { key: 'delivery', label: '快递配送' },
          { key: 'in_store', label: '到店服务' },
        ]}
      />

      <Space style={{ marginBottom: 12 }} wrap>
        <Input
          placeholder="商品名"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onPressEnter={handleSearch}
          style={{ width: 240 }}
          prefix={<SearchOutlined />}
          allowClear
        />
        <Select
          placeholder="按分类筛选"
          value={categoryId}
          onChange={(v) => { setCategoryId(v); setPage(1); }}
          allowClear
          style={{ width: 200 }}
          options={catTree}
          fieldNames={{ label: 'label', value: 'value', options: 'children' }}
          treeDefaultExpandAll
        />
        <Button type="primary" onClick={handleSearch}>搜索</Button>
        <span>
          <input
            type="checkbox"
            checked={allOnPageChecked}
            onChange={(e) => togglePage(e.target.checked)}
            id="pickAllOnPage"
          />
          <label htmlFor="pickAllOnPage" style={{ marginLeft: 4, cursor: 'pointer' }}>勾选本页</label>
        </span>
      </Space>

      <Table
        rowKey="id"
        size="small"
        loading={loading}
        dataSource={items}
        columns={columns as any}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: false,
          onChange: (p) => setPage(p),
        }}
        scroll={{ y: 360 }}
      />

      {selected.size > 0 && (
        <Popover
          title={`已选 ${selected.size} 个商品`}
          trigger="click"
          content={
            <div style={{ maxHeight: 360, overflow: 'auto', minWidth: 280 }}>
              <Space size={[4, 6]} wrap>
                {Array.from(selected).map(id => {
                  const d = selectedDetails[id];
                  return (
                    <Tag
                      key={id}
                      closable
                      onClose={(e) => { e.preventDefault(); toggleOne(id, false); }}
                    >
                      {d?.name || `商品#${id}`}
                    </Tag>
                  );
                })}
              </Space>
            </div>
          }
        >
          <Button type="link" style={{ marginTop: 8 }}>
            查看 / 移除已选 {selected.size} 个商品 ▼
          </Button>
        </Popover>
      )}
    </Modal>
  );
}
