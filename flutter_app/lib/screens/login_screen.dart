import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:fluttertoast/fluttertoast.dart';
import '../models/user.dart';
import '../providers/auth_provider.dart';
import '../services/auth_service.dart';
import '../services/logo_service.dart';

class LoginScreen extends StatefulWidget {
  final String? referrerNo;
  const LoginScreen({super.key, this.referrerNo});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _phoneController = TextEditingController();
  final _codeController = TextEditingController();
  bool _agreeTerms = false;
  int _countdown = 0;
  Timer? _timer;
  Map<String, dynamic>? _registerSettings;

  bool _parseBool(dynamic v, bool def) {
    if (v == null) return def;
    if (v is bool) return v;
    return {'1', 'true', 'yes', 'on'}.contains(v.toString().trim().toLowerCase());
  }

  bool get _enableSelfReg => _parseBool(_registerSettings?['enable_self_registration'], true);

  bool get _showProfilePromptSetting =>
      _parseBool(_registerSettings?['show_profile_completion_prompt'], true);

  bool get _layoutHorizontal =>
      (_registerSettings?['register_page_layout']?.toString() ?? 'vertical') == 'horizontal';

  String get _loginSubtitle =>
      _enableSelfReg ? '手机号验证码登录，新用户将自动注册' : '请使用已注册手机号验证登录';

  String get _primaryButtonLabel => _enableSelfReg ? '登录 / 注册' : '登录';

  @override
  void initState() {
    super.initState();
    _loadRegisterSettings();
  }

  Future<void> _loadRegisterSettings() async {
    final s = await AuthService().fetchRegisterSettings();
    if (!mounted) return;
    setState(() => _registerSettings = s);
  }

  @override
  void dispose() {
    _phoneController.dispose();
    _codeController.dispose();
    _timer?.cancel();
    super.dispose();
  }

