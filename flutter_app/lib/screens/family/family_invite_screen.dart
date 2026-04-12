import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:image_gallery_saver/image_gallery_saver.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../config/api_config.dart';
import '../../models/family_management.dart';
import '../../services/api_service.dart';

class FamilyInviteScreen extends StatefulWidget {
  final int memberId;

  const FamilyInviteScreen({super.key, required this.memberId});

  @override
  State<FamilyInviteScreen> createState() => _FamilyInviteScreenState();
}

class _FamilyInviteScreenState extends State<FamilyInviteScreen> {
  final ApiService _apiService = ApiService();
  final GlobalKey _qrCardKey = GlobalKey();
  bool _loading = true;
  FamilyInvitationModel? _invitation;
  String? _error;

  @override
  void initState() {
    super.initState();
    _createInvitation();
  }

  Future<void> _createInvitation() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final response = await _apiService.createFamilyInvitation(widget.memberId);
      if (response.statusCode == 200 && mounted) {
        final data = response.data is Map<String, dynamic>
            ? response.data as Map<String, dynamic>
            : <String, dynamic>{};
        setState(() {
          _invitation = FamilyInvitationModel.fromJson(data);
          _loading = false;
        });
      } else {
        setState(() {
          _error = '生成邀请失败，请重试';
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = '网络错误，请检查网络后重试';
          _loading = false;
        });
      }
    }
  }

  String get _qrContentUrl {
    if (_invitation == null) return '';
    return '${ApiConfig.baseUrl}/family-auth?code=${_invitation!.inviteCode}';
  }

  String get _inviteLink {
    if (_invitation == null) return '';
    return '${ApiConfig.baseUrl}${ApiConfig.familyInvitation}/${_invitation!.inviteCode}';
  }

  void _copyLink() {
    if (_invitation == null) return;
    Clipboard.setData(ClipboardData(text: _inviteLink));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('邀请链接已复制'),
        backgroundColor: Color(0xFF52C41A),
        duration: Duration(seconds: 2),
      ),
    );
  }

  void _shareInvitation() {
    if (_invitation == null) return;
    Clipboard.setData(ClipboardData(
      text: '邀请您关联健康档案，点击链接接受邀请：$_inviteLink',
    ));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('分享内容已复制到剪贴板'),
        backgroundColor: Color(0xFF52C41A),
        duration: Duration(seconds: 2),
      ),
    );
  }

  Future<void> _saveToLocal() async {
    try {
      final status = await Permission.photos.request();
      if (!status.isGranted && !await Permission.storage.request().isGranted) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('需要相册权限才能保存图片'), backgroundColor: Colors.orange),
          );
        }
        return;
      }

      final boundary = _qrCardKey.currentContext?.findRenderObject() as RenderRepaintBoundary?;
      if (boundary == null) return;

      final image = await boundary.toImage(pixelRatio: 3.0);
      final byteData = await image.toByteData(format: ui.ImageByteFormat.png);
      if (byteData == null) return;

      final pngBytes = byteData.buffer.asUint8List();
      final result = await ImageGallerySaver.saveImage(
        Uint8List.fromList(pngBytes),
        quality: 100,
        name: 'bini_invite_${DateTime.now().millisecondsSinceEpoch}',
      );

      if (mounted) {
        final success = result is Map && (result['isSuccess'] == true);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(success ? '邀请图片已保存到相册' : '保存失败，请重试'),
            backgroundColor: success ? const Color(0xFF52C41A) : Colors.red,
            duration: const Duration(seconds: 2),
          ),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('保存失败，请重试'), backgroundColor: Colors.red),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('邀请关联'),
        backgroundColor: const Color(0xFF52C41A),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError()
              : _buildContent(),
    );
  }

  Widget _buildError() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.error_outline, size: 60, color: Colors.grey[400]),
          const SizedBox(height: 16),
          Text(_error!, style: TextStyle(fontSize: 16, color: Colors.grey[600])),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: _createInvitation,
            child: const Text('重新生成'),
          ),
        ],
      ),
    );
  }

  Widget _buildContent() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          const SizedBox(height: 16),
          _buildInviteCard(),
          const SizedBox(height: 32),
          _buildActionButtons(),
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: const Color(0xFFFFF7E6),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFFFFD591)),
            ),
            child: const Row(
              children: [
                Icon(Icons.access_time, size: 18, color: Color(0xFFFA8C16)),
                SizedBox(width: 8),
                Text(
                  '邀请有效期：24 小时',
                  style: TextStyle(fontSize: 14, color: Color(0xFFFA8C16)),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          _buildBenefitsSection(),
        ],
      ),
    );
  }

  Widget _buildInviteCard() {
    return RepaintBoundary(
      key: _qrCardKey,
      child: GestureDetector(
        onLongPress: _saveToLocal,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.08),
                blurRadius: 16,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Column(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: const Color(0xFF52C41A).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: const Icon(Icons.favorite, color: Color(0xFF52C41A), size: 28),
              ),
              const SizedBox(height: 16),
              const Text(
                '邀请关联健康档案',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
              ),
              const SizedBox(height: 8),
              Text(
                '邀请「${_invitation?.memberNickname ?? ''}」本人关联档案',
                style: TextStyle(fontSize: 14, color: Colors.grey[600]),
              ),
              const SizedBox(height: 24),
              QrImageView(
                data: _qrContentUrl,
                version: QrVersions.auto,
                size: 180,
                gapless: false,
                embeddedImage: null,
                errorStateBuilder: (ctx, err) {
                  return const Center(child: Text('二维码生成失败'));
                },
              ),
              const SizedBox(height: 16),
              const Text(
                '宾尼小康AI健康管家',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
              ),
              const SizedBox(height: 4),
              Text(
                '长按二维码可保存到相册',
                style: TextStyle(fontSize: 12, color: Colors.grey[400]),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildActionButtons() {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            onPressed: _saveToLocal,
            icon: const Icon(Icons.save_alt, size: 18),
            label: const Text('保存到本地'),
            style: OutlinedButton.styleFrom(
              foregroundColor: const Color(0xFF52C41A),
              side: const BorderSide(color: Color(0xFF52C41A)),
              padding: const EdgeInsets.symmetric(vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
            ),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: OutlinedButton.icon(
            onPressed: _copyLink,
            icon: const Icon(Icons.copy, size: 18),
            label: const Text('复制链接'),
            style: OutlinedButton.styleFrom(
              foregroundColor: const Color(0xFF52C41A),
              side: const BorderSide(color: Color(0xFF52C41A)),
              padding: const EdgeInsets.symmetric(vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
            ),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: ElevatedButton.icon(
            onPressed: _shareInvitation,
            icon: const Icon(Icons.share, size: 18),
            label: const Text('分享'),
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 12),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildBenefitsSection() {
    const benefits = [
      {
        'icon': Icons.bar_chart,
        'title': '数据共享',
        'desc': '家人健康档案共同维护，随时掌握彼此健康状况',
        'color': Color(0xFF1890FF),
      },
      {
        'icon': Icons.notifications_active,
        'title': '异常提醒',
        'desc': '健康数据异常时实时通知，第一时间关注家人健康',
        'color': Color(0xFFFA8C16),
      },
      {
        'icon': Icons.medication,
        'title': '用药提醒',
        'desc': '远程监督用药情况，确保家人按时服药不遗漏',
        'color': Color(0xFF52C41A),
      },
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '关联好处',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
        ),
        const SizedBox(height: 12),
        ...benefits.map((b) => _buildBenefitCard(
              icon: b['icon'] as IconData,
              title: b['title'] as String,
              desc: b['desc'] as String,
              color: b['color'] as Color,
            )),
      ],
    );
  }

  Widget _buildBenefitCard({
    required IconData icon,
    required String title,
    required String desc,
    required Color color,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withOpacity(0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.15)),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: color.withOpacity(0.12),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: color, size: 24),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: const Color(0xFF333333),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  desc,
                  style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
