import 'dart:async';
import 'dart:io';

import '../../features/readings/data/drift_reading_repository.dart';
import '../../features/readings/domain/reading.dart';
import '../database/app_database.dart';
import '../network/odoo_api_client.dart';
import '../network/reading_api_service.dart';
import 'sync_settings_service.dart';

enum ConnectivityState { online, offline }

class PipelineStats {
  final int pending;
  final int inProgress;
  final int succeeded;
  final int failed;
  const PipelineStats({
    this.pending = 0,
    this.inProgress = 0,
    this.succeeded = 0,
    this.failed = 0,
  });
}

class SyncSnapshot {
  final ConnectivityState connectivity;
  final PipelineStats batchPipeline;
  final DateTime? lastSuccessfulSync;

  /// true = انتهت الجلسة → وجّه المستخدم لشاشة تسجيل الدخول
  final bool sessionExpired;

  const SyncSnapshot({
    required this.connectivity,
    required this.batchPipeline,
    this.lastSuccessfulSync,
    this.sessionExpired = false,
  });
}

/// SyncEngine الإنتاجي — يستخدم [DriftReadingRepository] + [ReadingApiService].
///
/// ملاحظة meterNumber: الخادم يطابق القراءات بالعداد عبر
/// `utility.meter.meter_number` (نص مثل "100004") وليس الـ id الرقمي.
/// حتى يُضاف حقل `meterNumber` لـ [MeterReading]، نستخدم
/// `meterRemoteId.toString()` كحل مؤقت — تحقق من أن meter_number في Odoo
/// يطابق الـ DB id قبل الإنتاج.
class SyncEngine {
  final DriftReadingRepository readingRepository;
  final AppDatabase db;
  final SyncSettingsService settingsService;
  final ReadingApiService readingApi;

  SyncSnapshot _last = const SyncSnapshot(
    connectivity: ConnectivityState.online,
    batchPipeline: PipelineStats(),
  );

  final _ctrl = StreamController<SyncSnapshot>.broadcast();
  Timer? _timer;
  ConnectivityState _connectivity = ConnectivityState.online;
  DateTime? _lastSuccess;

  SyncEngine(this.readingRepository, this.db, this.settingsService, this.readingApi);

  Stream<SyncSnapshot> get snapshots async* {
    yield _last;
    yield* _ctrl.stream;
  }

  void setConnectivity(ConnectivityState state) {
    _connectivity = state;
    _publish();
    if (state == ConnectivityState.online) _tick();
  }

  void start() {
    _timer = Timer.periodic(const Duration(seconds: 15), (_) => _tick());
    _publish();
  }

  void stop() => _timer?.cancel();

  void dispose() {
    stop();
    _ctrl.close();
  }

  /// الواجهة الرئيسية: يُستدعى بعد حفظ القراءة من شاشة إدخال القراءة
  Future<void> enqueue(MeterReading reading) async {
    await readingRepository.updateSyncStatus(
        reading.id, ReadingSyncStatus.pendingDataSync);
    _publish();

    final mode = await settingsService.getSyncMode();
    if (mode == SyncMode.immediate && _connectivity == ConnectivityState.online) {
      await _upload([reading]);
      return;
    }
    await _checkThreshold();
  }

  void retryFailed() async {
    final failed = await readingRepository.getByStatus('error');
    for (final r in failed) {
      enqueue(r);
    }
  }

  /// زر "مزامنة الآن" في sync_center_screen
  Future<void> syncNow() async {
    final mode = await settingsService.getSyncMode();
    if (mode == SyncMode.immediate) {
      await _uploadPendingSingles();
    } else {
      await _buildAndUploadBatch();
    }
  }

  // ── Pipeline internals ────────────────────────────────────────────────────

  Future<void> _tick() async {
    if (_connectivity == ConnectivityState.offline) return;
    final mode = await settingsService.getSyncMode();
    if (mode == SyncMode.immediate) {
      await _uploadPendingSingles();
    } else {
      await _checkThreshold();
    }
  }

