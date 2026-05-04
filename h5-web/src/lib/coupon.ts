/**
 * 优惠券通用工具函数（H5 端）
 *
 * - couponTypeLabel(type): 返回中文展示文案，统一 free_trial → "免费体验券"
 * - jumpToUseCoupon(router, userCouponId): 跳转到服务列表并带上 couponId 上下文
 */

import type { useRouter } from 'next/navigation';

export type CouponType = 'full_reduction' | 'discount' | 'voucher' | 'free_trial' | string;

const COUPON_TYPE_MAP: Record<string, string> = {
  full_reduction: '满减',
  discount: '折扣',
  voucher: '代金券',
  free_trial: '免费体验券',
};

export function couponTypeLabel(type: string | null | undefined): string {
  if (!type) return '';
  return COUPON_TYPE_MAP[type] || type;
}

type RouterLike = ReturnType<typeof useRouter>;

/**
 * 跳到服务列表并带上 couponId 上下文。
 * 注意：使用 router.push 时 Next.js 会自动拼上 basePath，
 * 这里**不要**手动加 basePath 前缀。
 */
export function jumpToUseCoupon(router: RouterLike, userCouponId: number | string): void {
  router.push(`/services?couponId=${userCouponId}`);
}
