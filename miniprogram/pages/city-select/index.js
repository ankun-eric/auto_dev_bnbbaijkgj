const { get } = require('../../utils/request');

Page({
  data: {
    keyword: '',
    searching: false,
    searchResults: [],
    gpsCity: '',
    gpsCityId: null,
    locating: false,
    recentCities: [],
    hotCities: [],
    cityGroups: [],
    letters: [],
    scrollToId: ''
  },

  _searchTimer: null,

  onLoad() {
    this.loadRecentCities();
    this.loadHotCities();
    this.loadAllCities();
    this.loadGPSCity();
  },

  loadRecentCities() {
    const recent = wx.getStorageSync('recent_cities') || [];
    this.setData({ recentCities: recent });
  },

  async loadHotCities() {
    try {
      const res = await get('/api/cities/hot', {}, { showLoading: false, suppressErrorToast: true });
      if (res && res.cities && Array.isArray(res.cities)) {
        this.setData({ hotCities: res.cities });
      } else if (res && Array.isArray(res)) {
        this.setData({ hotCities: res });
      }
    } catch (e) {
      // ignore
    }
  },

  async loadAllCities() {
    try {
      const res = await get('/api/cities/list', {}, { showLoading: false, suppressErrorToast: true });
      if (res && res.groups && Array.isArray(res.groups)) {
        const allCities = [];
        res.groups.forEach(g => {
          if (Array.isArray(g.cities)) {
            g.cities.forEach(c => {
              allCities.push({ ...c, first_letter: g.letter || c.first_letter });
            });
          }
        });
        this.buildCityGroups(allCities);
      } else {
        const cities = Array.isArray(res) ? res : [];
        this.buildCityGroups(cities);
      }
    } catch (e) {
      // ignore
    }
  },

  buildCityGroups(cities) {
    const map = {};
    cities.forEach(city => {
      const letter = (city.first_letter || '#').toUpperCase();
      if (!map[letter]) map[letter] = [];
      map[letter].push(city);
    });

    const sortedLetters = Object.keys(map).sort((a, b) => {
      if (a === '#') return 1;
      if (b === '#') return -1;
      return a.localeCompare(b);
    });

    const groups = sortedLetters.map(letter => ({
      letter,
      cities: map[letter]
    }));

    this.setData({ cityGroups: groups, letters: sortedLetters });
  },

  loadGPSCity() {
    const cached = wx.getStorageSync('gps_city_cache');
    if (cached && cached.expire > Date.now()) {
      this.setData({ gpsCity: cached.name, gpsCityId: cached.id });
      return;
    }
    this.doGPSLocate();
  },

  onRelocate() {
    this.doGPSLocate();
  },

  doGPSLocate() {
    this.setData({ locating: true, gpsCity: '定位中...' });
    wx.getLocation({
      type: 'gcj02',
      success: (res) => {
        this.locateByCoords(res.longitude, res.latitude);
      },
      fail: () => {
        this.setData({ locating: false, gpsCity: '定位失败' });
      }
    });
  },

  async locateByCoords(lng, lat) {
    try {
      const res = await get('/api/cities/locate', { lng, lat }, { showLoading: false, suppressErrorToast: true });
      const city = res && res.city ? res.city : res;
      if (city && city.id && city.name) {
        const cacheData = { id: city.id, name: city.name, expire: Date.now() + 30 * 60 * 1000 };
        wx.setStorageSync('gps_city_cache', cacheData);
        this.setData({ gpsCity: city.name, gpsCityId: city.id });
      } else {
        this.setData({ gpsCity: '定位失败' });
      }
    } catch (e) {
      this.setData({ gpsCity: '定位失败' });
    } finally {
      this.setData({ locating: false });
    }
  },

  onSearchInput(e) {
    const keyword = e.detail.value.trim();
    this.setData({ keyword });
    if (this._searchTimer) clearTimeout(this._searchTimer);
    if (!keyword) {
      this.setData({ searchResults: [], searching: false });
      return;
    }
    this.setData({ searching: true });
    this._searchTimer = setTimeout(() => this.doSearch(keyword), 300);
  },

  async doSearch(keyword) {
    try {
      const res = await get('/api/cities/list', { keyword }, { showLoading: false, suppressErrorToast: true });
      let cities = [];
      if (res && res.groups && Array.isArray(res.groups)) {
        res.groups.forEach(g => {
          if (Array.isArray(g.cities)) {
            cities = cities.concat(g.cities);
          }
        });
      } else if (Array.isArray(res)) {
        cities = res;
      }
      if (this.data.keyword === keyword) {
        this.setData({ searchResults: cities, searching: false });
      }
    } catch (e) {
      this.setData({ searchResults: [], searching: false });
    }
  },

  onClearSearch() {
    this.setData({ keyword: '', searchResults: [], searching: false });
  },

  onLetterTap(e) {
    const letter = e.currentTarget.dataset.letter;
    this.setData({ scrollToId: 'letter-' + letter });
  },

  onSelectGPSCity() {
    if (!this.data.gpsCityId || !this.data.gpsCity || this.data.gpsCity === '定位中...' || this.data.gpsCity === '定位失败') return;
    this.selectCity({ id: this.data.gpsCityId, name: this.data.gpsCity });
  },

  onSelectCity(e) {
    const city = e.currentTarget.dataset.city;
    if (!city || !city.id) return;
    this.selectCity(city);
  },

  selectCity(city) {
    wx.setStorageSync('selected_city_id', city.id);
    wx.setStorageSync('selected_city_name', city.name);
    this.updateRecentCities(city);
    wx.navigateBack();
  },

  updateRecentCities(city) {
    let recent = wx.getStorageSync('recent_cities') || [];
    recent = recent.filter(c => c.id !== city.id);
    recent.unshift({ id: city.id, name: city.name });
    if (recent.length > 3) recent = recent.slice(0, 3);
    wx.setStorageSync('recent_cities', recent);
  }
});
