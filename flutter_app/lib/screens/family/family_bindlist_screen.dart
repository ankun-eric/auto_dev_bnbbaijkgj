import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../models/family_management.dart';

class FamilyBindListScreen extends StatefulWidget {
  const FamilyBindListScreen({super.key});

  @override
  State<FamilyBindListScreen> createState() => _FamilyBindListScreenState();
}

class _FamilyBindListScreenState extends State<FamilyBindListScreen> {
  final ApiService _apiService = ApiService();
  bool _loading = true;
  List<ManagedByModel> _managedByList = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadManagedByList();
  }

  Future<void> _loadManagedByList() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final response = await _apiService.getManagedByList();
      if (response.statusCode == 200 && mounted) {
        final data = response.data;
        List items = [];
        if (data is Map && data['items'] is List) {
          items = data['items'] as List;
        } else if (data is List) {
          items = data;
        }
        setState(() {
          _managedByList = items
              .map((e) => ManagedByModel.fromJson(Map<String, dynamic>.from(e as Map)))
              .toList();
          _loading = false;
        });
      } else {
        setState(() {
          _error = '加载失败';
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

  void _showRevokeDialog(ManagedByModel item) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Icon(Icons.warning_amber_rounded, color: Color(0xFFFA8C16), size: 24),
            SizedBox(width: 8),
            Text('取消授权'),
          ],
        ),
        content: Text('确定取消「${item.managerNickname}」对您健康档案的管理权限吗？\n\n取消后对方将无法查看和管理您的健康信息。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('再想想'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              _revokeAuthorization(item.id);
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('确认取消'),
          ),
        ],
      ),
    );
  }

  Future<void> _revokeAuthorization(int id) async {
    try {
      final response = await _apiService.deleteFamilyManagement(id);
      if (response.statusCode == 200 && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('已取消授权'),
            backgroundColor: Color(0xFF52C41A),
            duration: Duration(seconds: 2),
          ),
        );
        _loadManagedByList();
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('操作失败，请重试'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('网络错误，请检查网络后重试'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('家庭关联'),
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
              : _managedByList.isEmpty
                  ? _buildEmpty()
                  : _buildList(),
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
            onPressed: _loadManagedByList,
            child: const Text('重新加载'),
          ),
        ],
      ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: const Color(0xFF52C41A).withOpacity(0.1),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.people_outline, size: 40, color: Color(0xFF52C41A)),
          ),
          const SizedBox(height: 20),
          const Text(
            '暂无关联记录',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
          ),
          const SizedBox(height: 8),
          Text(
            '当有人邀请您关联健康档案时\n将在此处显示',
            style: TextStyle(fontSize: 14, color: Colors.grey[500]),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildList() {
    return RefreshIndicator(
      onRefresh: _loadManagedByList,
      color: const Color(0xFF52C41A),
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _managedByList.length + 1,
        itemBuilder: (context, index) {
          if (index == 0) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(
                '以下用户正在管理您的健康档案',
                style: TextStyle(fontSize: 13, color: Colors.grey[600]),
              ),
            );
          }
          final item = _managedByList[index - 1];
          return _buildManagedByCard(item);
        },
      ),
    );
  }

  Widget _buildManagedByCard(ManagedByModel item) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: const Color(0xFF1890FF).withOpacity(0.1),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.person, size: 26, color: Color(0xFF1890FF)),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.managerNickname,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Container(
                      width: 6,
                      height: 6,
                      decoration: BoxDecoration(
                        color: item.status == 'active' ? const Color(0xFF52C41A) : Colors.grey,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      item.status == 'active' ? '管理中' : item.status,
                      style: TextStyle(fontSize: 13, color: Colors.grey[500]),
                    ),
                    if (item.createdAt != null) ...[
                      const SizedBox(width: 12),
                      Text(
                        '关联于 ${_formatDate(item.createdAt!)}',
                        style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
          TextButton(
            onPressed: () => _showRevokeDialog(item),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('取消授权', style: TextStyle(fontSize: 13)),
          ),
        ],
      ),
    );
  }

  String _formatDate(String dateStr) {
    try {
      final date = DateTime.parse(dateStr);
      return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
    } catch (_) {
      return dateStr;
    }
  }
}
