import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);
    final user = authProvider.user;

    return Scaffold(
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            expandedHeight: 200,
            pinned: true,
            automaticallyImplyLeading: false,
            backgroundColor: const Color(0xFF52C41A),
            flexibleSpace: FlexibleSpaceBar(
              background: Container(
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [Color(0xFF52C41A), Color(0xFF13C2C2)],
                  ),
                ),
                child: SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Row(
                      children: [
                        Container(
                          width: 72,
                          height: 72,
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.2),
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(color: Colors.white30, width: 2),
                          ),
                          child: const Icon(Icons.person, color: Colors.white, size: 40),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                user?.nickname ?? '用户${user?.phone.substring(7) ?? '****'}',
                                style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 6),
                              Row(
                                children: [
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                                    decoration: BoxDecoration(
                                      color: Colors.white.withOpacity(0.2),
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Text(
                                      '${user?.memberLevel ?? '普通'}会员',
                                      style: const TextStyle(color: Colors.white, fontSize: 12),
                                    ),
                                  ),
                                  if (user?.userNo != null && user!.userNo!.isNotEmpty) ...[
                                    const SizedBox(width: 8),
                                    GestureDetector(
                                      onTap: () {
                                        Clipboard.setData(ClipboardData(text: user.userNo!));
                                        ScaffoldMessenger.of(context).showSnackBar(
                                          const SnackBar(content: Text('已复制'), duration: Duration(seconds: 1)),
                                        );
                                      },
                                      child: Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                                        decoration: BoxDecoration(
                                          color: Colors.white.withOpacity(0.2),
                                          borderRadius: BorderRadius.circular(12),
                                        ),
                                        child: Row(
                                          mainAxisSize: MainAxisSize.min,
                                          children: [
                                            Text(
                                              '编号：${user.userNo}',
                                              style: const TextStyle(color: Colors.white, fontSize: 12),
                                            ),
                                            const SizedBox(width: 4),
                                            const Icon(Icons.copy, color: Colors.white70, size: 12),
                                          ],
                                        ),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.notifications_outlined, color: Colors.white),
                          onPressed: () => Navigator.pushNamed(context, '/notifications'),
                        ),
                        IconButton(
                          icon: const Icon(Icons.settings_outlined, color: Colors.white),
                          onPressed: () => Navigator.pushNamed(context, '/settings'),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
          SliverToBoxAdapter(
            child: Column(
              children: [
                Container(
                  margin: const EdgeInsets.fromLTRB(16, 0, 16, 0),
                  transform: Matrix4.translationValues(0, -20, 0),
                  padding: const EdgeInsets.symmetric(vertical: 20),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.06),
                        blurRadius: 12,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      _buildStatItem('${user?.points ?? 0}', '积分', () => Navigator.pushNamed(context, '/points')),
                      Container(width: 1, height: 30, color: Colors.grey[200]),
                      _buildStatItem('0', '优惠券', () {}),
                      Container(width: 1, height: 30, color: Colors.grey[200]),
                      _buildStatItem('0', '收藏', () {}),
                    ],
                  ),
                ),
                _buildMenuSection('健康管理', [
                  _MenuItem(Icons.folder_outlined, '健康档案', () => Navigator.pushNamed(context, '/health-profile')),
                  _MenuItem(Icons.family_restroom, '家庭成员', () => Navigator.pushNamed(context, '/family')),
                  _MenuItem(Icons.link, '家庭关联', () => Navigator.pushNamed(context, '/family-bindlist')),
                  _MenuItem(Icons.calendar_today, '健康计划', () => Navigator.pushNamed(context, '/health-plan')),
                  _MenuItem(Icons.assignment, '体检报告', () => Navigator.pushNamed(context, '/checkup')),
                ]),
                _buildMenuSection('订单服务', [
                  _MenuItem(Icons.receipt_long, '我的订单', () => Navigator.pushNamed(context, '/orders')),
                  _MenuItem(Icons.star_outline, '我的收藏', () {}),
                  _MenuItem(Icons.history, '浏览历史', () {}),
                ]),
                _buildMenuSection('其他', [
                  _MenuItem(Icons.card_giftcard, '邀请好友', () => Navigator.pushNamed(context, '/invite')),
                  _MenuItem(Icons.headset_mic, '联系客服', () => Navigator.pushNamed(context, '/customer-service')),
                  _MenuItem(Icons.info_outline, '关于我们', () {}),
                  _MenuItem(Icons.share_outlined, '分享给朋友', () {}),
                  _MenuItem(Icons.settings, '设置', () => Navigator.pushNamed(context, '/settings')),
                ]),
                const SizedBox(height: 30),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatItem(String value, String label, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        children: [
          Text(value, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
          const SizedBox(height: 4),
          Text(label, style: TextStyle(fontSize: 13, color: Colors.grey[500])),
        ],
      ),
    );
  }

  Widget _buildMenuSection(String title, List<_MenuItem> items) {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 6),
            child: Text(title, style: TextStyle(fontSize: 13, color: Colors.grey[500], fontWeight: FontWeight.w500)),
          ),
          ...items.map((item) => ListTile(
                leading: Icon(item.icon, color: const Color(0xFF52C41A), size: 22),
                title: Text(item.label, style: const TextStyle(fontSize: 15)),
                trailing: Icon(Icons.chevron_right, color: Colors.grey[400], size: 20),
                onTap: item.onTap,
                dense: true,
              )),
        ],
      ),
    );
  }
}

class _MenuItem {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  _MenuItem(this.icon, this.label, this.onTap);
}
