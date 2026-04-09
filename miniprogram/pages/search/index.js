const { get, del } = require('../../utils/request');
const { debounce } = require('../../utils/util');

const plugin = requirePlugin('WechatSI');

Page({
  data: {
    keyword: '',
    inputFocus: true,
    suggestions: [],
    hotList: [],
    historyList: [],
    showVoiceOverlay: false,
    voiceState: '',
    voiceErrorMsg: '',
    recordingTime: 0,
    autoSearchCountdown: 0
  },

  _suggestDebounce: null,
  _recordTimer: null,
  _autoSearchTimer: null,
  _countdownTimer: null,
  _recognizeManager: null,
  /** 下一次搜索是否来自语音识别（不落 data，避免 setData 下划线字段异常） */
  _pendingVoiceSource: false,

  onLoad() {
    this._suggestDebounce = debounce(this._fetchSuggestions.bind(this), 300);
    this._initRecognizeManager();
    this.loadHotSearch();
    this.loadHistory();
  },

  onUnload() {
    this._clearAllTimers();
    this._recognizeManager = null;
  },

  _clearAllTimers() {
    if (this._recordTimer) { clearInterval(this._recordTimer); this._recordTimer = null; }
    if (this._autoSearchTimer) { clearTimeout(this._autoSearchTimer); this._autoSearchTimer = null; }
    if (this._countdownTimer) { clearInterval(this._countdownTimer); this._countdownTimer = null; }
  },

  _removePunctuation(str) {
    return str.replace(/[\u3002\uff1b\uff0c\uff1a\u201c\u201d\u2018\u2019\uff08\uff09\u3001\uff1f\u300a\u300b\uff01\u3010\u3011\u2026\u2014\uff5e\u00b7.,!?;:'"()\[\]{}\-_\/\\@#\$%\^&\*\+=~`<>]/g, '').trim();
  },

  _initRecognizeManager() {
    const manager = plugin.getRecordRecognitionManager();

    manager.onRecognize = (res) => {
      if (res.result) {
        this.setData({ keyword: this._removePunctuation(res.result) });
      }
    };

    manager.onStop = (res) => {
      if (this._recordTimer) { clearInterval(this._recordTimer); this._recordTimer = null; }

      const text = res.result ? this._removePunctuation(res.result) : '';
      if (text) {
        this._pendingVoiceSource = true;
        this.setData({
          keyword: text,
          showVoiceOverlay: false,
          voiceState: '',
        });
        this._startAutoSearch();
      } else {
        this.setData({
          voiceState: 'error',
          voiceErrorMsg: '未识别到内容，请重试'
        });
      }
    };

    manager.onError = (res) => {
      if (this._recordTimer) { clearInterval(this._recordTimer); this._recordTimer = null; }
      this.setData({
        voiceState: 'error',
        voiceErrorMsg: res.msg || '语音识别出错，请重试'
      });
    };

    manager.onStart = () => {
      let t = 0;
      this._recordTimer = setInterval(() => {
        t++;
        this.setData({ recordingTime: t });
        if (t >= 15) {
          this._stopRecording();
        }
      }, 1000);
    };

    this._recognizeManager = manager;
  },

  // --- Hot Search ---
  async loadHotSearch() {
    try {
      const res = await get('/api/search/hot', {}, { showLoading: false, suppressErrorToast: true });
      const list = Array.isArray(res) ? res : (res && res.items ? res.items : []);
      this.setData({ hotList: list });
    } catch (e) {
      // ignore
    }
  },

  // --- Search History ---
  async loadHistory() {
    const app = getApp();
    if (!app.globalData.isLoggedIn) {
      const local = wx.getStorageSync('search_history') || [];
      this.setData({ historyList: local });
      return;
    }
    try {
      const res = await get('/api/search/history', {}, { showLoading: false, suppressErrorToast: true });
      const list = Array.isArray(res) ? res : (res && res.items ? res.items : []);
      this.setData({ historyList: list });
    } catch (e) {
      const local = wx.getStorageSync('search_history') || [];
      this.setData({ historyList: local });
    }
  },

  // --- Input & Suggest ---
  onInput(e) {
    const keyword = e.detail.value;
    this._pendingVoiceSource = false;
    this.setData({ keyword });
    this._cancelAutoSearch();
    if (keyword.trim()) {
      this._suggestDebounce(keyword.trim());
    } else {
      this.setData({ suggestions: [] });
    }
  },

  async _fetchSuggestions(q) {
    try {
      const res = await get('/api/search/suggest', { q }, { showLoading: false, suppressErrorToast: true });
      const list = Array.isArray(res) ? res : (res && res.items ? res.items : []);
      if (this.data.keyword.trim() === q) {
        this.setData({ suggestions: list });
      }
    } catch (e) {
      // ignore
    }
  },

  onClear() {
    this._pendingVoiceSource = false;
    this.setData({ keyword: '', suggestions: [], inputFocus: true });
    this._cancelAutoSearch();
  },

  // --- Search Actions ---
  onSearch() {
    const q = this.data.keyword.trim();
    if (!q) return;
    const source = this._pendingVoiceSource ? 'voice' : 'text';
    this._pendingVoiceSource = false;
    this._cancelAutoSearch();
    this._saveLocalHistory(q);
    wx.navigateTo({ url: `/pages/search-result/index?q=${encodeURIComponent(q)}&source=${source}` });
  },

  onTagTap(e) {
    const text = e.currentTarget.dataset.text;
    if (!text) return;
    this._pendingVoiceSource = false;
    this.setData({ keyword: text });
    this._cancelAutoSearch();
    this._saveLocalHistory(text);
    wx.navigateTo({ url: `/pages/search-result/index?q=${encodeURIComponent(text)}` });
  },

  onSuggestTap(e) {
    const text = e.currentTarget.dataset.text;
    if (!text) return;
    this._pendingVoiceSource = false;
    this.setData({ keyword: text, suggestions: [] });
    this._cancelAutoSearch();
    this._saveLocalHistory(text);
    wx.navigateTo({ url: `/pages/search-result/index?q=${encodeURIComponent(text)}` });
  },

  onClearHistory() {
    wx.showModal({
      title: '提示',
      content: '确认清空搜索历史？',
      success: async (res) => {
        if (res.confirm) {
          const app = getApp();
          if (app.globalData.isLoggedIn) {
            try {
              await del('/api/search/history', {}, { showLoading: false, suppressErrorToast: true });
            } catch (e) {
              // ignore
            }
          }
          this.setData({ historyList: [] });
          wx.removeStorageSync('search_history');
        }
      }
    });
  },

  _saveLocalHistory(q) {
    let list = wx.getStorageSync('search_history') || [];
    list = list.filter(item => item !== q);
    list.unshift(q);
    if (list.length > 20) list = list.slice(0, 20);
    wx.setStorageSync('search_history', list);
  },

  // --- Auto Search ---
  _startAutoSearch() {
    this._cancelAutoSearch();
    let countdown = 2;
    this.setData({ autoSearchCountdown: countdown });

    this._countdownTimer = setInterval(() => {
      countdown--;
      if (countdown <= 0) {
        this._cancelAutoSearch();
        this.onSearch();
      } else {
        this.setData({ autoSearchCountdown: countdown });
      }
    }, 1000);
  },

  cancelAutoSearch() {
    this._cancelAutoSearch();
  },

  _cancelAutoSearch() {
    if (this._countdownTimer) { clearInterval(this._countdownTimer); this._countdownTimer = null; }
    if (this._autoSearchTimer) { clearTimeout(this._autoSearchTimer); this._autoSearchTimer = null; }
    this.setData({ autoSearchCountdown: 0 });
  },

  // --- Voice ---
  onMicTap() {
    if (this.data.showVoiceOverlay) return;
    this._cancelAutoSearch();
    this.setData({
      showVoiceOverlay: true,
      voiceState: 'recording',
      recordingTime: 0,
      voiceErrorMsg: ''
    });
    this._startRecording();
  },

  onStopRecording() {
    this._stopRecording();
  },

  onMicLongPress() {
    this._cancelAutoSearch();
    this.setData({
      showVoiceOverlay: true,
      voiceState: 'recording',
      recordingTime: 0,
      voiceErrorMsg: ''
    });
    this._startRecording();
  },

  onMicTouchEnd() {
    if (this.data.voiceState === 'recording') {
      this._stopRecording();
    }
  },

  _startRecording() {
    if (!this._recognizeManager) {
      this._initRecognizeManager();
    }
    this._recognizeManager.start({ lang: 'zh_CN' });
  },

  _stopRecording() {
    if (this._recordTimer) { clearInterval(this._recordTimer); this._recordTimer = null; }
    this.setData({ voiceState: 'recognizing' });
    if (this._recognizeManager) {
      this._recognizeManager.stop();
    }
  },

  onRetryVoice() {
    this.setData({
      voiceState: 'recording',
      recordingTime: 0,
      voiceErrorMsg: ''
    });
    this._startRecording();
  },

  onCloseVoice() {
    this.setData({
      showVoiceOverlay: false,
      voiceState: '',
      voiceErrorMsg: ''
    });
  },

  preventMove() {
    // prevent scroll behind overlay
  }
});
