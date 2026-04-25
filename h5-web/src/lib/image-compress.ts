/**
 * [2026-04-25 PRD F1] 浏览器端图片压缩工具
 *
 * 目标：长边 ≤ 1600 px，输出体积 ≤ 600 KB（典型 300~600 KB）
 * 若压缩后体积反而更大（极少数低分辨率图），跳过压缩走原图。
 *
 * 仅作用于 image/* 文件，PDF / 非图片直接原样返回。
 */

export interface CompressOptions {
  maxEdge?: number;
  targetBytes?: number;
  initialQuality?: number;
  minQuality?: number;
}

const DEFAULTS: Required<CompressOptions> = {
  maxEdge: 1600,
  targetBytes: 600 * 1024,
  initialQuality: 0.85,
  minQuality: 0.55,
};

function isImage(file: File): boolean {
  return !!file.type && file.type.startsWith('image/') && file.type !== 'image/gif';
}

async function loadImage(file: File): Promise<HTMLImageElement> {
  const url = URL.createObjectURL(file);
  try {
    return await new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error('图片加载失败'));
      img.src = url;
    });
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}

function canvasToBlob(canvas: HTMLCanvasElement, type: string, quality: number): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob((b) => resolve(b), type, quality));
}

/**
 * 压缩单张图片。返回压缩后的 File（或原 File，若压缩后体积更大）。
 */
export async function compressImage(file: File, opts: CompressOptions = {}): Promise<File> {
  const o = { ...DEFAULTS, ...opts };

  if (!isImage(file)) return file;
  if (typeof document === 'undefined') return file;

  let img: HTMLImageElement;
  try {
    img = await loadImage(file);
  } catch {
    return file;
  }

  const w0 = img.naturalWidth || img.width;
  const h0 = img.naturalHeight || img.height;
  if (!w0 || !h0) return file;

  const longest = Math.max(w0, h0);
  const scale = longest > o.maxEdge ? o.maxEdge / longest : 1;
  const w = Math.round(w0 * scale);
  const h = Math.round(h0 * scale);

  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (!ctx) return file;
  ctx.drawImage(img, 0, 0, w, h);

  const outType = file.type === 'image/png' && file.size < 200 * 1024 ? 'image/png' : 'image/jpeg';

  let q = o.initialQuality;
  let blob = await canvasToBlob(canvas, outType, q);

  while (blob && blob.size > o.targetBytes && q > o.minQuality) {
    q = Math.max(o.minQuality, q - 0.1);
    blob = await canvasToBlob(canvas, outType, q);
  }

  if (!blob) return file;

  if (blob.size >= file.size) {
    return file;
  }

  const ext = outType === 'image/png' ? '.png' : '.jpg';
  const baseName = file.name.replace(/\.[^.]+$/, '') || 'image';
  return new File([blob], baseName + ext, { type: outType, lastModified: Date.now() });
}

/**
 * 批量压缩图片。
 */
export async function compressImages(files: File[], opts: CompressOptions = {}): Promise<File[]> {
  const out: File[] = [];
  for (const f of files) {
    try {
      out.push(await compressImage(f, opts));
    } catch {
      out.push(f);
    }
  }
  return out;
}
