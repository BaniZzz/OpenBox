import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/appearance/tokens.dart';
import '../../../shared/i18n/i18n.dart';
import '../../../shared/router/paths.dart';

class DesktopSubscriptionNotice extends ConsumerWidget {
  const DesktopSubscriptionNotice({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final i18n = ref.watch(i18nProvider);
    final t = context.tokens;
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.cloud_outlined, size: 36, color: t.a700),
            const SizedBox(height: 16),
            Text(
              i18n.t('workbench:activation.subscriptionRequired'),
              textAlign: TextAlign.center,
              style: TextStyle(
                color: t.ink,
                fontSize: 18,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              i18n.t('workbench:activation.subscriptionHint'),
              textAlign: TextAlign.center,
              style: TextStyle(color: t.n600, height: 1.6),
            ),
            const SizedBox(height: 20),
            FilledButton(
              onPressed: () => context.push(Paths.billing('purchase')),
              child: Text(i18n.t('workbench:activation.subscribe')),
            ),
          ],
        ),
      ),
    );
  }
}
