// [PRD-432] AI 回答顶部「咨询对象档案」折叠卡片 - 小程序组件
// [BUG_FIX_TIMEZONE_GLOBAL_20260517] 统一时间解析/格式化
const { parseServerTime, formatDateTime, formatDate, formatTime, formatRelativeTime, formatFriendlyTime } = require('../../utils/datetime');
const app = getApp();

const profileCardCache = {};
const CACHE_TTL = 30 * 1000;

Component({
  properties: {
    consultantId: { type: Number, value: 0 },
    fallbackText: { type: String, value: '' }
  },

  data: {
    expanded: false,
    drawerVisible: false,
    loading: false,
    error: false,
    profile: null
  },

  observers: {
    consultantId: function (val) {
      this._fetch();
    }
  },

  lifetimes: {
    attached() {
      this._fetch();
    }
  },

  methods: {
    _fetch(isRetry) {
      const cid = this.data.consultantId;
      if (typeof cid !== 'number') return;
      const cached = profileCardCache[cid];
      if (cached && Date.now() - cached.ts < CACHE_TTL) {
        this.setData({ profile: cached.data, error: false, loading: false });
        return;
      }
      const baseUrl = (app && app.globalData && app.globalData.baseUrl) || '';
      const token = (app && app.globalData && app.globalData.token) || wx.getStorageSync('token') || '';
      this.setData({ loading: true, error: false });
      // [Bug-432-fix 2026-05-09]
      // 修因：原写法在 success 分支没有判断 res.data 的"业务字段是否齐全"，
      //   小程序请求库本身不会二次脱壳，但若返回 200 且 body 异常（无 fields），
      //   仍走"profile=null + loading=false + error=false"分支 → wx:elif 不命中，卡片永卡 loading 文案。
      // 修复：① 收到响应后，强校验 fields 字段是否存在；② 失败后按 PRD 3.10 自动重试 1 次（3s 后）。
      const that = this;
      wx.request({
        url: `${baseUrl}/api/v1/consultant/${cid}/profile_card`,
        method: 'GET',
        header: token ? { Authorization: `Bearer ${token}` } : {},
        success: (res) => {
          if (res.statusCode === 200 && res.data && res.data.fields) {
            const transformed = that._transformProfile(res.data);
            profileCardCache[cid] = { data: transformed, ts: Date.now() };
            that.setData({ profile: transformed, error: false, loading: false });
          } else {
            that._handleFetchFail(isRetry);
          }
        },
        fail: () => that._handleFetchFail(isRetry),
      });
    },

    _handleFetchFail(isRetry) {
      // 已经是重试还是失败 → 标记 error=true，loading=false，卡片不再展示（按 PRD 不阻塞 AI 回答）
      if (isRetry) {
        this.setData({ error: true, loading: false });
        return;
      }
      // 首次失败：3 秒后自动重试 1 次（PRD 3.10）
      const that = this;
      setTimeout(() => {
        if (that.data && typeof that.data.consultantId === 'number') {
          that._fetch(true);
        }
      }, 3000);
    },

    _transformProfile(raw) {
      const f = raw.fields || {};
      const transform = (key) => {
        const item = f[key] || {};
        return Object.assign({}, item);
      };
      const past = transform('past_history');
      past.display = past.is_none
        ? '无'
        : (past.filled && past.value && past.value.length
            ? (past.value.length > 1
                ? `${past.value.slice(0, 2).join('、')} 等 ${past.value.length} 项`
                : past.value[0])
            : '未填写');
      const allergy = transform('allergy');
      allergy.display = allergy.is_none
        ? '无'
        : (allergy.filled && allergy.value && allergy.value.length
            ? (allergy.value.length > 1
                ? `${allergy.value.slice(0, 2).join('、')} 等 ${allergy.value.length} 项`
                : allergy.value[0])
            : '未填写');
      const meds = transform('long_term_meds');
      meds.display = meds.is_none
        ? '无'
        : (meds.count > 0
            ? (meds.value_brief || `共 ${meds.count} 项`)
            : '未填写');
      meds.clickable = !meds.is_none;
      return Object.assign({}, raw, {
        fields: Object.assign({}, f, {
          past_history: past,
          allergy: allergy,
          long_term_meds: meds
        }),
        last_updated_md: this._formatMD(raw.last_updated_at),
        gender_icon: this._genderIcon((f.gender && f.gender.value) || ''),
        is_complete: raw.completeness && raw.completeness.percent >= 100
      });
    },

    _formatMD(iso) {
      if (!iso) return '';
      try {
        const d = parseServerTime(iso);
        if (!d) return '';
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${m}/${dd}`;
      } catch (e) { return ''; }
    },

    _genderIcon(g) {
      if (g === '男') return '♂';
      if (g === '女') return '♀';
      return '👤';
    },

    onToggle() {
      this.setData({ expanded: !this.data.expanded });
    },

    onCompleteClick() {
      const profile = this.data.profile;
      if (!profile || profile.is_complete) return;
      const cid = profile.consultant_id;
      wx.navigateTo({ url: '/pages/health-profile/index' }).catch(() => {});
    },

    onMedsClick() {
      const profile = this.data.profile;
      if (!profile) return;
      const meds = profile.fields.long_term_meds;
      if (!meds.clickable) return;
      this.setData({ drawerVisible: true });
    },

    onDrawerClose() {
      this.setData({ drawerVisible: false });
    },

    onDrawerGoManage() {
      const profile = this.data.profile;
      this.setData({ drawerVisible: false });
      if (profile) {
        wx.navigateTo({ url: `/pages/health-plan/medications?target=${profile.consultant_id}` }).catch(() => {});
      }
    },

    onDrawerGoCreate() {
      const profile = this.data.profile;
      this.setData({ drawerVisible: false });
      if (profile) {
        wx.navigateTo({ url: `/pages/health-plan/medications?target=${profile.consultant_id}&action=create` }).catch(() => {});
      }
    },

    onFallbackClick() {
      this.triggerEvent('fallback');
    }
  }
});
