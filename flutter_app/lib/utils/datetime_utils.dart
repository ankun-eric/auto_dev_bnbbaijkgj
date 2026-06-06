// [日期时区简化 2026-06-06] 简化版时间格式化工具（Flutter App）
// 后端统一返回北京时间 "YYYY-MM-DD HH:mm:ss"，客户端直接解析即可。

import 'package:intl/intl.dart';

DateTime? parseServerTime(dynamic iso) {
  if (iso == null) return null;
  if (iso is DateTime) return iso;
  if (iso is int) {
    return DateTime.fromMillisecondsSinceEpoch(iso);
  }
  try {
    return DateTime.parse(iso.toString().trim());
  } catch (_) {
    return null;
  }
}

String _pad2(int n) => n.toString().padLeft(2, '0');

String formatDateTime(dynamic iso, {String pattern = 'yyyy-MM-dd HH:mm'}) {
  final d = parseServerTime(iso);
  if (d == null) return '';
  return DateFormat(pattern).format(d);
}

String formatFullTime(dynamic iso) =>
    formatDateTime(iso, pattern: 'yyyy-MM-dd HH:mm:ss');

String formatDate(dynamic iso) => formatDateTime(iso, pattern: 'yyyy-MM-dd');

String formatTime(dynamic iso) => formatDateTime(iso, pattern: 'HH:mm');

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

String formatFriendlyTime(dynamic iso) {
  final d = parseServerTime(iso);
  if (d == null) return '';
  final now = DateTime.now();
  final targetDay = DateTime(d.year, d.month, d.day);
  final todayDay = DateTime(now.year, now.month, now.day);
  final diffDays = todayDay.difference(targetDay).inDays;
  final hh = _pad2(d.hour);
  final mm = _pad2(d.minute);
  if (diffDays == 0) return '今日 $hh:$mm';
  if (diffDays == 1) return '昨日 $hh:$mm';
  if (diffDays >= 2 && diffDays <= 6) return '$diffDays 天前';
  if (d.year == now.year) {
    return '${_pad2(d.month)}-${_pad2(d.day)}';
  }
  return '${d.year}-${_pad2(d.month)}-${_pad2(d.day)}';
}
