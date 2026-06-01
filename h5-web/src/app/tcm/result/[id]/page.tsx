'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button, SpinLoading } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';
import { formatDate } from '@/lib/datetime';

/**
 * 体质测评结果页（一期 · 6 屏）。
 * 数据来源：后端 `/api/constitution/result/{id}` 聚合接口。
 *
 * 屏 1：体质名片（拟人形象 + 雷达图 + 一句话描述）
 * 屏 2：深度解读（特征 + 成因）
 * 屏 3：个性化养生方案（饮食 / 作息 / 运动 / 情志）
 * 屏 4：专属膳食套餐推荐
 * 屏 5：广州门店服务（领券 + 预约）
 * 屏 6：分享卡
 */

interface Persona {
  emoji?: string;
  avatar_keyword?: string;
  color?: string;
  one_line?: string;
}

// [PRD-TIZHI-OPTIM-V1] 优化点2：运营配置驱动的内容卡（专属膳食套餐 / 门店服务）
interface ContentCard {
  id: number;
  title: string;
  subtitle: string | null;
  image: string | null;
  tag: string | null;
  tag_color: string | null;
  price: number | null;
  original_price: number | null;
  link_type: 'product' | 'service' | 'order' | 'coupon' | 'url' | 'none';
  link_value: string | null;
  button_text: string | null;
}

interface CouponState {
  available: boolean;
  status: 'claimable' | 'claimed' | 'used' | 'unavailable';
  message: string;
  coupon_id: number | null;
  user_coupon_id?: number;
  validity_days?: number;
  expire_at?: string;
}

interface ResultData {
  diagnosis_id: number;
  created_at: string;
  member_label: string;
  screen1_card: {
    type: string;
    persona: Persona;
    one_line_desc: string;
    short_desc: string;
    color: string;
    radar: { dimensions: string[]; scores: number[] };
  };
  screen2_analysis: {
    features: {
      external?: string[];
      internal?: string[];
      easy_problems?: string[];
    };
    causes: { innate?: string; acquired?: string };
    ai_summary?: string;
  };
  screen3_plan: {
    diet: { good?: string[]; avoid?: string[] };
    lifestyle: string[];
    exercise: { name: string; frequency: string }[];
    emotion: string[];
    ai_extra?: string;
  };
  screen4_packages: ContentCard[];
  screen5_store: {
    services: ContentCard[];
    coupon: CouponState;
  };
  screen6_share: {
    title: string;
    share_title: string;
    subtitle: string;
    persona: Persona;
    brand: string;
    cover_image: string;
    logo_image: string;
    radar_preview: { dimensions: string[]; scores: number[] };
    poster_tips: string[];
    slogan: string;
    qr_hint: string;
  };
  disclaimer: string;
}

// ══════════════════════════════════════════════════════════
// 雷达图 SVG 组件（零依赖）
// ══════════════════════════════════════════════════════════
function RadarChart({
  dimensions,
  scores,
  color = '#0EA5E9',
  size = 220,
}: {
  dimensions: string[];
  scores: number[];
  color?: string;
  size?: number;
}) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.38;
  const n = dimensions.length;
  const angle = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2;
  const point = (i: number, v: number) => {
    const vv = Math.max(0, Math.min(100, v)) / 100;
    return [cx + r * vv * Math.cos(angle(i)), cy + r * vv * Math.sin(angle(i))];
  };

  // 背景同心多边形（4 层）
  const rings = [0.25, 0.5, 0.75, 1.0];

  // 计分点
  const pts = scores.map((v, i) => point(i, v));
  const polygon = pts.map((p) => `${p[0]},${p[1]}`).join(' ');

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {rings.map((ratio, ri) => {
        const bgPts = Array.from({ length: n }, (_, i) => {
          const x = cx + r * ratio * Math.cos(angle(i));
          const y = cy + r * ratio * Math.sin(angle(i));
          return `${x},${y}`;
        }).join(' ');
        return (
          <polygon
            key={ri}
            points={bgPts}
            fill="none"
            stroke="#e8e8e8"
            strokeWidth={1}
          />
        );
      })}
      {Array.from({ length: n }, (_, i) => {
        const x = cx + r * Math.cos(angle(i));
        const y = cy + r * Math.sin(angle(i));
        return (
          <line
            key={i}
            x1={cx}
            y1={cy}
            x2={x}
            y2={y}
            stroke="#e8e8e8"
            strokeWidth={1}
          />
        );
      })}
      <polygon
        points={polygon}
        fill={color}
        fillOpacity={0.25}
        stroke={color}
        strokeWidth={2}
      />
      {pts.map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r={3} fill={color} />
      ))}
      {dimensions.map((d, i) => {
        const x = cx + (r + 16) * Math.cos(angle(i));
        const y = cy + (r + 16) * Math.sin(angle(i));
        return (
          <text
            key={d}
            x={x}
            y={y}
            fontSize={11}
            fill="#555"
            textAnchor="middle"
            dominantBaseline="middle"
          >
            {d}
          </text>
        );
      })}
    </svg>
  );
}

