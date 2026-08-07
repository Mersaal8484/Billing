import 'dart:async';

import 'package:drift/drift.dart' as drift;
import 'package:path_provider/path_provider.dart';

import '../../features/readings/data/mock_reading_repository.dart';
import '../../features/readings/domain/reading.dart';
import '../database/app_database.dart';
import '../image/image_processing_service.dart';
import 'reading_archive_builder.dart';
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
  const SyncSnapshot({
    required this.connectivity,
    required this.batchPipeline,
    this.lastSuccessfulSync,
  });
}

class SyncEngine {
  final MockReadingRepository readingRepository;
  final AppDatabase db;
  final SyncSettingsService settingsService;
  final ReadingArchiveBuilder _archiveBuilder = ReadingArchiveBuilder();
  // Use a late-initialized seed so new subscribers always get the current value.
  SyncSnapshot _lastSnapshot = const SyncSnapshot(
    connectivity: ConnectivityState.online,
    batchPipeline: PipelineStats(),
  );
  final _snapshotController = StreamController<SyncSnapshot>.broadcast();
  Timer? _batchTimer;
  ConnectivityState _connectivity = ConnectivityState.online;
  DateTime? _lastSuccess;

  SyncEngine(this.readingRepository, this.db, this.settingsService);

  /// Always replays the last value to new subscribers.
  Stream<SyncSnapshot> get snapshots async* {
    yield _lastSnapshot; // seed: immediately gives the current state
    yield* _snapshotController.stream;
  }

  void setConnectivity(ConnectivityState state) {
    _connectivity = state;
    _publish();
    if (state == ConnectivityState.online) {
      _tickBatchPipeline();
    }
  }

  void start() {
    _batchTimer = Timer.periodic(
        const Duration(seconds: 15), (_) => _tickBatchPipeline());
    _publish();
  }

  void stop() {
    _batchTimer?.cancel();
  }

  /// Called by the UI/Repository when a reading becomes ready to leave the device.
  Future<void> enqueue(MeterReading reading) async {
    readingRepository.updateStatus(
        reading.id, ReadingSyncStatus.pendingDataSync);

    // In a fully wired app, the Reading would already be in Drift.
    // Since we are mocking, we ensure it's mirrored to Drift for the batch builder.
    try {
      await db.into(db.readings).insert(
            ReadingsCompanion.insert(
              id: reading.id,
              meterRemoteId: reading.meterRemoteId,
              readingValue: reading.readingValue,
              readingDate: reading.readingDate,
              readingCategory: drift.Value(reading.category.name),
              isEstimated: drift.Value(reading.isEstimated),
              remarks: drift.Value(reading.remarks),
              imageLocalPath: drift.Value(reading.imageLocalPath),
              syncStatus: const drift.Value('pending'),
              createdAt: DateTime.now(),
              updatedAt: DateTime.now(),
            ),
            mode: drift.InsertMode.insertOrReplace,
          );
    } catch (e) {
      // Ignored if meter doesn't exist in mock DB etc.
    }

    _publish();
    final mode = await settingsService.getSyncMode();
    if (mode == SyncMode.immediate) {
      if (_connectivity == ConnectivityState.online) {
        await _uploadSingleReadingImmediately(reading);
      }
      return;
    }

    await _checkThresholds();
  }

  void retryFailed() {
    for (final r in readingRepository.all) {
      if (r.syncStatus == ReadingSyncStatus.error) {
        enqueue(r);
      }
    }
  }

  /// Forces an immediate sync of whatever is pending.
  Future<void> syncNow() async {
    final mode = await settingsService.getSyncMode();
    if (mode == SyncMode.immediate) {
      await _uploadPendingSingles();
      return;
    }

    await _buildAndUploadBatch();
  }

  Future<void> _checkThresholds() async {
    if (await settingsService.getSyncMode() != SyncMode.batch) {
      return;
    }

    final batchThreshold = await settingsService.getBatchSize();
    final pendingCount = await _getPendingCount();
    if (pendingCount >= batchThreshold) {
      await _buildAndUploadBatch();
    }
  }

  Future<void> _tickBatchPipeline() async {
    if (_connectivity == ConnectivityState.offline) return;

    final mode = await settingsService.getSyncMode();
    if (mode == SyncMode.immediate) {
      await _uploadPendingSingles();
      return;
    }

    final batchThreshold = await settingsService.getBatchSize();
    final pendingCount = await _getPendingCount();
    if (pendingCount >= batchThreshold) {
      await _buildAndUploadBatch();
    }
  }

  Future<int> _getPendingCount() async {
    final query = db.select(db.readings)
      ..where((t) => t.syncStatus.equals('pending'));
    final results = await query.get();
    return results.length;
  }

