import 'package:flutter/material.dart';
import '../models/user.dart';
import '../services/auth_service.dart';

class AuthProvider extends ChangeNotifier {
  final AuthService _authService = AuthService();

  User? _user;
  bool _isLoggedIn = false;
  bool _isLoading = false;

  User? get user => _user;
  bool get isLoggedIn => _isLoggedIn;
  bool get isLoading => _isLoading;

  Future<bool> checkLoginStatus() async {
    _isLoading = true;
    notifyListeners();

    final loggedIn = await _authService.checkLoginStatus();
    _isLoggedIn = loggedIn;
    if (loggedIn) {
      _user = _authService.currentUser;
    }

    _isLoading = false;
    notifyListeners();
    return loggedIn;
  }

  Future<Map<String, dynamic>> login(String phone, String code, {String? referrerNo}) async {
    _isLoading = true;
    notifyListeners();

    final result = await _authService.login(phone, code, referrerNo: referrerNo);
    if (result['success'] == true) {
      _user = result['user'];
      _isLoggedIn = true;
    }

    _isLoading = false;
    notifyListeners();
    return result;
  }

  Future<Map<String, dynamic>> sendSmsCode(String phone) async {
    return await _authService.sendSmsCode(phone);
  }

  Future<Map<String, dynamic>> wechatLogin(String code) async {
    _isLoading = true;
    notifyListeners();

    final result = await _authService.wechatLogin(code);
    if (result['success'] == true) {
      _user = result['user'];
      _isLoggedIn = true;
    }

    _isLoading = false;
    notifyListeners();
    return result;
  }

  Future<Map<String, dynamic>> appleLogin(String identityToken) async {
    _isLoading = true;
    notifyListeners();

    final result = await _authService.appleLogin(identityToken);
    if (result['success'] == true) {
      _user = result['user'];
      _isLoggedIn = true;
    }

    _isLoading = false;
    notifyListeners();
    return result;
  }

  Future<void> logout() async {
    await _authService.logout();
    _user = null;
    _isLoggedIn = false;
    notifyListeners();
  }

  Future<void> refreshProfile() async {
    final user = await _authService.refreshUserProfile();
    if (user != null) {
      _user = user;
      notifyListeners();
    }
  }

  void updateUser(User user) {
    _user = user;
    notifyListeners();
  }
}
