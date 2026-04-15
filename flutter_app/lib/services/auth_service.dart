import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api_service.dart';
import '../models/user.dart';

String _detailFromBody(dynamic data) {
  if (data is Map) {
    final d = data['detail'];
    if (d is String && d.isNotEmpty) return d;
    if (d is List && d.isNotEmpty) return d.first.toString();
    final m = data['message'];
    if (m is String && m.isNotEmpty) return m;
  }
  return '请求失败';
}

String _dioErrorMessage(DioException e) {
  final data = e.response?.data;
  if (data != null) return _detailFromBody(data);
  return '网络错误，请稍后重试';
}

Map<String, dynamic> _unwrapUserPayload(dynamic data) {
  if (data is! Map) return {};
  final m = Map<String, dynamic>.from(data);
  final inner = m['data'];
  if (inner is Map) return Map<String, dynamic>.from(inner);
  return m;
}

Future<void> _persistAuthTokens(Map<String, dynamic> data) async {
  final prefs = await SharedPreferences.getInstance();
  final at = data['access_token']?.toString();
  if (at != null && at.isNotEmpty) {
    await prefs.setString('access_token', at);
  }
  final rt = data['refresh_token']?.toString();
  if (rt != null && rt.isNotEmpty) {
    await prefs.setString('refresh_token', rt);
  } else {
    await prefs.remove('refresh_token');
  }
}

User? _userFromTokenBody(Map<String, dynamic> map) {
  final u = map['user'];
  if (u is! Map) return null;
  return User.fromJson(Map<String, dynamic>.from(u));
}

class AuthService {
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  final ApiService _api = ApiService();
  User? _currentUser;

  User? get currentUser => _currentUser;
  bool get isLoggedIn => _currentUser != null;

  Future<Map<String, dynamic>?> fetchRegisterSettings() async {
    try {
      final response = await _api.getRegisterSettings();
      if (response.statusCode == 200 && response.data is Map) {
        return Map<String, dynamic>.from(response.data as Map);
      }
    } catch (_) {}
    return null;
  }

  Future<bool> checkLoginStatus() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');
    if (token == null || token.isEmpty) return false;

    try {
      final response = await _api.getUserProfile();
      if (response.statusCode == 200) {
        final payload = _unwrapUserPayload(response.data);
        if (payload.isEmpty) return false;
        _currentUser = User.fromJson(payload);
        return true;
      }
      return false;
    } catch (e) {
      return false;
    }
  }

  Future<Map<String, dynamic>> login(String phone, String code, {String? referrerNo}) async {
    try {
      final response = await _api.login(phone, code, referrerNo: referrerNo);
      final raw = response.data;
      if (raw is! Map) {
        return {'success': false, 'message': '登录失败'};
      }
      final data = Map<String, dynamic>.from(raw);
      await _persistAuthTokens(data);
      _currentUser = _userFromTokenBody(data);
      if (_currentUser == null) {
        return {'success': false, 'message': '登录数据异常'};
      }
      return {
        'success': true,
        'user': _currentUser,
        'is_new_user': data['is_new_user'] == true,
        'needs_profile_completion': data['needs_profile_completion'] == true,
      };
    } on DioException catch (e) {
      return {'success': false, 'message': _dioErrorMessage(e)};
    } catch (e) {
      return {'success': false, 'message': '网络错误，请稍后重试'};
    }
  }

  Future<Map<String, dynamic>> sendSmsCode(String phone) async {
    try {
      final response = await _api.sendSmsCode(phone);
      if (response.statusCode == 200) {
        return {'success': true};
      }
      return {'success': false, 'message': _detailFromBody(response.data)};
    } on DioException catch (e) {
      return {'success': false, 'message': _dioErrorMessage(e)};
    } catch (e) {
      return {'success': false, 'message': '网络错误，请稍后重试'};
    }
  }

  Future<Map<String, dynamic>> wechatLogin(String code) async {
    try {
      final response = await _api.wechatLogin(code);
      final raw = response.data;
      if (response.statusCode == 200 && raw is Map) {
        final data = Map<String, dynamic>.from(raw);
        await _persistAuthTokens(data);
        _currentUser = _userFromTokenBody(data);
        if (_currentUser == null) {
          return {'success': false, 'message': '微信登录失败'};
        }
        return {
          'success': true,
          'user': _currentUser,
          'is_new_user': data['is_new_user'] == true,
          'needs_profile_completion': data['needs_profile_completion'] == true,
        };
      }
      return {'success': false, 'message': _detailFromBody(raw)};
    } on DioException catch (e) {
      return {'success': false, 'message': _dioErrorMessage(e)};
    } catch (e) {
      return {'success': false, 'message': '网络错误，请稍后重试'};
    }
  }

  Future<Map<String, dynamic>> appleLogin(String identityToken) async {
    try {
      final response = await _api.appleLogin(identityToken);
      final raw = response.data;
      if (response.statusCode == 200 && raw is Map) {
        final data = Map<String, dynamic>.from(raw);
        await _persistAuthTokens(data);
        _currentUser = _userFromTokenBody(data);
        if (_currentUser == null) {
          return {'success': false, 'message': 'Apple登录失败'};
        }
        return {
          'success': true,
          'user': _currentUser,
          'is_new_user': data['is_new_user'] == true,
          'needs_profile_completion': data['needs_profile_completion'] == true,
        };
      }
      return {'success': false, 'message': _detailFromBody(raw)};
    } on DioException catch (e) {
      return {'success': false, 'message': _dioErrorMessage(e)};
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
        final payload = _unwrapUserPayload(response.data);
        if (payload.isEmpty) return null;
        _currentUser = User.fromJson(payload);
        return _currentUser;
      }
    } catch (_) {}
    return null;
  }
}