  Future<void> _buildAndUploadBatch() async {
    if (_connectivity == ConnectivityState.offline) return;

    final batchSize = await settingsService.getBatchSize();
    final pendingReadings = await (db.select(db.readings)
          ..where((t) => t.syncStatus.equals('pending'))
          ..limit(batchSize))
        .get();

    if (pendingReadings.isEmpty) return;

    final items = pendingReadings.map((r) {
      final meter = readingRepository.all.firstWhere((mem) => mem.id == r.id,
          orElse: () => MeterReading(
                id: r.id,
                meterRemoteId: r.meterRemoteId,
                readingValue: r.readingValue,
                readingDate: r.readingDate,
                category: ReadingCategory.values.firstWhere(
                    (c) => c.name == r.readingCategory,
                    orElse: () => ReadingCategory.customer),
                isEstimated: r.isEstimated,
                remarks: r.remarks,
                imageLocalPath: r.imageLocalPath,
                photoUuid: r.id, // use reading id as photo UUID fallback
              ));
      return ArchiveReadingItem(
        reading: meter,
        cycleId: 1,
        customerId: 1,
      );
    }).toList();

    try {
      final destDir = await getApplicationDocumentsDirectory();
      final archives = await _archiveBuilder.build(
        items: items,
        policy: SyncBatchPolicy(
          maxImagesPerArchive: batchSize,
          maxArchiveBytes: 5 * 1024 * 1024,
          maxImageBytes: ImageProcessingService.maxBytes,
        ),
        destination: destDir,
      );

      for (final archive in archives) {
        // Track batch in DB
        await db.into(db.syncBatches).insert(
              SyncBatchesCompanion.insert(
                id: archive.batchUuid,
                status: const drift.Value('uploading'),
                archivePath: drift.Value(archive.archiveFile.path),
                readingCount: archive.readingIds.length,
                createdAt: DateTime.now(),
              ),
            );

        // Update readings with batch ID
        await (db.update(db.readings)
              ..where((t) => t.id.isIn(archive.readingIds)))
            .write(ReadingsCompanion(
                syncBatchId: drift.Value(archive.batchUuid),
                syncStatus: const drift.Value('uploading')));

        // Mocking multipart upload success
        await Future.delayed(const Duration(seconds: 2));

        // Update successful
        await (db.update(db.syncBatches)
              ..where((t) => t.id.equals(archive.batchUuid)))
            .write(const SyncBatchesCompanion(status: drift.Value('success')));

        await (db.update(db.readings)
              ..where((t) => t.syncBatchId.equals(archive.batchUuid)))
            .write(const ReadingsCompanion(syncStatus: drift.Value('synced')));

        for (final id in archive.readingIds) {
          readingRepository.updateStatus(id, ReadingSyncStatus.synced);
        }

        // Cleanup ZIP and images
        if (await archive.archiveFile.exists()) {
          await archive.archiveFile.delete();
        }
        _lastSuccess = DateTime.now();
      }
    } catch (e) {
      // Handle failures
      for (final r in pendingReadings) {
        readingRepository.updateStatus(r.id, ReadingSyncStatus.error,
            error: e.toString());
        await (db.update(db.readings)..where((t) => t.id.equals(r.id))).write(
            ReadingsCompanion(
                syncStatus: const drift.Value('error'),
                lastError: drift.Value(e.toString())));
      }
    }

    _publish();
  }

  Future<void> _uploadPendingSingles() async {
    if (_connectivity == ConnectivityState.offline) return;

    final pendingReadings = await (db.select(db.readings)
          ..where((table) => table.syncStatus.equals('pending'))
          ..orderBy([(table) => drift.OrderingTerm.asc(table.createdAt)]))
        .get();

    for (final row in pendingReadings) {
      await _uploadSingleReadingImmediately(_meterReadingFromRow(row));
    }
  }

  Future<void> _uploadSingleReadingImmediately(MeterReading reading) async {
    if (_connectivity == ConnectivityState.offline) return;

    try {
      await (db.update(db.readings)
            ..where((table) => table.id.equals(reading.id)))
          .write(ReadingsCompanion(
        syncStatus: const drift.Value('uploading'),
        updatedAt: drift.Value(DateTime.now()),
      ));

      _publish();
      await Future.delayed(const Duration(seconds: 2));

      await (db.update(db.readings)
            ..where((table) => table.id.equals(reading.id)))
          .write(ReadingsCompanion(
        syncStatus: const drift.Value('synced'),
        updatedAt: drift.Value(DateTime.now()),
      ));
      readingRepository.updateStatus(reading.id, ReadingSyncStatus.synced);
      _lastSuccess = DateTime.now();
    } catch (error) {
      readingRepository.updateStatus(
        reading.id,
        ReadingSyncStatus.error,
        error: error.toString(),
      );
      await (db.update(db.readings)
            ..where((table) => table.id.equals(reading.id)))
          .write(ReadingsCompanion(
        syncStatus: const drift.Value('error'),
        lastError: drift.Value(error.toString()),
        updatedAt: drift.Value(DateTime.now()),
      ));
    }

    _publish();
  }

  MeterReading _meterReadingFromRow(Reading row) {
    return readingRepository.all.firstWhere(
      (reading) => reading.id == row.id,
      orElse: () => MeterReading(
        id: row.id,
        meterRemoteId: row.meterRemoteId,
        readingValue: row.readingValue,
        readingDate: row.readingDate,
        category: ReadingCategory.values.firstWhere(
          (category) => category.name == row.readingCategory,
          orElse: () => ReadingCategory.customer,
        ),
        isEstimated: row.isEstimated,
        remarks: row.remarks,
        imageLocalPath: row.imageLocalPath,
        photoUuid: row.id,
        syncStatus: ReadingSyncStatus.pendingDataSync,
      ),
    );
  }

  void _publish() {
    final all = readingRepository.all;
    final pending = all
        .where((r) => r.syncStatus == ReadingSyncStatus.pendingDataSync)
        .length;
    final succeeded =
        all.where((r) => r.syncStatus == ReadingSyncStatus.synced).length;
    final failed =
        all.where((r) => r.syncStatus == ReadingSyncStatus.error).length;

    _lastSnapshot = SyncSnapshot(
      connectivity: _connectivity,
      batchPipeline: PipelineStats(
        pending: pending,
        inProgress: 0,
        succeeded: succeeded,
        failed: failed,
      ),
      lastSuccessfulSync: _lastSuccess,
    );
    _snapshotController.add(_lastSnapshot);
  }

  void dispose() {
    stop();
    _snapshotController.close();
  }
}
