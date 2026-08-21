import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image/image.dart' as img;
import 'package:intl/intl.dart';
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';

import '../../../app/providers.dart';
import '../../../core/network/odoo_api_client.dart';
import '../../customers/data/mock_assignment_repository.dart';
import '../../customers/domain/entities.dart';
import '../domain/reading.dart';

class ReadingEntryScreen extends ConsumerStatefulWidget {
  final String assignmentId;
  const ReadingEntryScreen({super.key, required this.assignmentId});

  @override
  ConsumerState<ReadingEntryScreen> createState() => _ReadingEntryScreenState();
}

class _ReadingEntryScreenState extends ConsumerState<ReadingEntryScreen> {
  final _formKey = GlobalKey<FormState>();
  final _readingCtrl = TextEditingController();
  final _remarksCtrl = TextEditingController();

  ReadingAssignment? _assignment;
  _MeterInfo? _meterInfo;
  bool _loadingMeter = true;
  String? _loadError;
  File? _capturedImage;
  bool _savingReading = false;

  @override
  void initState() {
    super.initState();
    _loadAssignmentAndMeter();
  }

  @override
  void dispose() {
    _readingCtrl.dispose();
    _remarksCtrl.dispose();
    super.dispose();
  }

  // ── تحميل بيانات التكليف والعداد ─────────────────────────────────────────

  Future<void> _loadAssignmentAndMeter() async {
    setState(() {
      _loadingMeter = true;
      _loadError = null;
    });

    try {
      final repo = ref.read(assignmentRepositoryProvider);

      // استخدام getById أولاً، ثم البحث برقم العداد أو QR
      final assignment =
          await repo.getById(widget.assignmentId) ??
          await repo.lookupByMeterNumber(widget.assignmentId) ??
          await repo.resolveQr(widget.assignmentId);

      if (assignment == null) {
        setState(() => _loadError = 'لم يُعثر على التكليف');
        return;
      }

      _MeterInfo meterInfo;
      try {
        meterInfo = await _fetchMeterInfoFromOdoo(assignment.meter.meterNumber);
      } catch (_) {
        meterInfo = _MeterInfo.offline();
      }

      setState(() {
        _assignment = assignment;
        _meterInfo = meterInfo;
        _loadingMeter = false;
      });

      // ── منع القراءة المكررة ──────────────────────────────────────────────
      if (meterInfo.alreadyReadThisPeriod && mounted) {
        await showDialog(
          context: context,
          barrierDismissible: false,
          builder: (_) => AlertDialog(
            icon: const Icon(Icons.block, color: Colors.red, size: 40),
            title: const Text('تم أخذ القراءة مسبقاً'),
            content: Text(
              'لقد تم أخذ قراءة هذا العداد (${assignment.meter.meterNumber}) '
              'في الفترة الحالية بالفعل.\n\n'
              'القراءة المسجّلة: ${meterInfo.lastReadingValue} kWh',
            ),
            actions: [
              FilledButton(
                onPressed: () {
                  Navigator.of(context).pop();
                  if (mounted) context.pop();
                },
                child: const Text('العودة'),
              ),
            ],
          ),
        );
      }
    } on OdooSessionExpiredException {
      setState(() => _loadError = 'انتهت الجلسة — سجّل الدخول مجدداً');
    } catch (e) {
      setState(() {
        _loadingMeter = false;
        _meterInfo = _MeterInfo.offline();
      });
    }
  }

