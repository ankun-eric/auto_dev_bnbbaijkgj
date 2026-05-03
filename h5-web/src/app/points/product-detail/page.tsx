'use client';

/**
 * v3.1 — 积分商品详情页（PRD F4）
 *
 * 路由：/points/product-detail?id=xxx
 * 来源：/api/points/mall/items/{id} 统一返回商品详情 + 按钮状态 + 用户已兑次数等
 * 底部「立即兑换」按钮 5 态（按优先级）：
 *   1. offline/deleted  → 已下架
 *   2. sold_out         → 已兑完
 *   3. limit_reached    → 已达兑换上限
 *   4. insufficient     → 积分不足（差 XX 分）
 *   5. exchangeable     → 立即兑换（消耗 XXX 积分）
 */

import { useCallback, useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

export const dynamic = 'force-dynamic';
import {
  Button,
  Dialog,
  Swiper,
  Tag,
  Toast,
  SpinLoading,
  Empty,
} from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface ProductDetail {
  id: number;
  name: string;
  description?: string | null;
  detail_html?: string | null;
  images?: string[] | null;
  type: string;
  price_points: number;
  stock: number;
  limit_per_user?: number;
  status?: string;
  ref_coupon_id?: number | null;
  ref_service_id?: number | null;
  service_product?: {
    id: number;
    name: string;
    image?: string | null;
    price?: number | null;
  } | null;
  user_available_points?: number;
  user_exchanged_count?: number;
  button_state?:
    | 'exchangeable'
    | 'normal'
    | 'offline'
    | 'sold_out'
    | 'limit_reached'
    | 'insufficient'
    | 'not_enough'
    | string;
  button_text?: string;
}

const DISABLED_REASON: Record<string, string> = {
  offline: '商品已下架',
  sold_out: '商品已兑完',
  limit_reached: '已达兑换上限',
  insufficient: '积分不足',
  not_enough: '积分不足',
};

function isExchangeable(state?: string): boolean {
  if (!state) return true;
  return state === 'exchangeable' || state === 'normal';
}

const TYPE_BADGE: Record<string, { text: string; color: string }> = {
  coupon: { text: '优惠券', color: '#fa8c16' },
  service: { text: '体验服务', color: '#13c2c2' },
  physical: { text: '实物', color: '#722ed1' },
  virtual: { text: '虚拟（开发中）', color: '#bfbfbf' },
  third_party: { text: '第三方（开发中）', color: '#bfbfbf' },
};

function PointsProductDetailInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const id = searchParams?.get('id');
  const [item, setItem] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [exchanging, setExchanging] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      setLoading(true);
      const res: any = await api.get(`/api/points/mall/items/${id}`);
      const data = res?.data || res || {};
      setItem(data);
    } catch (err: any) {
      Toast.show({
        content: err?.response?.data?.detail || '加载失败',
        icon: 'fail',
      });
      setItem(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const handleExchange = async () => {
    if (!item) return;
    if (!isExchangeable(item.button_state)) {
      // Bug Fix(2026-05-04): 灰色按钮也给反馈，不再"完全无响应"
      const reason =
        DISABLED_REASON[item.button_state || ''] ||
        item.button_text ||
        '当前不可兑换';
      let content = reason;
      if (
        (item.button_state === 'insufficient' ||
          item.button_state === 'not_enough') &&
        typeof item.user_available_points === 'number'
      ) {
        const diff = Math.max(
          0,
          (item.price_points || 0) - (item.user_available_points || 0),
        );
        content = `积分不足，还差 ${diff} 分`;
      }
      Toast.show({ content });
      return;
    }

    const extraWarn =
      item.type === 'service' ? '\n\n⚠️ 兑换后 30 天内有效，过期作废，积分不退。' : '';
    const confirmed = await Dialog.confirm({
      content: `确认用 ${item.price_points} 积分兑换【${item.name}】吗？${extraWarn}`,
      confirmText: '确认兑换',
      cancelText: '取消',
    });
    if (!confirmed) return;

    setExchanging(true);
    try {
      await api.post('/api/points/mall/exchange', {
        goods_id: item.id,
        quantity: 1,
      });
      Toast.show({ content: '兑换成功', icon: 'success' });
      setTimeout(() => {
        router.push('/points/detail?tab=exchange');
      }, 800);
    } catch (err: any) {
      Toast.show({
        content: err?.response?.data?.detail || '兑换失败',
        icon: 'fail',
      });
    } finally {
      setExchanging(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <GreenNavBar>商品详情</GreenNavBar>
        <div className="flex items-center justify-center py-20">
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="min-h-screen bg-gray-50">
        <GreenNavBar>商品详情</GreenNavBar>
        <Empty description="商品不存在或已下架" style={{ marginTop: 80 }} />
      </div>
    );
  }

  const images = Array.isArray(item.images) && item.images.length > 0
    ? item.images
    : [];
  const badge = TYPE_BADGE[item.type] || TYPE_BADGE.virtual;
  const buttonState = item.button_state || 'exchangeable';
  const buttonText = item.button_text || '立即兑换';
  // Bug Fix(2026-05-04): 与列表页/小程序统一可兑换判定，兼容后端老的 'normal' 字段；
  // 同时按钮**保留可点击**（disabled=false）以触发置灰原因 toast，避免"完全无响应"。
  const exchangeable = isExchangeable(buttonState);

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <GreenNavBar>商品详情</GreenNavBar>

      {/* 顶部图片轮播 */}
      <div style={{ background: '#fff' }}>
        {images.length > 0 ? (
          <Swiper autoplay loop style={{ height: 280 }}>
            {images.map((src, idx) => (
              <Swiper.Item key={idx}>
                <div
                  style={{
                    height: 280,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: '#f5f5f5',
                  }}
                >
                  <img
                    src={src}
                    alt=""
                    style={{
                      maxWidth: '100%',
                      maxHeight: '100%',
                      objectFit: 'contain',
                    }}
                  />
                </div>
              </Swiper.Item>
            ))}
          </Swiper>
        ) : (
          <div
            style={{
              height: 280,
              background: '#f5f5f5',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 80,
            }}
          >
            🎁
          </div>
        )}
      </div>

      {/* 基本信息 */}
      <div style={{ background: '#fff', padding: 16, marginTop: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <Tag color={badge.color} style={{ fontSize: 10 }}>
            {badge.text}
          </Tag>
          {item.status !== 'active' && (
            <Tag color="#bfbfbf" fill="outline" style={{ fontSize: 10 }}>
              已下架
            </Tag>
          )}
        </div>
        <div style={{ fontSize: 18, fontWeight: 600, color: '#222' }}>{item.name}</div>
        <div style={{ marginTop: 10, display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <span style={{ color: '#2E7D32', fontWeight: 700, fontSize: 24 }}>
            {item.price_points}
          </span>
          <span style={{ color: '#2E7D32', fontSize: 13 }}>积分</span>
          <span style={{ color: '#999', fontSize: 12, marginLeft: 'auto' }}>
            {item.type === 'service'
              ? '服务券'
              : item.stock > 0
              ? `剩余库存 ${item.stock}`
              : '已兑完'}
          </span>
        </div>
        {typeof item.limit_per_user === 'number' && item.limit_per_user > 0 && (
          <div style={{ color: '#999', fontSize: 12, marginTop: 6 }}>
            每人限兑 {item.limit_per_user} 次（已兑 {item.user_exchanged_count || 0} 次）
          </div>
        )}
      </div>

      {/* 详情富文本 */}
      <div style={{ background: '#fff', padding: 16, marginTop: 8 }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: '#333' }}>
          商品详情
        </div>
        {item.detail_html ? (
          <div
            className="points-product-detail"
            style={{ fontSize: 14, color: '#333', lineHeight: 1.7 }}
            dangerouslySetInnerHTML={{ __html: item.detail_html }}
          />
        ) : (
          <div style={{ fontSize: 14, color: '#555', whiteSpace: 'pre-wrap' }}>
            {item.description || '暂无详情'}
          </div>
        )}
      </div>

      {/* 服务类关联商品 */}
      {item.type === 'service' && item.service_product && (
        <div style={{ background: '#fff', padding: 16, marginTop: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: '#333' }}>
            关联服务商品
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            {item.service_product.image && (
              <img
                src={item.service_product.image}
                alt=""
                style={{ width: 56, height: 56, borderRadius: 8, objectFit: 'cover' }}
              />
            )}
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14 }}>{item.service_product.name}</div>
              {item.service_product.price != null && (
                <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>
                  原价 ¥{item.service_product.price}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 使用须知 */}
      <div style={{ background: '#fff', padding: 16, marginTop: 8 }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: '#333' }}>
          使用须知
        </div>
        <ul style={{ fontSize: 13, color: '#666', paddingLeft: 18, lineHeight: 1.8 }}>
          {item.type === 'service' && <li>兑换后 30 天内有效，过期作废</li>}
          {item.type === 'coupon' && <li>券码将发放至「我的卡券」，请在有效期内使用</li>}
          {item.type === 'physical' && <li>实物商品需填写收货地址，由工作人员安排发货</li>}
          <li>兑换后积分即时扣除，一经兑换不予退还</li>
          {typeof item.limit_per_user === 'number' && item.limit_per_user > 0 && (
            <li>每人限兑 {item.limit_per_user} 次</li>
          )}
        </ul>
      </div>

      {/* 底部按钮 */}
      <div
        style={{
          position: 'fixed',
          left: 0,
          right: 0,
          bottom: 0,
          padding: '8px 16px',
          background: '#fff',
          borderTop: '1px solid #eee',
          zIndex: 10,
        }}
      >
        <Button
          block
          loading={exchanging}
          onClick={handleExchange}
          style={{
            height: 48,
            borderRadius: 10,
            fontSize: 16,
            background: exchangeable ? '#4CAF50' : '#e0e0e0',
            color: exchangeable ? '#fff' : '#999',
            border: 'none',
          }}
        >
          {buttonText}
        </Button>
      </div>
    </div>
  );
}

export default function PointsProductDetailPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-50" />}>
      <PointsProductDetailInner />
    </Suspense>
  );
}
