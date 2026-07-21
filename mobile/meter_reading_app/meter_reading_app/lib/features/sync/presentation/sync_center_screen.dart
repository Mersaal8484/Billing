import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../app/theme/app_theme.dart';
import '../../../core/sync/sync_engine.dart';
import '../../../shared/widgets/state_widgets.dart';

class SyncCenterScreen extends ConsumerWidget {
  const SyncCenterScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final snapshotAsync = ref.watch(syncSnapshotProvider);
    final engine = ref.read(syncEngineProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('مركز المزامنة'),
        actions: [
          IconButton(
            tooltip: 'عرض تفاصيل الطابور',
            icon: const Icon(Icons.list_alt_outlined),
            onPressed: () => context.push('/sync/queue'),
          ),
        ],
      ),
      body: snapshotAsync.when(
        loading: () => const LoadingState(),
        error: (e, _) => ErrorState(message: '$e'),
        data: (snapshot) {
          final offline = snapshot.connectivity == ConnectivityState.offline;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Card(
                color: offline
                    ? StatusColors.offline.withOpacity(0.08)
                    : null,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Icon(
                          offline ? Icons.cloud_off : Icons.cloud_done_outlined,
                          color: offline
                              ? StatusColors.offline
                              : StatusColors.synced),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          offline
                              ? 'غير متصل — العمل مستمر محلياً'
                              : 'متصل بالشبكة',
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                      ),
                      Switch(
                        value: !offline,
                        onChanged: (v) => engine.setConnectivity(v
                            ? ConnectivityState.online
                            : ConnectivityState.offline),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              _PipelineCard(
                title: 'بيانات القراءات',
                subtitle: 'مزامنة فورية — أولوية قصوى',
                icon: Icons.speed_rounded,
                stats: snapshot.dataPipeline,
              ),
              const SizedBox(height: 12),
              _PipelineCard(
                title: 'صور العدادات',
                subtitle: 'رفع خلفي — قابل للاستئناف تلقائياً',
                icon: Icons.image_outlined,
                stats: snapshot.imagePipeline,
              ),
              const SizedBox(height: 20),
              if (snapshot.dataPipeline.failed > 0 ||
                  snapshot.imagePipeline.failed > 0)
                FilledButton.tonalIcon(
                  onPressed: engine.retryFailed,
                  icon: const Icon(Icons.refresh_rounded),
                  label: const Text('إعادة محاولة العناصر الفاشلة'),
                ),
              const SizedBox(height: 12),
              if (snapshot.lastSuccessfulSync != null)
                Center(
                  child: Text(
                    'آخر مزامنة ناجحة: ${_formatTime(snapshot.lastSuccessfulSync!)}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  String _formatTime(DateTime t) =>
      '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}:${t.second.toString().padLeft(2, '0')}';
}

class _PipelineCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final PipelineStats stats;
  const _PipelineCard(
      {required this.title,
      required this.subtitle,
      required this.icon,
      required this.stats});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: Theme.of(context).colorScheme.primary),
                const SizedBox(width: 10),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: const TextStyle(fontWeight: FontWeight.w700)),
                    Text(subtitle,
                        style: Theme.of(context).textTheme.bodySmall),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 14),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                SyncStatusChip(
                    label: '${stats.pending} بالانتظار',
                    color: StatusColors.pending,
                    icon: Icons.hourglass_empty_rounded),
                SyncStatusChip(
                    label: '${stats.succeeded} تم',
                    color: StatusColors.synced,
                    icon: Icons.check_circle_outline),
                SyncStatusChip(
                    label: '${stats.failed} فشل',
                    color: StatusColors.error,
                    icon: Icons.error_outline),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
