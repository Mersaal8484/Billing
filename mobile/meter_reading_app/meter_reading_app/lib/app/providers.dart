import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/image/image_processing_service.dart';
import '../core/printing/thermal_printer_service.dart';
import '../core/sync/sync_engine.dart';
import '../features/collections/data/mock_collection_repository.dart';
import '../features/collections/domain/collection_models.dart';
import '../features/customers/data/mock_assignment_repository.dart';
import '../features/customers/domain/entities.dart';
import '../features/readings/data/mock_reading_repository.dart';
import '../features/readings/domain/reading.dart';

/// --- Repository providers -------------------------------------------------
/// Everything below is declared against an interface. To connect the real
/// backend later: implement e.g. `OdooAssignmentRepository implements
/// AssignmentRepository`, then change only the object constructed here.
/// No feature code outside this file needs to know the difference.

final assignmentRepositoryProvider = Provider<AssignmentRepository>((ref) {
  final repo = MockAssignmentRepository();
  ref.onDispose(repo.dispose);
  return repo;
});

final readingRepositoryProvider = Provider<MockReadingRepository>((ref) {
  final repo = MockReadingRepository();
  ref.onDispose(repo.dispose);
  return repo;
});

final collectionRepositoryProvider = Provider<CollectionRepository>((ref) {
  final repo = MockCollectionRepository();
  ref.onDispose(repo.dispose);
  return repo;
});

final imageProcessingServiceProvider = Provider<ImageProcessingService>((ref) {
  return ImageProcessingService();
});

final thermalPrinterServiceProvider = Provider<ThermalPrinterService>((ref) {
  return ThermalPrinterService();
});

final syncEngineProvider = Provider<SyncEngine>((ref) {
  final engine = SyncEngine(ref.watch(readingRepositoryProvider));
  engine.start();
  ref.onDispose(engine.dispose);
  return engine;
});

/// --- Derived/streamed state ------------------------------------------------

final assignmentsProvider = StreamProvider.autoDispose
    .family<List<ReadingAssignment>, AssignmentQuery>((ref, query) {
  final repo = ref.watch(assignmentRepositoryProvider);
  return repo.watchAssignments(query: query.text, filter: query.status);
});

class AssignmentQuery {
  final String? text;
  final AssignmentStatus? status;
  const AssignmentQuery({this.text, this.status});

  @override
  bool operator ==(Object other) =>
      other is AssignmentQuery && other.text == text && other.status == status;
  @override
  int get hashCode => Object.hash(text, status);
}

final readingsProvider = StreamProvider.autoDispose<List<MeterReading>>((ref) {
  final repo = ref.watch(readingRepositoryProvider);
  return repo.watchReadingsForPeriod(0);
});

final collectionAccountsProvider = StreamProvider.autoDispose
    .family<List<CollectionAccount>, String?>((ref, query) {
  final repo = ref.watch(collectionRepositoryProvider);
  return repo.watchAccounts(query: query);
});

final syncSnapshotProvider = StreamProvider.autoDispose<SyncSnapshot>((ref) {
  final engine = ref.watch(syncEngineProvider);
  return engine.snapshots;
});

/// Session state — replace with a real auth repository (token refresh,
/// device registration, secure storage) in the backend phase. The
/// abstraction is intentionally thin: the UI only needs to know
/// "logged in or not" right now.
final authStateProvider = StateProvider<bool>((ref) => false);
