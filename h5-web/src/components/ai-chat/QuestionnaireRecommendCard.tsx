/**
 * [PRD-TAG-RECOMMEND-V1 2026-05-20] 问卷完成后「推荐商品卡」
 *
 * 设计：横滑商品卡列表，最多展示 N 个；卡片上展示：
 * - 商品图（占位灰底）
 * - 商品名
 * - 价格
 * - 履约方式角标
 * 点击行为根据父组件传入 clickMode 决定：
 *   - drawer：父组件弹商品详情抽屉
 *   - external：跳商城 /product/{id}
 */

import React from 'react';

export interface RecommendGoodsItem {
  id: number;
  name: string;
  sale_price: number;
  original_price?: number | null;
  image?: string | null;
  fulfillment_type?: string | null;
  fulfillment_label?: string | null;
  sales_count?: number;
}

export interface QuestionnaireRecommendCardProps {
  goods: RecommendGoodsItem[];
  clickMode?: 'drawer' | 'external';
  onClickGoods?: (g: RecommendGoodsItem) => void;
}

const FULFILLMENT_COLOR_MAP: Record<string, string> = {
  delivery: '#3B82F6', // 实物配送 蓝
  in_store: '#F97316', // 到店 暖橙
  on_site: '#10B981',  // 上门 绿
  virtual: '#8B5CF6',  // 权益 紫
};

export default function QuestionnaireRecommendCard(
  props: QuestionnaireRecommendCardProps,
): JSX.Element | null {
  const { goods, clickMode = 'drawer', onClickGoods } = props;
  if (!goods || goods.length === 0) return null;
  return (
    <div
      data-testid="qn-recommend-card"
      style={{
        background: '#fff',
        borderRadius: 16,
        border: '1px solid #E0F2FE',
        boxShadow: '0 2px 12px rgba(2,132,199,.10)',
        padding: '12px 12px 14px',
        marginTop: 8,
      }}
    >
      <div
        style={{
          fontSize: 14,
          fontWeight: 600,
          color: '#0F172A',
          marginBottom: 10,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}
      >
        <span>🎯</span>
        <span>为你推荐</span>
        <span style={{ fontSize: 12, color: '#94A3B8', fontWeight: 400 }}>
          共 {goods.length} 个
        </span>
      </div>
      <div
        style={{
          display: 'flex',
          overflowX: 'auto',
          gap: 10,
          paddingBottom: 4,
          WebkitOverflowScrolling: 'touch',
        }}
        className="qn-rec-scroll"
      >
        {goods.map((g) => {
          const ffColor = FULFILLMENT_COLOR_MAP[g.fulfillment_type || ''] || '#64748B';
          const ffLabel = g.fulfillment_label || g.fulfillment_type || '';
          return (
            <div
              key={g.id}
              data-testid={`qn-rec-item-${g.id}`}
              onClick={() => onClickGoods?.(g)}
              style={{
                flex: '0 0 140px',
                width: 140,
                background: '#F8FAFC',
                borderRadius: 12,
                border: '1px solid #E2E8F0',
                cursor: 'pointer',
                overflow: 'hidden',
                position: 'relative',
              }}
            >
              <div
                style={{
                  width: '100%',
                  height: 100,
                  background: g.image
                    ? `url(${g.image}) center/cover no-repeat`
                    : 'linear-gradient(135deg,#E0F2FE,#BAE6FD)',
                  position: 'relative',
                }}
              >
                {ffLabel && (
                  <span
                    style={{
                      position: 'absolute',
                      top: 6,
                      left: 6,
                      background: ffColor,
                      color: '#fff',
                      fontSize: 10,
                      padding: '2px 6px',
                      borderRadius: 8,
                      lineHeight: 1.2,
                    }}
                    data-testid="qn-rec-ff-badge"
                  >
                    {ffLabel}
                  </span>
                )}
              </div>
              <div style={{ padding: '8px 8px 10px' }}>
                <div
                  style={{
                    fontSize: 13,
                    color: '#0F172A',
                    fontWeight: 500,
                    lineHeight: 1.3,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    minHeight: 34,
                  }}
                >
                  {g.name}
                </div>
                <div style={{ marginTop: 6, display: 'flex', alignItems: 'baseline', gap: 6 }}>
                  <span style={{ color: '#EF4444', fontWeight: 600, fontSize: 14 }}>
                    ¥{Number(g.sale_price || 0).toFixed(2)}
                  </span>
                  {g.original_price && Number(g.original_price) > Number(g.sale_price) && (
                    <span
                      style={{
                        color: '#94A3B8',
                        fontSize: 11,
                        textDecoration: 'line-through',
                      }}
                    >
                      ¥{Number(g.original_price).toFixed(2)}
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <style jsx>{`
        .qn-rec-scroll::-webkit-scrollbar {
          height: 4px;
        }
        .qn-rec-scroll::-webkit-scrollbar-thumb {
          background: #cbd5e1;
          border-radius: 2px;
        }
      `}</style>
    </div>
  );
}
