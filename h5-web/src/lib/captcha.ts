// [PRD V1.0 §M7] 图形验证码工具：统一封装 GET /api/captcha/image
// 返回 { captcha_id, image_base64 }，前端拿到后直接 <img src={image_base64}>。
//
// [Bug 修复 V1.0 / 2026-04-25] 新增滑块拼图相关方法 fetchSliderChallenge / verifySlider
// - fetchCaptchaImage 保留：用户端 H5 仍用旧字符验证码
// - 商家端登录页改用 SliderCaptcha 组件 + 下面两个方法
import api from './api';

export interface CaptchaImage {
  captcha_id: string;
  image_base64: string;
}

export async function fetchCaptchaImage(): Promise<CaptchaImage> {
  const res = await api.get<CaptchaImage, CaptchaImage>('/api/captcha/image');
  return res;
}

// ─────────── 滑块拼图（Bug 修复 V1.0 / 2026-04-25） ───────────

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
  return api.get<SliderChallenge, SliderChallenge>('/api/captcha/slider/issue');
}

export async function verifySlider(payload: {
  challenge_id: string;
  x: number;
  trail: SliderTrailPoint[];
}): Promise<SliderVerifyResult> {
  return api.post<SliderVerifyResult, SliderVerifyResult>(
    '/api/captcha/slider/verify',
    payload,
  );
}

// 校验密码强度（≥ 8 位，含字母 + 数字）
export const PASSWORD_REGEX = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/;
export const PASSWORD_HINT = '密码至少 8 位，须同时包含字母和数字';
