// PRD: 后台登录页图形验证码改造（v1.0 / 2026-04-25）
// 4 位字符图形验证码（数字 2-9 + 大写字母去 OIL，共 31 字符），160×60 PNG，5 分钟过期，一次性使用
import { get } from './api';

export interface CaptchaImage {
  captcha_id: string;
  image_base64: string;
  expire_seconds: number;
}

export async function fetchCaptchaImage(): Promise<CaptchaImage> {
  return get<CaptchaImage>('/api/captcha/image');
}
