// [Bug 修复 V1.0 / 2026-04-25] admin-web 滑块拼图验证码 API 封装
// 复用 lib/api 的 get/post（已自带响应拦截 + 401 跳转）
import { get, post } from './api';

export interface SliderChallenge {
  challenge_id: string;
  bg_image_base64: string;
  puzzle_image_base64: string;
  puzzle_y: number;
  bg_width: number;
  bg_height: number;
  puzzle_size: number;
}

export interface SliderTrailPoint {
  x: number;
  y: number;
  t: number;
}

export interface SliderVerifyResult {
  ok: boolean;
  captcha_token?: string;
  expires_in?: number;
  reason?: string;
  locked_seconds?: number;
}

export async function fetchSliderChallenge(): Promise<SliderChallenge> {
  return get<SliderChallenge>('/api/captcha/slider/issue');
}

export async function verifySlider(payload: {
  challenge_id: string;
  x: number;
  trail: SliderTrailPoint[];
}): Promise<SliderVerifyResult> {
  return post<SliderVerifyResult>('/api/captcha/slider/verify', payload);
}

/**
 * 提供给 SliderCaptcha 组件的统一 apiClient 适配器
 * 组件内部用 apiClient.get/apiClient.post 调用任意 URL
 */
export const sliderApiClient = {
  get: <T = any>(url: string) => get<T>(url),
  post: <T = any>(url: string, data: any) => post<T>(url, data),
};
