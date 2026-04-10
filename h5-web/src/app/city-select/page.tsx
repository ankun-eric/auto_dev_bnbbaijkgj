'use client';

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { SpinLoading, Toast } from 'antd-mobile';
import api from '@/lib/api';
import {
  CityInfo,
  getSelectedCity,
  setSelectedCity,
  addRecentCity,
  getRecentCities,
  getLocationCache,
  requestGeolocation,
} from '@/lib/cityUtils';

interface CityItem {
  id: number;
  name: string;
  pinyin?: string;
  first_letter?: string;
}

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

export default function CitySelectPage() {
  const router = useRouter();

  const [allCities, setAllCities] = useState<CityItem[]>([]);
  const [hotCities, setHotCities] = useState<CityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState('');
  const [filteredCities, setFilteredCities] = useState<CityItem[]>([]);
  const [searching, setSearching] = useState(false);

  const [recentCities, setRecentCities] = useState<CityInfo[]>([]);
  const [gpsCity, setGpsCity] = useState<CityInfo | null>(null);
  const [gpsStatus, setGpsStatus] = useState<'idle' | 'locating' | 'located' | 'failed'>('idle');

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const sectionRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const [activeLetter, setActiveLetter] = useState('');

  useEffect(() => {
    setRecentCities(getRecentCities());

    const cached = getLocationCache();
    if (cached) {
      setGpsCity(cached);
      setGpsStatus('located');
    } else {
      setGpsStatus('locating');
      requestGeolocation().then((city) => {
        if (city) {
          setGpsCity(city);
          setGpsStatus('located');
        } else {
          setGpsStatus('failed');
        }
      });
    }
  }, []);

  useEffect(() => {
    let active = true;
    const fetchData = async () => {
      try {
        const [citiesRes, hotRes] = await Promise.all([
          api.get('/api/cities/list') as Promise<any>,
          api.get('/api/cities/hot') as Promise<any>,
        ]);
        if (!active) return;
        let cities: CityItem[] = [];
        if (citiesRes?.groups && Array.isArray(citiesRes.groups)) {
          for (const g of citiesRes.groups) {
            if (Array.isArray(g.cities)) {
              for (const c of g.cities) {
                cities.push({ ...c, first_letter: g.letter ?? c.first_letter });
              }
            }
          }
        } else if (Array.isArray(citiesRes)) {
          cities = citiesRes;
        }
        const hot = hotRes?.cities ?? (Array.isArray(hotRes) ? hotRes : hotRes?.items ?? []);
        setAllCities(cities);
        setHotCities(hot);
      } catch {
        /* ignore */
      } finally {
        if (active) setLoading(false);
      }
    };
    fetchData();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!keyword.trim()) {
      setFilteredCities([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    let active = true;
    const timer = setTimeout(async () => {
      try {
        const res: any = await api.get('/api/cities/list', { params: { keyword: keyword.trim() } });
        if (!active) return;
        let list: CityItem[] = [];
        if (res?.groups && Array.isArray(res.groups)) {
          for (const g of res.groups) {
            if (Array.isArray(g.cities)) {
              list.push(...g.cities);
            }
          }
        } else if (Array.isArray(res)) {
          list = res;
        }
        setFilteredCities(list);
      } catch {
        if (active) setFilteredCities([]);
      } finally {
        if (active) setSearching(false);
      }
    }, 300);
    return () => { active = false; clearTimeout(timer); };
  }, [keyword]);

  const groupedCities = useMemo(() => {
    const map: Record<string, CityItem[]> = {};
    for (const city of allCities) {
      const letter = (city.first_letter || city.pinyin?.[0] || '#').toUpperCase();
      const key = LETTERS.includes(letter) ? letter : '#';
      if (!map[key]) map[key] = [];
      map[key].push(city);
    }
    const sorted = Object.keys(map).sort((a, b) => {
      if (a === '#') return 1;
      if (b === '#') return -1;
      return a.localeCompare(b);
    });
    return sorted.map((letter) => ({ letter, cities: map[letter] }));
  }, [allCities]);

  const availableLetters = useMemo(
    () => groupedCities.map((g) => g.letter),
    [groupedCities],
  );

  const handleSelectCity = useCallback((city: CityInfo) => {
    setSelectedCity(city);
    addRecentCity(city);
    router.back();
  }, [router]);

  const handleRelocate = useCallback(() => {
    setGpsStatus('locating');
    requestGeolocation().then((city) => {
      if (city) {
        setGpsCity(city);
        setGpsStatus('located');
      } else {
        setGpsStatus('failed');
        Toast.show({ content: '定位失败，请检查定位权限', icon: 'fail' });
      }
    });
  }, []);

  const scrollToLetter = useCallback((letter: string) => {
    setActiveLetter(letter);
    const el = sectionRefs.current[letter];
    if (el && scrollContainerRef.current) {
      const containerTop = scrollContainerRef.current.getBoundingClientRect().top;
      const elTop = el.getBoundingClientRect().top;
      scrollContainerRef.current.scrollTop += elTop - containerTop;
    }
  }, []);

  const isSearching = keyword.trim().length > 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-white">
        <SpinLoading color="primary" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-white">
      {/* Top nav */}
      <div className="flex items-center px-3 py-2 border-b border-gray-100 shrink-0">
        <button
          className="w-8 h-8 flex items-center justify-center shrink-0"
          onClick={() => router.back()}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#333" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <span className="flex-1 text-center text-base font-semibold text-gray-800">选择城市</span>
        <div className="w-8" />
      </div>

      {/* Search input */}
      <div className="px-4 py-2 shrink-0">
        <div className="flex items-center bg-gray-100 rounded-full px-3 h-9">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="输入城市名搜索"
            className="flex-1 bg-transparent border-none outline-none text-sm ml-2 text-gray-800 placeholder-gray-400"
          />
          {keyword && (
            <button
              className="w-5 h-5 rounded-full bg-gray-300 flex items-center justify-center shrink-0"
              onClick={() => setKeyword('')}
            >
              <span className="text-white text-xs leading-none">×</span>
            </button>
          )}
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto relative" ref={scrollContainerRef}>
        {isSearching ? (
          <div className="px-4 py-2">
            {searching && (
              <div className="flex justify-center py-6">
                <SpinLoading style={{ '--size': '20px', '--color': '#52c41a' } as any} />
              </div>
            )}
            {!searching && filteredCities.length === 0 && (
              <div className="text-center text-sm text-gray-400 py-8">没有找到匹配的城市</div>
            )}
            {filteredCities.map((city) => (
              <div
                key={city.id}
                className="py-3 border-b border-gray-50 text-sm text-gray-700 cursor-pointer active:bg-gray-50"
                onClick={() => handleSelectCity({ id: city.id, name: city.name })}
              >
                {city.name}
              </div>
            ))}
          </div>
        ) : (
          <>
            {/* GPS location */}
            <div className="px-4 pt-3 pb-2">
              <div className="text-xs text-gray-400 mb-2">GPS定位</div>
              <div className="flex items-center gap-2">
                {gpsStatus === 'locating' && (
                  <div className="flex items-center gap-1 text-sm text-gray-400">
                    <SpinLoading style={{ '--size': '14px', '--color': '#999' } as any} />
                    <span>定位中...</span>
                  </div>
                )}
                {gpsStatus === 'located' && gpsCity && (
                  <div
                    className="px-3 py-1.5 rounded-md text-sm cursor-pointer active:opacity-70"
                    style={{ background: '#e6f4ff', color: '#1677ff' }}
                    onClick={() => handleSelectCity(gpsCity)}
                  >
                    {gpsCity.name}
                  </div>
                )}
                {gpsStatus === 'failed' && (
                  <div
                    className="px-3 py-1.5 rounded-md text-sm cursor-pointer active:opacity-70"
                    style={{ background: '#fff2e8', color: '#fa8c16' }}
                    onClick={handleRelocate}
                  >
                    重新定位
                  </div>
                )}
              </div>
            </div>

            {/* Recent cities */}
            {recentCities.length > 0 && (
              <div className="px-4 pt-2 pb-2">
                <div className="text-xs text-gray-400 mb-2">最近访问</div>
                <div className="flex flex-wrap gap-2">
                  {recentCities.map((city) => (
                    <div
                      key={city.id}
                      className="px-3 py-1.5 rounded-md text-sm bg-gray-100 text-gray-700 cursor-pointer active:bg-gray-200"
                      onClick={() => handleSelectCity(city)}
                    >
                      {city.name}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Hot cities */}
            {hotCities.length > 0 && (
              <div className="px-4 pt-2 pb-2">
                <div className="text-xs text-gray-400 mb-2">热门城市</div>
                <div className="grid grid-cols-4 gap-2">
                  {hotCities.map((city) => (
                    <div
                      key={city.id}
                      className="px-2 py-2 rounded-md text-sm text-center bg-gray-100 text-gray-700 cursor-pointer active:bg-gray-200 truncate"
                      onClick={() => handleSelectCity({ id: city.id, name: city.name })}
                    >
                      {city.name}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Divider */}
            <div className="h-2 bg-gray-50" />

            {/* Full city list grouped by letter */}
            <div className="relative">
              {groupedCities.map(({ letter, cities }) => (
                <div
                  key={letter}
                  ref={(el) => { sectionRefs.current[letter] = el; }}
                >
                  <div
                    className="sticky top-0 z-[1] px-4 py-1 text-xs font-medium text-gray-500"
                    style={{ background: '#f7f7f7' }}
                  >
                    {letter}
                  </div>
                  {cities.map((city) => (
                    <div
                      key={city.id}
                      className="px-4 py-3 border-b border-gray-50 text-sm text-gray-700 cursor-pointer active:bg-gray-50"
                      onClick={() => handleSelectCity({ id: city.id, name: city.name })}
                    >
                      {city.name}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Letter index sidebar */}
      {!isSearching && (
        <div
          className="fixed right-0 flex flex-col items-center justify-center z-10"
          style={{
            top: '50%',
            transform: 'translateY(-50%)',
            width: 20,
            paddingRight: 2,
          }}
        >
          {availableLetters.map((letter) => (
            <div
              key={letter}
              className="flex items-center justify-center cursor-pointer"
              style={{
                width: 16,
                height: 16,
                fontSize: 9,
                fontWeight: activeLetter === letter ? 700 : 400,
                color: activeLetter === letter ? '#1677ff' : '#999',
                borderRadius: '50%',
                background: activeLetter === letter ? '#e6f4ff' : 'transparent',
              }}
              onClick={() => scrollToLetter(letter)}
            >
              {letter}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
