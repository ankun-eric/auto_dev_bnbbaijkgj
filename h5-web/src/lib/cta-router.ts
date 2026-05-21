/**
 * [PRD-HSC-OPTIM-V3 2026-05-21] 多端统一 CTA 路由分发器（H5 端）
 *
 * 按 target_type 自动分发到 H5 对应的跳转方式：
 *   H5_PATH         → router.push(value)
 *   EXTERNAL_URL    → window.open(value)
 *   MINIPROGRAM_PATH→ 按钮在 H5 端隐藏（shouldHideOnH5 提示）
 *   DOCTOR_ID       → router.push('/doctor/'+value)
 *   DEPARTMENT_ID   → router.push('/department/'+value)
 */

export interface ResultCta {
  text: string;
  target_type: string;
  target_value: string;
}

/** H5 端是否应该隐藏该按钮（小程序原生页类型在 H5 无法跳转） */
export function shouldHideOnH5(cta?: ResultCta | null): boolean {
  if (!cta) return true;
  if (cta.target_type === 'MINIPROGRAM_PATH') return true;
  if (!cta.target_value) return true;
  return false;
}

/**
 * 派发 CTA 跳转。
 * @param cta 后端返回的 result_cta 对象
 * @param router next/navigation 的 router 实例（push 方法）
 */
export function dispatchCta(cta: ResultCta | null | undefined, router: { push: (p: string) => void }) {
  if (!cta || !cta.target_value) return;
  const t = cta.target_type;
  const v = cta.target_value;
  try {
    switch (t) {
      case 'H5_PATH':
        router.push(v.startsWith('/') ? v : `/${v}`);
        return;
      case 'EXTERNAL_URL':
        if (typeof window !== 'undefined') {
          window.open(v, '_blank', 'noopener');
        }
        return;
      case 'DOCTOR_ID':
        router.push(`/doctor/${v}`);
        return;
      case 'DEPARTMENT_ID':
        router.push(`/department/${v}`);
        return;
      case 'MINIPROGRAM_PATH':
        // H5 端无法跳小程序原生页，按钮本应已隐藏，此处作为兜底直接忽略
        // eslint-disable-next-line no-console
        console.warn('[cta-router] MINIPROGRAM_PATH 类型在 H5 端不支持跳转');
        return;
      default:
        // eslint-disable-next-line no-console
        console.warn('[cta-router] 未知 target_type:', t);
        if (v.startsWith('http')) {
          if (typeof window !== 'undefined') window.open(v, '_blank', 'noopener');
        } else if (v.startsWith('/')) {
          router.push(v);
        }
    }
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn('[cta-router] dispatch failed', e);
  }
}