// ══════════════════════════════════════════════════════════
// 分享卡海报（Canvas 生成，用于保存图片）
// ══════════════════════════════════════════════════════════
/**
 * [PRD-TIZHI-OPTIM-V1] 优化点4·形态二：朋友圈长图海报。
 * 方案 A · 清爽留白版（浅蓝底 + 白卡片）。品牌天蓝、宾尼小康，
 * 顶部品牌 + 大标题，中部高亮体质结果（主/兼），下部 3 条按体质匹配的调理建议，
 * 底部小程序码占位 + 「长按识别测测你的体质」引导语。
 */
const BRAND_BLUE = '#0EA5E9';

async function generateShareCard(data: ResultData): Promise<string> {
  const w = 750;
  const h = 1334;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';

  // 浅蓝底（清爽留白版）
  ctx.fillStyle = '#EAF6FE';
  ctx.fillRect(0, 0, w, h);

  // 顶部：品牌
  ctx.textAlign = 'center';
  ctx.fillStyle = BRAND_BLUE;
  ctx.font = 'bold 40px "PingFang SC", sans-serif';
  ctx.fillText('宾尼小康', w / 2, 96);
  ctx.fillStyle = '#64748B';
  ctx.font = '26px "PingFang SC", sans-serif';
  ctx.fillText('中医体质测评', w / 2, 138);

  // 白色主卡片（圆角矩形）
  const cardX = 56;
  const cardY = 186;
  const cardW = w - cardX * 2;
  const cardH = 760;
  const radius = 28;
  ctx.fillStyle = '#FFFFFF';
  ctx.beginPath();
  ctx.moveTo(cardX + radius, cardY);
  ctx.arcTo(cardX + cardW, cardY, cardX + cardW, cardY + cardH, radius);
  ctx.arcTo(cardX + cardW, cardY + cardH, cardX, cardY + cardH, radius);
  ctx.arcTo(cardX, cardY + cardH, cardX, cardY, radius);
  ctx.arcTo(cardX, cardY, cardX + cardW, cardY, radius);
  ctx.closePath();
  ctx.fill();

  // 中部：拟人 emoji + 大标题（体质结果高亮）
  ctx.font = '120px serif';
  ctx.fillText(data.screen1_card.persona.emoji || '🌿', w / 2, cardY + 170);

  ctx.fillStyle = BRAND_BLUE;
  ctx.font = 'bold 30px "PingFang SC", sans-serif';
  ctx.fillText('我的体质是', w / 2, cardY + 230);

  ctx.fillStyle = '#0F172A';
  ctx.font = 'bold 72px "PingFang SC", sans-serif';
  ctx.fillText(`「${data.screen1_card.type}」`, w / 2, cardY + 318);

  // 一句话描述
  ctx.fillStyle = '#64748B';
  ctx.font = '28px "PingFang SC", sans-serif';
  const subtitle = data.screen1_card.one_line_desc || '';
  ctx.fillText(subtitle.length > 20 ? subtitle.slice(0, 20) + '…' : subtitle, w / 2, cardY + 368);

  // 下部：3 条按体质匹配的调理建议
  const tips = (data.screen6_share.poster_tips || []).slice(0, 3);
  ctx.textAlign = 'left';
  const tipLeft = cardX + 56;
  let tipY = cardY + 460;
  ctx.fillStyle = BRAND_BLUE;
  ctx.font = 'bold 28px "PingFang SC", sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('—— 调理建议 ——', w / 2, tipY);
  tipY += 50;
  ctx.textAlign = 'left';
  ctx.font = '26px "PingFang SC", sans-serif';
  tips.forEach((t, i) => {
    ctx.fillStyle = BRAND_BLUE;
    ctx.fillText(`${i + 1}`, tipLeft, tipY);
    ctx.fillStyle = '#334155';
    const text = String(t);
    const clipped = text.length > 22 ? text.slice(0, 22) + '…' : text;
    ctx.fillText(clipped, tipLeft + 40, tipY);
    tipY += 56;
  });

  // 底部：小程序码占位 + 引导语
  ctx.textAlign = 'center';
  ctx.strokeStyle = BRAND_BLUE;
  ctx.lineWidth = 3;
  ctx.strokeRect(w / 2 - 80, h - 280, 160, 160);
  ctx.fillStyle = BRAND_BLUE;
  ctx.font = '24px "PingFang SC", sans-serif';
  ctx.fillText('小程序码', w / 2, h - 280 + 86);
  ctx.fillStyle = '#0F172A';
  ctx.font = 'bold 32px "PingFang SC", sans-serif';
  ctx.fillText('长按识别测测你的体质', w / 2, h - 70);

  return canvas.toDataURL('image/png');
}

