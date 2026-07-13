/// Mirrors the subset of utility.reading (utility_core/utility_billing)
/// that the field app owns. Anything computed server-side (consumption,
/// consumption_alert, previous_reading) is NOT modeled here — the app
/// shows those only after the ERP returns them post-sync; it never
/// recomputes billing-relevant figures locally.
enum ReadingCategory { customer, transformer, feeder }

enum ReadingSyncStatus {
  draft, // captured offline, not yet queued
  pendingDataSync, // in Pipeline A queue
  dataSynced, // ERP has the reading record; image may still be pending
  pendingImageSync, // in Pipeline B queue
  synced, // fully synced, data + image
  error, // Pipeline A failed after retries — needs user attention
}

class MeterReading {
  final String id; // local uuid — stable identity before any remote id exists
  final int? remoteId;
  final int meterRemoteId;
  final double readingValue;
  final DateTime readingDate;
  final ReadingCategory category;
  final bool isEstimated;
  final String? remarks;
  final String? imageLocalPath;
  final String? imageSecondaryLocalPath;
  final ReadingSyncStatus syncStatus;
  final String? lastError;

  const MeterReading({
    required this.id,
    this.remoteId,
    required this.meterRemoteId,
    required this.readingValue,
    required this.readingDate,
    this.category = ReadingCategory.customer,
    this.isEstimated = false,
    this.remarks,
    this.imageLocalPath,
    this.imageSecondaryLocalPath,
    this.syncStatus = ReadingSyncStatus.draft,
    this.lastError,
  });

  MeterReading copyWith({
    double? readingValue,
    String? remarks,
    String? imageLocalPath,
    ReadingSyncStatus? syncStatus,
    String? lastError,
  }) {
    return MeterReading(
      id: id,
      remoteId: remoteId,
      meterRemoteId: meterRemoteId,
      readingValue: readingValue ?? this.readingValue,
      readingDate: readingDate,
      category: category,
      isEstimated: isEstimated,
      remarks: remarks ?? this.remarks,
      imageLocalPath: imageLocalPath ?? this.imageLocalPath,
      imageSecondaryLocalPath: imageSecondaryLocalPath,
      syncStatus: syncStatus ?? this.syncStatus,
      lastError: lastError,
    );
  }

  /// Client-side sanity check only — mirrors the *shape* of the ERP's
  /// billable-reading photo requirement (action_submit_review) so the
  /// reader gets the same feedback offline that they'd get on submit.
  /// This is NOT a substitute for server-side validation.
  bool get requiresPhoto => category == ReadingCategory.customer;
  bool get isReadyToQueue => !requiresPhoto || imageLocalPath != null;
}

/// Repository contract the UI depends on. In this phase it is backed by
/// [MockReadingRepository]; the real implementation will call the
/// existing /api/v1/utility/reading/* endpoints already present in
/// utility_billing without changing this interface.
abstract class ReadingRepository {
  Stream<List<MeterReading>> watchReadingsForPeriod(int periodId);
  Future<MeterReading> saveDraft(MeterReading reading);
  Future<void> enqueueForSync(String readingId);
  Future<void> retry(String readingId);
}
