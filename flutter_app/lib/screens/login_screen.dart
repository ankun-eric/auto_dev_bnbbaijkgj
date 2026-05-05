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

  /// 协议二次确认弹窗：未勾选协议时弹出，[再看看] / [同意并登录]
  Future<bool> _showAgreementConfirmDialog() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text(
          '为保障您的权益，请阅读并同意以下协议',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
        content: const Text(
          '您需要阅读并同意《用户服务协议》和《隐私政策》后才能继续登录。',
          style: TextStyle(fontSize: 14, height: 1.6, color: Color(0xFF555555)),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('再看看', style: TextStyle(color: Color(0xFF999999))),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text(
              '同意并登录',
              style: TextStyle(color: Color(0xFF2FB56A), fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
    return confirmed == true;
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
      final confirmed = await _showAgreementConfirmDialog();
      if (!confirmed) return;
      if (!mounted) return;
      setState(() => _agreeTerms = true);
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
    final size = MediaQuery.of(context).size;
    final topBrandHeight = size.height * 0.42;

    return Scaffold(
      backgroundColor: const Color(0xFFF7F8FA),
      body: SingleChildScrollView(
        physics: const ClampingScrollPhysics(),
        child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: size.height),
          child: Column(
            children: [
              // 顶部 42% 屏高的绿色渐变沉浸式品牌区
              Container(
                width: double.infinity,
                height: topBrandHeight,
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [Color(0xFF2FB56A), Color(0xFF5CD692)],
                  ),
                ),
                padding: const EdgeInsets.fromLTRB(32, 0, 32, 56),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    // 92×92 白色圆形托盘内嵌项目 LOGO
                    Container(
                      width: 92,
                      height: 92,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: Colors.white,
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withOpacity(0.12),
                            blurRadius: 24,
                            offset: const Offset(0, 8),
                          ),
                        ],
                      ),
                      child: ClipOval(child: _buildLoginLogo(76)),
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      '宾尼小康',
                      style: TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                        letterSpacing: 1,
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'AI 健康管家 · 您的私人健康助手',
                      style: TextStyle(
                        fontSize: 14,
                        color: Color(0xF2FFFFFF),
                        letterSpacing: 0.5,
                      ),
                    ),
                  ],
                ),
              ),

              // 表单卡片：上浮 -28，圆角 24，覆盖在渐变下沿
              Transform.translate(
                offset: const Offset(0, -28),
                child: Container(
                  margin: const EdgeInsets.symmetric(horizontal: 20),
                  padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(24),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.06),
                        blurRadius: 24,
                        offset: const Offset(0, -4),
                      ),
                      BoxShadow(
                        color: Colors.black.withOpacity(0.04),
                        blurRadius: 24,
                        offset: const Offset(0, 8),
                      ),
                    ],
                  ),
                  child: Column(
                    children: [
                      // 手机号输入
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
                            prefixIcon: Padding(
                              padding: EdgeInsets.symmetric(horizontal: 12),
                              child: Text(
                                '+86',
                                style: TextStyle(fontSize: 15, color: Color(0xFF555555)),
                              ),
                            ),
                            prefixIconConstraints: BoxConstraints(minWidth: 60),
                            border: InputBorder.none,
                            counterText: '',
                            contentPadding: EdgeInsets.symmetric(horizontal: 0, vertical: 16),
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                      // 验证码 + 获取验证码按钮（不换行）
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
                                  prefixIcon: Icon(Icons.lock_outline, color: Color(0xFF2FB56A)),
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
                                  _countdown > 0 ? '${_countdown} s' : '获取验证码',
                                  maxLines: 1,
                                  softWrap: false,
                                  overflow: TextOverflow.visible,
                                  style: TextStyle(
                                    color: _countdown > 0 ? Colors.grey : const Color(0xFF2FB56A),
                                    fontSize: 14,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 24),
                      // 登录按钮始终高亮可点
                      SizedBox(
                        width: double.infinity,
                        height: 48,
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(
                              begin: Alignment.topLeft,
                              end: Alignment.bottomRight,
                              colors: [Color(0xFF2FB56A), Color(0xFF5CD692)],
                            ),
                            borderRadius: BorderRadius.circular(24),
                            boxShadow: [
                              BoxShadow(
                                color: const Color(0xFF2FB56A).withOpacity(0.32),
                                blurRadius: 16,
                                offset: const Offset(0, 6),
                              ),
                            ],
                          ),
                          child: ElevatedButton(
                            onPressed: authProvider.isLoading ? null : _login,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.transparent,
                              shadowColor: Colors.transparent,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(24),
                              ),
                            ),
                            child: authProvider.isLoading
                                ? const SizedBox(
                                    width: 22,
                                    height: 22,
                                    child: CircularProgressIndicator(
                                      color: Colors.white,
                                      strokeWidth: 2,
                                    ),
                                  )
                                : Text(
                                    _primaryButtonLabel,
                                    style: const TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.w600,
                                      color: Colors.white,
                                    ),
                                  ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                      // 协议勾选行
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          GestureDetector(
                            onTap: () => setState(() => _agreeTerms = !_agreeTerms),
                            child: Container(
                              width: 18,
                              height: 18,
                              margin: const EdgeInsets.only(top: 2),
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                border: Border.all(
                                  color: _agreeTerms ? const Color(0xFF2FB56A) : Colors.grey[400]!,
                                ),
                                color: _agreeTerms ? const Color(0xFF2FB56A) : Colors.transparent,
                              ),
                              child: _agreeTerms
                                  ? const Icon(Icons.check, size: 12, color: Colors.white)
                                  : null,
                            ),
                          ),
                          const SizedBox(width: 8),
                          const Expanded(
                            child: Text.rich(
                              TextSpan(
                                style: TextStyle(fontSize: 12, color: Color(0xFF999999), height: 1.5),
                                children: [
                                  TextSpan(text: '我已阅读并同意'),
                                  TextSpan(
                                    text: '《用户服务协议》',
                                    style: TextStyle(color: Color(0xFF2FB56A)),
                                  ),
                                  TextSpan(text: '和'),
                                  TextSpan(
                                    text: '《隐私政策》',
                                    style: TextStyle(color: Color(0xFF2FB56A)),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                      if (widget.referrerNo != null && widget.referrerNo!.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        Text(
                          '🎉 已识别邀请码：${widget.referrerNo}',
                          style: const TextStyle(fontSize: 12, color: Color(0xFF2FB56A)),
                        ),
                      ],
                    ],
                  ),
                ),
              ),

              // 底部留白（删除「登录即表示您将享受 AI 智能健康陪伴服务」一行文案）
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  /// LOGO 显示：URL 取值逻辑不变（LogoService().logoUrl），只改外层容器/尺寸
  Widget _buildLoginLogo(double size) {
    final logoUrl = LogoService().logoUrl;
    if (logoUrl != null && logoUrl.isNotEmpty) {
      return Image.network(
        logoUrl,
        width: size,
        height: size,
        fit: BoxFit.contain,
        errorBuilder: (context, error, stackTrace) {
          return _buildDefaultLoginLogo(size);
        },
      );
    }
    return _buildDefaultLoginLogo(size);
  }

  Widget _buildDefaultLoginLogo(double size) {
    return Container(
      width: size,
      height: size,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [Color(0xFF2FB56A), Color(0xFF5CD692)],
        ),
        shape: BoxShape.circle,
      ),
      child: Icon(Icons.favorite, size: size / 2, color: Colors.white),
    );
  }
}