// ══════════════════════════════════════════════════════════
// 主页面
// ══════════════════════════════════════════════════════════
export default function TcmResultPage() {
  const router = useRouter();
  const params = useParams();
  const id = Array.isArray(params?.id) ? params.id[0] : (params?.id as string);

  const [data, setData] = useState<ResultData | null>(null);
  const [loading, setLoading] = useState(true);
  const [claimingCoupon, setClaimingCoupon] = useState(false);
  const [shareVisible, setShareVisible] = useState(false);
  const [shareImageUrl, setShareImageUrl] = useState<string | null>(null);
  const [generatingShare, setGeneratingShare] = useState(false);

  const fetchResult = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.get(`/api/constitution/result/${id}`);
      setData(res.data || res);
    } catch (err: any) {
      const status = err?.response?.status || err?.status;
      if (status === 404) {
        showToast('测评记录不存在，请重新测评', 'fail');
      } else {
        showToast('加载结果失败，请稍后重试', 'fail');
      }
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (id) fetchResult();
  }, [id, fetchResult]);

  const handleClaimCoupon = async () => {
    if (claimingCoupon || !data) return;
    setClaimingCoupon(true);
    try {
      const res: any = await api.post('/api/constitution/coupon/claim');
      const r = res.data || res;
      if (r.success) {
        showToast(r.already_claimed ? '您已领取过该券' : '领取成功，请到「我的优惠券」查看', 'success');
        await fetchResult();
      } else {
        showToast('领取失败，请稍后重试', 'fail');
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail || '领取失败，请稍后重试';
      showToast(String(msg), 'fail');
    } finally {
      setClaimingCoupon(false);
    }
  };

  const handleViewCoupons = () => {
    router.push('/my-coupons');
  };

  // [PRD-TIZHI-OPTIM-V1] 运营配置内容卡点击跳转（按 link_type 分发）
  const handleCardClick = (card: ContentCard) => {
    const v = card.link_value || '';
    switch (card.link_type) {
      case 'product':
        if (v) router.push(`/product-detail/${v}?source=tizhi_test`);
        break;
      case 'service':
        if (v) router.push(`/service-detail/${v}?source=tizhi_test`);
        break;
      case 'order':
        router.push(`/unified-orders?source=tizhi_test&project=${v || 'moxibustion'}`);
        break;
      case 'coupon':
        handleClaimCoupon();
        break;
      case 'url':
        if (v) window.location.href = v;
        break;
      default:
        break;
    }
  };

  // [PRD-TIZHI-OPTIM-V1] 形态一：转发给好友（H5 用系统分享/复制链接，标题动态带体质）
  const handleShareToFriend = async () => {
    if (!data) return;
    const shareTitle =
      data.screen6_share.share_title ||
      `我的体质是「${data.screen1_card.type}」，快来测测你是什么体质？`;
    const shareUrl =
      typeof window !== 'undefined' ? `${window.location.origin}/tcm` : '/tcm';
    try {
      const nav: any = typeof navigator !== 'undefined' ? navigator : null;
      if (nav && nav.share) {
        await nav.share({ title: shareTitle, text: shareTitle, url: shareUrl });
        return;
      }
      if (nav && nav.clipboard && nav.clipboard.writeText) {
        await nav.clipboard.writeText(`${shareTitle} ${shareUrl}`);
        showToast('分享文案已复制，快去粘贴给好友', 'success');
        return;
      }
      showToast('请使用右上角菜单转发给好友');
    } catch {
      showToast('请使用右上角菜单转发给好友');
    }
  };

  const handleShare = async () => {
    if (!data) return;
    setShareVisible(true);
    if (shareImageUrl) return;
    setGeneratingShare(true);
    try {
      const url = await generateShareCard(data);
      setShareImageUrl(url);
    } finally {
      setGeneratingShare(false);
    }
  };

  const handleSaveShareImage = () => {
    if (!shareImageUrl) return;
    const a = document.createElement('a');
    a.href = shareImageUrl;
    a.download = `constitution_${data?.screen1_card.type || 'share'}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    showToast('已保存到本地，可分享到朋友圈', 'success');
  };

  if (loading || !data) {
    return (
      <div className="min-h-screen bh-ai-page">
        <GreenNavBar back={() => router.push('/ai-home')}>体质分析报告</GreenNavBar>
        <div className="flex flex-col items-center justify-center py-32">
          <SpinLoading style={{ '--size': '36px', '--color': '#0EA5E9' }} />
          <span className="text-sm text-gray-500 mt-4">加载中...</span>
        </div>
      </div>
    );
  }

  const color = data.screen1_card.color || '#0EA5E9';

  return (
    <div className="min-h-screen bh-ai-page pb-20">
      {/* [PRD-TIZHI-OPTIM-V1] 优化点3：右上角返回直接回到 AI 首页（不再回旧列表页） */}
      <GreenNavBar back={() => router.push('/ai-home')}>体质分析报告</GreenNavBar>

      {/* ─────── 第一屏：体质名片 ─────── */}
      <section
        className="px-4 pt-5 pb-6"
        style={{
          background: `linear-gradient(180deg, ${color}15 0%, #fff 100%)`,
        }}
      >
        <div
          className="rounded-2xl p-5 text-center shadow-sm"
          style={{ background: '#fff', border: `1px solid ${color}30` }}
        >
          <div className="text-6xl mb-2">{data.screen1_card.persona.emoji || '🌿'}</div>
          <div className="text-2xl font-bold mb-1" style={{ color }}>
            {data.screen1_card.type}
          </div>
          <div className="text-xs text-gray-500 mb-2">
            为「{data.member_label}」分析 · {formatDate(data.created_at)}
          </div>
          <div
            className="inline-block px-3 py-1 rounded-full text-xs mb-4"
            style={{ background: `${color}15`, color }}
          >
            {data.screen1_card.one_line_desc}
          </div>
          <div className="flex justify-center">
            <RadarChart
              dimensions={data.screen1_card.radar.dimensions}
              scores={data.screen1_card.radar.scores}
              color={color}
              size={260}
            />
          </div>
          <div className="text-[11px] text-gray-400 mt-2">9 维体质倾向得分</div>
        </div>
        <div className="text-center text-xs text-gray-400 mt-3 animate-bounce">
          ↓ 向下滑动查看详细分析
        </div>
      </section>

      {/* ─────── 第二屏：深度解读 ─────── */}
      <section className="px-4 pt-2 pb-4">
        <div className="bg-white rounded-2xl p-4 shadow-sm">
          <div className="flex items-center mb-3">
            <span className="text-lg mr-2">🔍</span>
            <span className="font-semibold text-gray-800">深度解读</span>
          </div>
          <div className="text-sm text-gray-500 mb-3 leading-relaxed">
            {data.screen1_card.short_desc}
          </div>

          {data.screen2_analysis.features?.external && (
            <div className="mb-3">
              <div className="text-sm font-medium mb-1" style={{ color }}>外在表现</div>
              <div className="flex flex-wrap gap-1.5">
                {data.screen2_analysis.features.external.map((x, i) => (
                  <span
                    key={i}
                    className="text-xs px-2 py-1 rounded"
                    style={{ background: `${color}12`, color: '#555' }}
                  >
                    {x}
                  </span>
                ))}
              </div>
            </div>
          )}

          {data.screen2_analysis.features?.internal && (
            <div className="mb-3">
              <div className="text-sm font-medium mb-1" style={{ color }}>内在倾向</div>
              <ul className="text-xs text-gray-600 space-y-1 list-disc list-inside">
                {data.screen2_analysis.features.internal.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </div>
          )}

          {data.screen2_analysis.features?.easy_problems && (
            <div className="mb-3">
              <div className="text-sm font-medium mb-1 text-orange-500">易患倾向</div>
              <ul className="text-xs text-gray-600 space-y-1 list-disc list-inside">
                {data.screen2_analysis.features.easy_problems.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </div>
          )}

          {(data.screen2_analysis.causes?.innate || data.screen2_analysis.causes?.acquired) && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-sm font-medium mb-2" style={{ color }}>成因分析</div>
              {data.screen2_analysis.causes.innate && (
                <p className="text-xs text-gray-600 mb-2 leading-relaxed">
                  <strong>先天：</strong>
                  {data.screen2_analysis.causes.innate}
                </p>
              )}
              {data.screen2_analysis.causes.acquired && (
                <p className="text-xs text-gray-600 leading-relaxed">
                  <strong>后天：</strong>
                  {data.screen2_analysis.causes.acquired}
                </p>
              )}
            </div>
          )}
        </div>
      </section>

      {/* ─────── 第三屏：个性化养生方案 ─────── */}
      <section className="px-4 pb-4">
        <div className="bg-white rounded-2xl p-4 shadow-sm">
          <div className="flex items-center mb-3">
            <span className="text-lg mr-2">🌱</span>
            <span className="font-semibold text-gray-800">个性化养生方案</span>
          </div>

          {/* 饮食 */}
          <div className="mb-4">
            <div className="text-sm font-medium mb-2" style={{ color }}>🍲 饮食宜忌</div>
            {data.screen3_plan.diet?.good && (
              <div className="mb-2">
                <span className="text-xs text-green-600 font-medium mr-1">✓ 宜食：</span>
                <span className="text-xs text-gray-600">
                  {data.screen3_plan.diet.good.join(' · ')}
                </span>
              </div>
            )}
            {data.screen3_plan.diet?.avoid && (
              <div>
                <span className="text-xs text-red-500 font-medium mr-1">✗ 忌食：</span>
                <span className="text-xs text-gray-600">
                  {data.screen3_plan.diet.avoid.join(' · ')}
                </span>
              </div>
            )}
          </div>

          {/* 作息 */}
          {data.screen3_plan.lifestyle?.length > 0 && (
            <div className="mb-4">
              <div className="text-sm font-medium mb-2" style={{ color }}>🌙 作息建议</div>
              <ul className="text-xs text-gray-600 space-y-1 list-disc list-inside">
                {data.screen3_plan.lifestyle.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </div>
          )}

          {/* 运动 */}
          {data.screen3_plan.exercise?.length > 0 && (
            <div className="mb-4">
              <div className="text-sm font-medium mb-2" style={{ color }}>🏃 运动建议</div>
              <div className="space-y-1.5">
                {data.screen3_plan.exercise.map((x, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between text-xs px-3 py-2 rounded-lg"
                    style={{ background: `${color}08` }}
                  >
                    <span className="text-gray-700 font-medium">{x.name}</span>
                    <span className="text-gray-400 text-[11px]">{x.frequency}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 情志 */}
          {data.screen3_plan.emotion?.length > 0 && (
            <div>
              <div className="text-sm font-medium mb-2" style={{ color }}>🧘 情志调养</div>
              <ul className="text-xs text-gray-600 space-y-1 list-disc list-inside">
                {data.screen3_plan.emotion.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </section>

      {/* ─────── 第四屏：专属膳食套餐（运营配置驱动，无内容整块隐藏，无占位假文案）─────── */}
      {data.screen4_packages?.length > 0 && (
        <section className="px-4 pb-4" data-testid="tcm-meal-section">
          <div className="bg-white rounded-2xl p-4 shadow-sm">
            <div className="flex items-center mb-3">
              <span className="text-lg mr-2">🛒</span>
              <span className="font-semibold text-gray-800">专属膳食套餐</span>
            </div>
            <div className="space-y-3">
              {data.screen4_packages.map((pkg) => (
                <div
                  key={pkg.id}
                  className="rounded-xl p-3 border border-gray-100 transition-all active:bg-gray-50 cursor-pointer"
                  style={{ background: '#fafafa' }}
                  onClick={() => handleCardClick(pkg)}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className="w-16 h-16 rounded-lg flex-shrink-0 flex items-center justify-center text-2xl"
                      style={{
                        background: `${pkg.tag_color || color}15`,
                        border: `1px solid ${pkg.tag_color || color}30`,
                      }}
                    >
                      {pkg.image ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={pkg.image}
                          alt={pkg.title}
                          className="w-full h-full rounded-lg object-cover"
                          onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')}
                        />
                      ) : (
                        <span>🍲</span>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm mb-0.5 truncate">{pkg.title}</div>
                      {pkg.tag && (
                        <div
                          className="inline-block px-1.5 py-0.5 rounded text-[10px] mb-1"
                          style={{
                            background: `${pkg.tag_color || color}15`,
                            color: pkg.tag_color || color,
                          }}
                        >
                          {pkg.tag}
                        </div>
                      )}
                      {pkg.subtitle && (
                        <div className="text-[11px] text-gray-500 leading-snug line-clamp-2">
                          {pkg.subtitle}
                        </div>
                      )}
                      {pkg.price !== null && pkg.price !== undefined && (
                        <div className="text-[13px] mt-0.5">
                          <span className="font-bold" style={{ color: '#ff4d4f' }}>
                            ¥{pkg.price}
                          </span>
                          {pkg.original_price && pkg.original_price > (pkg.price || 0) && (
                            <span className="text-gray-300 line-through text-[11px] ml-1.5">
                              ¥{pkg.original_price}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    {pkg.link_type && pkg.link_type !== 'none' && (
                      <Button
                        size="mini"
                        onClick={(e) => { e.stopPropagation(); handleCardClick(pkg); }}
                        style={{
                          background: `linear-gradient(135deg, ${color}, #38BDF8)`,
                          color: '#fff',
                          border: 'none',
                          borderRadius: 16,
                          fontSize: 12,
                          padding: '4px 14px',
                        }}
                      >
                        {pkg.button_text || '查看'}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ─────── 第五屏：门店服务（运营配置驱动，无内容整块隐藏，无占位假文案）─────── */}
      {data.screen5_store?.services?.length > 0 && (
        <section className="px-4 pb-4" data-testid="tcm-store-section">
          <div
            className="rounded-2xl p-4 shadow-sm"
            style={{ background: `linear-gradient(135deg, ${color}10, #F0F9FF)` }}
          >
            <div className="flex items-center mb-3">
              <span className="text-lg mr-2">🏥</span>
              <span className="font-semibold text-gray-800">门店服务</span>
            </div>

            {/* 优惠券（仅在可领取/已领取/已核销时展示） */}
            {data.screen5_store.coupon.status !== 'unavailable' && (
              <div
                className="rounded-xl p-3 mb-3 flex items-center gap-3"
                style={{ background: '#fff', border: `1px dashed ${color}` }}
              >
                <div className="text-3xl">🎟️</div>
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-800">AI 精准检测体验券</div>
                  <div className="text-[11px] text-gray-500 mt-0.5">
                    {data.screen5_store.coupon.message}
                  </div>
                </div>
                {data.screen5_store.coupon.status === 'claimable' && (
                  <Button
                    size="small"
                    loading={claimingCoupon}
                    onClick={handleClaimCoupon}
                    style={{
                      background: `linear-gradient(135deg, ${color}, #38BDF8)`,
                      color: '#fff',
                      border: 'none',
                      borderRadius: 16,
                      fontSize: 12,
                      padding: '4px 14px',
                    }}
                  >
                    立即领取
                  </Button>
                )}
                {data.screen5_store.coupon.status === 'claimed' && (
                  <Button
                    size="small"
                    onClick={handleViewCoupons}
                    style={{
                      background: '#F0F9FF',
                      color: '#0EA5E9',
                      border: '1px solid #0EA5E9',
                      borderRadius: 16,
                      fontSize: 12,
                      padding: '4px 14px',
                    }}
                  >
                    查看我的券
                  </Button>
                )}
                {data.screen5_store.coupon.status === 'used' && (
                  <span className="text-[11px] text-gray-400">已核销</span>
                )}
              </div>
            )}

            {/* 运营配置的门店服务卡 */}
            <div className="space-y-2">
              {data.screen5_store.services.map((svc) => (
                <div
                  key={svc.id}
                  className="rounded-xl p-3 flex items-center gap-3 active:bg-gray-50 cursor-pointer"
                  style={{ background: '#fff', border: `1px solid ${color}30` }}
                  onClick={() => handleCardClick(svc)}
                >
                  <div className="text-3xl">{svc.image ? '🏥' : '🔥'}</div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-800">{svc.title}</div>
                    {svc.subtitle && (
                      <div className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">
                        {svc.subtitle}
                      </div>
                    )}
                  </div>
                  <span className="text-gray-300">›</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ─────── 第六屏：分享 CTA（形态一转发好友 + 形态二保存海报）─────── */}
      <section className="px-4 pb-6 space-y-3" data-testid="tcm-share-section">
        <Button
          block
          data-testid="tcm-share-friend"
          onClick={handleShareToFriend}
          style={{
            background: `linear-gradient(135deg, ${color}, #38BDF8)`,
            color: '#fff',
            border: 'none',
            borderRadius: 24,
            height: 46,
            fontWeight: 600,
          }}
        >
          👋 转发给好友，一起测体质
        </Button>
        <Button
          block
          data-testid="tcm-share-poster"
          onClick={handleShare}
          style={{
            background: '#fff',
            color,
            border: `1px solid ${color}`,
            borderRadius: 24,
            height: 46,
            fontWeight: 600,
          }}
        >
          🖼️ 保存海报，发朋友圈
        </Button>
        <div className="text-[11px] text-gray-400 mt-1 text-center px-4 leading-relaxed">
          {data.disclaimer}
        </div>
      </section>

      {/* 分享弹窗 */}
      {shareVisible && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center px-6"
          style={{ background: 'rgba(0,0,0,0.7)' }}
          onClick={() => setShareVisible(false)}
        >
          <div
            className="bg-white rounded-2xl max-h-[90vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-3 text-center text-sm font-semibold border-b">
              长按保存到相册，或点击下方按钮
            </div>
            <div className="p-4 overflow-auto flex items-center justify-center" style={{ minHeight: 360 }}>
              {generatingShare && !shareImageUrl && (
                <SpinLoading style={{ '--size': '36px', '--color': '#0EA5E9' }} />
              )}
              {shareImageUrl && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={resolveAssetUrl(shareImageUrl)} alt="分享卡" style={{ maxWidth: '100%', maxHeight: '60vh' }} />
              )}
            </div>
            <div className="flex gap-2 p-3 border-t">
              <Button
                block
                onClick={handleSaveShareImage}
                disabled={!shareImageUrl}
                style={{ background: '#0EA5E9', color: '#fff', border: 'none', borderRadius: 20 }}
              >
                保存图片
              </Button>
              <Button
                block
                onClick={() => setShareVisible(false)}
                style={{ borderRadius: 20 }}
              >
                关闭
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
