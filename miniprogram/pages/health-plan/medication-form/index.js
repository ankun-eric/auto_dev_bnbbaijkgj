// [PRD-MED-PLAN-OPTIM-V1 2026-05-17] 用药计划表单（终版）
// 与 H5 字段、文案、占位、标签项完全一致；主色 #0EA5E9
// 老数据迁移：服用时机映射兜底（早上→饭前 / 中午|下午|晚上→饭后 / 睡前→睡前）

const { get, post, put } = require('../../../utils/request');

const DOSAGE_VALUES = ['¼', '½', '1', '2', '3', '4', '5', '6', '8', '10'];
const DOSAGE_UNITS = ['片', '粒', 'mL', '滴', '袋', '支', '包', '瓶'];
const TIMING_OPTIONS = ['饭前', '饭后', '空腹', '随餐', '睡前'];
const FREQ_DEFAULTS = {
  1: ['08:00'],
  2: ['08:00', '20:00'],
  3: ['08:00', '14:00', '20:00'],
  4: ['08:00', '12:00', '16:00', '20:00'],
};

// 老数据迁移映射（F-07-1）
const TIMING_LEGACY_MAP = {
  '早上': '饭前',
  '中午': '饭后',
  '下午': '饭后',
  '晚上': '饭后',
  '睡前': '睡前',
  morning: '饭前',
  noon: '饭后',
  afternoon: '饭后',
  evening: '饭后',
  bedtime: '睡前',
};

function migrateTiming(raw) {
  if (!raw) return '';
  if (TIMING_OPTIONS.indexOf(raw) >= 0) return raw;
  return TIMING_LEGACY_MAP[raw] || '';
}

function pad(n) { return n < 10 ? '0' + n : '' + n; }
function toISO(d) {
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
}
function parseISO(s) {
  if (!s) return null;
  var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return null;
  var d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  d.setHours(0, 0, 0, 0);
  return d;
}
function addDays(d, n) {
  var r = new Date(d.getTime());
  r.setDate(r.getDate() + n);
  return r;
}
function diffDays(a, b) {
  return Math.round((b.getTime() - a.getTime()) / 86400000) + 1;
}
function dosageForBackend(v) {
  if (v === '¼') return '1/4';
  if (v === '½') return '1/2';
  return v;
}
function dosageForUI(v) {
  if (!v) return '1';
  if (v === '1/4') return '¼';
  if (v === '1/2') return '½';
  return v;
}
function unwrap(res) {
  if (res == null || typeof res !== 'object') return {};
  if (res.data && typeof res.data === 'object' && !Array.isArray(res.data)) return res.data;
  return res;
}

function buildCycleDisplay(startDate, endDate, isLongTerm) {
  if (isLongTerm) {
    return { main: startDate + ' 至 长期', sub: '长期服用' };
  }
  var s = parseISO(startDate);
  var e = parseISO(endDate);
  var sub = (s && e) ? ('共 ' + diffDays(s, e) + ' 天') : '—';
  return { main: (startDate || '—') + ' 至 ' + (endDate || '—'), sub: sub };
}

function buildCycleTip(startDate, endDate, isLongTerm) {
  if (isLongTerm) return '长期服用，无固定结束日';
  var s = parseISO(startDate);
  var e = parseISO(endDate);
  if (s && e) return '共 ' + diffDays(s, e) + ' 天';
  return '请选择起止日期';
}

