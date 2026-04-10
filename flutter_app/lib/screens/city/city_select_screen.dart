import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../services/api_service.dart';

class CitySelectScreen extends StatefulWidget {
  const CitySelectScreen({super.key});

  @override
  State<CitySelectScreen> createState() => _CitySelectScreenState();
}

class _CitySelectScreenState extends State<CitySelectScreen> {
  final ApiService _apiService = ApiService();
  final TextEditingController _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  bool _loading = true;
  String? _locatedCityName;
  String? _locatedCityId;
  List<Map<String, dynamic>> _recentCities = [];
  List<Map<String, dynamic>> _hotCities = [];
  List<Map<String, dynamic>> _allCities = [];
  List<Map<String, dynamic>> _filteredCities = [];
  Map<String, List<Map<String, dynamic>>> _groupedCities = {};
  List<String> _letterIndex = [];
  String? _activeLetter;
  bool _isSearching = false;

  @override
  void initState() {
    super.initState();
    _loadData();
    _searchController.addListener(_onSearchChanged);
  }

  @override
  void dispose() {
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    final prefs = await SharedPreferences.getInstance();

    _locatedCityName = prefs.getString('located_city_name');
    _locatedCityId = prefs.getString('located_city_id');

    final recentJson = prefs.getString('recent_cities');
    if (recentJson != null) {
      try {
        final list = jsonDecode(recentJson) as List;
        _recentCities = list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
      } catch (_) {}
    }

    try {
      final results = await Future.wait([
        _apiService.getHotCities().catchError((_) => <String, dynamic>{}),
        _apiService.getCityList().catchError((_) => <String, dynamic>{}),
      ]);

      final hotData = results[0];
      final listData = results[1];

      if (hotData['cities'] is List) {
        _hotCities = (hotData['cities'] as List)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
      } else if (hotData['items'] is List) {
        _hotCities = (hotData['items'] as List)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
      }

      if (listData['groups'] is List) {
        _allCities = [];
        for (final group in listData['groups'] as List) {
          final g = Map<String, dynamic>.from(group as Map);
          final letter = g['letter']?.toString() ?? '';
          if (g['cities'] is List) {
            for (final city in g['cities'] as List) {
              final c = Map<String, dynamic>.from(city as Map);
              c['first_letter'] = letter.isNotEmpty ? letter : (c['first_letter'] ?? '');
              _allCities.add(c);
            }
          }
        }
      } else if (listData['items'] is List) {
        _allCities = (listData['items'] as List)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
      }

      _buildGroupedCities();
    } catch (_) {}

    if (mounted) setState(() => _loading = false);
  }

  void _buildGroupedCities() {
    _groupedCities.clear();
    for (final city in _allCities) {
      final fl = city['first_letter']?.toString() ?? '';
      final letter = fl.isNotEmpty ? fl.toUpperCase() : '#';
      final key = RegExp(r'[A-Z]').hasMatch(letter) ? letter : '#';
      _groupedCities.putIfAbsent(key, () => []).add(city);
    }
    _letterIndex = _groupedCities.keys.toList()..sort((a, b) {
      if (a == '#') return 1;
      if (b == '#') return -1;
      return a.compareTo(b);
    });
  }

  void _onSearchChanged() {
    final keyword = _searchController.text.trim();
    if (keyword.isEmpty) {
      setState(() {
        _isSearching = false;
        _filteredCities = [];
      });
      return;
    }

    setState(() {
      _isSearching = true;
      _filteredCities = _allCities.where((city) {
        final name = city['name']?.toString() ?? '';
        final pinyin = city['pinyin']?.toString() ?? '';
        return name.contains(keyword) || pinyin.toLowerCase().contains(keyword.toLowerCase());
      }).toList();
    });
  }

  Future<void> _selectCity(Map<String, dynamic> city) async {
    final prefs = await SharedPreferences.getInstance();
    final name = city['name']?.toString() ?? '';
    final id = city['id']?.toString() ?? '';

    await prefs.setString('selected_city_name', name);
    await prefs.setString('selected_city_id', id);

    _updateRecentCities(city);

    if (mounted) {
      Navigator.pop(context, {'name': name, 'id': id});
    }
  }

  Future<void> _updateRecentCities(Map<String, dynamic> city) async {
    final prefs = await SharedPreferences.getInstance();
    final id = city['id']?.toString() ?? '';

    _recentCities.removeWhere((c) => c['id']?.toString() == id);
    _recentCities.insert(0, city);
    if (_recentCities.length > 3) _recentCities = _recentCities.sublist(0, 3);

    await prefs.setString('recent_cities', jsonEncode(_recentCities));
  }

