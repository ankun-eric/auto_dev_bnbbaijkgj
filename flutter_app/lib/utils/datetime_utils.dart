// [BUG_FIX_TIMEZONE_GLOBAL_20260517] 统一时间格式化工具（Flutter App，安卓/苹果通用）
// [BUG_FIX_TIMEZONE_BJ_UNIFIED_20260530] 全局固定北京时间口径，新增 formatFriendlyTime / formatFullTime
//
// 后端 datetime 应统一以 UTC 返回；老接口若无时区后缀，前端按 UTC 解析后转为北京时间显示。
// 与设备本地时区无关，全局以东八区为口径。

const Duration _bjOffset = Duration(hours: 8);

/// 解析服务端返回的时间字符串，返回 UTC 的 DateTime（isUtc=true）。
DateTime? parseServerTime(dynamic iso) {
  if (iso == null) return null;
  if (iso is DateTime) {
    return iso.isUtc ? iso : iso.toUtc();
  }
  if (iso is int) {
    return DateTime.fromMillisecondsSinceEpoch(iso, isUtc: true);
  }
  var s = iso.toString().trim();
  if (s.isEmpty) return null;
  final hasTz =
      s.endsWith('Z') || RegExp(r'[+-]\d{2}:?\d{2}$').hasMatch(s);
  if (!hasTz) {
    if (s.contains(' ') && !s.contains('T')) {
      s = s.replaceFirst(' ', 'T');
    }
    s = s + 'Z';
  }
  try {
    return DateTime.parse(s).toUtc();
  } catch (_) {
    return null;
  }
}

/// 将 UTC 时间转换为北京时间（作为 UTC 表示，仅用于读取年/月/日/时/分/秒字段）。
DateTime? _toBj(dynamic iso) {
  final d = parseServerTime(iso);
  if (d == null) return null;
  return d.add(_bjOffset);
}

String _pad2(int n) => n.toString().padLeft(2, '0');

/// 按北京时间格式化，支持模式占位符：YYYY/yyyy/MM/DD/dd/HH/mm/ss
String formatDateTime(dynamic iso, {String pattern = 'yyyy-MM-dd HH:mm'}) {
  final d = _toBj(iso);
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

String formatFullTime(dynamic iso) =>
    formatDateTime(iso, pattern: 'yyyy-MM-dd HH:mm:ss');

String formatDate(dynamic iso) => formatDateTime(iso, pattern: 'yyyy-MM-dd');

String formatTime(dynamic iso) => formatDateTime(iso, pattern: 'HH:mm');

/// 相对时间："刚刚" / "X 分钟前" / "X 小时前" / "X 天前" / 超过 30 天则回退到日期。
String formatRelativeTime(dynamic iso) {
  final d = parseServerTime(iso);
  if (d == null) return '';
  final diff = DateTime.now().toUtc().difference(d);
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

/// 友好时间（北京时间口径）：
/// - 今日 HH:mm / 昨日 HH:mm / X 天前(2~6) / MM-DD（同年） / YYYY-MM-DD（跨年）
String formatFriendlyTime(dynamic iso) {
  final dt = _toBj(iso);
  if (dt == null) return '';
  final nowBj = DateTime.now().toUtc().add(_bjOffset);
  final targetDay = DateTime.utc(dt.year, dt.month, dt.day);
  final todayDay = DateTime.utc(nowBj.year, nowBj.month, nowBj.day);
  final diffDays = todayDay.difference(targetDay).inDays;
  final hh = _pad2(dt.hour);
  final mm = _pad2(dt.minute);
  if (diffDays == 0) return '今日 $hh:$mm';
  if (diffDays == 1) return '昨日 $hh:$mm';
  if (diffDays >= 2 && diffDays <= 6) return '$diffDays 天前';
  if (dt.year == nowBj.year) {
    return '${_pad2(dt.month)}-${_pad2(dt.day)}';
  }
  return '${dt.year}-${_pad2(dt.month)}-${_pad2(dt.day)}';
}