Page({
  data: {
    isEdit: false,
    id: '',
    // [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.2] 必填红字校验错误集合
    errFields: {},
    name: '',
    nameDraft: '',
    nameDrawerOpen: false,
    nameSuggests: [],

    frequencyPerDay: 2,
    customTimes: FREQ_DEFAULTS[2].slice(),
    timesText: FREQ_DEFAULTS[2].join(' / '),

    dosageValue: '1',
    dosageUnit: '片',
    dosageValueIndex: 2,
    dosageUnitIndex: 0,
    dosageValues: DOSAGE_VALUES,
    dosageUnits: DOSAGE_UNITS,

    startDate: '',
    endDate: '',
    isLongTerm: false,
    cycleMain: '',
    cycleSub: '',
    cycleDraftStart: '',
    cycleDraftEnd: '',
    cycleDraftLong: false,
    cycleDraftTip: '',
    minStartDate: '',
    maxEndDate: '',

    timingOptions: TIMING_OPTIONS,
    guidance: '',

    notes: '',
    notesDraft: '',
    notesDrawerOpen: false,

    timeDrawerOpen: false,
    dosageDrawerOpen: false,
    cycleDrawerOpen: false,

    submitting: false,
  },

  onLoad: function (options) {
    var t = new Date(); t.setHours(0, 0, 0, 0);
    var start = toISO(t);
    var end = toISO(addDays(t, 4));
    var cd = buildCycleDisplay(start, end, false);
    var min = toISO(addDays(t, -90));
    var max = toISO(addDays(t, 365 * 3));
    this.setData({
      startDate: start,
      endDate: end,
      cycleMain: cd.main,
      cycleSub: cd.sub,
      minStartDate: min,
      maxEndDate: max,
    });
    if (options && options.id) {
      this.setData({ isEdit: true, id: options.id });
      wx.setNavigationBarTitle({ title: '编辑用药计划' });
      this.loadDetail(options.id);
    } else {
      wx.setNavigationBarTitle({ title: '添加用药计划' });
    }
  },

  loadDetail: function (id) {
    var self = this;
    get('/api/health-plan/medications/' + id, {}, { showLoading: true }).then(function (res) {
      var d = unwrap(res);
      var freq = d.frequency_per_day || 2;
      var times = Array.isArray(d.custom_times) && d.custom_times.length ? d.custom_times.slice(0, freq) : (FREQ_DEFAULTS[freq] || ['08:00']).slice();
      while (times.length < freq) times.push('08:00');
      var dv = dosageForUI(d.dosage_value);
      var du = d.dosage_unit || '片';
      var isLT = !!d.long_term;
      var sd = d.start_date || self.data.startDate;
      var ed = isLT ? '' : (d.end_date || '');
      var cd = buildCycleDisplay(sd, ed, isLT);
      var dvIdx = DOSAGE_VALUES.indexOf(dv); if (dvIdx < 0) dvIdx = 2;
      var duIdx = DOSAGE_UNITS.indexOf(du); if (duIdx < 0) duIdx = 0;
      self.setData({
        name: d.medicine_name || '',
        frequencyPerDay: freq,
        customTimes: times,
        timesText: times.join(' / '),
        dosageValue: dv,
        dosageUnit: du,
        dosageValueIndex: dvIdx,
        dosageUnitIndex: duIdx,
        startDate: sd,
        endDate: ed,
        isLongTerm: isLT,
        cycleMain: cd.main,
        cycleSub: cd.sub,
        guidance: migrateTiming(d.guidance),
        notes: (d.notes || '').slice(0, 200),
      });
    }).catch(function () {
      wx.showToast({ title: '加载失败', icon: 'none' });
    });
  },

  noop: function () {},

  // ───── 药品名称 ─────
  onTapName: function () {
    this._clearErr && this._clearErr('name');
    this.setData({ nameDrawerOpen: true, nameDraft: this.data.name, nameSuggests: [] });
  },
  closeNameDrawer: function () {
    this.setData({ nameDrawerOpen: false, nameSuggests: [] });
  },
  onNameInput: function (e) {
    var v = e.detail.value || '';
    this.setData({ nameDraft: v });
    this.triggerSuggest(v);
  },
  triggerSuggest: function (q) {
    var self = this;
    if (this._suggestTimer) clearTimeout(this._suggestTimer);
    if (!q || q.trim().length < 2) {
      this.setData({ nameSuggests: [] });
      return;
    }
    this._suggestTimer = setTimeout(function () {
      get('/api/medication-library/suggest', { q: q.trim(), limit: 6 }, { showLoading: false, suppressErrorToast: true }).then(function (res) {
        var data = unwrap(res);
        var items = (data && data.items) ? data.items : [];
        self.setData({ nameSuggests: items });
      }).catch(function () {
        self.setData({ nameSuggests: [] });
      });
    }, 250);
  },
  onPickSuggest: function (e) {
    var name = e.currentTarget.dataset.name;
    this.setData({ nameDraft: name, nameSuggests: [] });
  },
  confirmName: function () {
    this.setData({ name: (this.data.nameDraft || '').trim(), nameDrawerOpen: false, nameSuggests: [] });
  },

  // ───── 用药时间 ─────
  openTimeDrawer: function () {
    this._clearErr && this._clearErr('time');
    this.setData({ timeDrawerOpen: true });
  },
  closeTimeDrawer: function () { this.setData({ timeDrawerOpen: false }); },
  onChangeFreq: function (e) {
    var n = Number(e.currentTarget.dataset.n);
    var def = FREQ_DEFAULTS[n] || ['08:00'];
    var times = def.slice();
    this.setData({ frequencyPerDay: n, customTimes: times, timesText: times.join(' / ') });
  },
  onPickTime: function (e) {
    var idx = Number(e.currentTarget.dataset.idx);
    var v = e.detail.value;
    var times = this.data.customTimes.slice();
    times[idx] = v;
    this.setData({ customTimes: times, timesText: times.join(' / ') });
  },

  // ───── 剂量 ─────
  openDosageDrawer: function () {
    this._clearErr && this._clearErr('dosage');
    this.setData({ dosageDrawerOpen: true });
  },
  closeDosageDrawer: function () { this.setData({ dosageDrawerOpen: false }); },
  onChangeDosage: function (e) {
    var arr = e.detail.value;
    var vi = arr[0] || 0;
    var ui = arr[1] || 0;
    this.setData({
      dosageValueIndex: vi,
      dosageUnitIndex: ui,
      dosageValue: DOSAGE_VALUES[vi],
      dosageUnit: DOSAGE_UNITS[ui],
    });
  },

  // ───── 服用周期 ─────
  openCycleDrawer: function () {
    this._clearErr && this._clearErr('cycle');
    var start = this.data.startDate;
    var end = this.data.endDate;
    var isLT = this.data.isLongTerm;
    this.setData({
      cycleDrawerOpen: true,
      cycleDraftStart: start,
      cycleDraftEnd: end,
      cycleDraftLong: isLT,
      cycleDraftTip: buildCycleTip(start, end, isLT),
    });
  },
  closeCycleDrawer: function () { this.setData({ cycleDrawerOpen: false }); },
  onStartDateChange: function (e) {
    var v = e.detail.value;
    var end = this.data.cycleDraftEnd;
    if (!end || parseISO(end) < parseISO(v)) {
      var s = parseISO(v);
      end = toISO(addDays(s, 29));
    }
    this.setData({
      cycleDraftStart: v,
      cycleDraftEnd: end,
      cycleDraftTip: buildCycleTip(v, end, this.data.cycleDraftLong),
    });
  },
  onEndDateChange: function (e) {
    var v = e.detail.value;
    this.setData({
      cycleDraftEnd: v,
      cycleDraftTip: buildCycleTip(this.data.cycleDraftStart, v, this.data.cycleDraftLong),
    });
  },
  onLongTermChange: function (e) {
    var isLT = !!e.detail.value;
    this.setData({
      cycleDraftLong: isLT,
      cycleDraftTip: buildCycleTip(this.data.cycleDraftStart, this.data.cycleDraftEnd, isLT),
    });
  },
  confirmCycle: function () {
    var s = parseISO(this.data.cycleDraftStart);
    if (!s) {
      wx.showToast({ title: '请选择开始日期', icon: 'none' });
      return;
    }
    if (!this.data.cycleDraftLong) {
      var e = parseISO(this.data.cycleDraftEnd);
      if (!e) {
        wx.showToast({ title: '请选择结束日期', icon: 'none' });
        return;
      }
      if (e.getTime() < s.getTime()) {
        wx.showToast({ title: '结束日期不能早于开始日期', icon: 'none' });
        return;
      }
    }
    var isLT = this.data.cycleDraftLong;
    var endVal = isLT ? '' : this.data.cycleDraftEnd;
    var cd = buildCycleDisplay(this.data.cycleDraftStart, endVal, isLT);
    this.setData({
      startDate: this.data.cycleDraftStart,
      endDate: endVal,
      isLongTerm: isLT,
      cycleMain: cd.main,
      cycleSub: cd.sub,
      cycleDrawerOpen: false,
    });
  },

  // ───── 服用时机 ─────
  onTapTiming: function (e) {
    var v = e.currentTarget.dataset.val;
    this.setData({ guidance: v });
    this._clearErr('timing');
  },

  // [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.2] 工具：清除某字段红字
  _clearErr: function (key) {
    var ef = this.data.errFields || {};
    if (!ef[key]) return;
    var next = {};
    for (var k in ef) {
      if (k !== key) next[k] = ef[k];
    }
    this.setData({ errFields: next });
  },

  // ───── 备注 ─────
  openNotesDrawer: function () {
    this.setData({ notesDrawerOpen: true, notesDraft: this.data.notes });
  },
  closeNotesDrawer: function () { this.setData({ notesDrawerOpen: false }); },
  onNotesInput: function (e) {
    var v = (e.detail.value || '').slice(0, 200);
    this.setData({ notesDraft: v });
  },
  confirmNotes: function () {
    this.setData({ notes: (this.data.notesDraft || '').trim(), notesDrawerOpen: false });
  },

  // ───── 提交 ─────
  // [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.2-3.3] 必填红字校验 + 重复药品弹窗
  onSubmit: function () {
    var d = this.data;
    var errs = [];
    if (!d.name || !d.name.trim()) errs.push('name');
    if (!d.frequencyPerDay || d.customTimes.length !== d.frequencyPerDay) errs.push('time');
    if (!d.dosageValue || !d.dosageUnit) errs.push('dosage');
    if (!d.startDate) {
      errs.push('cycle');
    } else if (!d.isLongTerm) {
      var s = parseISO(d.startDate);
      var e = parseISO(d.endDate);
      if (!e) errs.push('cycle');
      else if (s && e.getTime() < s.getTime()) errs.push('cycle');
    }
    if (!d.guidance) errs.push('timing');
    var errMap = {};
    for (var i = 0; i < errs.length; i++) errMap[errs[i]] = true;
    this.setData({ errFields: errMap });
    if (errs.length > 0) {
      wx.showToast({ title: '请填写带 * 号的必填项', icon: 'none' });
      return;
    }

    // [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.3] 新增模式下调用 check-duplicate
    var self = this;
    if (!d.isEdit) {
      post('/api/health-plan/medications/check-duplicate', {
        drug_name: d.name.trim(),
        taker_id: 0,
      }, { showLoading: false, suppressErrorToast: true }).then(function (res) {
        var dd = (res && res.data) ? res.data : res || {};
        if (dd && dd.exists && dd.plan_id) {
          wx.showModal({
            title: '提示',
            content: '该药已加入用药计划,是否重新编辑?',
            confirmText: '确定',
            cancelText: '取消',
            success: function (mr) {
              if (mr && mr.confirm) {
                wx.redirectTo({
                  url: '/pages/health-plan/medication-form/index?id=' + dd.plan_id,
                });
              }
            },
          });
        } else {
          self._doSubmit();
        }
      }).catch(function () {
        // 接口失败 → 走老路径，让后端 409 兜底
        self._doSubmit();
      });
      return;
    }
    this._doSubmit();
  },

  _doSubmit: function () {
    var d = this.data;

    var dvBackend = dosageForBackend(d.dosageValue);
    var sParsed = parseISO(d.startDate);
    var eParsed = parseISO(d.endDate);
    var duration = (d.isLongTerm || !sParsed || !eParsed) ? null : diffDays(sParsed, eParsed);
    var payload = {
      medicine_name: d.name.trim(),
      dosage: dvBackend + ' ' + d.dosageUnit,
      dosage_value: dvBackend,
      dosage_unit: d.dosageUnit,
      frequency_per_day: d.frequencyPerDay,
      custom_times: d.customTimes,
      remind_time: d.customTimes[0] || '08:00',
      time_period: 'custom',
      start_date: d.startDate,
      end_date: d.isLongTerm ? null : d.endDate,
      duration_days: duration,
      long_term: d.isLongTerm,
      guidance: d.guidance,
      notes: d.notes || '',
      reminder_enabled: true,
    };

    var self = this;
    this.setData({ submitting: true });
    var req = d.isEdit
      ? put('/api/health-plan/medications/' + d.id, payload)
      : post('/api/health-plan/medications', payload);
    req.then(function (result) {
      wx.showToast({ title: d.isEdit ? '保存成功' : '添加成功', icon: 'success' });
      if (!d.isEdit) {
        self.requestSubscribeMessage(result && (result.id || (result.data && result.data.id)));
      }
      setTimeout(function () { wx.navigateBack(); }, 1200);
    }).catch(function (err) {
      // [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.3] 409 重复药品兜底
      var statusCode = err && (err.statusCode || (err.data && err.data.statusCode));
      var detail = err && err.data && err.data.detail;
      var isDup = statusCode === 409 && detail && typeof detail === 'object'
        && detail.code === 'MEDICATION_DUPLICATE_ACTIVE';
      if (isDup && !d.isEdit && detail.existing_id) {
        wx.showModal({
          title: '提示',
          content: '该药已加入用药计划,是否重新编辑?',
          confirmText: '确定',
          cancelText: '取消',
          success: function (mr) {
            if (mr && mr.confirm) {
              wx.redirectTo({
                url: '/pages/health-plan/medication-form/index?id=' + detail.existing_id,
              });
            }
          },
        });
      }
    }).then(function () {
      self.setData({ submitting: false });
    });
  },

  requestSubscribeMessage: function (reminderId) {
    try {
      var app = getApp();
      var tmplIds = app && app.globalData && app.globalData.subscribeTemplateIds;
      if (!tmplIds || tmplIds.length === 0) return;
      wx.requestSubscribeMessage({
        tmplIds: tmplIds,
        success: function (res) {
          var accepted = [];
          tmplIds.forEach(function (id) {
            if (res[id] === 'accept') accepted.push(id);
          });
          if (accepted.length > 0 && reminderId) {
            post('/api/health-plan/medications/' + reminderId + '/subscribe', {
              template_ids: accepted,
            }, { showLoading: false, suppressErrorToast: true }).catch(function () {});
          }
        },
        fail: function () {},
      });
    } catch (e) { /* ignore */ }
  },
});
