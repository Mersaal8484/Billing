import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/providers.dart';
import '../../../app/theme/app_theme.dart';
import '../../../core/sync/sync_settings_service.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../../readings/domain/reading.dart';

class QueueMonitorScreen extends ConsumerWidget {
  const QueueMonitorScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final readingsAsync = ref.watch(readingsProvider);
    final modeAsync = ref.watch(syncModeProvider);
    final batchSizeAsync = ref.watch(syncBatchSizeProvider);
    final mode = modeAsync.maybeWhen(
      data: (value) => value,
      orElse: () => SyncMode.batch,
    );
    final batchSize = batchSizeAsync.maybeWhen(
      data: (value) => value,
      orElse: () => 50,
    );

    return Scaffold(
      appBar: AppBar(title: const Text('طابور القراءات')),
      body: readingsAsync.when(
        loading: () => const LoadingState(),
        error: (e, _) => ErrorState(message: '$e'),
        data: (readings) {
          if (readings.isEmpty) {
            return ListView(
              padding: const EdgeInsets.all(12),
              children: [
                _QueueModeBanner(mode: mode, batchSize: batchSize),
                const SizedBox(height: 32),
                const EmptyState(
                  icon: Icons.inbox_outlined,
                  title: 'لا توجد قراءات في الطابور بعد',
                  subtitle:
                      'ستظهر هنا القراءات فور حفظها من شاشة إدخال القراءة',
                ),
              ],
            );
          }
          final sorted = [...readings]
            ..sort((a, b) => b.readingDate.compareTo(a.readingDate));
          return ListView.separated(
            padding: const EdgeInsets.all(12),
            itemCount: sorted.length + 1,
            separatorBuilder: (_, __) => const SizedBox(height: 6),
            itemBuilder: (context, i) {
              if (i == 0) {
                return _QueueModeBanner(mode: mode, batchSize: batchSize);
              }
              return _ReadingQueueTile(reading: sorted[i - 1]);
            },
          );
        },
      ),
    );
  }
}

class _QueueModeBanner extends StatelessWidget {
  final SyncMode mode;
  final int batchSize;

  const _QueueModeBanner({required this.mode, required this.batchSize});

  @override
  Widget build(BuildContext context) {
    final immediate = mode == SyncMode.immediate;
    return Card(
      child: ListTile(
        leading: Icon(
          immediate ? Icons.flash_on_outlined : Icons.archive_outlined,
          color: Theme.of(context).colorScheme.primary,
        ),
        title: Text(
          immediate
              ? 'الوضع الحالي: مزامنة فردية مباشرة'
              : 'الوضع الحالي: حزم مضغوطة ($batchSize/حزمة)',
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
    );
  }
}

class _ReadingQueueTile extends ConsumerWidget {
  final MeterReading reading;
  const _ReadingQueueTile({required this.reading});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final (label, color, icon) = _statusPresentation(reading.syncStatus);
    return Card(
      child: ListTile(
        leading: reading.imageLocalPath != null
            ? const Icon(Icons.image_outlined)
            : const Icon(Icons.image_not_supported_outlined),
        title: Text(
            'عداد #${reading.meterRemoteId} · ${reading.readingValue.toStringAsFixed(0)} kWh'),
        subtitle: reading.lastError != null
            ? Text(reading.lastError!,
                style: const TextStyle(color: StatusColors.error))
            : Text(
                '${reading.readingDate.hour.toString().padLeft(2, '0')}:${reading.readingDate.minute.toString().padLeft(2, '0')}'),
        trailing: reading.syncStatus == ReadingSyncStatus.error
            ? TextButton(
                onPressed: () =>
                    ref.read(readingRepositoryProvider).retry(reading.id),
                child: const Text('إعادة'),
              )
            : SyncStatusChip(label: label, color: color, icon: icon),
      ),
    );
  }

  (String, Color, IconData) _statusPresentation(ReadingSyncStatus status) {
    switch (status) {
      case ReadingSyncStatus.draft:
        return ('مسودة', StatusColors.offline, Icons.edit_outlined);
      case ReadingSyncStatus.pendingDataSync:
        return ('بانتظار الرفع', StatusColors.pending, Icons.schedule_outlined);
      case ReadingSyncStatus.dataSynced:
        return (
          'بيانات مرفوعة',
          StatusColors.pending,
          Icons.hourglass_top_rounded
        );
      case ReadingSyncStatus.pendingImageSync:
        return ('رفع الصورة', StatusColors.inProgress, Icons.image_outlined);
      case ReadingSyncStatus.synced:
        return ('مكتملة', StatusColors.synced, Icons.check_circle_outline);
      case ReadingSyncStatus.error:
        return ('فشل', StatusColors.error, Icons.error_outline);
    }
  }
}
