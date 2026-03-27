import 'package:shared_preferences/shared_preferences.dart';
import 'api_service.dart';
import '../models/user.dart';

class AuthService {
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  final ApiService _api = ApiService();
  User? _currentUser;

  User? get currentUser => _currentUser;
  bool get isLoggedIn => _currentUser != null;

  Future<bool> checkLoginStatus() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');
    if (token == null || token.isEmpty) return false;

    try {
      final response = await _api.getUserProfile();
      if (response.statusCode == 200) {
        _currentUser = User.fromJson(response.data['data']);
        return true;
      }
      return false;
    } catch (e) {
      return false;
    }
  }

  Future<Map<String, dynamic>> login(String phone, String code) async {
    try {
      final response = await _api.login(phone, code);
      if (response.statusCode == 200) {
        final data = response.data;
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('access_token', data['access_token']);
        await prefs.setString('refresh_token', data['refresh_token']);
        _currentUser = User.fromJson(data['user']);
        return {'success': true, 'user': _currentUser};
      }
      return {'success': false, 'message': response.data['message'] ?? '登录失败'};
    } catch (e) {
      return {'success': false, 'message': '网络错误，请稍后重试'};
    }
  }

  Future<bool> sendSmsCode(String phone) async {
    try {
      final response = await _api.sendSmsCode(phone);
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  Future<Map<String, dynamic>> wechatLogin(String code) async {
    try {
      final response = await _api.wechatLogin(code);
      if (response.statusCode == 200) {
        final data = response.data;
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('access_token', data['access_token']);
        await prefs.setString('refresh_token', data['refresh_token']);
        _currentUser = User.fromJson(data['user']);
        return {'success': true, 'user': _currentUser};
      }
      return {'success': false, 'message': '微信登录失败'};
    } catch (e) {
      return {'success': false, 'message': '网络错误，请稍后重试'};
    }
  }

  Future<Map<String, dynamic>> appleLogin(String identityToken) async {
    try {
      final response = await _api.appleLogin(identityToken);
      if (response.statusCode == 200) {
        final data = response.data;
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('access_token', data['access_token']);
        await prefs.setString('refresh_token', data['refresh_token']);
        _currentUser = User.fromJson(data['user']);
        return {'success': true, 'user': _currentUser};
      }
      return {'success': false, 'message': 'Apple登录失败'};
    } catch (e) {
      return {'success': false, 'message': '网络错误，请稍后重试'};
    }
  }

  Future<void> logout() async {
    try {
      await _api.logout();
    } catch (_) {}
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
    await prefs.remove('refresh_token');
    _currentUser = null;
  }

  Future<User?> refreshUserProfile() async {
    try {
      final response = await _api.getUserProfile();
      if (response.statusCode == 200) {
        _currentUser = User.fromJson(response.data['data']);
        return _currentUser;
      }
    } catch (_) {}
    return null;
  }
}
