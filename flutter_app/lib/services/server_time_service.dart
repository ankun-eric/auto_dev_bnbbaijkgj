// [BUG-FIX-RESCHEDULE-V2 2026-05-07] 服务器时间工具（Flutter 版本）。
// 用途：改约弹窗按服务器时间过滤已过去的整段时段。

import 'package:dio/dio.dart';
import 'api_service.dart';

class ServerTimeService {
  ServerTimeService._internal();
  static final ServerTimeService _instance = ServerTimeService._internal();
  factory ServerTimeService() => _instance;

  int _offsetMs = 0;
  bool _initialized = false;
  bool _lastFailed = false;
  Future<void>? _initing;

  Future<void> init() async {
    if (_initialized) return;
    if (_initing != null) return _initing;
    _initing = _doInit();
    try {
      await _initing;
    } finally {
      _initing = null;
    }
  }

  Future<void> _doInit() async {
    try {
      final Response resp = await ApiService().dio.get('/api/system/server-time');
      final data = resp.data;
      if (data is Map && data['now_unix_ms'] != null) {
        final serverMs = (data['now_unix_ms'] is int)
            ? data['now_unix_ms'] as int
            : int.tryParse(data['now_unix_ms'].toString()) ?? 0;
        if (serverMs > 0) {
          _offsetMs = serverMs - DateTime.now().millisecondsSinceEpoch;
          _initialized = true;
          _lastFailed = false;
          return;
        }
      }
      _lastFailed = true;
    } catch (_) {
      _lastFailed = true;
    }
  }

  DateTime now() {
    return DateTime.fromMillisecondsSinceEpoch(
      DateTime.now().millisecondsSinceEpoch + _offsetMs,
    );
  }

  bool get isUnreliable => _lastFailed && !_initialized;

  bool isSameDayAsServer(DateTime d) {
    final n = now();
    return d.year == n.year && d.month == n.month && d.day == n.day;
  }

  /// 解析 "HH:mm-HH:mm" 形式的时段字符串，返回 [开始分钟数, 结束分钟数]，跨日 24:00 → 1440。
  static List<int>? parseSlotRange(String slot) {
    final m = RegExp(r'^(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})$').firstMatch(slot);
    if (m == null) return null;
    try {
      final sh = int.parse(m.group(1)!);
      final sm = int.parse(m.group(2)!);
      final eh = int.parse(m.group(3)!);
      final em = int.parse(m.group(4)!);
      return [sh * 60 + sm, eh * 60 + em];
    } catch (_) {
      return null;
    }
  }

  /// 过滤已过去的整段时段。
  /// 仅当 [selectedDate] == 服务器今天 时按 (时段结束 > 服务器现在的分钟数) 过滤。
  List<String> filterPastSlots(DateTime? selectedDate, List<String> slots) {
    if (selectedDate == null || slots.isEmpty) return slots;
    if (!isSameDayAsServer(selectedDate)) return slots;
    final n = now();
    final nowMin = n.hour * 60 + n.minute;
    final result = <String>[];
    for (final s in slots) {
      final r = parseSlotRange(s);
      if (r == null) {
        result.add(s);
        continue;
      }
      if (r[1] > nowMin) {
        result.add(s);
      }
    }
    return result;
  }
}
