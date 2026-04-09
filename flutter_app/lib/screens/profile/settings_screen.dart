import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/custom_app_bar.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _pushNotification = true;
  bool _healthReminder = true;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(title: '设置'),
      body: SingleChildScrollView(
        child: Column(
          children: [
            const SizedBox(height: 12),
            Container(
              color: Colors.white,
              child: Column(
                children: [
                  _buildSettingItem('个人资料', Icons.person_outline, onTap: () {}),
                  _buildDivider(),
                  _buildSettingItem('账号安全', Icons.shield_outlined, onTap: () {}),
                  _buildDivider(),
                  _buildSettingItem('隐私设置', Icons.lock_outline, onTap: () {}),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Container(
              color: Colors.white,
              child: Column(
                children: [
                  SwitchListTile(
                    title: const Text('消息推送', style: TextStyle(fontSize: 15)),
                    secondary: const Icon(Icons.notifications_outlined, color: Color(0xFF52C41A)),
                    value: _pushNotification,
                    activeColor: const Color(0xFF52C41A),
                    onChanged: (v) => setState(() => _pushNotification = v),
                  ),
                  _buildDivider(),
                  SwitchListTile(
                    title: const Text('健康提醒', style: TextStyle(fontSize: 15)),
                    secondary: const Icon(Icons.alarm, color: Color(0xFF52C41A)),
                    value: _healthReminder,
                    activeColor: const Color(0xFF52C41A),
                    onChanged: (v) => setState(() => _healthReminder = v),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Container(
              color: Colors.white,
              child: Column(
                children: [
                  _buildSettingItem('清除缓存', Icons.cleaning_services_outlined, trailing: '23.5MB', onTap: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('缓存已清除'), backgroundColor: Color(0xFF52C41A)),
                    );
                  }),
                  _buildDivider(),
                  _buildSettingItem('意见反馈', Icons.feedback_outlined, onTap: () {}),
                  _buildDivider(),
                  _buildSettingItem('关于我们', Icons.info_outline, onTap: () {}),
                  _buildDivider(),
                  _buildSettingItem('用户协议', Icons.description_outlined, onTap: () {}),
                  _buildDivider(),
                  _buildSettingItem('隐私政策', Icons.policy_outlined, onTap: () {}),
                ],
              ),
            ),
            const SizedBox(height: 24),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 32),
              child: SizedBox(
                width: double.infinity,
                height: 48,
                child: OutlinedButton(
                  onPressed: () => _showLogoutDialog(context),
                  style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: Colors.red),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                  ),
                  child: const Text('退出登录', style: TextStyle(color: Colors.red, fontSize: 16)),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text('版本 1.0.0', style: TextStyle(fontSize: 13, color: Colors.grey[400])),
            const SizedBox(height: 30),
          ],
        ),
      ),
    );
  }

  Widget _buildSettingItem(String title, IconData icon, {String? trailing, VoidCallback? onTap}) {
    return ListTile(
      leading: Icon(icon, color: const Color(0xFF52C41A), size: 22),
      title: Text(title, style: const TextStyle(fontSize: 15)),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (trailing != null) Text(trailing, style: TextStyle(fontSize: 14, color: Colors.grey[400])),
          Icon(Icons.chevron_right, color: Colors.grey[400], size: 20),
        ],
      ),
      onTap: onTap,
    );
  }

  Widget _buildDivider() {
    return Divider(height: 1, indent: 56, color: Colors.grey[100]);
  }

  void _showLogoutDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('退出登录'),
        content: const Text('确定要退出登录吗？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('取消', style: TextStyle(color: Colors.grey[600])),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(context);
              await Provider.of<AuthProvider>(context, listen: false).logout();
              if (context.mounted) {
                Navigator.of(context).pushNamedAndRemoveUntil('/login', (route) => false);
              }
            },
            child: const Text('确定', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }
}
