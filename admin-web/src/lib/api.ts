import axios, { AxiosRequestConfig } from 'axios';

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

const api = axios.create({
  baseURL: '',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use(
  (config) => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('admin_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('admin_token');
        localStorage.removeItem('admin_user');
        window.location.href = `${basePath}/login`;
      }
    }
    return Promise.reject(error);
  }
);

export async function get<T = any>(url: string, params?: any, config?: AxiosRequestConfig): Promise<T> {
  const res = await api.get(url, { params, ...config });
  return res.data;
}

export async function post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
  const res = await api.post(url, data, config);
  return res.data;
}

export async function put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
  const res = await api.put(url, data, config);
  return res.data;
}

export async function del<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const res = await api.delete(url, config);
  return res.data;
}

export async function upload<T = any>(url: string, file: File, fieldName = 'file'): Promise<T> {
  const formData = new FormData();
  formData.append(fieldName, file);
  const res = await api.post(url, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export default api;
