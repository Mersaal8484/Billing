import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';

class QrScannerScreen extends ConsumerStatefulWidget {
  final bool isReaderMode;

  const QrScannerScreen({super.key, this.isReaderMode = false});

  @override
  ConsumerState<QrScannerScreen> createState() => _QrScannerScreenState();
}

class _QrScannerScreenState extends ConsumerState<QrScannerScreen> {
  bool _scanning = false;
  bool _failed = false;

  Future<void> _simulateScan() async {
    setState(() {
      _scanning = true;
      _failed = false;
    });

    if (widget.isReaderMode) {
      final assignment = await ref
          .read(assignmentRepositoryProvider)
          .resolveQr('UTILITY:ACC-100000');
      if (!mounted) return;
      setState(() => _scanning = false);
      if (assignment == null) {
        setState(() => _failed = true);
        return;
      }
      context.go('/customers/${assignment.id}');
    } else {
      final account = await ref
          .read(collectionRepositoryProvider)
          .resolveQr('UTILITY:ACC-220000');
      if (!mounted) return;
      setState(() => _scanning = false);
      if (account == null) {
        setState(() => _failed = true);
        return;
      }
      context.go('/collector/accounts/${account.id}');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('مسح QR'),
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              Expanded(
                child: Center(
                  child: AspectRatio(
                    aspectRatio: 1,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        border: Border.all(color: Colors.white, width: 3),
                        borderRadius: BorderRadius.circular(24),
                      ),
                      child: Center(
                        child: _scanning
                            ? const CircularProgressIndicator(
                                color: Colors.white)
                            : const Icon(Icons.qr_code_2_rounded,
                                color: Colors.white70, size: 120),
                      ),
                    ),
                  ),
                ),
              ),
              if (_failed)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  margin: const EdgeInsets.only(bottom: 12),
                  decoration: BoxDecoration(
                    color: Colors.red.withOpacity(0.18),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Text(
                    'تعذر قراءة الرمز. نظف الملصق أو استخدم الإدخال اليدوي.',
                    style: TextStyle(color: Colors.white),
                    textAlign: TextAlign.center,
                  ),
                ),
              FilledButton.icon(
                onPressed: _scanning ? null : _simulateScan,
                icon: const Icon(Icons.qr_code_scanner_rounded),
                label: const Text('محاكاة مسح ناجح'),
              ),
              const SizedBox(height: 10),
              OutlinedButton.icon(
                onPressed: () => setState(() => _failed = true),
                icon: const Icon(Icons.report_problem_outlined),
                label: const Text('محاكاة فشل القراءة'),
                style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.white,
                    side: const BorderSide(color: Colors.white54)),
              ),
              const SizedBox(height: 10),
              TextButton.icon(
                onPressed: () => context.go(widget.isReaderMode ? '/customers' : '/collector'),
                icon: const Icon(Icons.keyboard_alt_outlined),
                label: const Text('إدخال يدوي'),
                style: TextButton.styleFrom(foregroundColor: Colors.white),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
