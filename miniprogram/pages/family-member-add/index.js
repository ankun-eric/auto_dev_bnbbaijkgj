// [PRD-FAMILY-MEMBER-V2 2026-05-18] 小程序：添加家庭成员（与 H5 对齐）
const { get, post } = require('../../utils/request.js');

// 15 种预置关系 + 其他
const RELATION_DEFS = [
  { name: '爸爸', gender: 'M', unique: true,  badge: '爸',   tone: 'elder',   offset: 25,   rule: 'elder'   },
  { name: '妈妈', gender: 'F', unique: true,  badge: '妈',   tone: 'elder',   offset: 25,   rule: 'elder'   },
  { name: '老公', gender: 'M', unique: true,  badge: '夫',   tone: 'peer',    offset: -2,   rule: null      },
  { name: '老婆', gender: 'F', unique: true,  badge: '妻',   tone: 'peer',    offset: 2,    rule: null      },
  { name: '儿子', gender: 'M', unique: false, badge: '儿',   tone: 'younger', offset: -25,  rule: 'younger' },
  { name: '女儿', gender: 'F', unique: false, badge: '女',   tone: 'younger', offset: -25,  rule: 'younger' },
  { name: '哥哥', gender: 'M', unique: false, badge: '哥',   tone: 'peer',    offset: 3,    rule: null      },
  { name: '姐姐', gender: 'F', unique: false, badge: '姐',   tone: 'peer',    offset: 3,    rule: null      },
  { name: '弟弟', gender: 'M', unique: false, badge: '弟',   tone: 'peer',    offset: -3,   rule: null      },
  { name: '妹妹', gender: 'F', unique: false, badge: '妹',   tone: 'peer',    offset: -3,   rule: null      },
  { name: '爷爷', gender: 'M', unique: true,  badge: '爷',   tone: 'elder',   offset: 50,   rule: 'elder'   },
  { name: '奶奶', gender: 'F', unique: true,  badge: '奶',   tone: 'elder',   offset: 50,   rule: 'elder'   },
  { name: '外公', gender: 'M', unique: true,  badge: '外公', tone: 'elder',   offset: 50,   rule: 'elder'   },
  { name: '外婆', gender: 'F', unique: true,  badge: '外婆', tone: 'elder',   offset: 50,   rule: 'elder'   },
  { name: '其他', gender: null,unique: false, badge: '',    tone: 'other',   offset: 'same',rule: null     },
];

const CHRONICS = ['高血压', '糖尿病', '高血脂', '冠心病', '脑卒中', '慢阻肺', '哮喘', '慢性肾病', '甲状腺', '痛风'];

function calcAge(birthday) {
  if (!birthday) return null;
  const m = String(birthday).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  const by = parseInt(m[1], 10);
  const bm = parseInt(m[2], 10);
  const bd = parseInt(m[3], 10);
  const today = new Date();
  let age = today.getFullYear() - by;
  const tm = today.getMonth() + 1;
  const td = today.getDate();
  if (tm < bm || (tm === bm && td < bd)) age -= 1;
  return age >= 0 ? age : null;
}

function computeDefaultBirthday(selfYear, def) {
  if (!def) return selfYear + '-01-01';
  const currentYear = new Date().getFullYear();
  let year;
  if (def.offset === 'same') {
    year = selfYear;
  } else {
    year = selfYear + def.offset;
  }
  if (def.rule === 'younger' && year >= currentYear) year = currentYear - 1;
  if (year < 1900) year = 1900;
  if (year > currentYear) year = currentYear;
  return year + '-01-01';
}

function validateRelationAge(def, memberBirthday, selfBirthday) {
  if (!def || !def.rule) return true;
  const ma = calcAge(memberBirthday);
  const sa = calcAge(selfBirthday);
  if (ma == null || sa == null) return true;
  if (def.rule === 'elder') return ma > sa;
  if (def.rule === 'younger') return ma < sa;
  return true;
}

