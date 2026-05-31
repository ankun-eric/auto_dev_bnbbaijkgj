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
    // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31] 三端口径统一：
    //   AppBar 标题 / 主标题 / 说明 / 有效期 / 三个 emoji 标签 / 按钮配色
    return Scaffold(
      backgroundColor: const Color(0xFFF0F5FF),
      appBar: AppBar(
        title: const Text('邀请 TA 加入我的健康守护', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
        backgroundColor: const Color(0xFF0EA5E9),
        foregroundColor: Colors.white,
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
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          const SizedBox(height: 8),
          _buildInviteCard(),
          const SizedBox(height: 24),
          _buildActionButtons(),
        ],
      ),
    );
  }

  Widget _buildInviteCard() {
    // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31]
    // 顶部蓝色渐变 + 三个 emoji 标签；二维码下方说明 + "邀请 24 小时内有效"
    return RepaintBoundary(
      key: _qrCardKey,
      child: GestureDetector(
        onLongPress: _saveToLocal,
        child: Container(
          width: double.infinity,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(20),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF0EA5E9).withOpacity(0.12),
                blurRadius: 24,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          clipBehavior: Clip.antiAlias,
          child: Column(
            children: [
              // 顶部蓝色渐变区
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 20),
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [Color(0xFF0EA5E9), Color(0xFF38BDF8)],
                  ),
                ),
                child: Column(
                  children: [
                    const Text(
                      '邀请 TA 加入我的健康守护',
                      style: TextStyle(fontSize: 19, fontWeight: FontWeight.w700, color: Colors.white),
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      alignment: WrapAlignment.center,
                      children: const [
                        _InviteTag(text: '📋 档案管理'),
                        _InviteTag(text: '💊 用药提醒'),
                        _InviteTag(text: '🔔 异常提醒'),
                      ],
                    ),
                  ],
                ),
              ),
              // 二维码与说明
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
                child: Column(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(color: const Color(0xFFE0F2FE), width: 2),
                      ),
                      child: QrImageView(
                        data: _qrContentUrl,
                        version: QrVersions.auto,
                        size: 180,
                        gapless: false,
                        embeddedImage: null,
                        errorStateBuilder: (ctx, err) {
                          return const Center(child: Text('二维码生成失败'));
                        },
                      ),
                    ),
                    const SizedBox(height: 14),
                    Text(
                      '邀请 24 小时内有效',
                      style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                    ),
                    const SizedBox(height: 10),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF0F9FF),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Text(
                        '让 TA 扫码或打开链接，确认后就能加入啦',
                        style: TextStyle(fontSize: 13, color: Color(0xFF0369A1)),
                      ),
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

  Widget _buildActionButtons() {
    // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31]
    // 保存到本地 / 复制链接 = 实心主色蓝；转发微信好友 = 微信绿
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: ElevatedButton.icon(
                onPressed: _saveToLocal,
                icon: const Icon(Icons.save_alt, size: 18, color: Colors.white),
                label: const Text('保存到本地', style: TextStyle(color: Colors.white)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF0284C7),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
                  elevation: 4,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: ElevatedButton.icon(
                onPressed: _copyLink,
                icon: const Icon(Icons.copy, size: 18, color: Colors.white),
                label: const Text('复制链接', style: TextStyle(color: Colors.white)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF0284C7),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
                  elevation: 4,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: _shareInvitation,
            icon: const Icon(Icons.share, size: 18, color: Colors.white),
            label: const Text('转发微信好友', style: TextStyle(color: Colors.white)),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF07C160),
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
              elevation: 4,
            ),
          ),
        ),
      ],
    );
  }
}

class _InviteTag extends StatelessWidget {
  final String text;
  const _InviteTag({required this.text});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.22),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Text(
        text,
        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: Colors.white),
      ),
    );
  }
}
