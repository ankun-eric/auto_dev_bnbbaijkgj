import 'dart:convert';
import 'package:flutter/services.dart' show rootBundle;

/// [2026-05-05 用户地址改造 PRD v1.0] 行政区划数据加载工具。
class RegionDistrict {
  final String code;
  final String name;
  RegionDistrict(this.code, this.name);
}

class RegionCity {
  final String code;
  final String name;
  final List<RegionDistrict> districts;
  RegionCity(this.code, this.name, this.districts);
}

class RegionProvince {
  final String code;
  final String name;
  final List<RegionCity> cities;
  RegionProvince(this.code, this.name, this.cities);
}

class RegionsLoader {
  static List<RegionProvince>? _cached;
  static String? _version;

  static Future<List<RegionProvince>> load() async {
    if (_cached != null) return _cached!;
    final raw = await rootBundle.loadString('assets/data/regions.json');
    final data = json.decode(raw) as Map<String, dynamic>;
    _version = data['version']?.toString();
    final provinces = (data['provinces'] as List).map<RegionProvince>((p) {
      return RegionProvince(
        p['code'] as String,
        p['name'] as String,
        (p['cities'] as List).map<RegionCity>((c) {
          return RegionCity(
            c['code'] as String,
            c['name'] as String,
            (c['districts'] as List).map<RegionDistrict>((d) {
              return RegionDistrict(d['code'] as String, d['name'] as String);
            }).toList(),
          );
        }).toList(),
      );
    }).toList();
    _cached = provinces;
    return provinces;
  }

  static String? get version => _version;
}
