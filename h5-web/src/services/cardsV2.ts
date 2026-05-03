/**
 * 卡管理 v2.0（第 2~5 期）H5 端 API 客户端封装。
 *
 * 所有接口均使用全局 api（带 token、basePath 自适配 /autodev/{DEPLOY_ID}）。
 */
import api from '@/lib/api';

export interface PurchaseRequest {
  card_definition_id: number;
  payment_method?: string;
  notes?: string;
  from_product_id?: number;
  renew_from_user_card_id?: number;
}

export interface PurchaseResponse {
  order_id: number;
  order_no: string;
  total_amount: number;
  product_type: string;
  card_definition_id: number;
  status: string;
  from_product_id?: number | null;
  renew_from_user_card_id?: number | null;
}

export interface RedemptionCode {
  user_card_id: number;
  token: string;
  digits: string;
  issued_at: string;
  expires_at: string;
  status: string;
}

export interface CardUsageLog {
  id: number;
  user_card_id: number;
  product_id: number;
  product_name?: string | null;
  store_id?: number | null;
  store_name?: string | null;
  technician_id?: number | null;
  used_at: string;
  notes?: string | null;
}

export interface SavingsTip {
  has_card: boolean;
  card_id?: number | null;
  card_name?: string | null;
  save_amount?: number | null;
  per_use_price?: number | null;
}

export interface RenewableCard {
  user_card_id: number;
  card_definition_id: number;
  card_name: string;
  valid_to: string;
  days_to_expire: number;
  renew_strategy: string;
  can_renew: boolean;
  reason?: string | null;
}

const cardsV2 = {
  // 第 2 期：购卡
  purchase: (data: PurchaseRequest) =>
    api.post<PurchaseResponse, PurchaseResponse>('/api/cards/purchase', data),
  payCardOrder: (orderId: number) =>
    api.post<{ message: string; order_id: number; user_card_id?: number }>(
      `/api/orders/unified/${orderId}/pay-card`
    ),

  // 第 3 期：核销码
  issueRedemptionCode: (userCardId: number) =>
    api.post<RedemptionCode, RedemptionCode>(`/api/cards/me/${userCardId}/redemption-code`),
  getCurrentRedemptionCode: (userCardId: number) =>
    api.get<RedemptionCode | null, RedemptionCode | null>(
      `/api/cards/me/${userCardId}/redemption-code/current`
    ),
  myUsageLogs: (userCardId: number, params?: { page?: number; page_size?: number }) =>
    api.get<{ total: number; items: CardUsageLog[] }, { total: number; items: CardUsageLog[] }>(
      `/api/cards/me/${userCardId}/usage-logs`,
      { params }
    ),
  refundCardOrder: (orderId: number) =>
    api.post(`/api/orders/unified/${orderId}/refund-card`),

  // 第 4 期：拆单 / 续卡 / 省钱提示 / 可续卡列表
  checkout: (items: Array<Record<string, unknown>>, notes?: string) =>
    api.post<{ split_group_id: string; order_ids: number[] }>('/api/orders/unified/checkout', {
      items,
      notes,
    }),
  renewCard: (userCardId: number, payment_method = 'wechat') =>
    api.post(`/api/cards/me/${userCardId}/renew`, { payment_method }),
  productSavingsTip: (productId: number) =>
    api.get<SavingsTip, SavingsTip>(`/api/products/${productId}/savings-tip`),
  myRenewableCards: () =>
    api.get<{ total: number; items: RenewableCard[] }, { total: number; items: RenewableCard[] }>(
      '/api/cards/me/renewable'
    ),

  // 第 5 期：分享海报
  sharePosterUrl: (cardId: number, inviterUserId?: number) => {
    const params = inviterUserId ? `?inviter_user_id=${inviterUserId}` : '';
    return `/api/cards/${cardId}/share-poster${params}`;
  },
};

export default cardsV2;
