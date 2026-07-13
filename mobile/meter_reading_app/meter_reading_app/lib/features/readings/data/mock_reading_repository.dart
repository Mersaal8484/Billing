import 'dart:async';

import '../domain/reading.dart';

/// Stands in for the Drift-backed repository. Swapping this for a real
/// `DriftReadingRepository` (same interface) is the only change needed
/// once local persistence is wired in; swapping *that* for a networked
/// one later needs no further UI changes either, since sync is driven by
/// [enqueueForSync] / the queue tables, never by direct API calls from
/// the UI layer.
class MockReadingRepository implements ReadingRepository {
  final Map<String, MeterReading> _store = {};
  final _controller = StreamController<List<MeterReading>>.broadcast();

  void _emit() => _controller.add(_store.values.toList(growable: false));

  @override
  Stream<List<MeterReading>> watchReadingsForPeriod(int periodId) {
    // periodId ignored in mock — single active period is simulated.
    return _controller.stream;
  }

  @override
  Future<MeterReading> saveDraft(MeterReading reading) async {
    _store[reading.id] = reading;
    _emit();
    return reading;
  }

  @override
  Future<void> enqueueForSync(String readingId) async {
    final r = _store[readingId];
    if (r == null) return;
    _store[readingId] =
        r.copyWith(syncStatus: ReadingSyncStatus.pendingDataSync);
    _emit();
  }

  @override
  Future<void> retry(String readingId) async {
    final r = _store[readingId];
    if (r == null) return;
    _store[readingId] = r.copyWith(
        syncStatus: ReadingSyncStatus.pendingDataSync, lastError: null);
    _emit();
  }

  /// Test/demo seam used only by the sync engine simulation below.
  void updateStatus(String id, ReadingSyncStatus status, {String? error}) {
    final r = _store[id];
    if (r == null) return;
    _store[id] = r.copyWith(syncStatus: status, lastError: error);
    _emit();
  }

  List<MeterReading> get all => _store.values.toList(growable: false);

  void dispose() => _controller.close();
}
