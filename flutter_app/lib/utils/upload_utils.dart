import 'dart:io';
import '../services/api_service.dart';

class UploadLimitItem {
  final String module;
  final String moduleName;
  final double maxSizeMb;

  UploadLimitItem({
    required this.module,
    required this.moduleName,
    required this.maxSizeMb,
  });

  factory UploadLimitItem.fromJson(Map<String, dynamic> json) {
    return UploadLimitItem(
      module: json['module']?.toString() ?? '',
      moduleName: json['module_name']?.toString() ?? '',
      maxSizeMb: (json['max_size_mb'] is num)
          ? (json['max_size_mb'] as num).toDouble()
          : double.tryParse(json['max_size_mb']?.toString() ?? '0') ?? 0,
    );
  }
}

class UploadUtils {
  static List<UploadLimitItem>? _cache;
  static DateTime? _cacheTime;
  static const _cacheTtl = Duration(minutes: 10);

  static Future<List<UploadLimitItem>> fetchUploadLimits() async {
    if (_cache != null &&
        _cacheTime != null &&
        DateTime.now().difference(_cacheTime!) < _cacheTtl) {
      return _cache!;
    }
    try {
      final response = await ApiService().dio.get('/api/cos/upload-limits');
      final data = response.data;
      if (data is Map && data['items'] is List) {
        _cache = (data['items'] as List)
            .map((e) => UploadLimitItem.fromJson(Map<String, dynamic>.from(e)))
            .toList();
      } else {
        _cache = [];
      }
      _cacheTime = DateTime.now();
      return _cache!;
    } catch (_) {
      return _cache ?? [];
    }
  }

  static Future<FileSizeCheckResult> checkFileSize(
    File file,
    String module,
  ) async {
    final limits = await fetchUploadLimits();
    final rule = limits.where((l) => l.module == module).firstOrNull;
    if (rule == null) return FileSizeCheckResult(ok: true);

    final fileSize = await file.length();
    final maxBytes = (rule.maxSizeMb * 1024 * 1024).toInt();
    if (fileSize > maxBytes) {
      return FileSizeCheckResult(ok: false, maxMb: rule.maxSizeMb);
    }
    return FileSizeCheckResult(ok: true);
  }
}

class FileSizeCheckResult {
  final bool ok;
  final double? maxMb;

  FileSizeCheckResult({required this.ok, this.maxMb});
}
