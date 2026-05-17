// [BUG_FIX_TIMEZONE_GLOBAL_20260517] 统一时间格式化工具（Flutter App，安卓/苹果通用）
//
// 设计目标：
// - 后端 datetime 统一为 UTC ISO（带 "+00:00" 或 "Z" 后缀）
// - App 按设备本地时区显示
// - 兼容无时区后缀的老接口：强制按 UTC 解析，避免 8 小时偏差

/// 解析服务端返回的时间字符串。
///
/// 兼容三种情况：
/// - 带 Z 后缀："2026-05-17T02:30:00Z"
/// - 带 +HH:MM/-HH:MM 后缀："2026-05-17T02:30:00+00:00"
/// - 不带时区后缀（老接口遗留）："2026-05-17T02:30:00" → 强制按 UTC 解析
///
/// 返回的 DateTime 已转为本地时区，可直接 `.year/.month/.hour` 取本地时间。
DateTime? parseServerTime(dynamic iso) {
  if (iso == null) return null;
  if (iso is DateTime) return iso.toLocal();
  if (iso is int) {
    return DateTime.fromMillisecondsSinceEpoch(iso, isUtc: true).toLocal();
  }
  final s = iso.toString().trim();
  if (s.isEmpty) return null;
  // 检测是否带时区后缀
  final hasTz =
      s.endsWith('Z') || RegExp(r'[+-]\d{2}:?\d{2}$').hasMatch(s);
  final normalized = hasTz ? s : s + 'Z';
  try {
    return DateTime.parse(normalized).toLocal();
  } catch (_) {
    return null;
  }
}

String _pad2(int n) => n.toString().padLeft(2, '0');

/// 按本地时区格式化，支持模式占位符：YYYY/MM/DD/HH/mm/ss
String formatDateTime(dynamic iso, {String pattern = 'yyyy-MM-dd HH:mm'}) {
  final d = parseServerTime(iso);
  if (d == null) return '';
  return pattern
      .replaceAll('yyyy', d.year.toString())
      .replaceAll('YYYY', d.year.toString())
      .replaceAll('MM', _pad2(d.month))
      .replaceAll('dd', _pad2(d.day))
      .replaceAll('DD', _pad2(d.day))
      .replaceAll('HH', _pad2(d.hour))
      .replaceAll('mm', _pad2(d.minute))
      .replaceAll('ss', _pad2(d.second));
}

String formatDate(dynamic iso) => formatDateTime(iso, pattern: 'yyyy-MM-dd');

String formatTime(dynamic iso) => formatDateTime(iso, pattern: 'HH:mm');

/// 相对时间："刚刚" / "X 分钟前" / "X 小时前" / "X 天前" / 超过 30 天则回退到日期。
String formatRelativeTime(dynamic iso) {
  final d = parseServerTime(iso);
  if (d == null) return '';
  final diff = DateTime.now().difference(d);
  if (diff.isNegative) return formatDateTime(iso);
  final sec = diff.inSeconds;
  if (sec < 60) return '刚刚';
  final min = diff.inMinutes;
  if (min < 60) return '$min 分钟前';
  final hour = diff.inHours;
  if (hour < 24) return '$hour 小时前';
  final day = diff.inDays;
  if (day < 30) return '$day 天前';
  return formatDate(iso);
}

/// 友好时间：今天 "HH:mm" / 昨天 "昨天 HH:mm" / 今年 "MM-DD HH:mm" / 更早 "YYYY-MM-DD"
String formatFriendlyTime(dynamic iso) {
  final d = parseServerTime(iso);
  if (d == null) return '';
  final now = DateTime.now();
  final isSameDay =
      d.year == now.year && d.month == now.month && d.day == now.day;
  if (isSameDay) return formatTime(iso);
  final yesterday = DateTime(now.year, now.month, now.day - 1);
  final isYesterday = d.year == yesterday.year &&
      d.month == yesterday.month &&
      d.day == yesterday.day;
  if (isYesterday) return '昨天 ${formatTime(iso)}';
  if (d.year == now.year) {
    return formatDateTime(iso, pattern: 'MM-dd HH:mm');
  }
  return formatDate(iso);
}
