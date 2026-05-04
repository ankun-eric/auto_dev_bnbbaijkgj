'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Tabs, Table, Input, Button, Space, Tag, Drawer, Radio, Select,
  message, Modal, Image, Empty, Spin,
} from 'antd';
import { SearchOutlined, LinkOutlined, DisconnectOutlined } from '@ant-design/icons';
import { get, post } from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';

interface ProductItem {
  id: number;
  name: string;
  images: string[];
  category_name: string;
  sale_price: number;
  status: string;
  bound_store_count: number;
}

interface StoreItem {
  id: number;
  store_name: string;
  store_code: string;
  status: string;
  address: string;
  bound_product_count: number;
}

interface DrawerStoreItem {
  store_id: number;
  store_name: string;
  store_code: string;
  status: string;
  address: string;
  is_bound: boolean;
}

interface DrawerProductItem {
  product_id: number;
  name: string;
  images: string[];
  category_name: string;
  sale_price: number;
  status: string;
  is_bound: boolean;
}

interface CategoryOption {
  id: number;
  name: string;
}

export default function StoreBinddingPage() {
  const [activeTab, setActiveTab] = useState<'product' | 'store'>('product');

  // Product tab state
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [productLoading, setProductLoading] = useState(false);
  const [productSearch, setProductSearch] = useState('');
  const [productPagination, setProductPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [selectedProductIds, setSelectedProductIds] = useState<number[]>([]);

  // Store tab state
  const [stores, setStores] = useState<StoreItem[]>([]);
  const [storeLoading, setStoreLoading] = useState(false);
  const [storeSearch, setStoreSearch] = useState('');
  const [storePagination, setStorePagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [selectedStoreIds, setSelectedStoreIds] = useState<number[]>([]);

  // Product -> Stores drawer
  const [productDrawerOpen, setProductDrawerOpen] = useState(false);
  const [drawerProduct, setDrawerProduct] = useState<ProductItem | null>(null);
  const [drawerStores, setDrawerStores] = useState<DrawerStoreItem[]>([]);
  const [drawerStoreLoading, setDrawerStoreLoading] = useState(false);
  const [drawerStoreSearch, setDrawerStoreSearch] = useState('');
  const [drawerStoreFilter, setDrawerStoreFilter] = useState<'all' | 'bound' | 'unbound'>('all');
  const [drawerStorePagination, setDrawerStorePagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [drawerStoreSelectedIds, setDrawerStoreSelectedIds] = useState<number[]>([]);
  const [bindingStoreId, setBindingStoreId] = useState<number | null>(null);

  // Store -> Products drawer
  const [storeDrawerOpen, setStoreDrawerOpen] = useState(false);
  const [drawerStore, setDrawerStore] = useState<StoreItem | null>(null);
  const [drawerProducts, setDrawerProducts] = useState<DrawerProductItem[]>([]);
  const [drawerProductLoading, setDrawerProductLoading] = useState(false);
  const [drawerProductSearch, setDrawerProductSearch] = useState('');
  const [drawerProductCategory, setDrawerProductCategory] = useState<number | undefined>(undefined);
  const [drawerProductFilter, setDrawerProductFilter] = useState<'all' | 'bound' | 'unbound'>('all');
  const [drawerProductPagination, setDrawerProductPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [drawerProductSelectedIds, setDrawerProductSelectedIds] = useState<number[]>([]);
  const [bindingProductId, setBindingProductId] = useState<number | null>(null);

  // Batch modal state
  const [batchModalVisible, setBatchModalVisible] = useState(false);
  const [batchAction, setBatchAction] = useState<'bind' | 'unbind'>('bind');
  const [batchTargetStoreId, setBatchTargetStoreId] = useState<number | undefined>(undefined);
  const [allStoreOptions, setAllStoreOptions] = useState<{ id: number; store_name: string }[]>([]);
  const [batchConfirming, setBatchConfirming] = useState(false);

  // Store batch modal (store tab -> batch bind/unbind products)
  const [storeBatchModalVisible, setStoreBatchModalVisible] = useState(false);
  const [storeBatchAction, setStoreBatchAction] = useState<'bind' | 'unbind'>('bind');

  // Categories for filter
  const [categories, setCategories] = useState<CategoryOption[]>([]);

  // Fetch product list
  const fetchProducts = useCallback(async (page = 1, pageSize = 20, search = productSearch) => {
    setProductLoading(true);
    try {
      const res = await get('/api/admin/store-bindding/products', { search, page, page_size: pageSize });
      setProducts(res?.items || []);
      setProductPagination({ current: res?.page || page, pageSize: res?.page_size || pageSize, total: res?.total || 0 });
    } catch {
      message.error('加载商品列表失败');
    } finally {
      setProductLoading(false);
    }
  }, [productSearch]);

  // Fetch store list
  const fetchStores = useCallback(async (page = 1, pageSize = 20, search = storeSearch) => {
    setStoreLoading(true);
    try {
      const res = await get('/api/admin/store-bindding/stores', { search, page, page_size: pageSize });
      setStores(res?.items || []);
      setStorePagination({ current: res?.page || page, pageSize: res?.page_size || pageSize, total: res?.total || 0 });
    } catch {
      message.error('加载门店列表失败');
    } finally {
      setStoreLoading(false);
    }
  }, [storeSearch]);

  // Fetch all stores for batch selector
  const fetchAllStores = useCallback(async () => {
    try {
      const res = await get('/api/admin/merchant/stores');
      const items = res?.items || res || [];
      setAllStoreOptions(Array.isArray(items) ? items : []);
    } catch {
      setAllStoreOptions([]);
    }
  }, []);

  // Fetch categories
  const fetchCategories = useCallback(async () => {
    try {
      const res = await get('/api/admin/products/categories');
      const items = res?.items || res || [];
      setCategories(Array.isArray(items) ? items : []);
    } catch {
      setCategories([]);
    }
  }, []);

  useEffect(() => {
    fetchProducts();
    fetchStores();
    fetchAllStores();
    fetchCategories();
  }, []);

  // Drawer: product's stores
  const fetchDrawerStores = useCallback(async (productId: number, page = 1, pageSize = 20, search = drawerStoreSearch, statusFilter = drawerStoreFilter) => {
    setDrawerStoreLoading(true);
    try {
      const res = await get(`/api/admin/store-bindding/products/${productId}/stores`, {
        search, status_filter: statusFilter, page, page_size: pageSize,
      });
      setDrawerStores(res?.items || []);
      setDrawerStorePagination({ current: res?.page || page, pageSize: res?.page_size || pageSize, total: res?.total || 0 });
    } catch {
      message.error('加载门店列表失败');
    } finally {
      setDrawerStoreLoading(false);
    }
  }, [drawerStoreSearch, drawerStoreFilter]);

  // Drawer: store's products
  const fetchDrawerProducts = useCallback(async (storeId: number, page = 1, pageSize = 20, search = drawerProductSearch, categoryId = drawerProductCategory, statusFilter = drawerProductFilter) => {
    setDrawerProductLoading(true);
    try {
      const params: Record<string, any> = { search, status_filter: statusFilter, page, page_size: pageSize };
      if (categoryId) params.category_id = categoryId;
      const res = await get(`/api/admin/store-bindding/stores/${storeId}/products`, params);
      setDrawerProducts(res?.items || []);
      setDrawerProductPagination({ current: res?.page || page, pageSize: res?.page_size || pageSize, total: res?.total || 0 });
    } catch {
      message.error('加载商品列表失败');
    } finally {
      setDrawerProductLoading(false);
    }
  }, [drawerProductSearch, drawerProductCategory, drawerProductFilter]);

  // Open product drawer
  const openProductDrawer = (product: ProductItem) => {
    setDrawerProduct(product);
    setDrawerStoreSearch('');
    setDrawerStoreFilter('all');
    setDrawerStoreSelectedIds([]);
    setProductDrawerOpen(true);
    fetchDrawerStores(product.id, 1, 20, '', 'all');
  };

  // Open store drawer
  const openStoreDrawer = (store: StoreItem) => {
    setDrawerStore(store);
    setDrawerProductSearch('');
    setDrawerProductCategory(undefined);
    setDrawerProductFilter('all');
    setDrawerProductSelectedIds([]);
    setStoreDrawerOpen(true);
    fetchDrawerProducts(store.id, 1, 20, '', undefined, 'all');
  };

  // Bind/unbind single store for a product
  const handleBindStore = async (productId: number, storeId: number, bind: boolean) => {
    setBindingStoreId(storeId);
    try {
      if (bind) {
        await post('/api/admin/store-bindding/bind', { product_id: productId, store_id: storeId });
      } else {
        await post('/api/admin/store-bindding/unbind', { product_id: productId, store_id: storeId });
      }
      message.success('操作成功');
      if (drawerProduct) {
        fetchDrawerStores(drawerProduct.id, drawerStorePagination.current, drawerStorePagination.pageSize, drawerStoreSearch, drawerStoreFilter);
      }
      fetchProducts(productPagination.current, productPagination.pageSize, productSearch);
    } catch {
      message.error('操作失败');
    } finally {
      setBindingStoreId(null);
    }
  };

  const handleBindProduct = async (storeId: number, productId: number, bind: boolean) => {
    setBindingProductId(productId);
    try {
      if (bind) {
        await post('/api/admin/store-bindding/bind', { product_id: productId, store_id: storeId });
      } else {
        await post('/api/admin/store-bindding/unbind', { product_id: productId, store_id: storeId });
      }
      message.success('操作成功');
      if (drawerStore) {
        fetchDrawerProducts(drawerStore.id, drawerProductPagination.current, drawerProductPagination.pageSize, drawerProductSearch, drawerProductCategory, drawerProductFilter);
      }
      fetchStores(storePagination.current, storePagination.pageSize, storeSearch);
    } catch {
      message.error('操作失败');
    } finally {
      setBindingProductId(null);
    }
  };

  // Batch bind/unbind (product tab)
  const openBatchModal = (action: 'bind' | 'unbind') => {
    setBatchAction(action);
    setBatchTargetStoreId(undefined);
    setBatchModalVisible(true);
  };

  const handleBatchConfirm = async () => {
    if (!batchTargetStoreId) {
      message.warning('请选择门店');
      return;
    }
    setBatchConfirming(true);
    try {
      const endpoint = batchAction === 'bind' ? '/api/admin/store-bindding/batch-bind' : '/api/admin/store-bindding/batch-unbind';
      const res = await post(endpoint, { product_ids: selectedProductIds, store_id: batchTargetStoreId });
      message.success(res?.message || `操作成功，成功 ${res?.success_count || 0} 个`);
      setBatchModalVisible(false);
      setSelectedProductIds([]);
      fetchProducts(productPagination.current, productPagination.pageSize, productSearch);
    } catch {
      message.error('批量操作失败');
    } finally {
      setBatchConfirming(false);
    }
  };

  // Batch in drawer (product -> stores)
  const handleDrawerStoreBatch = (action: 'bind' | 'unbind') => {
    if (drawerStoreSelectedIds.length === 0) return;
    Modal.confirm({
      title: action === 'bind' ? '批量关联' : '批量取消关联',
      content: `确认${action === 'bind' ? '关联' : '取消关联'}选中的 ${drawerStoreSelectedIds.length} 个门店？`,
      onOk: async () => {
        if (!drawerProduct) return;
        try {
          for (const storeId of drawerStoreSelectedIds) {
            if (action === 'bind') {
              await post('/api/admin/store-bindding/bind', { product_id: drawerProduct.id, store_id: storeId });
            } else {
              await post('/api/admin/store-bindding/unbind', { product_id: drawerProduct.id, store_id: storeId });
            }
          }
          message.success('批量操作成功');
          setDrawerStoreSelectedIds([]);
          fetchDrawerStores(drawerProduct.id, drawerStorePagination.current, drawerStorePagination.pageSize, drawerStoreSearch, drawerStoreFilter);
          fetchProducts(productPagination.current, productPagination.pageSize, productSearch);
        } catch {
          message.error('批量操作失败');
        }
      },
    });
  };

  // Batch in drawer (store -> products)
  const handleDrawerProductBatch = (action: 'bind' | 'unbind') => {
    if (drawerProductSelectedIds.length === 0) return;
    Modal.confirm({
      title: action === 'bind' ? '批量关联' : '批量取消关联',
      content: `确认${action === 'bind' ? '关联' : '取消关联'}选中的 ${drawerProductSelectedIds.length} 个商品？`,
      onOk: async () => {
        if (!drawerStore) return;
        try {
          const endpoint = action === 'bind' ? '/api/admin/store-bindding/batch-bind' : '/api/admin/store-bindding/batch-unbind';
          await post(endpoint, { product_ids: drawerProductSelectedIds, store_id: drawerStore.id });
          message.success('批量操作成功');
          setDrawerProductSelectedIds([]);
          fetchDrawerProducts(drawerStore.id, drawerProductPagination.current, drawerProductPagination.pageSize, drawerProductSearch, drawerProductCategory, drawerProductFilter);
          fetchStores(storePagination.current, storePagination.pageSize, storeSearch);
        } catch {
          message.error('批量操作失败');
        }
      },
    });
  };

  // Store tab batch (select stores -> bind/unbind all their products... actually this is batch for store tab)
  // Per requirements: store tab batch is similar - select stores then pick a product? 
  // Actually re-reading: the batch in store tab is not specified in detail. The main batch flow is for product tab.
  // Store tab just has the drawer for individual store management.

  // Product columns
  const productColumns = [
    {
      title: '商品图片', dataIndex: 'images', key: 'images', width: 70,
      render: (images: string[]) => images && images.length > 0
        ? <Image src={resolveAssetUrl(images[0])} width={50} height={50} style={{ objectFit: 'cover', borderRadius: 4 }} preview={false} />
        : <div style={{ width: 50, height: 50, background: '#f5f5f5', borderRadius: 4 }} />,
    },
    { title: '商品名称', dataIndex: 'name', key: 'name', width: 200, ellipsis: true },
    { title: '商品分类', dataIndex: 'category_name', key: 'category_name', width: 120 },
    {
      title: '价格', dataIndex: 'sale_price', key: 'sale_price', width: 100,
      render: (v: number) => <span style={{ color: '#f5222d' }}>¥{v?.toFixed(2)}</span>,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 90,
      render: (v: string) => {
        if (v === 'active') return <Tag color="green">上架中</Tag>;
        if (v === 'inactive') return <Tag color="default">已下架</Tag>;
        return <Tag color="default">草稿</Tag>;
      },
    },
    {
      title: '已绑定门店数', dataIndex: 'bound_store_count', key: 'bound_store_count', width: 120,
      render: (v: number, record: ProductItem) => (
        <a onClick={() => openProductDrawer(record)} style={{ color: '#1677ff' }}>{v ?? 0}</a>
      ),
    },
    {
      title: '操作', key: 'action', width: 120,
      render: (_: unknown, record: ProductItem) => (
        <Button type="link" size="small" icon={<LinkOutlined />} onClick={() => openProductDrawer(record)}>
          管理门店
        </Button>
      ),
    },
  ];

  // Store columns
  const storeColumns = [
    { title: '门店名称', dataIndex: 'store_name', key: 'store_name', width: 200, ellipsis: true },
    { title: '门店编号', dataIndex: 'store_code', key: 'store_code', width: 120 },
    {
      title: '营业状态', dataIndex: 'status', key: 'status', width: 100,
      render: (v: string) => {
        if (v === 'active' || v === 'open') return <Tag color="green">营业中</Tag>;
        return <Tag color="default">已关闭</Tag>;
      },
    },
    {
      title: '已关联商品数', dataIndex: 'bound_product_count', key: 'bound_product_count', width: 120,
      render: (v: number, record: StoreItem) => (
        <a onClick={() => openStoreDrawer(record)} style={{ color: '#1677ff' }}>{v ?? 0}</a>
      ),
    },
    {
      title: '操作', key: 'action', width: 120,
      render: (_: unknown, record: StoreItem) => (
        <Button type="link" size="small" icon={<LinkOutlined />} onClick={() => openStoreDrawer(record)}>
          管理商品
        </Button>
      ),
    },
  ];

  // Drawer store columns
  const drawerStoreColumns = [
    { title: '门店名称', dataIndex: 'store_name', key: 'store_name', width: 160, ellipsis: true },
    { title: '门店编号', dataIndex: 'store_code', key: 'store_code', width: 100 },
    {
      title: '营业状态', dataIndex: 'status', key: 'status', width: 90,
      render: (v: string) => {
        if (v === 'active' || v === 'open') return <Tag color="green">营业中</Tag>;
        return <Tag color="default">已关闭</Tag>;
      },
    },
    { title: '门店地址', dataIndex: 'address', key: 'address', ellipsis: true },
  ];

  // Drawer product columns
  const drawerProductColumns = [
    {
      title: '商品图片', dataIndex: 'images', key: 'images', width: 60,
      render: (images: string[]) => images && images.length > 0
        ? <Image src={resolveAssetUrl(images[0])} width={40} height={40} style={{ objectFit: 'cover', borderRadius: 4 }} preview={false} />
        : <div style={{ width: 40, height: 40, background: '#f5f5f5', borderRadius: 4 }} />,
    },
    { title: '商品名称', dataIndex: 'name', key: 'name', width: 150, ellipsis: true },
    { title: '商品分类', dataIndex: 'category_name', key: 'category_name', width: 100 },
    {
      title: '价格', dataIndex: 'sale_price', key: 'sale_price', width: 80,
      render: (v: number) => <span style={{ color: '#f5222d' }}>¥{v?.toFixed(2)}</span>,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => {
        if (v === 'active') return <Tag color="green">上架中</Tag>;
        if (v === 'inactive') return <Tag color="default">已下架</Tag>;
        return <Tag color="default">草稿</Tag>;
      },
    },
  ];

  const productTabContent = (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Input
          placeholder="搜索商品名称"
          prefix={<SearchOutlined />}
          value={productSearch}
          onChange={e => setProductSearch(e.target.value)}
          onPressEnter={() => fetchProducts(1, 20, productSearch)}
          style={{ width: 280 }}
          allowClear
        />
        <Button type="primary" onClick={() => fetchProducts(1, 20, productSearch)}>搜索</Button>
      </Space>

      <Spin spinning={productLoading}>
        <Table
          columns={productColumns}
          dataSource={products}
          rowKey="id"
          rowSelection={{
            selectedRowKeys: selectedProductIds,
            onChange: (keys) => setSelectedProductIds(keys as number[]),
          }}
          rowClassName={(record) => record.status === 'inactive' ? 'row-disabled' : ''}
          pagination={{
            current: productPagination.current,
            pageSize: productPagination.pageSize,
            total: productPagination.total,
            showTotal: total => `共 ${total} 条`,
            onChange: (page, pageSize) => fetchProducts(page, pageSize, productSearch),
          }}
          locale={{ emptyText: <Empty description="暂无商品" /> }}
        />
      </Spin>

      {selectedProductIds.length > 0 && (
        <div style={{
          position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 1000,
          background: '#fff', padding: '12px 24px', boxShadow: '0 -2px 8px rgba(0,0,0,0.1)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span>已选择 <b>{selectedProductIds.length}</b> 个商品</span>
          <Space>
            <Button type="primary" icon={<LinkOutlined />} onClick={() => openBatchModal('bind')}>
              批量绑定门店
            </Button>
            <Button danger icon={<DisconnectOutlined />} onClick={() => openBatchModal('unbind')}>
              批量解绑门店
            </Button>
          </Space>
        </div>
      )}
    </div>
  );

  const storeTabContent = (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Input
          placeholder="搜索门店名称"
          prefix={<SearchOutlined />}
          value={storeSearch}
          onChange={e => setStoreSearch(e.target.value)}
          onPressEnter={() => fetchStores(1, 20, storeSearch)}
          style={{ width: 280 }}
          allowClear
        />
        <Button type="primary" onClick={() => fetchStores(1, 20, storeSearch)}>搜索</Button>
      </Space>

      <Spin spinning={storeLoading}>
        <Table
          columns={storeColumns}
          dataSource={stores}
          rowKey="id"
          rowSelection={{
            selectedRowKeys: selectedStoreIds,
            onChange: (keys) => setSelectedStoreIds(keys as number[]),
          }}
          rowClassName={(record) => (record.status !== 'active' && record.status !== 'open') ? 'row-disabled' : ''}
          pagination={{
            current: storePagination.current,
            pageSize: storePagination.pageSize,
            total: storePagination.total,
            showTotal: total => `共 ${total} 条`,
            onChange: (page, pageSize) => fetchStores(page, pageSize, storeSearch),
          }}
          locale={{ emptyText: <Empty description="暂无门店" /> }}
        />
      </Spin>

      {selectedStoreIds.length > 0 && (
        <div style={{
          position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 1000,
          background: '#fff', padding: '12px 24px', boxShadow: '0 -2px 8px rgba(0,0,0,0.1)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span>已选择 <b>{selectedStoreIds.length}</b> 个门店</span>
          <Space>
            <Button type="primary" icon={<LinkOutlined />} onClick={() => { setStoreBatchAction('bind'); setStoreBatchModalVisible(true); }}>
              批量绑定商品
            </Button>
            <Button danger icon={<DisconnectOutlined />} onClick={() => { setStoreBatchAction('unbind'); setStoreBatchModalVisible(true); }}>
              批量解绑商品
            </Button>
          </Space>
        </div>
      )}
    </div>
  );

  return (
    <div>
      <style jsx global>{`
        .row-disabled td { color: #999 !important; }
      `}</style>

      <Card title="适用门店管理" bordered={false}>
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as 'product' | 'store')}
          items={[
            { key: 'product', label: '商品维度', children: productTabContent },
            { key: 'store', label: '门店维度', children: storeTabContent },
          ]}
        />
      </Card>

      {/* Product -> Store Drawer */}
      <Drawer
        title={
          drawerProduct ? (
            <Space>
              {drawerProduct.images?.[0] && (
                <Image src={resolveAssetUrl(drawerProduct.images[0])} width={32} height={32} style={{ objectFit: 'cover', borderRadius: 4 }} preview={false} />
              )}
              <span>{drawerProduct.name} - 门店管理</span>
            </Space>
          ) : '门店管理'
        }
        open={productDrawerOpen}
        onClose={() => setProductDrawerOpen(false)}
        width={640}
        destroyOnClose
      >
        <Space style={{ marginBottom: 16, width: '100%' }} direction="vertical">
          <Space wrap>
            <Input
              placeholder="搜索门店名称"
              prefix={<SearchOutlined />}
              value={drawerStoreSearch}
              onChange={e => setDrawerStoreSearch(e.target.value)}
              onPressEnter={() => drawerProduct && fetchDrawerStores(drawerProduct.id, 1, 20, drawerStoreSearch, drawerStoreFilter)}
              style={{ width: 200 }}
              allowClear
            />
            <Radio.Group
              value={drawerStoreFilter}
              onChange={e => {
                setDrawerStoreFilter(e.target.value);
                if (drawerProduct) fetchDrawerStores(drawerProduct.id, 1, 20, drawerStoreSearch, e.target.value);
              }}
            >
              <Radio.Button value="all">全部</Radio.Button>
              <Radio.Button value="bound">已绑定</Radio.Button>
              <Radio.Button value="unbound">未绑定</Radio.Button>
            </Radio.Group>
          </Space>
        </Space>

        <Spin spinning={drawerStoreLoading}>
          <Table
            columns={drawerStoreColumns}
            dataSource={drawerStores}
            rowKey="store_id"
            size="small"
            rowSelection={{
              selectedRowKeys: drawerStoreSelectedIds,
              onChange: (keys) => setDrawerStoreSelectedIds(keys as number[]),
              onSelect: (record, selected) => {
                if (drawerProduct) {
                  handleBindStore(drawerProduct.id, record.store_id, selected);
                }
              },
              getCheckboxProps: (record) => ({
                disabled: bindingStoreId === record.store_id,
                defaultChecked: record.is_bound,
              }),
            }}
            rowClassName={(record) => (record.status !== 'active' && record.status !== 'open') ? 'row-disabled' : ''}
            pagination={{
              current: drawerStorePagination.current,
              pageSize: drawerStorePagination.pageSize,
              total: drawerStorePagination.total,
              size: 'small',
              showTotal: total => `共 ${total} 条`,
              onChange: (page, pageSize) => drawerProduct && fetchDrawerStores(drawerProduct.id, page, pageSize, drawerStoreSearch, drawerStoreFilter),
            }}
            locale={{ emptyText: <Empty description="暂无门店" /> }}
          />
        </Spin>

        {drawerStoreSelectedIds.length > 0 && (
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 10,
            background: '#fff', padding: '12px 16px', boxShadow: '0 -2px 8px rgba(0,0,0,0.1)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span>已选 {drawerStoreSelectedIds.length} 个</span>
            <Space>
              <Button type="primary" size="small" onClick={() => handleDrawerStoreBatch('bind')}>批量关联</Button>
              <Button danger size="small" onClick={() => handleDrawerStoreBatch('unbind')}>批量取消关联</Button>
            </Space>
          </div>
        )}
      </Drawer>

      {/* Store -> Product Drawer */}
      <Drawer
        title={
          drawerStore ? (
            <Space>
              <span>{drawerStore.store_name}（{drawerStore.store_code}）- 商品管理</span>
            </Space>
          ) : '商品管理'
        }
        open={storeDrawerOpen}
        onClose={() => setStoreDrawerOpen(false)}
        width={640}
        destroyOnClose
      >
        <Space style={{ marginBottom: 16, width: '100%' }} direction="vertical">
          <Space wrap>
            <Input
              placeholder="搜索商品名称"
              prefix={<SearchOutlined />}
              value={drawerProductSearch}
              onChange={e => setDrawerProductSearch(e.target.value)}
              onPressEnter={() => drawerStore && fetchDrawerProducts(drawerStore.id, 1, 20, drawerProductSearch, drawerProductCategory, drawerProductFilter)}
              style={{ width: 180 }}
              allowClear
            />
            <Select
              placeholder="商品分类"
              allowClear
              style={{ width: 140 }}
              value={drawerProductCategory}
              onChange={v => {
                setDrawerProductCategory(v);
                if (drawerStore) fetchDrawerProducts(drawerStore.id, 1, 20, drawerProductSearch, v, drawerProductFilter);
              }}
              options={categories.map(c => ({ label: c.name, value: c.id }))}
            />
            <Radio.Group
              value={drawerProductFilter}
              onChange={e => {
                setDrawerProductFilter(e.target.value);
                if (drawerStore) fetchDrawerProducts(drawerStore.id, 1, 20, drawerProductSearch, drawerProductCategory, e.target.value);
              }}
            >
              <Radio.Button value="all">全部</Radio.Button>
              <Radio.Button value="bound">已关联</Radio.Button>
              <Radio.Button value="unbound">未关联</Radio.Button>
            </Radio.Group>
          </Space>
        </Space>

        <Spin spinning={drawerProductLoading}>
          <Table
            columns={drawerProductColumns}
            dataSource={drawerProducts}
            rowKey="product_id"
            size="small"
            rowSelection={{
              selectedRowKeys: drawerProductSelectedIds,
              onChange: (keys) => setDrawerProductSelectedIds(keys as number[]),
              onSelect: (record, selected) => {
                if (drawerStore) {
                  handleBindProduct(drawerStore.id, record.product_id, selected);
                }
              },
              getCheckboxProps: (record) => ({
                disabled: bindingProductId === record.product_id,
                defaultChecked: record.is_bound,
              }),
            }}
            rowClassName={(record) => record.status === 'inactive' ? 'row-disabled' : ''}
            pagination={{
              current: drawerProductPagination.current,
              pageSize: drawerProductPagination.pageSize,
              total: drawerProductPagination.total,
              size: 'small',
              showTotal: total => `共 ${total} 条`,
              onChange: (page, pageSize) => drawerStore && fetchDrawerProducts(drawerStore.id, page, pageSize, drawerProductSearch, drawerProductCategory, drawerProductFilter),
            }}
            locale={{ emptyText: <Empty description="暂无商品" /> }}
          />
        </Spin>

        {drawerProductSelectedIds.length > 0 && (
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 10,
            background: '#fff', padding: '12px 16px', boxShadow: '0 -2px 8px rgba(0,0,0,0.1)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span>已选 {drawerProductSelectedIds.length} 个</span>
            <Space>
              <Button type="primary" size="small" onClick={() => handleDrawerProductBatch('bind')}>批量关联</Button>
              <Button danger size="small" onClick={() => handleDrawerProductBatch('unbind')}>批量取消关联</Button>
            </Space>
          </div>
        )}
      </Drawer>

      {/* Batch Modal - Product Tab */}
      <Modal
        title={batchAction === 'bind' ? '批量绑定门店' : '批量解绑门店'}
        open={batchModalVisible}
        onCancel={() => setBatchModalVisible(false)}
        onOk={handleBatchConfirm}
        confirmLoading={batchConfirming}
        okText="确认执行"
      >
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 8 }}>选择目标门店：</div>
          <Select
            placeholder="请选择门店"
            style={{ width: '100%' }}
            showSearch
            optionFilterProp="label"
            value={batchTargetStoreId}
            onChange={setBatchTargetStoreId}
            options={allStoreOptions.map(s => ({ label: s.store_name, value: s.id }))}
          />
        </div>
        {batchTargetStoreId && (
          <div style={{ background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 6, padding: 12 }}>
            <div style={{ marginBottom: 8 }}>
              即将为 <b>{selectedProductIds.length}</b> 个商品
              {batchAction === 'bind' ? '绑定' : '解绑'}到
              【{allStoreOptions.find(s => s.id === batchTargetStoreId)?.store_name}】，确认执行？
            </div>
            <details>
              <summary style={{ cursor: 'pointer', color: '#1677ff' }}>查看商品清单</summary>
              <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                {selectedProductIds.map(id => {
                  const p = products.find(item => item.id === id);
                  return <li key={id}>{p?.name || `商品ID: ${id}`}</li>;
                })}
              </ul>
            </details>
          </div>
        )}
      </Modal>

      {/* Batch Modal - Store Tab (simplified: just confirm) */}
      <Modal
        title={storeBatchAction === 'bind' ? '批量绑定商品' : '批量解绑商品'}
        open={storeBatchModalVisible}
        onCancel={() => setStoreBatchModalVisible(false)}
        footer={null}
      >
        <div style={{ marginBottom: 16 }}>
          <p>已选择 <b>{selectedStoreIds.length}</b> 个门店，请通过"门店维度"逐个门店管理商品绑定关系。</p>
          <p style={{ color: '#999' }}>提示：门店维度的批量操作请点击门店行进入管理商品抽屉进行操作。</p>
        </div>
        <Button onClick={() => setStoreBatchModalVisible(false)}>关闭</Button>
      </Modal>
    </div>
  );
}
