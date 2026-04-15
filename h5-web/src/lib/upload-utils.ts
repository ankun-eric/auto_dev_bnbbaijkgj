import api from './api';

export interface UploadLimitItem {
  module: string;
  module_name: string;
  max_size_mb: number;
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