Page({
  data: {
    relationDefs: RELATION_DEFS,
    chronics: CHRONICS,
    selectedRelation: '',
    selectedDef: null,
    isOther: false,
    customRelation: '',
    name: '',
    gender: '',
    birthday: '',
    showSelfBlocker: false,
    selfBirthday: '',
    selfBirthYear: 0,
    usedUnique: {},
    moreOpen: false,
    height: '',
    weight: '',
    pickedChronics: [],
    drugAllergy: '',
    foodAllergy: '',
    otherAllergy: '',
    errFields: {},
    ageInvalid: false,
    submitting: false,
    currentDate: '',
    // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31]
    // 保存成功后弹"成员已添加成功🎉"框（可跳过）
    showAddedDialog: false,
    addedNickname: '',
    addedMemberId: '',
    // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31] 名额已满弹框（quota_max 来自后端，绝不写死）
    showQuotaFull: false,
    quotaFullMax: 0,
  },

  async onLoad() {
    const today = new Date();
    const currentDate = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
    this.setData({ currentDate: currentDate });
    // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31]
    // 进入"添加成员"页前先查配额：满了直接弹"名额已满"框，不打开添加表单
    try {
      const qr = await get('/api/family/member/quota', {}, { showLoading: false, suppressErrorToast: true }).catch(() => null);
      if (qr) {
        const qd = (qr.data || qr) || {};
        const qMax = Number(qd.quota_max == null ? 0 : qd.quota_max);
        const qRemaining = Number(qd.quota_remaining == null ? 0 : qd.quota_remaining);
        if (qMax !== -1 && qRemaining <= 0) {
          this.setData({ showQuotaFull: true, quotaFullMax: qMax });
          return;
        }
      }
    } catch (_) { /* 降级：放行 */ }
    try {
      const [hpRes, mbRes] = await Promise.all([
        get('/api/health/profile', {}, { showLoading: false, suppressErrorToast: true }).catch(() => null),
        get('/api/family/members', {}, { showLoading: false, suppressErrorToast: true }).catch(() => null),
      ]);
      let selfBd = '';
      if (hpRes) {
        const d = (hpRes.data || hpRes);
        if (d && d.birthday) selfBd = String(d.birthday).slice(0, 10);
      }
      const usedUnique = {};
      if (mbRes) {
        const items = (mbRes.data && mbRes.data.items) || mbRes.items || [];
        items.forEach(function (m) {
          if (m.is_self) {
            if (!selfBd && m.birthday) selfBd = String(m.birthday).slice(0, 10);
            return;
          }
          const rn = m.relation_type_name || m.relationship_type;
          const def = RELATION_DEFS.find(function (d) { return d.name === rn; });
          if (def && def.unique) usedUnique[def.name] = 1;
        });
      }
      const m = selfBd.match(/^(\d{4})/);
      const selfYear = m ? parseInt(m[1], 10) : 0;
      this.setData({
        selfBirthday: selfBd,
        selfBirthYear: selfYear,
        usedUnique: usedUnique,
        showSelfBlocker: !selfYear,
      });
    } catch (_) {
      this.setData({ showSelfBlocker: true });
    }
  },

  onSelectRelation(e) {
    const name = e.currentTarget.dataset.name;
    if (this.data.usedUnique[name]) {
      wx.showToast({ title: '已添加过该关系', icon: 'none' });
      return;
    }
    const def = RELATION_DEFS.find(function (d) { return d.name === name; });
    const update = {
      selectedRelation: name,
      selectedDef: def,
      isOther: def && def.name === '其他',
      errFields: Object.assign({}, this.data.errFields, { relation: undefined, birthday: undefined }),
      ageInvalid: false,
    };
    if (def && def.gender === 'M') update.gender = 'male';
    else if (def && def.gender === 'F') update.gender = 'female';
    else update.gender = '';
    if (def && this.data.selfBirthYear) {
      update.birthday = computeDefaultBirthday(this.data.selfBirthYear, def);
    }
    this.setData(update);
  },

  onInputName(e) {
    this.setData({ name: e.detail.value, errFields: Object.assign({}, this.data.errFields, { name: undefined }) });
  },
  onInputCustomRelation(e) {
    this.setData({ customRelation: e.detail.value, errFields: Object.assign({}, this.data.errFields, { customRelation: undefined }) });
  },
  onSelectGender(e) {
    this.setData({ gender: e.currentTarget.dataset.gender, errFields: Object.assign({}, this.data.errFields, { gender: undefined }) });
  },
  onBirthdayChange(e) {
    this.setData({ birthday: e.detail.value, errFields: Object.assign({}, this.data.errFields, { birthday: undefined }), ageInvalid: false });
  },
  toggleMore() {
    this.setData({ moreOpen: !this.data.moreOpen });
  },
  onInputHeight(e) { this.setData({ height: e.detail.value }); },
  onInputWeight(e) { this.setData({ weight: e.detail.value }); },
  toggleChronic(e) {
    const name = e.currentTarget.dataset.name;
    let arr = this.data.pickedChronics.slice();
    const idx = arr.indexOf(name);
    if (idx >= 0) arr.splice(idx, 1); else arr.push(name);
    this.setData({ pickedChronics: arr });
  },
  onInputDrug(e) { this.setData({ drugAllergy: e.detail.value }); },
  onInputFood(e) { this.setData({ foodAllergy: e.detail.value }); },
  onInputOther(e) { this.setData({ otherAllergy: e.detail.value }); },

  goCompleteSelfProfile() {
    this.setData({ showSelfBlocker: false });
    wx.redirectTo({ url: '/pages/health-profile/index' });
  },
  cancelBlocker() {
    this.setData({ showSelfBlocker: false });
    wx.navigateBack({ delta: 1, fail() { wx.switchTab({ url: '/pages/home/index' }); } });
  },

  goInvite() {
    wx.navigateTo({ url: '/pages/family-invite/index', fail() { wx.showToast({ title: '邀请页未配置', icon: 'none' }); } });
  },

  // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31] 名额已满弹框 - 暂不升级
  onQuotaFullSkip() {
    this.setData({ showQuotaFull: false });
    wx.navigateBack({
      delta: 1,
      fail() { wx.switchTab({ url: '/pages/home/index' }); },
    });
  },

  // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31] 名额已满弹框 - 去升级
  onQuotaFullUpgrade() {
    this.setData({ showQuotaFull: false });
    wx.redirectTo({
      url: '/pages/member-center/index',
      fail() { wx.showToast({ title: '会员中心未配置', icon: 'none' }); },
    });
  },

  // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31]
  // "成员已添加成功🎉"弹框 → 去邀请 TA：跳转二维码邀请页（带 member_id）
  onInviteNow() {
    const mid = this.data.addedMemberId;
    const url = mid
      ? `/pages/family-invite/index?member_id=${mid}`
      : '/pages/family-invite/index';
    this.setData({ showAddedDialog: false });
    wx.redirectTo({
      url: url,
      fail() {
        wx.showToast({ title: '邀请页未配置', icon: 'none' });
      },
    });
  },

  // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31]
  // "成员已添加成功🎉"弹框 → 暂不邀请：关闭弹框并返回上一页
  onInviteSkip() {
    this.setData({ showAddedDialog: false });
    wx.navigateBack({
      delta: 1,
      fail() {
        wx.switchTab({ url: '/pages/home/index' });
      },
    });
  },

  validate() {
    const errs = {};
    if (!this.data.selectedRelation) errs.relation = 1;
    if (this.data.isOther) {
      const tr = (this.data.customRelation || '').trim();
      if (!tr || tr.length < 1 || tr.length > 8) errs.customRelation = 1;
    }
    const n = (this.data.name || '').trim();
    if (!n || n.length < 1 || n.length > 12) errs.name = 1;
    if (!this.data.gender) errs.gender = 1;
    if (!this.data.birthday) errs.birthday = 1;
    let invalidAge = false;
    if (this.data.selectedDef && this.data.birthday && this.data.selfBirthday) {
      if (!validateRelationAge(this.data.selectedDef, this.data.birthday, this.data.selfBirthday)) {
        invalidAge = true;
        errs.relation = 1;
        errs.birthday = 1;
      }
    }
    this.setData({ errFields: errs, ageInvalid: invalidAge });
    return Object.keys(errs).length === 0;
  },

  async onSubmit() {
    if (!this.validate()) {
      wx.showToast({ title: '请补全或修正标红字段', icon: 'none' });
      return;
    }
    const def = this.data.selectedDef;
    const relationLabel = this.data.isOther ? (this.data.customRelation || '').trim() : def.name;
    const nickname = (this.data.name || '').trim();
    this.setData({ submitting: true });
    try {
      const body = {
        relationship_type: relationLabel,
        nickname: nickname,
        name: nickname,
        gender: this.data.gender === 'male' ? 'male' : 'female',
        birthday: this.data.birthday,
      };
      if (this.data.height) body.height = Number(this.data.height);
      if (this.data.weight) body.weight = Number(this.data.weight);
      if (this.data.pickedChronics.length) body.medical_histories = this.data.pickedChronics;
      const allergies = [];
      const pushParts = (prefix, raw) => {
        (raw || '').split(/[,，;；\s]+/).filter(Boolean).forEach(s => allergies.push(prefix + ':' + s));
      };
      if ((this.data.drugAllergy || '').trim()) pushParts('药物', this.data.drugAllergy);
      if ((this.data.foodAllergy || '').trim()) pushParts('食物', this.data.foodAllergy);
      if ((this.data.otherAllergy || '').trim()) pushParts('其他', this.data.otherAllergy);
      if (allergies.length) body.allergies = allergies;
      const r = await post('/api/family/members', body, { showLoading: true });
      // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31]
      // 保存成功后弹"成员已添加成功🎉"框（可跳过 / 去邀请 TA）
      // 取出新成员 id，邀请页传 member_id 避免"缺少成员参数"错误
      let newMemberId = '';
      try {
        const rd = (r && (r.data || r)) || {};
        newMemberId = rd.id || rd.member_id || (rd.data && (rd.data.id || rd.data.member_id)) || '';
      } catch (_) {}
      this.setData({
        submitting: false,
        showAddedDialog: true,
        addedNickname: nickname,
        addedMemberId: newMemberId,
      });
      return;
    } catch (e) {
      const detail = (e && e.data && e.data.detail) || '保存失败';
      wx.showToast({ title: typeof detail === 'string' ? detail : '保存失败', icon: 'none' });
    } finally {
      this.setData({ submitting: false });
    }
  },
});
