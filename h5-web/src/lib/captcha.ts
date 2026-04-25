// [PRD V1.0 §M7] 图形验证码工具：统一封装 GET /api/captcha/image
// 返回 { captcha_id, image_base64 }，前端拿到后直接 <img src={image_base64}>。
import api from './api';

export interface CaptchaImage {
  captcha_id: string;
  image_base64: string;
}

export async function fetchCaptchaImage(): Promise<CaptchaImage> {
  const res = await api.get<CaptchaImage, CaptchaImage>('/api/captcha/image');
  return res;
}

// 校验密码强度（≥ 8 位，含字母 + 数字）
export const PASSWORD_REGEX = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/;
export const PASSWORD_HINT = '密码至少 8 位，须同时包含字母和数字';
