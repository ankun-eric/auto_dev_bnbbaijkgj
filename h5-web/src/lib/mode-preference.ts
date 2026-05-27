// [BUG_FIX_CARE_MODE_ENTRY_H5_20260527] 关怀模式入口缺失修复
// 模式偏好读写工具：localStorage 优先，后端异步双写，失败不阻塞跳转。

import api from '@/lib/api';

export type AppMode = 'standard' | 'care';

const LS_KEY = 'app_mode_preference';

export function getLocalMode(): AppMode {
  if (typeof window === 'undefined') return 'standard';
  try {
    const v = window.localStorage.getItem(LS_KEY);
    return v === 'care' ? 'care' : 'standard';
  } catch {
    return 'standard';
  }
}

export function setLocalMode(mode: AppMode): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(LS_KEY, mode);
  } catch {
    // ignore quota / privacy mode errors
  }
}

export async function saveModePreference(mode: AppMode): Promise<void> {
  setLocalMode(mode);
  try {
    await api.post('/api/user/mode-preference', { mode });
  } catch (e) {
    // 静默：本地已存，跳转优先级高于偏好持久化
    // eslint-disable-next-line no-console
    console.warn('[mode-preference] 保存到后端失败，已写入本地', e);
  }
}

export async function fetchRemoteMode(): Promise<AppMode> {
  try {
    const resp = await api.get('/api/user/mode-preference');
    const m = resp?.data?.mode;
    return m === 'care' ? 'care' : 'standard';
  } catch {
    return getLocalMode();
  }
}
