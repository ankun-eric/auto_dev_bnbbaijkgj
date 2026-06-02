// [PRD-SAFETY-ROPE-V1 2026-06-03] 数字安全绳 WebView 容器
// App 内嵌 H5 /care-safety-rope 页面，与小程序/H5 三端共用同一套界面与逻辑。
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:webview_flutter/webview_flutter.dart';
import '../../config/api_config.dart';

class SafetyRopeWebView extends StatefulWidget {
  const SafetyRopeWebView({super.key});

  @override
  State<SafetyRopeWebView> createState() => _SafetyRopeWebViewState();
}

class _SafetyRopeWebViewState extends State<SafetyRopeWebView> {
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
        ? '$base/care-safety-rope${sep}token=${Uri.encodeComponent(token)}'
        : '$base/care-safety-rope';
    final controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFFF5F6FA))
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
        title: const Text('数字安全绳'),
        backgroundColor: const Color(0xFF4A9B8E),
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: Stack(
        children: [
          if (_controller != null) WebViewWidget(controller: _controller!),
          if (_loading)
            const Center(
              child: CircularProgressIndicator(
                valueColor: AlwaysStoppedAnimation<Color>(Color(0xFF4A9B8E)),
              ),
            ),
        ],
      ),
    );
  }
}
