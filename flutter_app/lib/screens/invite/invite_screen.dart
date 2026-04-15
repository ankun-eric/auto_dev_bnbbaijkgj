import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:share_plus/share_plus.dart';

import '../../providers/auth_provider.dart';
import '../../services/api_service.dart';

class InviteScreen extends StatefulWidget {
  const InviteScreen({super.key});

  @override
  State<InviteScreen> createState() => _InviteScreenState();
}

class _InviteScreenState extends State<InviteScreen> {
  final ApiService _apiService = ApiService();
  bool _loading = true;
  String? _shareLink;
  String? _userNo;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadShareLink();
  }

  Future<void> _loadShareLink() async {
    try {
      final response = await _apiService.getShareLink();
      if (response.statusCode == 200 && response.data is Map) {
        final data = Map<String, dynamic>.from(response.data as Map);
        setState(() {
          _shareLink = data['share_link']?.toString();
          _userNo = data['user_no']?.toString();
          _loading = false;
        });
      } else {
        setState(() {
          _error = '获取分享链接失败';
          _loading = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = '网络错误，请稍后重试';
        _loading = false;
      });
    }
  }

  void _copyLink() {
    if (_shareLink == null) return;
    Clipboard.setData(ClipboardData(text: _shareLink!));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('已复制'), duration: Duration(seconds: 1)),
    );
  }

  void _shareToFriend() {
    if (_shareLink == null) return;
    Share.share('我在使用宾尼小康AI健康管家，快来一起体验吧！$_shareLink');
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);
    if (!authProvider.isLoggedIn) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        Navigator.of(context).pushReplacementNamed('/login');
      });
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      appBar: AppBar(title: const Text('邀请好友')),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)))
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.error_outline, size: 48, color: Colors.grey[400]),
                      const SizedBox(height: 12),
                      Text(_error!, style: TextStyle(color: Colors.grey[500], fontSize: 15)),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: () {
                          setState(() {
                            _loading = true;
                            _error = null;
                          });
                          _loadShareLink();
                        },
                        child: const Text('重试'),
                      ),
                    ],
                  ),
                )
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    children: [
                      const SizedBox(height: 16),
                      Container(
                        padding: const EdgeInsets.all(24),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(16),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.06),
                              blurRadius: 16,
                              offset: const Offset(0, 4),
                            ),
                          ],
                        ),
                        child: Column(
                          children: [
                            Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: Colors.white,
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(color: const Color(0xFF52C41A).withOpacity(0.3)),
                              ),
                              child: _shareLink != null
                                  ? QrImageView(
                                      data: _shareLink!,
                                      version: QrVersions.auto,
                                      size: 200,
                                      eyeStyle: const QrEyeStyle(
                                        eyeShape: QrEyeShape.roundedOuter,
                                        color: Color(0xFF333333),
                                      ),
                                      dataModuleStyle: const QrDataModuleStyle(
                                        dataModuleShape: QrDataModuleShape.roundedOutsideCorners,
                                        color: Color(0xFF333333),
                                      ),
                                    )
                                  : const SizedBox(width: 200, height: 200),
                            ),
                            const SizedBox(height: 16),
                            Text(
                              '扫描二维码或分享链接邀请好友一起体验',
                              style: TextStyle(fontSize: 14, color: Colors.grey[600]),
                              textAlign: TextAlign.center,
                            ),
                            if (_userNo != null) ...[
                              const SizedBox(height: 8),
                              Text(
                                '我的邀请码：$_userNo',
                                style: const TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w600,
                                  color: Color(0xFF52C41A),
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                      const SizedBox(height: 32),
                      SizedBox(
                        width: double.infinity,
                        height: 50,
                        child: ElevatedButton.icon(
                          onPressed: _copyLink,
                          icon: const Icon(Icons.copy),
                          label: const Text('复制分享链接', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF52C41A),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(25)),
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                      SizedBox(
                        width: double.infinity,
                        height: 50,
                        child: OutlinedButton.icon(
                          onPressed: _shareToFriend,
                          icon: const Icon(Icons.share, color: Color(0xFF52C41A)),
                          label: const Text(
                            '分享给好友',
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF52C41A)),
                          ),
                          style: OutlinedButton.styleFrom(
                            side: const BorderSide(color: Color(0xFF52C41A)),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(25)),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
    );
  }
}