  Future<_MeterInfo> _fetchMeterInfoFromOdoo(String meterNumber) async {
    final client = ref.read(odooApiClientProvider);

    // جلب الفترة الحالية
    final periodResult =
        await client.postJson('/api/v1/utility/reading/periods', {});
    final periods = (periodResult['periods'] as List?) ?? [];
    int? currentPeriodId;
    if (periods.isNotEmpty) {
      final current = periods
          .cast<Map<String, dynamic>>()
          .firstWhere((p) => p['is_current'] == true,
              orElse: () => periods.first as Map<String, dynamic>);
      currentPeriodId = current['id'] as int?;
    }

    // جلب آخر قراءة للعداد
    final lookupResult = await client.postJson(
        '/api/v1/utility/reading/meter/lookup', {'meter_code': meterNumber});

    final lastValue =
        (lookupResult['last_reading_value'] as num?)?.toDouble() ?? 0.0;
    final lastDate = lookupResult['last_reading_date'] as String?;
    final avgConsumption =
        (lookupResult['avg_consumption'] as num?)?.toDouble() ?? 0.0;

    // التحقق من القراءة المكررة
    bool alreadyRead = false;
    if (currentPeriodId != null) {
      try {
        final checkResult = await client.postJson(
            '/api/v1/utility/reading/check_period_reading', {
          'meter_code': meterNumber,
          'period_id': currentPeriodId,
        });
        alreadyRead = checkResult['has_reading'] == true;
      } catch (_) {}
    }

    return _MeterInfo(
      lastReadingValue: lastValue,
      lastReadingDate: lastDate,
      avgConsumption: avgConsumption,
      currentPeriodId: currentPeriodId,
      alreadyReadThisPeriod: alreadyRead,
    );
  }

  // ── التقاط الصورة + Watermark ─────────────────────────────────────────────

  Future<void> _capturePhotoWithWatermark() async {
    final cameras = await availableCameras();
    if (cameras.isEmpty) {
      _showSnack('الكاميرا غير متاحة');
      return;
    }
    if (!mounted) return;
    final result = await Navigator.of(context).push<File>(
      MaterialPageRoute(builder: (_) => _CameraScreen(camera: cameras.first)),
    );
    if (result == null) return;
    final watermarked = await _addWatermark(result);
    setState(() => _capturedImage = watermarked);
  }

  Future<File> _addWatermark(File imageFile) async {
    final bytes = await imageFile.readAsBytes();
    final original = img.decodeImage(bytes);
    if (original == null) return imageFile;

    final now = DateTime.now();
    final dateStr = DateFormat('yyyy-MM-dd HH:mm:ss').format(now);
    final meterNum = _assignment?.meter.meterNumber ?? '';

    img.drawString(
      original,
      '$dateStr  عداد: $meterNum',
      font: img.arial14,
      x: 10,
      y: original.height - 30,
      color: img.ColorRgba8(255, 255, 0, 220),
    );

    final dir = await getApplicationDocumentsDirectory();
    final path = '${dir.path}/reading_${const Uuid().v4()}.jpg';
    final outFile = File(path);
    await outFile.writeAsBytes(img.encodeJpg(original, quality: 85));
    return outFile;
  }

  // ── حفظ القراءة ──────────────────────────────────────────────────────────

  Future<void> _saveReading() async {
    if (!_formKey.currentState!.validate()) return;

    if (_capturedImage == null) {
      _showSnack('يجب تصوير العداد قبل الحفظ');
      return;
    }
    if (_meterInfo?.alreadyReadThisPeriod == true) {
      _showSnack('تم أخذ هذه القراءة مسبقاً في الفترة الحالية');
      return;
    }

    final readingValue = double.tryParse(_readingCtrl.text.trim()) ?? 0;
    final prevValue = _meterInfo?.lastReadingValue ?? 0;
    if (readingValue < prevValue) {
      _showSnack(
          'القراءة الحالية ($readingValue) أقل من السابقة ($prevValue kWh)!',
          isError: true);
      return;
    }

    setState(() => _savingReading = true);

    try {
      final assignment = _assignment!;

      final reading = MeterReading(
        id: const Uuid().v4(),
        meterRemoteId: assignment.meter.remoteId,
        meterNumber: assignment.meter.meterNumber,
        readingValue: readingValue,
        readingDate: DateTime.now(),
        category: ReadingCategory.customer,
        isEstimated: false,
        remarks: _remarksCtrl.text.trim().isEmpty
            ? null
            : _remarksCtrl.text.trim(),
        imageLocalPath: _capturedImage!.path,
        photoUuid: const Uuid().v4(),
        syncStatus: ReadingSyncStatus.draft,
      );

      // 1. حفظ محلي
      await ref.read(readingRepositoryProvider).saveDraft(reading);

      // 2. تحديث حالة التكليف → read
      await ref
          .read(assignmentRepositoryProvider)
          .markStatus(assignment.id, AssignmentStatus.read);

      // 3. إضافة لطابور المزامنة
      await ref.read(syncEngineProvider).enqueue(reading);

      if (mounted) {
        _showSnack('تم حفظ القراءة وإضافتها لطابور الرفع ✓');
        await Future.delayed(const Duration(milliseconds: 800));
        context.pop();
      }
    } catch (e) {
      _showSnack('خطأ في الحفظ: $e', isError: true);
    } finally {
      if (mounted) setState(() => _savingReading = false);
    }
  }

