// [Bug 修复 v1.0 §3.1.4 2026-05-26] 会员中心 WebView
// 在 Flutter App AI 主页右上角「更多」菜单中作为入口；点击后内置 WebView
// 加载 H5 版会员中心 URL（带 token 透传，由 H5 拦截器消费）。
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:webview_flutter/webview_flutter.dart';
import '../../config/api_config.dart';

class MemberCenterWebView extends StatefulWidget {
  const MemberCenterWebView({super.key});

  @override
  State<MemberCenterWebView> createState() => _MemberCenterWebViewState();
}

class _MemberCenterWebViewState extends State<MemberCenterWebView> {
  WebViewController? _controller;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token') ?? '';
    final base = ApiConfig.baseUrl;
    final sep = base.contains('?') ? '&' : '?';
    final url = token.isNotEmpty
        ? '$base/member-center${sep}token=${Uri.encodeComponent(token)}'
        : '$base/member-center';
    final controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFFF5F4FB))
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageFinished: (_) {
            if (!mounted) return;
            setState(() => _loading = false);
          },
        ),
      )
      ..loadRequest(Uri.parse(url));
    if (!mounted) return;
    setState(() => _controller = controller);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('会员中心'),
        backgroundColor: const Color(0xFF5B7CFA),
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: Stack(
        children: [
          if (_controller != null) WebViewWidget(controller: _controller!),
          if (_loading)
            const Center(
              child: CircularProgressIndicator(
                valueColor: AlwaysStoppedAnimation<Color>(Color(0xFF5B7CFA)),
              ),
            ),
        ],
      ),
    );
  }
}
