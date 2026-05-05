/// [PRD-01 全平台固定时段切片体系 v1.0] Flutter 端 9 段时段常量与工具
///
/// 全平台固定 9 段（每段 2 小时，最早 06:00，最晚 24:00），凌晨 00:00-06:00 不开放。
/// 与后端 backend/app/utils/time_slots.py 保持完全一致；
/// PRD §4 异常处理：当 GET /api/common/time-slots 接口失败时，使用本常量兜底，
/// 确保下单 / 改期 / 时段选择不阻塞。

class TimeSlotItem {
  final int slotNo;
  final String start;
  final String end;
  const TimeSlotItem({required this.slotNo, required this.start, required this.end});

  String get label => '$start-$end';

  factory TimeSlotItem.fromJson(Map<String, dynamic> json) => TimeSlotItem(
        slotNo: json['slot_no'] is int ? json['slot_no'] as int : int.tryParse('${json['slot_no']}') ?? 0,
        start: '${json['start'] ?? ''}',
        end: '${json['end'] ?? ''}',
      );
}

const List<TimeSlotItem> kFixedTimeSlots = <TimeSlotItem>[
  TimeSlotItem(slotNo: 1, start: '06:00', end: '08:00'),
  TimeSlotItem(slotNo: 2, start: '08:00', end: '10:00'),
  TimeSlotItem(slotNo: 3, start: '10:00', end: '12:00'),
  TimeSlotItem(slotNo: 4, start: '12:00', end: '14:00'),
  TimeSlotItem(slotNo: 5, start: '14:00', end: '16:00'),
  TimeSlotItem(slotNo: 6, start: '16:00', end: '18:00'),
  TimeSlotItem(slotNo: 7, start: '18:00', end: '20:00'),
  TimeSlotItem(slotNo: 8, start: '20:00', end: '22:00'),
  TimeSlotItem(slotNo: 9, start: '22:00', end: '24:00'),
];

String slotLabel(int slotNo) {
  if (slotNo < 1 || slotNo > 9) return '';
  final s = kFixedTimeSlots[slotNo - 1];
  return s.label;
}

/// 时间 → 段号 1-9（凌晨段 / null 输入返回 null）。
/// 跨日订单（22:00-次日 00:00）按起始时间归段（PRD R-01-03）。
int? appointmentToSlot(DateTime? dt) {
  if (dt == null) return null;
  final h = dt.hour;
  if (h < 6) return null;
  if (h >= 22) return 9;
  return ((h - 6) ~/ 2) + 1;
}

/// 拉取 /api/common/time-slots，失败时回退到常量。
/// fetcher 应返回包含 `{slots: [...]}` 结构的 Map，由调用方注入 HTTP 客户端。
Future<List<TimeSlotItem>> fetchTimeSlotsWithFallback(
  Future<Map<String, dynamic>?> Function() fetcher,
) async {
  try {
    final resp = await fetcher();
    final slots = resp?['slots'];
    if (slots is List && slots.length == 9) {
      return slots
          .map((e) => TimeSlotItem.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(growable: false);
    }
  } catch (_) {
    // 接口失败 → 兜底
  }
  return kFixedTimeSlots;
}
