import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

import '../utils/regions_loader.dart';

/// [2026-05-05 用户地址改造 PRD v1.0] 三级行政区划滚轮选择弹层。
///
/// 用法：
///   final r = await showRegionPickerSheet(context,
///     initialProvinceCode: addr.provinceCode);
///   if (r != null) { ... }
class RegionPickResult {
  final RegionProvince province;
  final RegionCity city;
  final RegionDistrict? district;
  RegionPickResult(this.province, this.city, this.district);
}

Future<RegionPickResult?> showRegionPickerSheet(
  BuildContext context, {
  String? initialProvinceCode,
  String? initialCityCode,
  String? initialDistrictCode,
}) {
  return showModalBottomSheet<RegionPickResult>(
    context: context,
    backgroundColor: Colors.white,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
    ),
    builder: (ctx) => _RegionPickerSheet(
      initialProvinceCode: initialProvinceCode,
      initialCityCode: initialCityCode,
      initialDistrictCode: initialDistrictCode,
    ),
  );
}

class _RegionPickerSheet extends StatefulWidget {
  final String? initialProvinceCode;
  final String? initialCityCode;
  final String? initialDistrictCode;
  const _RegionPickerSheet({
    this.initialProvinceCode,
    this.initialCityCode,
    this.initialDistrictCode,
  });
  @override
  State<_RegionPickerSheet> createState() => _RegionPickerSheetState();
}

class _RegionPickerSheetState extends State<_RegionPickerSheet> {
  List<RegionProvince> _provinces = [];
  int _provinceIdx = 0;
  int _cityIdx = 0;
  int _districtIdx = 0;
  bool _loading = true;
  late FixedExtentScrollController _provCtrl;
  late FixedExtentScrollController _cityCtrl;
  late FixedExtentScrollController _distCtrl;

  @override
  void initState() {
    super.initState();
    _provCtrl = FixedExtentScrollController();
    _cityCtrl = FixedExtentScrollController();
    _distCtrl = FixedExtentScrollController();
    _load();
  }

  Future<void> _load() async {
    final list = await RegionsLoader.load();
    int pIdx = 0, cIdx = 0, dIdx = 0;
    if (widget.initialProvinceCode != null) {
      final i = list.indexWhere((e) => e.code == widget.initialProvinceCode);
      if (i >= 0) pIdx = i;
    }
    if (list.isNotEmpty && widget.initialCityCode != null) {
      final cities = list[pIdx].cities;
      final j = cities.indexWhere((e) => e.code == widget.initialCityCode);
      if (j >= 0) cIdx = j;
    }
    if (list.isNotEmpty && widget.initialDistrictCode != null) {
      final cities = list[pIdx].cities;
      if (cities.isNotEmpty) {
        final dists = cities[cIdx].districts;
        final k = dists.indexWhere((e) => e.code == widget.initialDistrictCode);
        if (k >= 0) dIdx = k;
      }
    }
    setState(() {
      _provinces = list;
      _provinceIdx = pIdx;
      _cityIdx = cIdx;
      _districtIdx = dIdx;
      _loading = false;
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _provCtrl.jumpToItem(pIdx);
      _cityCtrl.jumpToItem(cIdx);
      _distCtrl.jumpToItem(dIdx);
    });
  }

  List<RegionCity> get _cities =>
      _provinces.isEmpty ? [] : _provinces[_provinceIdx].cities;
  List<RegionDistrict> get _districts =>
      _cities.isEmpty || _cityIdx >= _cities.length ? [] : _cities[_cityIdx].districts;

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return SizedBox(
        height: 320,
        child: const Center(child: CupertinoActivityIndicator()),
      );
    }
    return SafeArea(
      child: SizedBox(
        height: 320,
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: Color(0xFFF0F0F0))),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('取消', style: TextStyle(color: Color(0xFF999999))),
                  ),
                  const Text('选择所在地区', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
                  TextButton(
                    onPressed: () {
                      final p = _provinces[_provinceIdx];
                      final c = _cities.isNotEmpty ? _cities[_cityIdx] : null;
                      final d = _districts.isNotEmpty ? _districts[_districtIdx] : null;
                      if (c == null) {
                        Navigator.of(context).pop();
                        return;
                      }
                      Navigator.of(context).pop(RegionPickResult(p, c, d));
                    },
                    child: const Text('确定', style: TextStyle(color: Color(0xFF52C41A), fontWeight: FontWeight.w500)),
                  ),
                ],
              ),
            ),
            Expanded(
              child: Row(
                children: [
                  _buildColumn(_provinces.map((e) => e.name).toList(), _provinceIdx, _provCtrl, (i) {
                    setState(() {
                      _provinceIdx = i;
                      _cityIdx = 0;
                      _districtIdx = 0;
                    });
                    _cityCtrl.jumpToItem(0);
                    _distCtrl.jumpToItem(0);
                  }),
                  _buildColumn(_cities.map((e) => e.name).toList(), _cityIdx, _cityCtrl, (i) {
                    setState(() {
                      _cityIdx = i;
                      _districtIdx = 0;
                    });
                    _distCtrl.jumpToItem(0);
                  }),
                  _buildColumn(_districts.map((e) => e.name).toList(), _districtIdx, _distCtrl, (i) {
                    setState(() => _districtIdx = i);
                  }),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildColumn(List<String> items, int selected, FixedExtentScrollController ctrl, ValueChanged<int> onChanged) {
    if (items.isEmpty) return const Expanded(child: SizedBox.shrink());
    return Expanded(
      child: CupertinoPicker(
        scrollController: ctrl,
        itemExtent: 36,
        onSelectedItemChanged: onChanged,
        children: items.map((s) => Center(
          child: Text(s, style: const TextStyle(fontSize: 14)),
        )).toList(),
      ),
    );
  }

  @override
  void dispose() {
    _provCtrl.dispose();
    _cityCtrl.dispose();
    _distCtrl.dispose();
    super.dispose();
  }
}
