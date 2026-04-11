import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../models/family_management.dart';

class FamilyAuthScreen extends StatefulWidget {
  final String code;

  const FamilyAuthScreen({super.key, required this.code});

  @override
  State<FamilyAuthScreen> createState() => _FamilyAuthScreenState();
}

class _FamilyAuthScreenState extends State<FamilyAuthScreen> {
  final ApiService _apiService = ApiService();
  bool _loading = true;
  bool _processing = false;
  FamilyInvitationModel? _invitation;
  String? _error;
  String? _resultMessage;
  bool _isSuccess = false;

  @override
  void initState() {
    super.initState();
    _loadInvitation();
  }

  Future<void> _loadInvitation() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final response = await _apiService.getFamilyInvitation(widget.code);
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
          _error = '邀请信息获取失败';
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = '邀请链接无效或已过期';
          _loading = false;
        });
      }
    }
  }

  Future<void> _acceptInvitation() async {
    setState(() => _processing = true);
    try {
      final response = await _apiService.acceptFamilyInvitation(widget.code);
      if (response.statusCode == 200 && mounted) {
        setState(() {
          _resultMessage = '授权成功！对方现在可以管理您的健康档案';
          _isSuccess = true;
          _processing = false;
        });
      } else {
        setState(() {
          _resultMessage = '授权失败，请重试';
          _isSuccess = false;
          _processing = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _resultMessage = '网络错误，请检查网络后重试';
          _isSuccess = false;
          _processing = false;
        });
      }
    }
  }

  Future<void> _rejectInvitation() async {
    setState(() => _processing = true);
    try {
      final response = await _apiService.rejectFamilyInvitation(widget.code);
      if (response.statusCode == 200 && mounted) {
        setState(() {
          _resultMessage = '已拒绝该邀请';
          _isSuccess = true;
          _processing = false;
        });
      } else {
        setState(() {
          _resultMessage = '操作失败，请重试';
          _isSuccess = false;
          _processing = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _resultMessage = '网络错误，请检查网络后重试';
          _isSuccess = false;
          _processing = false;
        });
      }
    }
  }

  void _showConfirmDialog(bool isAccept) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            Icon(
              isAccept ? Icons.check_circle_outline : Icons.cancel_outlined,
              color: isAccept ? const Color(0xFF52C41A) : Colors.red,
              size: 24,
            ),
            const SizedBox(width: 8),
            Text(isAccept ? '确认授权' : '拒绝授权'),
          ],
        ),
        content: Text(
          isAccept
              ? '确认授权「${_invitation?.inviterNickname ?? ''}」管理您的健康档案吗？\n\n授权后对方可以查看和编辑您的健康信息。'
              : '确认拒绝「${_invitation?.inviterNickname ?? ''}」的关联邀请吗？',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              if (isAccept) {
                _acceptInvitation();
              } else {
                _rejectInvitation();
              }
            },
            style: isAccept
                ? null
                : ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: Text(isAccept ? '确认' : '拒绝'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('授权确认'),
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
              : _resultMessage != null
                  ? _buildResult()
                  : _buildContent(),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: Colors.red.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.link_off, size: 40, color: Colors.red),
            ),
            const SizedBox(height: 24),
            Text(
              _error!,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            Text(
              '请检查链接是否正确或联系邀请人重新生成',
              style: TextStyle(fontSize: 14, color: Colors.grey[600]),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            ElevatedButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('返回'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResult() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: (_isSuccess ? const Color(0xFF52C41A) : Colors.red).withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(
                _isSuccess ? Icons.check_circle : Icons.error,
                size: 48,
                color: _isSuccess ? const Color(0xFF52C41A) : Colors.red,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              _resultMessage!,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            ElevatedButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('返回'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          const SizedBox(height: 32),
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: const Color(0xFF52C41A).withOpacity(0.1),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.person_add, size: 40, color: Color(0xFF52C41A)),
          ),
          const SizedBox(height: 24),
          const Text(
            '健康档案关联邀请',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
          ),
          const SizedBox(height: 32),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
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
            child: Column(
              children: [
                _buildInfoRow('邀请人', _invitation?.inviterNickname ?? ''),
                const Divider(height: 24),
                _buildInfoRow('关联成员', _invitation?.memberNickname ?? ''),
                const Divider(height: 24),
                _buildInfoRow('邀请状态', _statusText(_invitation?.status ?? '')),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFFF6FFED),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFFB7EB8F)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('授权说明', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF52C41A))),
                const SizedBox(height: 8),
                Text(
                  '同意后，对方可以查看并管理您的健康档案信息。您可以随时在「家庭关联」中取消授权。',
                  style: TextStyle(fontSize: 13, color: Colors.grey[700], height: 1.6),
                ),
              ],
            ),
          ),
          const SizedBox(height: 40),
          if (_invitation?.status == 'pending') ...[
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _processing ? null : () => _showConfirmDialog(true),
                child: _processing
                    ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Text('同意授权'),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: _processing ? null : () => _showConfirmDialog(false),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.red,
                  side: const BorderSide(color: Colors.red),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                ),
                child: const Text('拒绝'),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: TextStyle(fontSize: 15, color: Colors.grey[600])),
        Text(value, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Color(0xFF333333))),
      ],
    );
  }

  String _statusText(String status) {
    switch (status) {
      case 'pending':
        return '待确认';
      case 'accepted':
        return '已同意';
      case 'rejected':
        return '已拒绝';
      case 'expired':
        return '已过期';
      default:
        return status;
    }
  }
}