  void _scrollToLetter(String letter) {
    double offset = 0;
    // Header heights: search(56) + GPS section + recent section + hot section
    // Approximate: calculate based on sections before the letter
    for (final l in _letterIndex) {
      if (l == letter) break;
      final count = _groupedCities[l]?.length ?? 0;
      offset += 32 + count * 48.0; // letter header + items
    }
    _scrollController.animateTo(
      offset,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeOut,
    );
    setState(() => _activeLetter = letter);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        title: const Text('选择城市'),
        backgroundColor: const Color(0xFF52C41A),
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)))
          : Stack(
              children: [
                Column(
                  children: [
                    _buildSearchBar(),
                    Expanded(
                      child: _isSearching ? _buildSearchResults() : _buildCityContent(),
                    ),
                  ],
                ),
                if (!_isSearching && _letterIndex.isNotEmpty)
                  Positioned(
                    right: 2,
                    top: 0,
                    bottom: 0,
                    child: _buildLetterIndex(),
                  ),
              ],
            ),
    );
  }

  Widget _buildSearchBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      color: Colors.white,
      child: TextField(
        controller: _searchController,
        decoration: InputDecoration(
          hintText: '搜索城市名称或拼音',
          hintStyle: TextStyle(color: Colors.grey[400], fontSize: 14),
          prefixIcon: Icon(Icons.search, color: Colors.grey[400], size: 20),
          suffixIcon: _searchController.text.isNotEmpty
              ? IconButton(
                  icon: Icon(Icons.clear, color: Colors.grey[400], size: 18),
                  onPressed: () {
                    _searchController.clear();
                  },
                )
              : null,
          filled: true,
          fillColor: const Color(0xFFF5F7FA),
          contentPadding: const EdgeInsets.symmetric(vertical: 10),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(20),
            borderSide: BorderSide.none,
          ),
        ),
      ),
    );
  }

  Widget _buildSearchResults() {
    if (_filteredCities.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.location_city, size: 48, color: Colors.grey[300]),
            const SizedBox(height: 12),
            Text('未找到相关城市', style: TextStyle(color: Colors.grey[400], fontSize: 14)),
          ],
        ),
      );
    }
    return ListView.builder(
      itemCount: _filteredCities.length,
      itemBuilder: (context, index) {
        final city = _filteredCities[index];
        return _buildCityItem(city);
      },
    );
  }

  Widget _buildCityContent() {
    return ListView(
      controller: _scrollController,
      padding: const EdgeInsets.only(right: 20),
      children: [
        if (_locatedCityName != null && _locatedCityName!.isNotEmpty) ...[
          _buildSectionTitle('GPS定位城市'),
          _buildLocatedCity(),
        ],
        if (_recentCities.isNotEmpty) ...[
          _buildSectionTitle('最近访问'),
          _buildCityTags(_recentCities),
        ],
        if (_hotCities.isNotEmpty) ...[
          _buildSectionTitle('热门城市'),
          _buildCityTags(_hotCities),
        ],
        ..._buildGroupedList(),
      ],
    );
  }

  Widget _buildSectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: Color(0xFF999999),
        ),
      ),
    );
  }

  Widget _buildLocatedCity() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: GestureDetector(
        onTap: () => _selectCity({
          'id': _locatedCityId ?? '',
          'name': _locatedCityName ?? '',
        }),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: const Color(0xFFF5F7FA),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.my_location, size: 16, color: Color(0xFF52C41A)),
              const SizedBox(width: 6),
              Text(
                _locatedCityName!,
                style: const TextStyle(fontSize: 14, color: Color(0xFF333333)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCityTags(List<Map<String, dynamic>> cities) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Wrap(
        spacing: 10,
        runSpacing: 10,
        children: cities.map((city) {
          return GestureDetector(
            onTap: () => _selectCity(city),
            child: Container(
              width: (MediaQuery.of(context).size.width - 32 - 20 - 30) / 4,
              padding: const EdgeInsets.symmetric(vertical: 10),
              decoration: BoxDecoration(
                color: const Color(0xFFF5F7FA),
                borderRadius: BorderRadius.circular(8),
              ),
              alignment: Alignment.center,
              child: Text(
                city['name']?.toString() ?? '',
                style: const TextStyle(fontSize: 13, color: Color(0xFF333333)),
                overflow: TextOverflow.ellipsis,
                maxLines: 1,
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  List<Widget> _buildGroupedList() {
    final widgets = <Widget>[];
    for (final letter in _letterIndex) {
      final cities = _groupedCities[letter]!;
      widgets.add(
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
          color: const Color(0xFFF5F7FA),
          child: Text(
            letter,
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF999999)),
          ),
        ),
      );
      for (final city in cities) {
        widgets.add(_buildCityItem(city));
      }
    }
    return widgets;
  }

  Widget _buildCityItem(Map<String, dynamic> city) {
    return InkWell(
      onTap: () => _selectCity(city),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          border: Border(bottom: BorderSide(color: Colors.grey[100]!, width: 0.5)),
        ),
        child: Text(
          city['name']?.toString() ?? '',
          style: const TextStyle(fontSize: 15, color: Color(0xFF333333)),
        ),
      ),
    );
  }

  Widget _buildLetterIndex() {
    return Center(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: _letterIndex.map((letter) {
            final isActive = _activeLetter == letter;
            return GestureDetector(
              onTap: () => _scrollToLetter(letter),
              child: Container(
                width: 18,
                height: 18,
                alignment: Alignment.center,
                decoration: isActive
                    ? const BoxDecoration(
                        shape: BoxShape.circle,
                        color: Color(0xFF52C41A),
                      )
                    : null,
                child: Text(
                  letter,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    color: isActive ? Colors.white : const Color(0xFF999999),
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ),
    );
  }
}