  // ── UI ────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('إدخال القراءة'),
        centerTitle: true,
      ),
      body: _loadingMeter
          ? const Center(child: CircularProgressIndicator())
          : _loadError != null
              ? _ErrorState(
                  message: _loadError!, onRetry: _loadAssignmentAndMeter)
              : _buildForm(scheme),
    );
  }

  Widget _buildForm(ColorScheme scheme) {
    final assignment = _assignment!;
    final meterInfo = _meterInfo!;

    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // بطاقة المشترك
          Card(
            child: ListTile(
              leading:
                  const CircleAvatar(child: Icon(Icons.person_outline)),
              title: Text(assignment.customer.name,
                  style: const TextStyle(fontWeight: FontWeight.bold)),
              subtitle: Text(
                'عداد ${assignment.meter.meterNumber} · حساب ${assignment.customer.accountNumber}',
              ),
            ),
          ),
          const SizedBox(height: 12),

          // القراءة السابقة
          Card(
            color: scheme.secondaryContainer.withOpacity(0.4),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                children: [
                  Icon(Icons.history, color: scheme.secondary),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('القراءة السابقة',
                            style: TextStyle(
                                color: scheme.secondary,
                                fontWeight: FontWeight.w600)),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Text('${meterInfo.lastReadingValue} kWh',
                                style: const TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.bold)),
                            if (meterInfo.avgConsumption > 0) ...[
                              const SizedBox(width: 12),
                              Text(
                                '· المتوسط ${meterInfo.avgConsumption.toStringAsFixed(0)} kWh',
                                style: TextStyle(
                                    color: scheme.outline, fontSize: 12),
                              ),
                            ],
                          ],
                        ),
                        if (meterInfo.isOffline)
                          Text('⚠ وضع غير متصل',
                              style: TextStyle(
                                  color: scheme.error, fontSize: 11)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),

          // حقل القراءة الحالية
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('القراءة الحالية (kWh)',
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _readingCtrl,
                    keyboardType: const TextInputType.numberWithOptions(
                        decimal: true),
                    decoration: InputDecoration(
                      hintText: 'أدخل قراءة العداد',
                      suffixText: 'kWh',
                      border: const OutlineInputBorder(),
                      filled: true,
                      fillColor:
                          scheme.surfaceVariant.withOpacity(0.3),
                    ),
                    style: const TextStyle(
                        fontSize: 22, fontWeight: FontWeight.bold),
                    validator: (v) {
                      if (v == null || v.isEmpty) return 'القراءة مطلوبة';
                      final val = double.tryParse(v);
                      if (val == null) return 'رقم غير صحيح';
                      if (val < meterInfo.lastReadingValue) {
                        return 'يجب أن تكون >= ${meterInfo.lastReadingValue} kWh';
                      }
                      return null;
                    },
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),

          // تصوير العداد
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text('صورة العداد',
                          style:
                              Theme.of(context).textTheme.titleMedium),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: _capturedImage != null
                              ? Colors.green.withOpacity(0.15)
                              : scheme.errorContainer,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          _capturedImage != null ? 'تم ✓' : 'مطلوب',
                          style: TextStyle(
                            fontSize: 11,
                            color: _capturedImage != null
                                ? Colors.green
                                : scheme.error,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  if (_capturedImage != null) ...[
                    ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: Image.file(_capturedImage!,
                          height: 180,
                          width: double.infinity,
                          fit: BoxFit.cover),
                    ),
                    const SizedBox(height: 8),
                  ],
                  OutlinedButton.icon(
                    onPressed: _capturePhotoWithWatermark,
                    icon: Icon(_capturedImage != null
                        ? Icons.refresh
                        : Icons.camera_alt_outlined),
                    label: Text(_capturedImage != null
                        ? 'إعادة التصوير'
                        : 'تصوير العداد'),
                    style: OutlinedButton.styleFrom(
                        minimumSize: const Size.fromHeight(44)),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),

          // ملاحظات
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: TextFormField(
                controller: _remarksCtrl,
                maxLines: 2,
                decoration: const InputDecoration(
                  labelText: 'ملاحظات (اختياري)',
                  border: OutlineInputBorder(),
                ),
              ),
            ),
          ),
          const SizedBox(height: 24),

          // زر الحفظ
          FilledButton.icon(
            onPressed:
                (_savingReading || meterInfo.alreadyReadThisPeriod)
                    ? null
                    : _saveReading,
            icon: _savingReading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.cloud_upload_outlined),
            label: Text(_savingReading
                ? 'جاري الحفظ...'
                : 'حفظ القراءة وإضافتها للرفع'),
            style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(52)),
          ),

          if (meterInfo.isOffline)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.cloud_off, size: 14, color: scheme.outline),
                  const SizedBox(width: 4),
                  Text(
                    'وضع غير متصل — تُرفع عند توفر الشبكة',
                    style:
                        TextStyle(fontSize: 11, color: scheme.outline),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  void _showSnack(String msg, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg),
      backgroundColor:
          isError ? Theme.of(context).colorScheme.error : null,
    ));
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// شاشة الكاميرا
// ─────────────────────────────────────────────────────────────────────────────

