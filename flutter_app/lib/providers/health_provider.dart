import 'package:flutter/material.dart';
import '../models/health_profile.dart';
import '../services/api_service.dart';

class HealthProvider extends ChangeNotifier {
  final ApiService _api = ApiService();

  HealthProfile? _healthProfile;
  bool _isLoading = false;
  List<Map<String, dynamic>> _checkupReports = [];
  Map<String, dynamic>? _latestAnalysis;

  HealthProfile? get healthProfile => _healthProfile;
  bool get isLoading => _isLoading;
  List<Map<String, dynamic>> get checkupReports => _checkupReports;
  Map<String, dynamic>? get latestAnalysis => _latestAnalysis;

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
