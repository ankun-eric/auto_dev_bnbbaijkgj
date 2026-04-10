import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';
import '../../services/api_service.dart';

class SearchResultScreen extends StatefulWidget {
  const SearchResultScreen({super.key});

  @override
  State<SearchResultScreen> createState() => _SearchResultScreenState();
}

class _SearchResultScreenState extends State<SearchResultScreen> with TickerProviderStateMixin {
  static const List<Map<String, String>> _tabs = [
    {'key': 'all', 'label': '全部'},
    {'key': 'article', 'label': '文章'},
    {'key': 'video', 'label': '视频'},
    {'key': 'service', 'label': '服务'},
    {'key': 'points_mall', 'label': '积分商品'},
  ];

  final TextEditingController _controller = TextEditingController();
  final ApiService _apiService = ApiService();
  final AudioRecorder _audioRecorder = AudioRecorder();
  late TabController _tabController;

  String _query = '';
  String _currentType = 'all';
  String _searchSource = 'text';
  int _page = 1;
  bool _loading = false;
  bool _hasMore = true;
  List<dynamic> _results = [];
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabs.length, vsync: this);
    _tabController.addListener(_onTabChanged);
    _scrollController.addListener(_onScroll);
    _controller.addListener(() => setState(() {}));

    WidgetsBinding.instance.addPostFrameCallback((_) {
      final args = ModalRoute.of(context)?.settings.arguments;
      if (args is Map) {
        _query = args['query']?.toString() ?? '';
        final raw = args['source']?.toString();
        _searchSource = raw == 'voice' ? 'voice' : 'text';
      } else if (args is String && args.isNotEmpty) {
        _query = args;
      }
      if (_query.isNotEmpty) {
        _controller.text = _query;
        _doSearch();
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _tabController.dispose();
    _scrollController.dispose();
    _audioRecorder.dispose();
    super.dispose();
  }

  void _onTabChanged() {
    if (!_tabController.indexIsChanging) return;
    _currentType = _tabs[_tabController.index]['key']!;
    _page = 1;
    _hasMore = true;
    _results = [];
    _doSearch();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200) {
      _loadMore();
    }
  }

  Future<void> _doSearch() async {
    final q = _query.trim();
    if (q.isEmpty) return;
    setState(() {
      _loading = true;
      _page = 1;
      _hasMore = true;
    });

    try {
      final data = await _apiService.search(q: q, type: _currentType, page: 1, source: _searchSource);
      if (!mounted) return;
      final items = data['items'] ?? data['results'] ?? [];
      final total = data['total'] ?? 0;
      setState(() {
        _results = items is List ? items : [];
        _hasMore = _results.length < (total is int ? total : 0);
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _results = [];
        _loading = false;
      });
    }
  }

  Future<void> _loadMore() async {
    if (_loading || !_hasMore) return;
    setState(() => _loading = true);
    final nextPage = _page + 1;
    try {
      final data = await _apiService.search(q: _query, type: _currentType, page: nextPage, source: _searchSource);
      if (!mounted) return;
      final items = data['items'] ?? data['results'] ?? [];
      final total = data['total'] ?? 0;
      setState(() {
        if (items is List) _results.addAll(items);
        _page = nextPage;
        _hasMore = _results.length < (total is int ? total : 0);
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loading = false);
    }
  }

  void _onSubmit(String value) {
    _query = value.trim();
    if (_query.isEmpty) return;
    _doSearch();
  }

  Future<void> _startRecording() async {
    final status = await Permission.microphone.request();
    if (!status.isGranted) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('无法访问麦克风，请在系统设置中开启权限')),
      );
      return;
    }

    if (!mounted) return;
    final result = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => _VoiceRecordDialog(audioRecorder: _audioRecorder, apiService: _apiService),
    );

    if (result != null && result.isNotEmpty && mounted) {
      _controller.text = result;
      _controller.selection = TextSelection.fromPosition(
        TextPosition(offset: result.length),
      );
      _query = result;
      _searchSource = 'voice';
      _doSearch();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF52C41A),
        titleSpacing: 0,
        title: _buildSearchBar(),
        actions: [
          TextButton(
            onPressed: () => _onSubmit(_controller.text),
            child: const Text('搜索', style: TextStyle(color: Colors.white, fontSize: 15)),
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          indicatorColor: Colors.white,
          indicatorWeight: 3,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          labelStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
          unselectedLabelStyle: const TextStyle(fontSize: 14),
          tabs: _tabs.map((t) => Tab(text: t['label'])).toList(),
        ),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildSearchBar() {
    return Container(
      height: 38,
      margin: const EdgeInsets.only(left: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(19),
      ),
      child: Row(
        children: [
          const SizedBox(width: 12),
          const Icon(Icons.search, color: Color(0xFF999999), size: 20),
          const SizedBox(width: 6),
          Expanded(
            child: TextField(
              controller: _controller,
              textInputAction: TextInputAction.search,
              onSubmitted: _onSubmit,
              decoration: const InputDecoration(
                hintText: '搜索症状、疾病、药品',
                hintStyle: TextStyle(color: Color(0xFF999999), fontSize: 14),
                border: InputBorder.none,
                isDense: true,
                contentPadding: EdgeInsets.symmetric(vertical: 8),
              ),
              style: const TextStyle(fontSize: 14),
            ),
          ),
          GestureDetector(
            onTap: _startRecording,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: const Color(0xFF52C41A).withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.mic, color: Color(0xFF52C41A), size: 18),
              ),
            ),
          ),
          if (_controller.text.isNotEmpty)
            GestureDetector(
              onTap: () => _controller.clear(),
              child: const Padding(
                padding: EdgeInsets.symmetric(horizontal: 8),
                child: Icon(Icons.close, size: 18, color: Color(0xFF999999)),
              ),
            ),
          const SizedBox(width: 4),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_loading && _results.isEmpty) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)));
    }
    if (_results.isEmpty) {
      return _buildEmpty();
    }
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: _results.length + (_hasMore ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _results.length) {
          return const Padding(
            padding: EdgeInsets.all(16),
            child: Center(child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF52C41A))),
          );
        }
        return _buildResultItem(_results[index]);
      },
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.search_off, size: 64, color: Colors.grey[300]),
          const SizedBox(height: 16),
          Text(
            _query.isEmpty ? '请输入搜索关键词' : '未找到相关结果',
            style: TextStyle(fontSize: 15, color: Colors.grey[500]),
          ),
          if (_query.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text('换个关键词试试吧', style: TextStyle(fontSize: 13, color: Colors.grey[400])),
          ],
        ],
      ),
    );
  }

  Widget _buildResultItem(dynamic item) {
    if (item is! Map) return const SizedBox.shrink();
    final title = item['title']?.toString() ?? '';
    final summary = item['summary']?.toString() ?? item['description']?.toString() ?? '';
    final type = item['type']?.toString() ?? '';
    final imageUrl = item['cover_image']?.toString() ?? item['image_url']?.toString() ?? '';

    return InkWell(
      onTap: () => _onResultTap(item),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: const BoxDecoration(
          border: Border(bottom: BorderSide(color: Color(0xFFF0F0F0))),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      if (type.isNotEmpty)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          margin: const EdgeInsets.only(right: 6),
                          decoration: BoxDecoration(
                            color: _typeColor(type).withOpacity(0.1),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            _typeLabel(type),
                            style: TextStyle(fontSize: 11, color: _typeColor(type)),
                          ),
                        ),
                      Expanded(
                        child: Text(
                          title,
                          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500, color: Color(0xFF333333)),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                  if (summary.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      summary,
                      style: const TextStyle(fontSize: 13, color: Color(0xFF999999), height: 1.4),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ],
              ),
            ),
            if (imageUrl.isNotEmpty) ...[
              const SizedBox(width: 12),
              ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: Image.network(
                  imageUrl,
                  width: 80,
                  height: 60,
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => Container(
                    width: 80,
                    height: 60,
                    color: const Color(0xFFF5F5F5),
                    child: const Icon(Icons.image, color: Color(0xFFCCCCCC)),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _onResultTap(Map item) {
    final type = item['type']?.toString() ?? '';
    final id = item['id']?.toString() ?? '';
    switch (type) {
      case 'article':
        Navigator.pushNamed(context, '/article-detail', arguments: id);
        break;
      case 'service':
        Navigator.pushNamed(context, '/service-detail', arguments: id);
        break;
      case 'points_mall':
        Navigator.pushNamed(context, '/points-mall');
        break;
      default:
        if (id.isNotEmpty) {
          Navigator.pushNamed(context, '/article-detail', arguments: id);
        }
    }
  }

  Color _typeColor(String type) {
    switch (type) {
      case 'article':
        return const Color(0xFF1890FF);
      case 'video':
        return const Color(0xFFFA541C);
      case 'service':
        return const Color(0xFF52C41A);
      case 'points_mall':
        return const Color(0xFFFA8C16);
      default:
        return const Color(0xFF999999);
    }
  }

  String _typeLabel(String type) {
    switch (type) {
      case 'article':
        return '文章';
      case 'video':
        return '视频';
      case 'service':
        return '服务';
      case 'points_mall':
        return '积分商品';
      default:
        return type;
    }
  }
}

class _VoiceRecordDialog extends StatefulWidget {
  final AudioRecorder audioRecorder;
  final ApiService apiService;

  const _VoiceRecordDialog({required this.audioRecorder, required this.apiService});

  @override
  State<_VoiceRecordDialog> createState() => _VoiceRecordDialogState();
}

class _VoiceRecordDialogState extends State<_VoiceRecordDialog> with TickerProviderStateMixin {
  static const int _maxSeconds = 15;

  int _elapsed = 0;
  Timer? _timer;
  Timer? _amplitudeTimer;
  bool _recording = true;
  bool _recognizing = false;
  String? _error;
  String? _filePath;

  late AnimationController _waveController;
  late Animation<double> _pulseAnimation;
  List<double> _amplitudes = List.filled(7, 0.15);
  final Random _random = Random();

  @override
  void initState() {
    super.initState();
    _waveController = AnimationController(vsync: this, duration: const Duration(milliseconds: 750));
    _pulseAnimation = Tween<double>(begin: 0.94, end: 1.06).animate(
      CurvedAnimation(parent: _waveController, curve: Curves.easeInOut),
    );
    _waveController.repeat(reverse: true);
    _startRecording();
  }

  @override
  void dispose() {
    _timer?.cancel();
    _amplitudeTimer?.cancel();
    _waveController.dispose();
    super.dispose();
  }

  Future<void> _startRecording() async {
    try {
      final path = '${DateTime.now().millisecondsSinceEpoch}.m4a';
      await widget.audioRecorder.start(
        const RecordConfig(
          encoder: AudioEncoder.aacLc,
          sampleRate: 16000,
          numChannels: 1,
        ),
        path: path,
      );

      _timer = Timer.periodic(const Duration(seconds: 1), (t) {
        if (!mounted) return;
        setState(() => _elapsed++);
        if (_elapsed >= _maxSeconds) {
          _stopAndRecognize();
        }
      });

      _amplitudeTimer = Timer.periodic(const Duration(milliseconds: 150), (_) async {
        try {
          final amp = await widget.audioRecorder.getAmplitude();
          if (!mounted) return;
          final normalized = ((amp.current + 50) / 50).clamp(0.1, 1.0);
          setState(() {
            _amplitudes = List.generate(7, (i) {
              final base = normalized * (0.5 + _random.nextDouble() * 0.5);
              return base.clamp(0.15, 1.0);
            });
          });
        } catch (_) {}
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _recording = false;
        _error = '录音启动失败';
      });
    }
  }

  Future<void> _stopAndRecognize() async {
    _timer?.cancel();
    _amplitudeTimer?.cancel();

    if (!mounted) return;

    if (_elapsed < 1) {
      setState(() {
        _recording = false;
        _error = '说话时间太短';
      });
      try { await widget.audioRecorder.stop(); } catch (_) {}
      return;
    }

    try {
      final path = await widget.audioRecorder.stop();
      _filePath = path;
    } catch (_) {}

    if (!mounted) return;
    setState(() {
      _recording = false;
      _recognizing = true;
    });

    await _recognize();
  }

  Future<void> _recognize() async {
    if (_filePath == null || _filePath!.isEmpty) {
      if (!mounted) return;
      setState(() {
        _recognizing = false;
        _error = '录音文件异常';
      });
      return;
    }
    try {
      final result = await widget.apiService.asrRecognize(_filePath!, 'm4a');
      if (!mounted) return;
      if (result['success'] == false) {
        setState(() {
          _recognizing = false;
          _error = result['error']?.toString() ?? '未识别到有效内容，请重试';
        });
        return;
      }
      final asrData = result['data'];
      final rawText = (asrData is Map ? asrData['text']?.toString() : null) ?? result['text']?.toString() ?? '';
      final text = _removePunctuation(rawText);
      if (text.isEmpty) {
        setState(() {
          _recognizing = false;
          _error = '未识别到有效内容，请重试';
        });
        return;
      }
      Navigator.pop(context, text);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _recognizing = false;
        _error = '识别失败，请重试';
      });
    }
  }

  static String _removePunctuation(String str) {
    return str
        .replaceAll(
          RegExp(
            r'[\u3002\uff1b\uff0c\uff1a\u201c\u201d\u2018\u2019\uff08\uff09\u3001\uff1f\u300a\u300b\uff01\u3010\u3011\u2026\u2014\uff5e\u00b7.,!?;:\x27\x22()\[\]{}\-_\/\\@#\$%\^&\*\+=~`<>]',
          ),
          '',
        )
        .trim();
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: Colors.transparent,
      insetPadding: EdgeInsets.zero,
      child: GestureDetector(
        onTap: () {
          if (_recording) {
            _stopAndRecognize();
          } else if (_error != null) {
            Navigator.pop(context);
          }
        },
        child: Container(
          width: double.infinity,
          height: double.infinity,
          color: Colors.black.withOpacity(0.6),
          child: Center(child: _buildContent()),
        ),
      ),
    );
  }

  Widget _buildContent() {
    if (_error != null) return _buildError();
    if (_recognizing) return _buildRecognizing();
    return _buildRecording();
  }

  Widget _buildRecording() {
    final remaining = _maxSeconds - _elapsed;
    final isWarning = remaining <= 3;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          height: 100,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: List.generate(7, (i) {
              return AnimatedContainer(
                duration: const Duration(milliseconds: 150),
                width: 6,
                height: 100 * _amplitudes[i],
                margin: const EdgeInsets.symmetric(horizontal: 3),
                decoration: BoxDecoration(
                  color: const Color(0xFF52C41A),
                  borderRadius: BorderRadius.circular(3),
                ),
              );
            }),
          ),
        ),
        const SizedBox(height: 20),
        Text(
          '${_elapsed}s / ${_maxSeconds}s',
          style: TextStyle(
            color: isWarning ? Colors.redAccent : Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 24),
        GestureDetector(
          onTap: _stopAndRecognize,
          child: ScaleTransition(
            scale: _pulseAnimation,
            child: Container(
              width: 100,
              height: 100,
              decoration: BoxDecoration(
                color: Colors.white,
                shape: BoxShape.circle,
                border: Border.all(color: const Color(0xFF52C41A), width: 3),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF52C41A).withOpacity(0.35),
                    blurRadius: 14,
                    spreadRadius: 0,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(
                      color: const Color(0xFF52C41A),
                      borderRadius: BorderRadius.circular(1),
                    ),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    '点我结束~',
                    style: TextStyle(
                      fontSize: 16,
                      color: Color(0xFF52C41A),
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildRecognizing() {
    return const Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        CircularProgressIndicator(color: Color(0xFF52C41A), strokeWidth: 3),
        SizedBox(height: 20),
        Text('正在识别...', style: TextStyle(color: Colors.white, fontSize: 16)),
      ],
    );
  }

  Widget _buildError() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.error_outline, color: Colors.redAccent, size: 48),
        const SizedBox(height: 16),
        Text(_error!, style: const TextStyle(color: Colors.white, fontSize: 16)),
        const SizedBox(height: 20),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('关闭', style: TextStyle(color: Colors.white70, fontSize: 14)),
            ),
            const SizedBox(width: 24),
            TextButton(
              onPressed: () {
                setState(() {
                  _error = null;
                  _recording = true;
                  _elapsed = 0;
                  _amplitudes = List.filled(7, 0.15);
                });
                _startRecording();
              },
              child: const Text('重试', style: TextStyle(color: Color(0xFF52C41A), fontSize: 14)),
            ),
          ],
        ),
      ],
    );
  }
}