class _CameraScreen extends StatefulWidget {
  final CameraDescription camera;
  const _CameraScreen({required this.camera});

  @override
  State<_CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<_CameraScreen> {
  late CameraController _controller;
  late Future<void> _initFuture;
  bool _taking = false;

  @override
  void initState() {
    super.initState();
    _controller = CameraController(widget.camera, ResolutionPreset.medium,
        enableAudio: false);
    _initFuture = _controller.initialize();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _shoot() async {
    if (_taking) return;
    setState(() => _taking = true);
    try {
      final xfile = await _controller.takePicture();
      if (mounted) Navigator.of(context).pop(File(xfile.path));
    } catch (e) {
      setState(() => _taking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: FutureBuilder<void>(
        future: _initFuture,
        builder: (_, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(
                child:
                    CircularProgressIndicator(color: Colors.white));
          }
          return Stack(
            fit: StackFit.expand,
            children: [
              CameraPreview(_controller),
              Positioned(
                bottom: 32,
                left: 0,
                right: 0,
                child: Center(
                  child: GestureDetector(
                    onTap: _shoot,
                    child: Container(
                      width: 72,
                      height: 72,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: Colors.white.withOpacity(0.9),
                        border:
                            Border.all(color: Colors.white, width: 3),
                      ),
                      child: _taking
                          ? const Padding(
                              padding: EdgeInsets.all(16),
                              child: CircularProgressIndicator(
                                  strokeWidth: 2))
                          : const Icon(Icons.camera_alt,
                              size: 36, color: Colors.black),
                    ),
                  ),
                ),
              ),
              Positioned(
                top: 48,
                right: 16,
                child: IconButton(
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.close,
                      color: Colors.white, size: 30),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// خطأ
// ─────────────────────────────────────────────────────────────────────────────

class _ErrorState extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorState({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.error_outline, size: 48, color: Colors.red),
          const SizedBox(height: 12),
          Text(message),
          const SizedBox(height: 16),
          FilledButton(
              onPressed: onRetry,
              child: const Text('إعادة المحاولة')),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// بيانات العداد من Odoo
// ─────────────────────────────────────────────────────────────────────────────

class _MeterInfo {
  final double lastReadingValue;
  final String? lastReadingDate;
  final double avgConsumption;
  final int? currentPeriodId;
  final bool alreadyReadThisPeriod;
  final bool isOffline;

  const _MeterInfo({
    required this.lastReadingValue,
    this.lastReadingDate,
    this.avgConsumption = 0,
    this.currentPeriodId,
    this.alreadyReadThisPeriod = false,
    this.isOffline = false,
  });

  factory _MeterInfo.offline() =>
      const _MeterInfo(lastReadingValue: 0, isOffline: true);
}
