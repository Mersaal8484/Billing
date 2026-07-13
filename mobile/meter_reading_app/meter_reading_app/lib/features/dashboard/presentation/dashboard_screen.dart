import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../../customers/domain/entities.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final assignments = ref.watch(assignmentsProvider(const AssignmentQuery()));
    final sync = ref.watch(syncSnapshotProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('الرئيسية'),
        actions: [
          IconButton(
            tooltip: 'الإعدادات',
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => context.push('/settings'),
          ),
        ],
      ),
      body: assignments.when(
        loading: () => const LoadingState(),
        error: (e, _) => ErrorState(message: 'تعذر تحميل المهام: $e'),
        data: (list) {
          final total = list.length;
          final done =
              list.where((a) => a.status == AssignmentStatus.read).length;
          final pending =
              list.where((a) => a.status == AssignmentStatus.pending).length;
          final pendingDecision = list
              .where((a) => a.status == AssignmentStatus.pendingDecision)
              .length;
          final rejected =
              list.where((a) => a.status == AssignmentStatus.rejected).length;
          final offline = sync.value?.connectivity.name == 'offline';
          final pendingSync = (sync.value?.dataPipeline.pending ?? 0) +
              (sync.value?.imagePipeline.pending ?? 0);

          return Column(
            children: [
              OfflineBanner(
                  offline: offline,
                  pendingCount: pendingSync,
                  onSyncNow: () => context.push('/sync')),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    _ProgressCard(
                      total: total,
                      done: done,
                      pending: pending,
                      pendingDecision: pendingDecision,
                      rejected: rejected,
                    ),
                    const SizedBox(height: 16),
                    Text('مسارات العمل',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    GridView.count(
                      shrinkWrap: true,
                      crossAxisCount: 2,
                      childAspectRatio: 1.15,
                      crossAxisSpacing: 10,
                      mainAxisSpacing: 10,
                      physics: const NeverScrollableScrollPhysics(),
                      children: [
                        _QuickAction(
                          icon: Icons.speed_rounded,
                          label: 'الكاشف',
                          subtitle: 'مهام القراءة',
                          onTap: () => context.push('/customers'),
                        ),
                        _QuickAction(
                          icon: Icons.qr_code_scanner_rounded,
                          label: 'المتحصل',
                          subtitle: 'QR والتحصيل',
                          onTap: () => context.push('/collector'),
                        ),
                        _QuickAction(
                          icon: Icons.rule_folder_outlined,
                          label: 'المشرف',
                          subtitle: 'اعتماد ومتابعة',
                          onTap: () => context.push('/supervisor'),
                        ),
                        _QuickAction(
                          icon: Icons.sync_rounded,
                          label: 'المزامنة',
                          subtitle: 'الطابور والحالة',
                          onTap: () => context.push('/sync'),
                        ),
                      ],
                    ),
                    const SizedBox(height: 24),
                    Text('مهام قريبة',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    ...list.take(4).map((assignment) =>
                        _UpcomingTaskTile(assignment: assignment)),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _ProgressCard extends StatelessWidget {
  final int total;
  final int done;
  final int pending;
  final int pendingDecision;
  final int rejected;

  const _ProgressCard({
    required this.total,
    required this.done,
    required this.pending,
    required this.pendingDecision,
    required this.rejected,
  });

  @override
  Widget build(BuildContext context) {
    final progress = total == 0 ? 0.0 : done / total;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('تقدم قراءات اليوم',
                    style: Theme.of(context).textTheme.titleMedium),
                Text('$done / $total',
                    style: Theme.of(context).textTheme.titleMedium),
              ],
            ),
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(value: progress, minHeight: 10),
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                SyncStatusChip(
                    label: '$pending متبقي',
                    color: Colors.orange,
                    icon: Icons.hourglass_empty_rounded),
                SyncStatusChip(
                    label: '$pendingDecision قرار',
                    color: Colors.blue,
                    icon: Icons.rule_rounded),
                SyncStatusChip(
                    label: '$rejected مرفوض',
                    color: Colors.red,
                    icon: Icons.cancel_outlined),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _QuickAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final String subtitle;
  final VoidCallback onTap;

  const _QuickAction({
    required this.icon,
    required this.label,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon,
                  size: 30, color: Theme.of(context).colorScheme.primary),
              const Spacer(),
              Text(label,
                  style: Theme.of(context)
                      .textTheme
                      .titleMedium
                      ?.copyWith(fontWeight: FontWeight.w800)),
              Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
        ),
      ),
    );
  }
}

class _UpcomingTaskTile extends StatelessWidget {
  final ReadingAssignment assignment;

  const _UpcomingTaskTile({required this.assignment});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        onTap: () => context.push('/customers/${assignment.id}'),
        leading: const CircleAvatar(child: Icon(Icons.speed_rounded)),
        title: Text(assignment.customer.name,
            style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(
            '${assignment.customer.accountNumber} · عداد ${assignment.meter.meterNumber}'),
        trailing: Text(_statusLabel(assignment.status),
            style: Theme.of(context).textTheme.bodySmall),
      ),
    );
  }

  String _statusLabel(AssignmentStatus status) => switch (status) {
        AssignmentStatus.pending => 'متبقي',
        AssignmentStatus.pendingDecision => 'بانتظار قرار',
        AssignmentStatus.read => 'مكتمل',
        AssignmentStatus.rejected => 'مرفوض',
        AssignmentStatus.escalated => 'مصعد',
        AssignmentStatus.skipped => 'متجاوز',
      };
}
