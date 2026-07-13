import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../../app/providers.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../../customers/domain/entities.dart';
import '../domain/reading.dart';

class ReadingEntryScreen extends ConsumerStatefulWidget {
  final String assignmentId;

  const ReadingEntryScreen({super.key, required this.assignmentId});

  @override
  ConsumerState<ReadingEntryScreen> createState() => _ReadingEntryScreenState();
}

class _ReadingEntryScreenState extends ConsumerState<ReadingEntryScreen> {
  final _formKey = GlobalKey<FormState>();
  final _valueCtrl = TextEditingController();
  final _remarksCtrl = TextEditingController();
  final _uuid = const Uuid();
  String? _imagePath;
  bool _saving = false;

  @override
  Widget build(BuildContext context) {
    final assignments = ref.watch(assignmentsProvider(const AssignmentQuery()));

    return Scaffold(
      appBar: AppBar(title: const Text('إدخال القراءة')),
      body: assignments.when(
        loading: () => const LoadingState(),
        error: (e, _) => ErrorState(message: '$e'),
        data: (list) {
          final match = list.where((a) => a.id == widget.assignmentId);
          if (match.isEmpty) {
            return const EmptyState(
                icon: Icons.error_outline, title: 'المهمة غير موجودة');
          }
          final assignment = match.first;
          final previous = assignment.customer.lastReadingValue ?? 0;

          return Form(
            key: _formKey,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.person_outline),
                    title: Text(assignment.customer.name),
                    subtitle: Text(
                        'عداد ${assignment.meter.meterNumber} · حساب ${assignment.customer.accountNumber}'),
                  ),
                ),
                const SizedBox(height: 16),
                _InfoBanner(
                  icon: Icons.history_rounded,
                  text:
                      'القراءة السابقة: ${previous.toStringAsFixed(0)} kWh · المتوسط ${assignment.averageConsumption.toStringAsFixed(0)} kWh',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _valueCtrl,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  style: const TextStyle(
                      fontSize: 28, fontWeight: FontWeight.w800),
                  decoration:
                      const InputDecoration(labelText: 'القراءة الحالية (kWh)'),
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return 'أدخل القراءة';
                    }
                    final reading = double.tryParse(value);
                    if (reading == null) {
                      return 'قيمة غير صالحة';
                    }
                    if (reading < previous) {
                      return 'القراءة أقل من القراءة السابقة';
                    }
                    return null;
                  },
                  onChanged: (_) => setState(() {}),
                ),
                if (_consumptionHint(previous, assignment.averageConsumption) !=
                    null) ...[
                  const SizedBox(height: 8),
                  _InfoBanner(
                    icon: Icons.warning_amber_rounded,
                    text: _consumptionHint(
                        previous, assignment.averageConsumption)!,
                    warning: true,
                  ),
                ],
                const SizedBox(height: 16),
                _PhotoPicker(
                  imagePath: _imagePath,
                  onCapture: () => _openCamera(),
                  onMockCapture: () =>
                      setState(() => _imagePath = 'mock://meter-photo'),
                  onClear: () => setState(() => _imagePath = null),
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _remarksCtrl,
                  maxLines: 2,
                  decoration:
                      const InputDecoration(labelText: 'ملاحظات (اختياري)'),
                ),
                const SizedBox(height: 24),
                FilledButton.icon(
                  onPressed: _saving ? null : () => _submit(assignment),
                  icon: _saving
                      ? const SizedBox(
                          height: 18,
                          width: 18,
                          child: CircularProgressIndicator(strokeWidth: 2.5))
                      : const Icon(Icons.rule_rounded),
                  label: const Text('حفظ القراءة وفتح قرار العداد'),
                ),
                const SizedBox(height: 8),
                Text(
                  'ستبقى القراءة محلية ضمن بيانات المحاكاة. لا يوجد أي إرسال شبكي في هذه المرحلة.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context)
                      .textTheme
                      .bodySmall
                      ?.copyWith(color: Theme.of(context).colorScheme.outline),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  String? _consumptionHint(double previous, double average) {
    final value = double.tryParse(_valueCtrl.text);
    if (value == null || previous <= 0) {
      return null;
    }
    final consumption = value - previous;
    if (consumption < 0) {
      return null;
    }
    final variance =
        average == 0 ? 0.0 : ((consumption - average) / average) * 100;
    if (variance.abs() > 35) {
      return 'الاستهلاك المحسوب ${consumption.toStringAsFixed(0)} kWh يختلف عن المتوسط بنسبة ${variance.toStringAsFixed(0)}%.';
    }
    return null;
  }

  Future<void> _openCamera() async {
    final path = await context.push<String>('/readings/photo');
    if (path != null) setState(() => _imagePath = path);
  }

  Future<void> _submit(ReadingAssignment assignment) async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    if (_imagePath == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content:
                Text('يجب تصوير العداد أو استخدام صورة تجريبية قبل الحفظ')),
      );
      return;
    }

    setState(() => _saving = true);
    final reading = MeterReading(
      id: _uuid.v4(),
      meterRemoteId: assignment.meter.remoteId,
      readingValue: double.parse(_valueCtrl.text),
      readingDate: DateTime.now(),
      category: ReadingCategory.customer,
      remarks: _remarksCtrl.text.isEmpty ? null : _remarksCtrl.text,
      imageLocalPath: _imagePath,
      syncStatus: ReadingSyncStatus.draft,
    );

    final repo = ref.read(readingRepositoryProvider);
    await repo.saveDraft(reading);
    await ref
        .read(assignmentRepositoryProvider)
        .markStatus(assignment.id, AssignmentStatus.pendingDecision);

    if (mounted) {
      setState(() => _saving = false);
      context
          .go('/readings/decision/${assignment.id}?value=${_valueCtrl.text}');
    }
  }
}

