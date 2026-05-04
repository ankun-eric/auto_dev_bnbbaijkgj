'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Image, ImageViewer, Tag, Toast } from 'antd-mobile';
import { DislikeOutlined, LikeOutlined } from '@ant-design/icons';
import { resolveAssetUrl } from '@/lib/asset-url';

export interface KnowledgeHit {
  entry_id: number;
  kb_name?: string;
  match_type?: string;
  match_score?: number;
  title?: string;
  question?: string;
  content_json?: unknown;
  display_mode?: string;
  hit_log_id?: number;
  /** 兼容关键词命中里的分数字段 */
  score?: number;
  products?: Array<{
    id: number;
    name: string;
    price: number;
    image?: string;
    type: string;
    detail_url?: string;
  }>;
}

export interface KnowledgeCardProps {
  hit: KnowledgeHit;
  hitLogId?: number;
  onFeedback?: (hitLogId: number, feedback: 'like' | 'dislike') => void | Promise<void>;
}

const IMG_EXT = /\.(jpe?g|png|gif|webp|bmp)(\?|#|$)/i;
const VIDEO_EXT = /\.(mp4|webm|m3u8)(\?|#|$)/i;

function collectUrls(value: unknown, pred: (u: string) => boolean): string[] {
  const found: string[] = [];
  const walk = (v: unknown) => {
    if (v == null) return;
    if (typeof v === 'string') {
      if (/^https?:\/\//i.test(v) && pred(v)) found.push(v);
      return;
    }
    if (Array.isArray(v)) {
      v.forEach(walk);
      return;
    }
    if (typeof v === 'object') {
      Object.values(v as object).forEach(walk);
    }
  };
  walk(value);
  return [...new Set(found)];
}

function extractImgSrcsFromHtml(html: string): string[] {
  const re = /<img[^>]+src=["']([^"']+)["']/gi;
  const out: string[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(html)) !== null) {
    out.push(m[1]);
  }
  return out;
}

function getRichHtml(contentJson: unknown): string | null {
  if (contentJson == null) return null;
  if (typeof contentJson === 'string') {
    const t = contentJson.trim();
    if (t.startsWith('<') || t.includes('</')) return contentJson;
    return null;
  }
  if (typeof contentJson === 'object') {
    const o = contentJson as Record<string, unknown>;
    for (const k of ['html', 'body', 'rich_text', 'content']) {
      const v = o[k];
      if (typeof v === 'string' && (v.includes('<') || v.includes('</'))) return v;
    }
    if (Array.isArray(o.blocks)) {
      const parts: string[] = [];
      for (const b of o.blocks as unknown[]) {
        if (!b || typeof b !== 'object') continue;
        const block = b as Record<string, unknown>;
        const type = String(block.type || '');
        if (type === 'html' && typeof block.content === 'string') parts.push(block.content);
        else if (type === 'text' && typeof block.text === 'string') {
          parts.push(`<p>${escapeHtml(block.text)}</p>`);
        }
      }
      if (parts.length) return parts.join('');
    }
  }
  return null;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function getPlainText(contentJson: unknown): string {
  if (typeof contentJson === 'string') {
    const t = contentJson.trim();
    if (!t.startsWith('<') && !t.includes('</')) return contentJson;
    return '';
  }
  if (contentJson && typeof contentJson === 'object') {
    const o = contentJson as Record<string, unknown>;
    if (typeof o.text === 'string') return o.text;
    if (typeof o.plain === 'string') return o.plain;
  }
  return '';
}

function getImageListField(contentJson: unknown): string[] {
  if (!contentJson || typeof contentJson !== 'object') return [];
  const o = contentJson as Record<string, unknown>;
  const raw = o.images ?? o.image_urls ?? o.imageList;
  if (!Array.isArray(raw)) return [];
  return raw.filter((x): x is string => typeof x === 'string' && /^https?:\/\//i.test(x));
}

export function KnowledgeCard({ hit, hitLogId, onFeedback }: KnowledgeCardProps) {
  const router = useRouter();
  const [localFeedback, setLocalFeedback] = useState<'like' | 'dislike' | null>(null);

  const logId = hitLogId ?? hit.hit_log_id;

  const richHtml = useMemo(() => getRichHtml(hit.content_json), [hit.content_json]);
  const plain = useMemo(() => getPlainText(hit.content_json), [hit.content_json]);

  const htmlImgSrcs = useMemo(() => (richHtml ? extractImgSrcsFromHtml(richHtml) : []), [richHtml]);

  const gridImages = useMemo(() => {
    const fromField = getImageListField(hit.content_json);
    if (fromField.length) return fromField;
    const all = collectUrls(hit.content_json, (u) => IMG_EXT.test(u));
    const embedded = new Set(htmlImgSrcs);
    return all.filter((u) => !embedded.has(u));
  }, [hit.content_json, htmlImgSrcs]);

  const videos = useMemo(
    () => collectUrls(hit.content_json, (u) => VIDEO_EXT.test(u)),
    [hit.content_json]
  );

  const score = hit.match_score ?? hit.score ?? 0;
  const matchLabel = hit.match_type || '—';

  const openImage = (url: string, index: number) => {
    const list = gridImages.length ? gridImages : [url];
    const start = gridImages.length ? index : 0;
    ImageViewer.Multi.show({
      images: list,
      defaultIndex: Math.min(start, list.length - 1),
    });
  };

  const handleProductDetail = (p: NonNullable<KnowledgeHit['products']>[0]) => {
    if (p.detail_url) {
      window.location.href = p.detail_url;
      return;
    }
    router.push('/points/mall');
  };

  const submitFeedback = async (kind: 'like' | 'dislike') => {
    if (localFeedback) {
      Toast.show({ content: '已反馈' });
      return;
    }
    if (logId == null) {
      Toast.show({ content: '暂无法反馈，请稍后重试' });
      return;
    }
    if (!onFeedback) {
      Toast.show({ content: '反馈未就绪' });
      return;
    }
    try {
      await Promise.resolve(onFeedback(logId, kind));
      setLocalFeedback(kind);
    } catch {
      // 由调用方提示错误时可忽略
    }
  };

  return (
    <div
      className="mt-2 rounded-xl bg-white overflow-hidden"
      style={{
        boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
        border: '1px solid #f0f0f0',
      }}
    >
      <div className="px-3 pt-3 pb-2 border-b border-gray-100">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {hit.kb_name ? (
            <Tag color="primary" style={{ '--border-radius': '6px', fontSize: 11 }}>
              {hit.kb_name}
            </Tag>
          ) : null}
          <span className="text-gray-400">匹配：{matchLabel}</span>
          <span className="text-gray-400">相关度 {(score * 100).toFixed(0)}%</span>
          {hit.display_mode ? (
            <Tag style={{ '--border-radius': '6px', fontSize: 11 }}>{hit.display_mode}</Tag>
          ) : null}
        </div>
        {hit.title ? <div className="text-sm font-medium text-gray-800 mt-2">{hit.title}</div> : null}
        {hit.question ? <div className="text-xs text-gray-500 mt-1">Q：{hit.question}</div> : null}
      </div>

      <div className="px-3 py-2">
        {richHtml ? (
          <div
            className="kb-rich text-sm text-gray-700 leading-relaxed [&_img]:max-w-full [&_img]:rounded-lg [&_a]:text-[#52c41a] [&_p]:mb-1"
            dangerouslySetInnerHTML={{ __html: richHtml }}
          />
        ) : plain ? (
          <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{plain}</p>
        ) : (
          <p className="text-xs text-gray-400">暂无正文</p>
        )}

        {gridImages.length > 0 ? (
          <div className="grid grid-cols-3 gap-2 mt-3">
            {gridImages.map((url, i) => (
              <button
                key={`${url}-${i}`}
                type="button"
                className="relative w-full pt-[100%] rounded-lg overflow-hidden bg-gray-100 active:opacity-90"
                onClick={() => openImage(url, i)}
                aria-label="查看大图"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={url}
                  alt=""
                  className="absolute inset-0 w-full h-full object-cover"
                  loading="lazy"
                />
              </button>
            ))}
          </div>
        ) : null}

        {videos.map((src) => (
          <video
            key={src}
            src={src}
            controls
            playsInline
            className="w-full max-h-[220px] rounded-lg mt-3 bg-black"
          />
        ))}

        {hit.products && hit.products.length > 0 ? (
          <div className="mt-3 space-y-2">
            {hit.products.map((p) => (
              <div
                key={`${p.type}-${p.id}`}
                className="flex items-stretch gap-3 p-2 rounded-xl bg-gray-50 border border-gray-100"
              >
                <div className="w-[72px] h-[72px] flex-shrink-0 rounded-lg overflow-hidden bg-white">
                  {p.image ? (
                    <Image src={resolveAssetUrl(p.image)} fit="cover" className="w-full h-full" lazy />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-gray-300 text-xs">无图</div>
                  )}
                </div>
                <div className="flex-1 min-w-0 flex flex-col justify-between py-0.5">
                  <div className="text-sm font-medium text-gray-800 line-clamp-2">{p.name}</div>
                  <div className="text-primary font-semibold text-sm mt-1">
                    ¥{p.price}
                  </div>
                  <div className="mt-2">
                    <Button
                      size="mini"
                      color="primary"
                      fill="outline"
                      onClick={() => handleProductDetail(p)}
                      style={{ borderRadius: 16, fontSize: 12 }}
                    >
                      查看详情
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      <div className="flex items-center justify-end gap-6 px-3 py-2 border-t border-gray-100 bg-gray-50/80">
        <button
          type="button"
          className="flex items-center gap-1.5 text-sm text-gray-600 min-h-[44px] min-w-[44px] justify-center active:opacity-70"
          onClick={() => submitFeedback('like')}
          aria-label="点赞"
        >
          <LikeOutlined
            style={{
              fontSize: 20,
              color: localFeedback === 'like' ? '#52c41a' : '#999',
            }}
          />
          <span style={{ color: localFeedback === 'like' ? '#52c41a' : '#666' }}>有用</span>
        </button>
        <button
          type="button"
          className="flex items-center gap-1.5 text-sm text-gray-600 min-h-[44px] min-w-[44px] justify-center active:opacity-70"
          onClick={() => submitFeedback('dislike')}
          aria-label="点踩"
        >
          <DislikeOutlined
            style={{
              fontSize: 20,
              color: localFeedback === 'dislike' ? '#ff4d4f' : '#999',
            }}
          />
          <span style={{ color: localFeedback === 'dislike' ? '#ff4d4f' : '#666' }}>无用</span>
        </button>
      </div>
    </div>
  );
}

export default KnowledgeCard;