  Future<void> _checkThreshold() async {
    final threshold = await settingsService.getBatchSize();
    final pending = await readingRepository.getByStatus('pending');
    if (pending.length >= threshold) await _buildAndUploadBatch();
  }

  Future<void> _uploadPendingSingles() async {
    if (_connectivity == ConnectivityState.offline) return;
    final pending = await readingRepository.getByStatus('pending');
    for (final r in pending) {
      await _upload([r]);
    }
  }

  Future<void> _buildAndUploadBatch() async {
    if (_connectivity == ConnectivityState.offline) return;
    final size = await settingsService.getBatchSize();
    final pending = await readingRepository.getByStatus('pending');
    if (pending.isEmpty) return;
    await _upload(pending.take(size).toList());
  }

  /// المسار الموحد للرفع:
  /// 1. تحديد الفترة الحالية
  /// 2. إنشاء batch على الخادم
  /// 3. رفع بيانات القراءات (JSON)
  /// 4. رفع صور كل قراءة (multipart)
  /// 5. تأكيد الـ batch
  Future<void> _upload(List<MeterReading> readings) async {
    if (readings.isEmpty) return;

    // علامة "جاري الرفع"
    for (final r in readings) {
      await readingRepository.updateSyncStatus(
          r.id, ReadingSyncStatus.pendingDataSync);
    }
    _publish();

    try {
      final periodId = await readingApi.getCurrentPeriodId();
      final batchResult = await readingApi.createBatch(dateRangeId: periodId);
      final batchId = batchResult['batch_id'] as int;

      // رفع البيانات
      final payloads = readings
          .map((r) => MeterReadingPayload(
                meterNumber: r.effectiveMeterNumber,
                readingValue: r.readingValue,
                readingDate: r.readingDate,
                readingCategory: r.category.name,
                clientReadingUuid: r.id,
              ))
          .toList();
      await readingApi.uploadData(batchId: batchId, readings: payloads);

      // رفع الصور
      for (final r in readings) {
        if (r.imageLocalPath == null) continue;
        final file = File(r.imageLocalPath!);
        if (!await file.exists()) continue;
        await readingApi.uploadImageMultipart(
          batchId: batchId,
          imageFile: file,
          readingUuid: r.id,
        );
      }

      // تأكيد الـ batch
      await readingApi.confirmBatch(batchId);

      // تحديث الحالة إلى synced
      for (final r in readings) {
        await readingRepository.updateSyncStatus(r.id, ReadingSyncStatus.synced);
      }
      _lastSuccess = DateTime.now();
      _publish();
    } on OdooSessionExpiredException catch (e) {
      for (final r in readings) {
        await readingRepository.updateSyncStatus(
            r.id, ReadingSyncStatus.error, error: e.toString());
      }
      // أبلغ الـ UI بانتهاء الجلسة → يُعيد التوجيه لشاشة تسجيل الدخول
      _last = SyncSnapshot(
        connectivity: _connectivity,
        batchPipeline: _last.batchPipeline,
        lastSuccessfulSync: _lastSuccess,
        sessionExpired: true,
      );
      _ctrl.add(_last);
    } catch (e) {
      for (final r in readings) {
        await readingRepository.updateSyncStatus(
            r.id, ReadingSyncStatus.error, error: e.toString());
      }
      _publish();
    }
  }

  void _publish() async {
    final pending = await readingRepository.getByStatus('pending');
    final synced = await readingRepository.getByStatus('synced');
    final failed = await readingRepository.getByStatus('error');

    _last = SyncSnapshot(
      connectivity: _connectivity,
      batchPipeline: PipelineStats(
        pending: pending.length,
        inProgress: 0,
        succeeded: synced.length,
        failed: failed.length,
      ),
      lastSuccessfulSync: _lastSuccess,
    );
    _ctrl.add(_last);
  }
}
