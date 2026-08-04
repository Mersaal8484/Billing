import 'package:flutter/material.dart';
import '../../app/theme/app_theme.dart';

class LoadingState extends StatelessWidget {
  final String? message;
  const LoadingState({super.key, this.message});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(),
          if (message != null) ...[
            const SizedBox(height: 16),
            Text(message!, style: Theme.of(context).textTheme.bodyMedium),
          ],
        ],
      ),
    );
  }
}

class EmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final Widget? action;
  const EmptyState(
      {super.key,
      required this.icon,
      required this.title,
      this.subtitle,
      this.action});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 64, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 16),
            Text(title,
                textAlign: TextAlign.center,
                style: Theme.of(context)
                    .textTheme
                    .titleMedium
                    ?.copyWith(fontWeight: FontWeight.w600)),
            if (subtitle != null) ...[
              const SizedBox(height: 8),
              Text(subtitle!,
                  textAlign: TextAlign.center,
                  style: Theme.of(context)
                      .textTheme
                      .bodyMedium
                      ?.copyWith(color: Theme.of(context).colorScheme.outline)),
            ],
            if (action != null) ...[const SizedBox(height: 20), action!],
          ],
        ),
      ),
    );
  }
}

class ErrorState extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;
  const ErrorState({super.key, required this.message, this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline,
                size: 56, color: StatusColors.error),
            const SizedBox(height: 16),
            Text(message,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyLarge),
            if (onRetry != null) ...[
              const SizedBox(height: 20),
              FilledButton.tonal(
                  onPressed: onRetry, child: const Text('إعادة المحاولة')),
            ],
          ],
        ),
      ),
    );
  }
}

/// Persistent, non-intrusive banner communicating that offline work is
/// completely normal — never an error state — with a manual sync affordance.
class OfflineBanner extends StatelessWidget {
  final bool offline;
  final int pendingCount;
  final VoidCallback onSyncNow;
  const OfflineBanner(
      {super.key,
      required this.offline,
      required this.pendingCount,
      required this.onSyncNow});

  @override
  Widget build(BuildContext context) {
    if (!offline && pendingCount == 0) return const SizedBox.shrink();
    final color = offline ? StatusColors.offline : StatusColors.pending;
    final text = offline
        ? 'وضع عدم الاتصال — سيتم الرفع تلقائياً عند توفر الشبكة'
        : '$pendingCount عنصر بانتظار المزامنة';
    return Material(
      color: color.withValues(alpha: 0.12),
      child: InkWell(
        onTap: offline ? null : onSyncNow,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Row(
            children: [
              Icon(offline ? Icons.cloud_off : Icons.sync,
                  size: 18, color: color),
              const SizedBox(width: 8),
              Expanded(
                  child: Text(text,
                      style: TextStyle(
                          color: color,
                          fontWeight: FontWeight.w600,
                          fontSize: 13))),
              if (!offline)
                Text('مزامنة الآن',
                    style: TextStyle(
                        color: color,
                        fontSize: 13,
                        fontWeight: FontWeight.w700)),
            ],
          ),
        ),
      ),
    );
  }
}

class SyncStatusChip extends StatelessWidget {
  final String label;
  final Color color;
  final IconData icon;
  const SyncStatusChip(
      {super.key,
      required this.label,
      required this.color,
      required this.icon});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(20)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(label,
              style: TextStyle(
                  color: color, fontSize: 12, fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }
}
