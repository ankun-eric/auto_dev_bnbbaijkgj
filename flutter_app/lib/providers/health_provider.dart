import 'package:flutter/material.dart';
import '../models/health_profile.dart';
import '../models/checkup_report.dart';
import '../services/api_service.dart';
import '../utils/image_compress_util.dart';

class HealthProvider extends ChangeNotifier {
  final ApiService _api = ApiService();

  HealthProfile? _healthProfile;
  bool _isLoading = false;
  List<Map<String, dynamic>> _checkupReports = [];
  Map<String, dynamic>? _latestAnalysis;

  List<CheckupReport> _reportList = [];
  List<ReportAlert> _alerts = [];
  int _unreadAlertCount = 0;
  bool _isUploading = false;

  HealthProfile? get healthProfile => _healthProfile;
  bool get isLoading => _isLoading;
  List<Map<String, dynamic>> get checkupReports => _checkupReports;
  Map<String, dynamic>? get latestAnalysis => _latestAnalysis;

  List<CheckupReport> get reportList => _reportList;
  List<ReportAlert> get alerts => _alerts;
  int get unreadAlertCount => _unreadAlertCount;
  bool get isUploading => _isUploading;

  Future<void> loadHealthProfile() async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await _api.getHealthProfile();
      if (response.statusCode == 200) {
        _healthProfile = HealthProfile.fromJson(response.data['data']);
      }
    } catch (_) {}

    _isLoading = false;
    notifyListeners();
  }

  Future<bool> updateHealthProfile(Map<String, dynamic> data) async {
    try {
      final response = await _api.updateHealthProfile(data);
      if (response.statusCode == 200) {
        _healthProfile = HealthProfile.fromJson(response.data['data']);
        notifyListeners();
        return true;
      }
    } catch (_) {}
    return false;
  }

  Future<void> loadCheckupReports() async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await _api.getCheckupReports();
      if (response.statusCode == 200) {
        _checkupReports = List<Map<String, dynamic>>.from(response.data['data'] ?? []);
      }
    } catch (_) {}

    _isLoading = false;
    notifyListeners();
  }

  Future<Map<String, dynamic>?> uploadAndAnalyzeCheckup(String filePath) async {
    _isLoading = true;
    notifyListeners();

    try {
      final uploadResponse = await _api.uploadCheckupReport(filePath);
      if (uploadResponse.statusCode == 200) {
        final reportId = uploadResponse.data['data']['id'].toString();
        final analyzeResponse = await _api.analyzeCheckup(reportId);
        if (analyzeResponse.statusCode == 200) {
          _latestAnalysis = analyzeResponse.data['data'];
          await loadCheckupReports();
          return _latestAnalysis;
        }
      }
    } catch (_) {}

    _isLoading = false;
    notifyListeners();
    return null;
  }

  // --- New report methods ---

  Future<void> loadReportList({int page = 1, int pageSize = 20}) async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await _api.getReportList(page: page, pageSize: pageSize);
      if (response.statusCode == 200) {
        final body = response.data;
        final list = body is List
            ? body as List
            : (body?['items'] as List?) ?? [];
        _reportList = list.map((e) => CheckupReport.fromJson(e)).toList();
      }
    } catch (_) {}

    _isLoading = false;
    notifyListeners();
  }

  Future<CheckupReport?> uploadAndAnalyzeReport(String filePath, {String fileType = 'image'}) async {
    _isUploading = true;
    notifyListeners();

    try {
      final uploadResponse = await _api.uploadReport(filePath);
      if (uploadResponse.statusCode == 200) {
        final reportId = uploadResponse.data['id'];
        if (reportId == null) {
          _isUploading = false;
          notifyListeners();
          return null;
        }
        final analyzeResponse = await _api.analyzeReport(reportId is int ? reportId : int.parse(reportId.toString()));
        if (analyzeResponse.statusCode == 200) {
          final report = CheckupReport.fromJson(analyzeResponse.data);
          await loadReportList();
          _isUploading = false;
          notifyListeners();
          return report;
        }
      }
    } catch (_) {}

    _isUploading = false;
    notifyListeners();
    return null;
  }

  Future<CheckupReport?> uploadAndAnalyzeMultipleReports(
    List<String> filePaths, {
    Function(int current, int total)? onProgress,
    int? familyMemberId,
  }) async {
    _isUploading = true;
    notifyListeners();

    try {
      // [2026-04-25 PRD F1] 上传前自动压缩：长边≤1600px、目标≤600KB；压缩失败自动回退原图
      onProgress?.call(0, filePaths.length);
      List<String> uploadPaths;
      try {
        uploadPaths = await CheckupImageCompressor.compressAll(filePaths);
      } catch (_) {
        uploadPaths = filePaths;
      }

      onProgress?.call(1, uploadPaths.length);
      final response = await _api.ocrBatchRecognize(
        uploadPaths,
        sceneName: '体检报告识别',
        familyMemberId: familyMemberId,
      );
      if (response.statusCode == 200) {
        final data = response.data is Map ? response.data : {};
        final reportId = data['report_id'] ?? data['merged_record_id'];
        if (reportId != null) {
          final recordId = reportId is int ? reportId : int.parse(reportId.toString());
          await loadReportList();
          _isUploading = false;
          notifyListeners();
          return CheckupReport(
            id: recordId,
            status: 'completed',
            createdAt: DateTime.now().toIso8601String(),
            fileType: 'image',
          );
        }
      }
    } catch (_) {}

    _isUploading = false;
    notifyListeners();
    return null;
  }

  Future<Map<String, dynamic>?> recognizeMultipleDrugs(
    List<String> filePaths, {
    Function(int current, int total)? onProgress,
  }) async {
    onProgress?.call(1, filePaths.length);
    try {
      final response = await _api.ocrBatchRecognize(filePaths, sceneName: '拍照识药');
      if (response.statusCode == 200) {
        final data = response.data is Map ? response.data : {};
        final sessionId = data['session_id']?.toString() ?? '';
        if (sessionId.isNotEmpty) {
          final aiResult = data['merged_ai_result'];
          final drugName = (aiResult is Map
                  ? (aiResult['drug_name'] ?? aiResult['drugName'] ?? aiResult['药品名称'])
                  : null)
              ?.toString() ??
              '药品识别';
          return {
            'session_id': sessionId,
            'drug_name': drugName,
            'merged_ai_result': aiResult,
            'single_select_notice': data['single_select_notice'] == true,
            'notice_message': data['notice_message']?.toString() ?? '',
          };
        }
      }
    } catch (_) {}
    return null;
  }

  Future<CheckupReport?> getReportDetail(int id) async {
    try {
      final response = await _api.getReportDetail(id);
      if (response.statusCode == 200) {
        return CheckupReport.fromJson(response.data);
      }
    } catch (_) {}
    return null;
  }

  Future<void> loadAlerts() async {
    try {
      final response = await _api.getReportAlerts();
      if (response.statusCode == 200) {
        final body = response.data;
        final list = body is List
            ? body as List
            : (body?['items'] as List?) ?? [];
        _alerts = list.map((e) => ReportAlert.fromJson(e)).toList();
        _unreadAlertCount = _alerts.where((a) => !a.isRead).length;
        notifyListeners();
      }
    } catch (_) {}
  }

  Future<void> markAlertRead(int id) async {
    try {
      final response = await _api.markAlertRead(id);
      if (response.statusCode == 200) {
        final idx = _alerts.indexWhere((a) => a.id == id);
        if (idx >= 0) {
          _alerts[idx] = ReportAlert(
            id: _alerts[idx].id,
            indicatorName: _alerts[idx].indicatorName,
            alertType: _alerts[idx].alertType,
            alertMessage: _alerts[idx].alertMessage,
            isRead: true,
            createdAt: _alerts[idx].createdAt,
          );
          _unreadAlertCount = _alerts.where((a) => !a.isRead).length;
          notifyListeners();
        }
      }
    } catch (_) {}
  }

  Future<Map<String, dynamic>?> checkSymptom(Map<String, dynamic> data) async {
    try {
      final response = await _api.analyzeSymptom(data);
      if (response.statusCode == 200) {
        return response.data['data'];
      }
    } catch (_) {}
    return null;
  }

  Future<Map<String, dynamic>?> tcmDiagnose(String imagePath, String type) async {
    try {
      final response = await _api.tcmDiagnose(imagePath, type);
      if (response.statusCode == 200) {
        return response.data['data'];
      }
    } catch (_) {}
    return null;
  }

  Future<List<Map<String, dynamic>>> searchDrug(String keyword) async {
    try {
      final response = await _api.searchDrug(keyword);
      if (response.statusCode == 200) {
        return List<Map<String, dynamic>>.from(response.data['data'] ?? []);
      }
    } catch (_) {}
    return [];
  }
}
