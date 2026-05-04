// [PRD「商家 PC 后台预约日历优化」v1.0] 共享类型 + 状态色配置

export type CalendarView = 'month' | 'week' | 'day' | 'resource' | 'list';

export type AppointmentStatus =
  | 'pending'
  | 'verified'
  | 'cancelled'
  | 'refunded'
  | 'other';

export interface CalendarFilters {
  product_ids?: number[];
  staff_ids?: number[];
  statuses?: AppointmentStatus[];
  sources?: string[];
  q?: string;
}

export interface KpiData {
  today_count: number;
  week_count: number;
  month_count: number;
}

export interface CellInfo {
  date: string;
  booking_count: number;
  verified_count: number;
  occupied_rate: number;
  revenue: number;
  cancelled_count: number;
}

export interface ItemCard {
  order_id: number;
  order_item_id: number;
  appointment_time?: string | null;
  time_slot?: string | null;
  customer_nickname: string;
  product_name?: string | null;
  product_id?: number | null;
  staff_id?: number | null;
  staff_name?: string | null;
  status: AppointmentStatus;
  amount: number;
  source?: string | null;
}

export interface ListItem {
  order_id: number;
  order_item_id: number;
  appointment_date?: string | null;
  appointment_time?: string | null;
  customer_nickname: string;
  customer_phone?: string | null;
  product_name?: string | null;
  staff_name?: string | null;
  status: AppointmentStatus;
  amount: number;
  source?: string | null;
}

export interface MyView {
  id: number;
  name: string;
  view_type: CalendarView;
  filter_payload?: CalendarFilters | null;
  is_default: boolean;
  created_at: string;
}

// 状态色：pending=warning / verified=success / cancelled+refunded=default
export const STATUS_CONFIG: Record<
  AppointmentStatus,
  { text: string; color: string; bg: string }
> = {
  pending: { text: '待核销', color: 'warning', bg: '#fffbe6' },
  verified: { text: '已核销', color: 'success', bg: '#f6ffed' },
  cancelled: { text: '已取消', color: 'default', bg: '#fafafa' },
  refunded: { text: '已退款', color: 'default', bg: '#fafafa' },
  other: { text: '其它', color: 'default', bg: '#fafafa' },
};

export const SOURCE_OPTIONS = [
  { label: '小程序', value: 'miniprogram' },
  { label: 'H5', value: 'h5' },
  { label: '到店', value: 'store' },
  { label: '电话', value: 'phone' },
  { label: '管理端', value: 'admin' },
];

export const STATUS_FILTER_OPTIONS: { label: string; value: AppointmentStatus }[] = [
  { label: '待核销', value: 'pending' },
  { label: '已核销', value: 'verified' },
  { label: '已取消', value: 'cancelled' },
  { label: '已退款', value: 'refunded' },
];
