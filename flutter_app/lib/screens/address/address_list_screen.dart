import 'package:flutter/material.dart';
import '../../models/address.dart';
import '../../services/api_service.dart';

class AddressListScreen extends StatefulWidget {
  const AddressListScreen({super.key});

  @override
  State<AddressListScreen> createState() => _AddressListScreenState();
}

class _AddressListScreenState extends State<AddressListScreen> {
  final ApiService _api = ApiService();
  List<UserAddress> _addresses = [];
  bool _loading = true;
  bool _selectMode = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _selectMode = ModalRoute.of(context)?.settings.arguments == true;
    _loadAddresses();
  }

  Future<void> _loadAddresses() async {
    setState(() => _loading = true);
    try {
      final res = await _api.getAddresses();
      if (res.data is Map && res.data['items'] is List) {
        setState(() {
          _addresses = (res.data['items'] as List)
              .map((e) => UserAddress.fromJson(e as Map<String, dynamic>))
              .toList();
        });
      }
    } catch (_) {}
    setState(() => _loading = false);
  }

  Future<void> _deleteAddress(UserAddress address) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除地址'),
        content: const Text('确定要删除该地址吗？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('删除')),
        ],
      ),
    );
    if (confirm != true) return;
    try {
      await _api.deleteAddress(address.id);
      _loadAddresses();
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('删除失败')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_selectMode ? '选择地址' : '收货地址'),
        backgroundColor: const Color(0xFF52C41A),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)))
          : _addresses.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.location_off, size: 64, color: Colors.grey[300]),
                      const SizedBox(height: 12),
                      Text('暂无收货地址', style: TextStyle(color: Colors.grey[500])),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadAddresses,
                  color: const Color(0xFF52C41A),
                  child: ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: _addresses.length,
                    itemBuilder: (context, index) => _buildAddressCard(_addresses[index]),
                  ),
                ),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          await Navigator.pushNamed(context, '/address-edit');
          _loadAddresses();
        },
        backgroundColor: const Color(0xFF52C41A),
        child: const Icon(Icons.add),
      ),
    );
  }

  Widget _buildAddressCard(UserAddress address) {
    return GestureDetector(
      onTap: _selectMode ? () => Navigator.pop(context, address) : null,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(address.name, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                const SizedBox(width: 12),
                Text(address.phone, style: TextStyle(color: Colors.grey[600])),
                if (address.isDefault) ...[
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                    decoration: BoxDecoration(
                      color: const Color(0xFF52C41A).withOpacity(0.1),
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(color: const Color(0xFF52C41A)),
                    ),
                    child: const Text('默认', style: TextStyle(color: Color(0xFF52C41A), fontSize: 10)),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 6),
            Text(address.fullAddress, style: TextStyle(fontSize: 13, color: Colors.grey[600])),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton.icon(
                  onPressed: () async {
                    await Navigator.pushNamed(context, '/address-edit', arguments: address);
                    _loadAddresses();
                  },
                  icon: const Icon(Icons.edit, size: 16),
                  label: const Text('编辑', style: TextStyle(fontSize: 13)),
                  style: TextButton.styleFrom(foregroundColor: Colors.grey[600]),
                ),
                TextButton.icon(
                  onPressed: () => _deleteAddress(address),
                  icon: const Icon(Icons.delete_outline, size: 16),
                  label: const Text('删除', style: TextStyle(fontSize: 13)),
                  style: TextButton.styleFrom(foregroundColor: Colors.red[300]),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
