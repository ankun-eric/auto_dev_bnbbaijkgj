import api from './api';

export interface UploadLimitItem {
  module: string;
  module_name: string;
  max_size_mb: number;
}

/**
 * [Bug-471 2026-05-15] AI 对话卡片 / 胶囊「相册 / 拍照 / 本机 / 微信」共用的文件选择器。
 *
 * 修复要点：
 *  1) input 元素必须 appendChild 到 document.body，否则 iOS Safari / 微信内置浏览器会判定
 *     该 input 无任何引用、提前 GC，导致用户选完图后 onchange 不触发——这是「选完图毫无反应」
 *     的直接原因（原卡片版只是 new 了 input 然后 .click()，没有挂到 DOM）。
 *  2) 用 try/finally + 软延迟 removeChild 释放，避免泄漏；同时 onchange 是异步回调，
 *     需要在回调完成后再 removeChild，使用一次性 cleanup 函数兜底。
 *  3) 支持 multiple，让用户一次最多选 N 张图；超过的由调用方截断 + Toast 提示。
 *
 * 参数：
 *  - accept：file input 的 accept 属性（如 "image/*" / "image/*,application/pdf"）
 *  - source：'album' = 相册 / 'camera' = 拍照（添加 capture=environment 调起摄像头）
 *  - multiple：是否允许多选
 *  - onPicked：用户确认选择后回调（files = 用户所选 File 列表；可能为空）
 */
export function pickFilesViaHiddenInput(opts: {
  accept: string;
  source: 'album' | 'camera';
  multiple?: boolean;
  onPicked: (files: File[]) => void | Promise<void>;
}): void {
  if (typeof document === 'undefined') return;
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = opts.accept;
  if (opts.multiple) input.setAttribute('multiple', 'multiple');
  if (opts.source === 'camera') {
    input.setAttribute('capture', 'environment');
  }
  input.style.position = 'fixed';
  input.style.left = '-9999px';
  input.style.top = '-9999px';
  input.style.opacity = '0';
  input.style.pointerEvents = 'none';

  let removed = false;
  const removeInput = () => {
    if (removed) return;
    removed = true;
    try {
      if (input.parentNode) input.parentNode.removeChild(input);
    } catch {
      /* ignore */
    }
  };

  input.onchange = async (e) => {
    try {
      const fileList = (e.target as HTMLInputElement).files;
      const files: File[] = fileList ? Array.from(fileList) : [];
      await opts.onPicked(files);
    } finally {
      removeInput();
    }
  };

  document.body.appendChild(input);

  try {
    input.click();
  } catch {
    removeInput();
    return;
  }

  setTimeout(() => {
    if (!removed) removeInput();
  }, 5 * 60 * 1000);
}

/**
 * [Bug-471 2026-05-15] 上传单张图片到 /api/upload/image，返回服务器 URL。
 *
 * 这是 /drug 多图上传里"上传到服务器拿 URL"的同款做法，AI 对话卡片 / 胶囊
 * 选完图后逐张调用本函数，得到 URL 数组后再渲染到对话气泡里。
 */
export async function uploadImageToServer(file: File): Promise<string> {
  const fd = new FormData();
  fd.append('file', file);
  const res: any = await api.post('/api/upload/image', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  });
  const data = res?.data ?? res;
  const url = data?.url || data?.file_url;
  if (!url || typeof url !== 'string') {
    throw new Error('上传响应缺少 url 字段');
  }
  return url;
}

/**
 * [Bug-471 2026-05-15] 上传单个文件（非图片）到 /api/upload/file，返回服务器 URL。
 */
export async function uploadFileToServer(file: File): Promise<string> {
  const fd = new FormData();
  fd.append('file', file);
  const res: any = await api.post('/api/upload/file', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  });
  const data = res?.data ?? res;
  const url = data?.url || data?.file_url;
  if (!url || typeof url !== 'string') {
    throw new Error('上传响应缺少 url 字段');
  }
  return url;
}

let _limitsCache: { items: UploadLimitItem[]; ts: number } | null = null;
const CACHE_TTL = 10 * 60 * 1000;

export async function fetchUploadLimits(): Promise<UploadLimitItem[]> {
  if (_limitsCache && Date.now() - _limitsCache.ts < CACHE_TTL) {
    return _limitsCache.items;
  }
  try {
    const res: any = await api.get('/api/cos/upload-limits');
    const data = res.data || res;
    const items: UploadLimitItem[] = Array.isArray(data.items) ? data.items : [];
    _limitsCache = { items, ts: Date.now() };
    return items;
  } catch {
    return _limitsCache?.items || [];
  }
}

export async function checkFileSize(
  file: File | { size: number },
  module: string,
): Promise<{ ok: boolean; maxMb?: number }> {
  const limits = await fetchUploadLimits();
  const rule = limits.find((l) => l.module === module);
  if (!rule) return { ok: true };
  const maxBytes = rule.max_size_mb * 1024 * 1024;
  if (file.size > maxBytes) {
    return { ok: false, maxMb: rule.max_size_mb };
  }
  return { ok: true };
}

export function uploadWithProgress(
  url: string,
  formData: FormData,
  onProgress?: (percent: number) => void,
  options?: { timeout?: number },
): Promise<any> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
    const fullUrl = url.startsWith('http') ? url : basePath + url;

    xhr.open('POST', fullUrl);
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }

    if (options?.timeout) {
      xhr.timeout = options.timeout;
    }

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          resolve(xhr.responseText);
        }
      } else if (xhr.status === 401) {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          window.location.href = `${basePath}/login`;
        }
        reject(new Error('Unauthorized'));
      } else {
        let detail = '上传失败';
        try {
          const body = JSON.parse(xhr.responseText);
          detail = body.detail || body.message || detail;
        } catch { /* ignore */ }
        const err: any = new Error(detail);
        err.status = xhr.status;
        err.response = { status: xhr.status, data: xhr.responseText };
        reject(err);
      }
    };

    xhr.onerror = () => reject(new Error('网络连接失败'));
    xhr.ontimeout = () => reject(new Error('上传超时'));

    xhr.send(formData);
  });
}