class _InfoBanner extends StatelessWidget {
  final IconData icon;
  final String text;
  final bool warning;

  const _InfoBanner(
      {required this.icon, required this.text, this.warning = false});

  @override
  Widget build(BuildContext context) {
    final color =
        warning ? Colors.orange : Theme.of(context).colorScheme.primary;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(12)),
      child: Row(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 8),
          Expanded(
              child: Text(text,
                  style: TextStyle(color: color, fontWeight: FontWeight.w700))),
        ],
      ),
    );
  }
}

class _PhotoPicker extends StatelessWidget {
  final String? imagePath;
  final VoidCallback onCapture;
  final VoidCallback onMockCapture;
  final VoidCallback onClear;

  const _PhotoPicker({
    required this.imagePath,
    required this.onCapture,
    required this.onMockCapture,
    required this.onClear,
  });

  @override
  Widget build(BuildContext context) {
    if (imagePath == null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          OutlinedButton.icon(
            onPressed: onCapture,
            icon: const Icon(Icons.camera_alt_outlined),
            label: const Text('تصوير العداد (مطلوب)'),
          ),
          const SizedBox(height: 8),
          TextButton.icon(
            onPressed: onMockCapture,
            icon: const Icon(Icons.image_outlined),
            label: const Text('استخدام صورة تجريبية للمعاينة'),
          ),
        ],
      );
    }

    final mock = imagePath!.startsWith('mock://');
    return Stack(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: mock
              ? Container(
                  height: 180,
                  width: double.infinity,
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  child: const Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.speed_rounded, size: 48),
                      SizedBox(height: 8),
                      Text('صورة عداد تجريبية'),
                    ],
                  ),
                )
              : Image.file(File(imagePath!),
                  height: 180, width: double.infinity, fit: BoxFit.cover),
        ),
        Positioned(
          top: 8,
          left: 8,
          child: IconButton.filledTonal(
              icon: const Icon(Icons.close), onPressed: onClear),
        ),
      ],
    );
  }
}
