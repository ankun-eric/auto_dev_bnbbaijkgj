/**
 * [2026-04-25 PRD F1] 浏览器端图片压缩工具
 *
 * 目标：长边 ≤ 1920 px，输出体积 ≤ 1 MB（quality 0.8 起步，逐级 0.1 衰减）
 * 若压缩后体积反而更大（极少数低分辨率图），跳过压缩走原图。
 *
 * 仅作用于 image/* 文件，PDF / 非图片 / GIF 直接原样返回。
 *
 * 调试：所有早返回（fallback to original）分支均会输出 console.warn，
 * 便于线上排查 "为什么没压缩 / 为什么体积没下来"。
 */

export interface CompressOptions {
  maxEdge?: number;
  targetBytes?: number;
  initialQuality?: number;
  minQuality?: number;
}

const DEFAULTS: Required<CompressOptions> = {
  maxEdge: 1920,
  targetBytes: 1024 * 1024,
  initialQuality: 0.8,
  minQuality: 0.5,
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
 * 压缩单张图片。返回压缩后的 File（或原 File，若压缩后体积更大 / 不可压缩）。
 */
export async function compressImage(file: File, opts: CompressOptions = {}): Promise<File> {
  const o = { ...DEFAULTS, ...opts };

  if (!isImage(file)) {
    console.warn('[compress] fallback to original (not image / gif):', file.name, file.size, file.type);
    return file;
  }
  if (typeof document === 'undefined') {
    console.warn('[compress] fallback to original (no document, SSR?):', file.name, file.size);
    return file;
  }

  let img: HTMLImageElement;
  try {
    img = await loadImage(file);
  } catch {
    console.warn('[compress] fallback to original (image load failed):', file.name, file.size);
    return file;
  }

  const w0 = img.naturalWidth || img.width;
  const h0 = img.naturalHeight || img.height;
  if (!w0 || !h0) {
    console.warn('[compress] fallback to original (invalid size):', file.name, file.size, w0, h0);
    return file;
  }

  const longest = Math.max(w0, h0);
  const scale = longest > o.maxEdge ? o.maxEdge / longest : 1;
  const w = Math.round(w0 * scale);
  const h = Math.round(h0 * scale);

  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    console.warn('[compress] fallback to original (no 2d ctx):', file.name, file.size);
    return file;
  }
  ctx.drawImage(img, 0, 0, w, h);

  const outType = file.type === 'image/png' && file.size < 200 * 1024 ? 'image/png' : 'image/jpeg';

  const qualitySeq: number[] = [];
  for (let q = o.initialQuality; q >= o.minQuality - 1e-6; q = +(q - 0.1).toFixed(2)) {
    qualitySeq.push(+q.toFixed(2));
  }
  if (qualitySeq.length === 0) qualitySeq.push(o.initialQuality);

  let blob: Blob | null = null;
  let usedQuality = qualitySeq[0];
  for (const q of qualitySeq) {
    usedQuality = q;
    blob = await canvasToBlob(canvas, outType, q);
    if (!blob) continue;
    if (blob.size <= o.targetBytes) break;
  }

  if (!blob) {
    console.warn('[compress] fallback to original (toBlob returned null):', file.name, file.size);
    return file;
  }

  if (blob.size >= file.size) {
    console.warn(
      '[compress] fallback to original (compressed >= original):',
      file.name,
      'orig=', file.size,
      'compressed=', blob.size,
      'quality=', usedQuality,
      'maxEdge=', o.maxEdge,
      'target=', o.targetBytes,
    );
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
    } catch (e) {
      console.warn('[compress] fallback to original (exception):', f.name, f.size, e);
      out.push(f);
    }
  }
  return out;
}
