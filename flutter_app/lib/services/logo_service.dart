import 'package:flutter/foundation.dart';
import 'api_service.dart';

class LogoService extends ChangeNotifier {
  static final LogoService _instance = LogoService._internal();
  factory LogoService() => _instance;
  LogoService._internal();

  String? _logoUrl;
  String? get logoUrl => _logoUrl;
  bool _loaded = false;

  Future<void> fetchLogo() async {
    if (_loaded) return;
    try {
      final response = await ApiService().dio.get('/api/settings/logo');
      if (response.data != null && response.data['code'] == 0) {
        final data = response.data['data'];
        if (data != null && data['logo_url'] != null && data['logo_url'].toString().isNotEmpty) {
          _logoUrl = data['logo_url'];
          if (_logoUrl != null && !_logoUrl!.startsWith('http')) {
            _logoUrl = ApiService().dio.options.baseUrl + _logoUrl!;
          }
        }
      }
      _loaded = true;
      notifyListeners();
    } catch (e) {
      _loaded = true;
    }
  }

  void reset() {
    _loaded = false;
    _logoUrl = null;
  }
}
