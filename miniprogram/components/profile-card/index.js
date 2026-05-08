// [PRD-432] AI 回答顶部「咨询对象档案」折叠卡片 - 小程序组件
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
    _fetch() {
      const cid = this.data.consultantId;
      if (typeof cid !== 'number') return;
      const cached = profileCardCache[cid];
      if (cached && Date.now() - cached.ts < CACHE_TTL) {
        this.setData({ profile: cached.data, error: false });
        return;
      }
      const baseUrl = (app && app.globalData && app.globalData.baseUrl) || '';
      const token = (app && app.globalData && app.globalData.token) || wx.getStorageSync('token') || '';
      this.setData({ loading: true, error: false });
      wx.request({
        url: `${baseUrl}/api/v1/consultant/${cid}/profile_card`,
        method: 'GET',
        header: token ? { Authorization: `Bearer ${token}` } : {},
        success: (res) => {
          if (res.statusCode === 200 && res.data) {
            const transformed = this._transformProfile(res.data);
            profileCardCache[cid] = { data: transformed, ts: Date.now() };
            this.setData({ profile: transformed, error: false });
          } else {
            this.setData({ error: true });
          }
        },
        fail: () => this.setData({ error: true }),
        complete: () => this.setData({ loading: false })
      });
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
        const d = new Date(iso);
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
      wx.navigateTo({ url: `/pages/health-archive/index?target=${cid}&from=ai-chat` }).catch(() => {});
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