  void _startCountdown() {
    setState(() => _countdown = 60);
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_countdown > 0) {
        setState(() => _countdown--);
      } else {
        timer.cancel();
      }
    });
  }

  Future<void> _sendCode() async {
    final phone = _phoneController.text.trim();
    if (phone.length != 11) {
      Fluttertoast.showToast(msg: '请输入正确的手机号');
      return;
    }

    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    final sent = await authProvider.sendSmsCode(phone);
    if (sent['success'] == true) {
      _startCountdown();
      Fluttertoast.showToast(msg: '验证码已发送');
    } else {
      Fluttertoast.showToast(msg: sent['message']?.toString() ?? '发送失败，请稍后重试');
    }
  }

  Future<void> _showPostLoginHints(Map<String, dynamic> result) async {
    final user = result['user'] as User?;
    if (result['is_new_user'] == true) {
      final card = user?.memberCardNo;
      if (card != null && card.isNotEmpty && mounted) {
        await showDialog<void>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('注册成功'),
            content: SelectableText('您的会员卡号：$card'),
            actions: [
              TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('知道了')),
            ],
          ),
        );
      }
    }
    final needProfile =
        result['needs_profile_completion'] == true && _showProfilePromptSetting;
    if (needProfile && mounted) {
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('完善资料'),
          content: const Text('为给您更精准的健康建议，建议尽快完善个人健康档案。'),
          actions: [
            TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('知道了')),
          ],
        ),
      );
    }
  }

  Future<void> _login() async {
    final phone = _phoneController.text.trim();
    final code = _codeController.text.trim();

    if (phone.length != 11) {
      Fluttertoast.showToast(msg: '请输入正确的手机号');
      return;
    }
    if (code.length != 6) {
      Fluttertoast.showToast(msg: '请输入6位验证码');
      return;
    }
    if (!_agreeTerms) {
      Fluttertoast.showToast(msg: '请先同意用户协议和隐私政策');
      return;
    }

    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    final result = await authProvider.login(phone, code, referrerNo: widget.referrerNo);

    if (!mounted) return;
    if (result['success'] == true) {
      await _showPostLoginHints(result);
      if (!mounted) return;
      Navigator.of(context).pushReplacementNamed('/main');
    } else {
      Fluttertoast.showToast(msg: result['message']?.toString() ?? '登录失败');
    }
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);

    return Scaffold(
      body: SingleChildScrollView(
        child: Container(
          height: MediaQuery.of(context).size.height,
          padding: const EdgeInsets.symmetric(horizontal: 32),
          child: Column(
            children: [
              SizedBox(height: _layoutHorizontal ? 72 : 100),
              if (_layoutHorizontal)
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildLoginLogo(72, 18),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            '宾尼小康',
                            style: TextStyle(
                              fontSize: 22,
                              fontWeight: FontWeight.bold,
                              color: Color(0xFF333333),
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            _loginSubtitle,
                            style: TextStyle(fontSize: 13, color: Colors.grey[600], height: 1.35),
                          ),
                        ],
                      ),
                    ),
                  ],
                )
              else ...[
                _buildLoginLogo(80, 20),
                const SizedBox(height: 16),
                const Text(
                  '宾尼小康',
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
                ),
                const SizedBox(height: 6),
                Text(
                  _loginSubtitle,
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 14, color: Colors.grey[600], height: 1.4),
                ),
                if (widget.referrerNo != null && widget.referrerNo!.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    '🎉 已识别邀请码：${widget.referrerNo}',
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 13, color: Color(0xFF52C41A)),
                  ),
                ],
              ],
              const SizedBox(height: 48),
              Container(
                decoration: BoxDecoration(
                  color: const Color(0xFFF5F7FA),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: TextField(
                  controller: _phoneController,
                  keyboardType: TextInputType.phone,
                  maxLength: 11,
                  decoration: const InputDecoration(
                    hintText: '请输入手机号',
                    prefixIcon: Icon(Icons.phone_android, color: Color(0xFF52C41A)),
                    border: InputBorder.none,
                    counterText: '',
                    contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Container(
                decoration: BoxDecoration(
                  color: const Color(0xFFF5F7FA),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _codeController,
                        keyboardType: TextInputType.number,
                        maxLength: 6,
                        decoration: const InputDecoration(
                          hintText: '请输入验证码',
                          prefixIcon: Icon(Icons.lock_outline, color: Color(0xFF52C41A)),
                          border: InputBorder.none,
                          counterText: '',
                          contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                        ),
                      ),
                    ),
                    GestureDetector(
                      onTap: _countdown > 0 ? null : _sendCode,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        child: Text(
                          _countdown > 0 ? '${_countdown}s' : '获取验证码',
                          style: TextStyle(
                            color: _countdown > 0 ? Colors.grey : const Color(0xFF52C41A),
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 32),
              SizedBox(
                width: double.infinity,
                height: 50,
                child: ElevatedButton(
                  onPressed: authProvider.isLoading ? null : _login,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF52C41A),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(25)),
                  ),
                  child: authProvider.isLoading
                      ? const SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                        )
                      : Text(_primaryButtonLabel, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                ),
              ),
              const SizedBox(height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  GestureDetector(
                    onTap: () => setState(() => _agreeTerms = !_agreeTerms),
                    child: Container(
                      width: 18,
                      height: 18,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: _agreeTerms ? const Color(0xFF52C41A) : Colors.grey[400]!,
                        ),
                        color: _agreeTerms ? const Color(0xFF52C41A) : Colors.transparent,
                      ),
                      child: _agreeTerms
                          ? const Icon(Icons.check, size: 12, color: Colors.white)
                          : null,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text('已阅读并同意', style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                  GestureDetector(
                    onTap: () {},
                    child: const Text(
                      '《用户协议》',
                      style: TextStyle(fontSize: 12, color: Color(0xFF52C41A)),
                    ),
                  ),
                  Text('和', style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                  GestureDetector(
                    onTap: () {},
                    child: const Text(
                      '《隐私政策》',
                      style: TextStyle(fontSize: 12, color: Color(0xFF52C41A)),
                    ),
                  ),
                ],
              ),
              const Spacer(),
              Padding(
                padding: const EdgeInsets.only(bottom: 40),
                child: Column(
                  children: [
                    Text('其他登录方式', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                    const SizedBox(height: 20),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        _buildSocialButton(
                          icon: Icons.wechat,
                          color: const Color(0xFF07C160),
                          label: '微信',
                          onTap: () {
                            Fluttertoast.showToast(msg: '微信登录功能开发中');
                          },
                        ),
                        const SizedBox(width: 40),
                        _buildSocialButton(
                          icon: Icons.apple,
                          color: Colors.black,
                          label: 'Apple',
                          onTap: () {
                            Fluttertoast.showToast(msg: 'Apple登录功能开发中');
                          },
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLoginLogo(double size, double radius) {
    final logoUrl = LogoService().logoUrl;
    if (logoUrl != null) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(radius),
        child: Image.network(
          logoUrl,
          width: size,
          height: size,
          fit: BoxFit.contain,
          errorBuilder: (context, error, stackTrace) {
            return _buildDefaultLoginLogo(size, radius);
          },
        ),
      );
    }
    return _buildDefaultLoginLogo(size, radius);
  }

  Widget _buildDefaultLoginLogo(double size, double radius) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF52C41A), Color(0xFF13C2C2)],
        ),
        borderRadius: BorderRadius.circular(radius),
      ),
      child: Icon(Icons.favorite, size: size / 2, color: Colors.white),
    );
  }

  Widget _buildSocialButton({
    required IconData icon,
    required Color color,
    required String label,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        children: [
          Container(
            width: 50,
            height: 50,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: color.withOpacity(0.1),
            ),
            child: Icon(icon, color: color, size: 28),
          ),
          const SizedBox(height: 6),
          Text(label, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
        ],
      ),
    );
  }
}
