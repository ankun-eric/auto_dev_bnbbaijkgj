import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_service.dart';

class MemberCardScreen extends StatefulWidget {
  const MemberCardScreen({super.key});

  @override
  State<MemberCardScreen> createState() => _MemberCardScreenState();
}

class _MemberCardScreenState extends State<MemberCardScreen> {
  final ApiService _api = ApiService();
  String? _qrToken;
  String? _expiresAt;
  bool _loading = true;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _loadQRCode();
    _refreshTimer = Timer.periodic(const Duration(minutes: 4), (_) => _loadQRCode());
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadQRCode() async {
    try {
      final res = await _api.getMemberQRCode();
      if (res.data is Map) {
        setState(() {
          _qrToken = res.data['token'];
          _expiresAt = res.data['expires_at']?.toString();
          _loading = false;
        });
      }
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);
    final user = authProvider.user;

    return Scaffold(
      appBar: AppBar(
        title: const Text('会员卡'),
        backgroundColor: const Color(0xFF52C41A),
      ),
      body: SingleChildScrollView(
        child: Column(
          children: [
            Container(
              width: double.infinity,
              margin: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFF52C41A), Color(0xFF13C2C2)],
                ),
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(color: const Color(0xFF52C41A).withOpacity(0.3), blurRadius: 12, offset: const Offset(0, 6)),
                ],
              ),
              child: Column(
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
                    child: Row(
                      children: [
                        Container(
                          width: 56,
                          height: 56,
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.2),
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: const Icon(Icons.person, color: Colors.white, size: 32),
                        ),
                        const SizedBox(width: 14),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              user?.nickname ?? '用户${user?.phone.substring(7) ?? '****'}',
                              style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                            ),
                            const SizedBox(height: 4),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: Colors.white.withOpacity(0.2),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Text(
                                '${user?.memberLevel ?? '普通'}会员',
                                style: const TextStyle(color: Colors.white, fontSize: 12),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  if (user?.memberCardNo != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      child: Row(
                        children: [
                          Text('卡号: ${user!.memberCardNo}',
                              style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 13)),
                        ],
                      ),
                    ),
                  Container(
                    width: double.infinity,
                    margin: const EdgeInsets.all(16),
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Column(
                      children: [
                        const Text('会员码', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w500)),
                        const SizedBox(height: 16),
                        _loading
                            ? const SizedBox(
                                width: 40,
                                height: 40,
                                child: CircularProgressIndicator(color: Color(0xFF52C41A), strokeWidth: 2),
                              )
                            : _qrToken != null
                                ? Column(
                                    children: [
                                      Container(
                                        width: 200,
                                        height: 200,
                                        decoration: BoxDecoration(
                                          border: Border.all(color: Colors.grey[200]!),
                                          borderRadius: BorderRadius.circular(8),
                                        ),
                                        child: Center(
                                          child: Column(
                                            mainAxisAlignment: MainAxisAlignment.center,
                                            children: [
                                              const Icon(Icons.qr_code_2, size: 120, color: Color(0xFF333333)),
                                              const SizedBox(height: 8),
                                              Text(
                                                _qrToken!.substring(0, _qrToken!.length > 16 ? 16 : _qrToken!.length),
                                                style: TextStyle(fontSize: 10, color: Colors.grey[400]),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ),
                                      const SizedBox(height: 12),
                                      Text('向商家出示此码', style: TextStyle(color: Colors.grey[500], fontSize: 13)),
                                      const SizedBox(height: 4),
                                      GestureDetector(
                                        onTap: _loadQRCode,
                                        child: Text('点击刷新', style: TextStyle(color: const Color(0xFF52C41A).withOpacity(0.8), fontSize: 13)),
                                      ),
                                    ],
                                  )
                                : Column(
                                    children: [
                                      const Icon(Icons.error_outline, size: 40, color: Colors.grey),
                                      const SizedBox(height: 8),
                                      const Text('获取二维码失败'),
                                      TextButton(onPressed: _loadQRCode, child: const Text('重试')),
                                    ],
                                  ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),
            Container(
              margin: const EdgeInsets.symmetric(horizontal: 16),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                children: [
                  _buildInfoRow('积分余额', '${user?.points ?? 0}'),
                  const Divider(height: 20),
                  _buildInfoRow('会员等级', '${user?.memberLevel ?? '普通'}'),
                  const Divider(height: 20),
                  _buildInfoRow('注册时间', _formatTime(user?.createdAt)),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Container(
              margin: const EdgeInsets.symmetric(horizontal: 16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                children: [
                  ListTile(
                    leading: const Icon(Icons.local_offer, color: Color(0xFF52C41A)),
                    title: const Text('我的优惠券'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.pushNamed(context, '/my-coupons'),
                  ),
                  ListTile(
                    leading: const Icon(Icons.star, color: Color(0xFF52C41A)),
                    title: const Text('积分中心'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.pushNamed(context, '/points'),
                  ),
                  ListTile(
                    leading: const Icon(Icons.receipt_long, color: Color(0xFF52C41A)),
                    title: const Text('我的订单'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.pushNamed(context, '/unified-orders'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 30),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: TextStyle(color: Colors.grey[600], fontSize: 14)),
        Text(value, style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 14)),
      ],
    );
  }

  String _formatTime(String? time) {
    if (time == null) return '';
    return time.split('T').first;
  }
}
