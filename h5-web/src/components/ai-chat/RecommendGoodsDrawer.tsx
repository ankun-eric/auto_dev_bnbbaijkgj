/**
 * [PRD-TAG-RECOMMEND-V1 2026-05-20] 推荐商品详情抽屉
 *
 * 用户在 AI 对话页点击推荐卡片商品后，默认在抽屉中打开商品简介，
 * 不离开 AI 对话上下文。抽屉底部提供「前往商城查看更多」弱入口。
 */

import React, { useEffect, useState } from 'react';
import { Popup } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

import type { RecommendGoodsItem } from './QuestionnaireRecommendCard';

export interface RecommendGoodsDrawerProps {
  open: boolean;
  goods: RecommendGoodsItem | null;
  onClose: () => void;
}

interface ProductDetail {
  id: number;
  name: string;
  sale_price?: number;
  original_price?: number | null;
  description?: string | null;
  selling_point?: string | null;
  images?: string[];
  fulfillment_type?: string | null;
  fulfillment_label?: string | null;
  sales_count?: number;
}

const FULFILLMENT_LABEL_MAP: Record<string, string> = {
  delivery: '实物配送',
  in_store: '到店服务',
  on_site: '上门服务',
  virtual: '权益服务',
};

export default function RecommendGoodsDrawer(
  props: RecommendGoodsDrawerProps,
): JSX.Element {
  const { open, goods, onClose } = props;
  const router = useRouter();
  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !goods) {
      setDetail(null);
      return;
    }
    setDetail({
      id: goods.id,
      name: goods.name,
      sale_price: goods.sale_price,
      original_price: goods.original_price,
      images: goods.image ? [goods.image] : [],
      fulfillment_type: goods.fulfillment_type,
      fulfillment_label: goods.fulfillment_label,
    });
    setLoading(true);
    api
      .get<any>(`/api/products/${goods.id}`)
      .then((res) => {
        const d = res?.data || res || {};
        setDetail({
          id: goods.id,
          name: d.name || goods.name,
          sale_price: Number(d.sale_price || goods.sale_price || 0),
          original_price: d.original_price ? Number(d.original_price) : goods.original_price,
          description: d.description || d.selling_point || '',
          selling_point: d.selling_point,
          images: Array.isArray(d.images) && d.images.length ? d.images : (goods.image ? [goods.image] : []),
          fulfillment_type: d.fulfillment_type || goods.fulfillment_type,
          fulfillment_label:
            FULFILLMENT_LABEL_MAP[d.fulfillment_type] ||
            goods.fulfillment_label ||
            FULFILLMENT_LABEL_MAP[goods.fulfillment_type || ''] ||
            '',
          sales_count: d.sales_count,
        });
      })
      .catch(() => {
        // 兜底使用 goods 简要数据
      })
      .finally(() => setLoading(false));
  }, [open, goods]);

  return (
    <Popup
      visible={open}
      onMaskClick={onClose}
      onClose={onClose}
      position="right"
      bodyStyle={{ width: '88vw', height: '100vh', background: '#fff' }}
      data-testid="qn-rec-goods-drawer"
    >
      <div style={{ padding: 16, height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
          <button
            onClick={onClose}
            style={{
              border: 0,
              background: 'transparent',
              fontSize: 18,
              cursor: 'pointer',
            }}
          >
            ←
          </button>
          <span style={{ fontWeight: 600, fontSize: 16, marginLeft: 8 }}>商品详情</span>
        </div>
        {detail ? (
          <div style={{ flex: 1, overflowY: 'auto' }}>
            <div
              style={{
                width: '100%',
                height: 200,
                borderRadius: 12,
                background: detail.images && detail.images[0]
                  ? `url(${detail.images[0]}) center/cover no-repeat`
                  : 'linear-gradient(135deg,#E0F2FE,#BAE6FD)',
                marginBottom: 12,
              }}
            />
            <div style={{ fontWeight: 600, fontSize: 18, color: '#0F172A', marginBottom: 6 }}>
              {detail.name}
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 8 }}>
              <span style={{ color: '#EF4444', fontSize: 22, fontWeight: 700 }}>
                ¥{Number(detail.sale_price || 0).toFixed(2)}
              </span>
              {detail.original_price && Number(detail.original_price) > Number(detail.sale_price || 0) && (
                <span style={{ color: '#94A3B8', textDecoration: 'line-through', fontSize: 13 }}>
                  ¥{Number(detail.original_price).toFixed(2)}
                </span>
              )}
            </div>
            {detail.fulfillment_label && (
              <div style={{ marginBottom: 12 }}>
                <span
                  style={{
                    background: '#E0F2FE',
                    color: '#0284C7',
                    padding: '2px 10px',
                    borderRadius: 10,
                    fontSize: 12,
                  }}
                >
                  {detail.fulfillment_label}
                </span>
              </div>
            )}
            {detail.selling_point && (
              <div style={{ color: '#64748B', fontSize: 13, marginBottom: 8 }}>
                {detail.selling_point}
              </div>
            )}
            {detail.description && (
              <div
                style={{
                  background: '#F8FAFC',
                  padding: 12,
                  borderRadius: 8,
                  fontSize: 13,
                  lineHeight: 1.6,
                  color: '#334155',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {detail.description}
              </div>
            )}
            {loading && (
              <div style={{ color: '#94A3B8', fontSize: 12, marginTop: 12 }}>
                加载中…
              </div>
            )}
          </div>
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94A3B8' }}>
            正在加载…
          </div>
        )}

        {/* 底部「前往商城查看更多」弱入口 */}
        <div style={{ paddingTop: 12, borderTop: '1px solid #F1F5F9' }}>
          <button
            data-testid="qn-rec-goods-go-mall"
            onClick={() => {
              if (detail?.id) {
                router.push(`/product/${detail.id}`);
              }
            }}
            style={{
              width: '100%',
              height: 40,
              borderRadius: 20,
              border: '1px solid #0284C7',
              background: '#fff',
              color: '#0284C7',
              fontSize: 14,
              cursor: 'pointer',
            }}
          >
            前往商城查看更多 →
          </button>
        </div>
      </div>
    </Popup>
  );
}
