import api from '@/lib/api';

export interface CityInfo {
  id: number;
  name: string;
}

const SELECTED_CITY_ID_KEY = 'selected_city_id';
const SELECTED_CITY_NAME_KEY = 'selected_city_name';
const RECENT_CITIES_KEY = 'recent_cities';
const LOCATION_CACHE_KEY = 'location_cache';
const LOCATION_CACHE_DURATION = 30 * 60 * 1000;

export function getSelectedCity(): CityInfo | null {
  if (typeof window === 'undefined') return null;
  const id = localStorage.getItem(SELECTED_CITY_ID_KEY);
  const name = localStorage.getItem(SELECTED_CITY_NAME_KEY);
  if (id && name) return { id: Number(id), name };
  return null;
}

export function setSelectedCity(city: CityInfo): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(SELECTED_CITY_ID_KEY, String(city.id));
  localStorage.setItem(SELECTED_CITY_NAME_KEY, city.name);
}

export function getRecentCities(): CityInfo[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(RECENT_CITIES_KEY);
    if (!raw) return [];
    const list = JSON.parse(raw) as CityInfo[];
    return Array.isArray(list) ? list.slice(0, 3) : [];
  } catch {
    return [];
  }
}

export function addRecentCity(city: CityInfo): void {
  if (typeof window === 'undefined') return;
  const list = getRecentCities().filter((c) => c.id !== city.id);
  list.unshift(city);
  localStorage.setItem(RECENT_CITIES_KEY, JSON.stringify(list.slice(0, 3)));
}

interface LocationCache {
  city: CityInfo;
  timestamp: number;
}

export function getLocationCache(): CityInfo | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(LOCATION_CACHE_KEY);
    if (!raw) return null;
    const cache = JSON.parse(raw) as LocationCache;
    if (Date.now() - cache.timestamp < LOCATION_CACHE_DURATION) {
      return cache.city;
    }
    localStorage.removeItem(LOCATION_CACHE_KEY);
    return null;
  } catch {
    return null;
  }
}

export function setLocationCache(city: CityInfo): void {
  if (typeof window === 'undefined') return;
  const cache: LocationCache = { city, timestamp: Date.now() };
  localStorage.setItem(LOCATION_CACHE_KEY, JSON.stringify(cache));
}

export async function requestGeolocation(): Promise<CityInfo | null> {
  const cached = getLocationCache();
  if (cached) return cached;

  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve(null);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const { longitude, latitude } = position.coords;
          const data: any = await api.get('/api/cities/locate', {
            params: { lng: longitude, lat: latitude },
          });
          const rawCity = data?.city ?? data;
          const city: CityInfo = {
            id: rawCity?.id,
            name: rawCity?.name,
          };
          if (city.id && city.name) {
            setLocationCache(city);
            resolve(city);
          } else {
            resolve(null);
          }
        } catch {
          resolve(null);
        }
      },
      () => {
        resolve(null);
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: LOCATION_CACHE_DURATION },
    );
  });
}

export function getCurrentCityDisplay(): string {
  const selected = getSelectedCity();
  if (selected) return selected.name;
  const cached = getLocationCache();
  if (cached) return cached.name;
  return '定位';
}
