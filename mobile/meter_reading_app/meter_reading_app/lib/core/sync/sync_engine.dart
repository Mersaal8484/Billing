import 'dart:async';
import 'dart:math';

import '../../features/readings/data/mock_reading_repository.dart';
import '../../features/readings/domain/reading.dart';

enum ConnectivityState { online, offline }

class PipelineStats {
  final int pending;
  final int inProgress;
  final int succeeded;
  final int failed;
  const PipelineStats(
      {this.pending = 0,
      this.inProgress = 0,
      this.succeeded = 0,
      this.failed = 0});
}

class SyncSnapshot {
  final ConnectivityState connectivity;
  final PipelineStats dataPipeline;
  final PipelineStats imagePipeline;
  final DateTime? lastSuccessfulSync;
  const SyncSnapshot({
    required this.connectivity,
    required this.dataPipeline,
    required this.imagePipeline,
    this.lastSuccessfulSync,
  });
}

/// Simulates the two-pipeline synchronization architecture described in
/// the spec:
///  - Pipeline A (reading data): small JSON payloads, immediate, highest
///    priority, mirrors /api/v1/utility/reading/batch/upload_data.
///  - Pipeline B (images): independent queue, resumable, retried on its
///    own schedule, mirrors /api/v1/utility/reading/batch/upload_image.
/// Neither pipeline waits on the other. A reading can be "data_synced"
/// while its photo is still climbing the image queue in the background.
///
/// This is a local simulation only — no network calls are made. The real
/// engine will replace `_simulateUpload*` with calls through the
/// (not-yet-implemented) ApiClient, keyed by the same idempotency tokens
/// generated here, so retries remain safe to replay server-side.
class SyncEngine {
  final MockReadingRepository readingRepository;
  final _random = Random();
  final _snapshotController = StreamController<SyncSnapshot>.broadcast();
  Timer? _dataTimer;
  Timer? _imageTimer;
  ConnectivityState _connectivity = ConnectivityState.online;
  DateTime? _lastSuccess;

  final List<_QueueEntry> _dataQueue = [];
  final List<_QueueEntry> _imageQueue = [];

  SyncEngine(this.readingRepository);

  Stream<SyncSnapshot> get snapshots => _snapshotController.stream;

  void setConnectivity(ConnectivityState state) {
    _connectivity = state;
    _publish();
  }

  void start() {
    _dataTimer =
        Timer.periodic(const Duration(seconds: 2), (_) => _tickDataPipeline());
    _imageTimer =
        Timer.periodic(const Duration(seconds: 4), (_) => _tickImagePipeline());
    _publish();
  }

  void stop() {
    _dataTimer?.cancel();
    _imageTimer?.cancel();
  }

  /// Called by the UI when a reading becomes ready to leave the device.
  void enqueue(MeterReading reading) {
    final idempotencyKey =
        '${reading.id}-${DateTime.now().microsecondsSinceEpoch}';
    _dataQueue.add(_QueueEntry(reading.id, idempotencyKey));
    readingRepository.updateStatus(
        reading.id, ReadingSyncStatus.pendingDataSync);
    if (reading.imageLocalPath != null) {
      _imageQueue.add(_QueueEntry(reading.id, idempotencyKey));
    }
    _publish();
  }

  void retryFailed() {
    for (final r in readingRepository.all) {
      if (r.syncStatus == ReadingSyncStatus.error) {
        enqueue(r);
      }
    }
  }

  void _tickDataPipeline() {
    if (_connectivity == ConnectivityState.offline || _dataQueue.isEmpty) {
      _publish();
      return;
    }
    final entry = _dataQueue.removeAt(0);
    readingRepository.updateStatus(
        entry.readingId, ReadingSyncStatus.pendingDataSync);
    // Simulate network round trip with an occasional transient failure.
    final willFail = _random.nextDouble() < 0.12 && entry.attempts < 1;
    Future.delayed(const Duration(milliseconds: 600), () {
      if (willFail) {
        entry.attempts++;
        entry.lastError = 'انقطاع مؤقت في الشبكة أثناء رفع البيانات';
        if (entry.attempts <= 3) {
          _dataQueue.add(entry); // requeue with backoff-by-position
        } else {
          readingRepository.updateStatus(
              entry.readingId, ReadingSyncStatus.error,
              error: entry.lastError);
        }
      } else {
        readingRepository.updateStatus(
            entry.readingId, ReadingSyncStatus.dataSynced);
        _lastSuccess = DateTime.now();
      }
      _publish();
    });
    _publish();
  }

  void _tickImagePipeline() {
    if (_connectivity == ConnectivityState.offline || _imageQueue.isEmpty) {
      _publish();
      return;
    }
    final entry = _imageQueue.removeAt(0);
    final willFail = _random.nextDouble() < 0.15 && entry.attempts < 2;
    Future.delayed(const Duration(milliseconds: 900), () {
      if (willFail) {
        entry.attempts++;
        entry.lastError = 'فشل استئناف رفع الصورة — سيُعاد المحاولة تلقائياً';
        _imageQueue.add(entry); // resumable: same idempotency key on retry
      } else {
        final current = readingRepository.all.firstWhere(
            (r) => r.id == entry.readingId,
            orElse: () => throw StateError('missing'));
        final finalStatus = current.syncStatus == ReadingSyncStatus.error
            ? ReadingSyncStatus.error
            : ReadingSyncStatus.synced;
        readingRepository.updateStatus(entry.readingId, finalStatus);
      }
      _publish();
    });
    _publish();
  }

  void _publish() {
    PipelineStats statsFor(List<_QueueEntry> q, bool isImage) {
      final all = readingRepository.all;
      final succeeded = all
          .where((r) => isImage
              ? r.syncStatus == ReadingSyncStatus.synced
              : r.syncStatus == ReadingSyncStatus.dataSynced ||
                  r.syncStatus == ReadingSyncStatus.synced)
          .length;
      final failed =
          all.where((r) => r.syncStatus == ReadingSyncStatus.error).length;
      return PipelineStats(
          pending: q.length,
          inProgress: 0,
          succeeded: succeeded,
          failed: failed);
    }

    _snapshotController.add(SyncSnapshot(
      connectivity: _connectivity,
      dataPipeline: statsFor(_dataQueue, false),
      imagePipeline: statsFor(_imageQueue, true),
      lastSuccessfulSync: _lastSuccess,
    ));
  }

  void dispose() {
    stop();
    _snapshotController.close();
  }
}

class _QueueEntry {
  final String readingId;
  final String idempotencyKey;
  int attempts = 0;
  String? lastError;
  _QueueEntry(this.readingId, this.idempotencyKey);
}
