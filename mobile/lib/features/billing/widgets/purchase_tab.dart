import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/appearance/tokens.dart';
import '../../../shared/appearance/type_scale.dart';
import '../../../shared/i18n/i18n.dart';
import '../../../shared/models/billing.dart';
import '../../../shared/utils/format.dart';
import '../../../shared/widgets/toast.dart';
import '../api/billing_api.dart';
import '../payment/payment_launcher.dart';
import '../state/billing_providers.dart';
import 'billing_widgets.dart';
import 'purchase_controls.dart';

class BillingPurchaseTab extends ConsumerStatefulWidget {
  const BillingPurchaseTab({super.key, required this.onOpenOrders});

  final VoidCallback onOpenOrders;

  @override
  ConsumerState<BillingPurchaseTab> createState() => _BillingPurchaseTabState();
}

class _BillingPurchaseTabState extends ConsumerState<BillingPurchaseTab> {
  final _topup = TextEditingController(text: '10');
  String _cycle = 'monthly';
  String? _selectedProvider;
  bool _busy = false;
  String? _attemptSignature;
  String? _attemptKey;
  bool _operationFailed = false;

  @override
  void dispose() {
    _topup.dispose();
    super.dispose();
  }

  String? _provider(List<PaymentProviderInfo> providers) {
    if (providers.any((item) => item.id == _selectedProvider)) {
      return _selectedProvider;
    }
    for (final item in providers) {
      if (item.id == 'alipay') return item.id;
    }
    return providers.isEmpty ? null : providers.first.id;
  }

  PaymentProviderInfo? _providerInfo(
    List<PaymentProviderInfo> providers,
    String? id,
  ) {
    for (final provider in providers) {
      if (provider.id == id) return provider;
    }
    return null;
  }

  String _requestKey(String signature) {
    if (_attemptSignature != signature || _attemptKey == null) {
      _attemptSignature = signature;
      _attemptKey = newPaymentRequestKey();
    }
    return _attemptKey!;
  }

  Future<void> _subscribe(
    BillingPlan plan,
    PaymentProviderInfo provider,
  ) async {
    if (_busy || plan.id == 'free') return;
    setState(() {
      _busy = true;
      _operationFailed = false;
    });
    final i18n = ref.read(i18nProvider);
    try {
      final signature = '${provider.id}:${plan.id}:$_cycle';
      final order = await ref
          .read(billingApiProvider)
          .createSubscriptionOrder(
            provider: provider.id,
            planId: plan.id,
            cycle: _cycle,
            requestKey: _requestKey(signature),
          );
      final result = await ref
          .read(paymentLauncherProvider)
          .launch(order, provider);
      if (result.order.status == 'paid') {
        _attemptKey = null;
        ref
            .read(toastProvider.notifier)
            .success(i18n.t('billing:plans.paymentConfirmed'));
      }
      if (mounted) {
        invalidateBilling(ref);
        widget.onOpenOrders();
      }
    } catch (_) {
      if (mounted) setState(() => _operationFailed = true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _topUp(TopupRules rules, PaymentProviderInfo provider) async {
    final amountFen = _parseFen(_topup.text);
    if (_busy ||
        amountFen == null ||
        amountFen < rules.minAmountFen ||
        amountFen > rules.maxAmountFen) {
      setState(() => _operationFailed = true);
      return;
    }
    setState(() {
      _busy = true;
      _operationFailed = false;
    });
    final i18n = ref.read(i18nProvider);
    try {
      final signature = '${provider.id}:$amountFen';
      final order = await ref
          .read(billingApiProvider)
          .createTopupOrder(
            provider: provider.id,
            amountFen: amountFen,
            requestKey: _requestKey(signature),
          );
      final result = await ref
          .read(paymentLauncherProvider)
          .launch(order, provider);
      if (result.order.status == 'paid') {
        _attemptKey = null;
        ref
            .read(toastProvider.notifier)
            .success(
              i18n.t(
                'billing:usage.paid',
                vars: {'value': formatCredits(result.order.credits)},
              ),
            );
      }
      if (mounted) {
        invalidateBilling(ref);
        widget.onOpenOrders();
      }
    } catch (_) {
      if (mounted) setState(() => _operationFailed = true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final i18n = ref.watch(i18nProvider);
    final tokens = context.tokens;
    final balance = ref.watch(billingBalanceProvider);
    final plans = ref.watch(billingPlansProvider);
    final subscription = ref.watch(billingSubscriptionProvider);
    final providers = ref.watch(billingProvidersProvider);
    final providerItems =
        providers.valueOrNull ?? const <PaymentProviderInfo>[];
    final providerId = _provider(providerItems);
    final selectedProvider = _providerInfo(providerItems, providerId);
    final hasError =
        balance.hasError ||
        plans.hasError ||
        subscription.hasError ||
        providers.hasError;

    return I18nScope(
      state: i18n,
      child: RefreshIndicator(
        onRefresh: () async => invalidateBilling(ref),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          children: [
            CreditBalanceCard(
              balance: balance.valueOrNull?.balance,
              footer: subscription.valueOrNull == null
                  ? null
                  : _SubscriptionLine(subscription.valueOrNull!),
            ),
            if (hasError) ...[
              const SizedBox(height: 12),
              BillingErrorBar(
                label: i18n.t('billing:usage.loadError'),
                onRetry: () => invalidateBilling(ref),
              ),
            ],
            if ((plans.isLoading || subscription.isLoading) &&
                plans.valueOrNull == null) ...[
              const SizedBox(height: 28),
              Center(
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: tokens.a700,
                ),
              ),
            ],
            if (plans.valueOrNull case final catalog?) ...[
              if (subscription.valueOrNull case final current?) ...[
                const SizedBox(height: 22),
                _SectionHeader(
                  title: i18n.t('billing:plans.title'),
                  trailing: Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      if (providerItems.isNotEmpty)
                        BillingProviderPicker(
                          providers: providerItems,
                          value: providerId,
                          onChanged: _busy
                              ? null
                              : (value) =>
                                    setState(() => _selectedProvider = value),
                        ),
                      _CyclePicker(
                        value: _cycle,
                        onChanged: _busy
                            ? null
                            : (value) => setState(() => _cycle = value),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                for (final plan in catalog.plans) ...[
                  _PlanCard(
                    plan: plan,
                    cycle: _cycle,
                    subscription: current,
                    enabled:
                        !_busy &&
                        selectedProvider != null &&
                        current.canManage &&
                        plan.id != 'free',
                    busy: _busy,
                    onPressed: selectedProvider == null
                        ? null
                        : () => _subscribe(plan, selectedProvider),
                  ),
                  const SizedBox(height: 12),
                ],
                if (current.queued.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  BillingCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          i18n.t('billing:plans.queued'),
                          style: TextStyle(
                            fontSize: FontSizes.sm,
                            fontWeight: FontWeight.w500,
                            color: tokens.ink,
                          ),
                        ),
                        const SizedBox(height: 7),
                        for (final term in current.queued)
                          Padding(
                            padding: const EdgeInsets.only(top: 5),
                            child: Text(
                              i18n.t(
                                'billing:plans.scheduled',
                                vars: {
                                  'name': i18n.t(
                                    'billing:plans.names.${term.planId}',
                                  ),
                                  'date': term.startsAt == null
                                      ? '—'
                                      : formatDateTime(
                                          term.startsAt!,
                                          i18n.language,
                                        ),
                                },
                              ),
                              style: TextStyle(
                                fontSize: FontSizes.xs,
                                color: tokens.n600,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: 18),
                BillingTopupCard(
                  controller: _topup,
                  rules: catalog.topup,
                  allowed: current.topupAllowed,
                  canManage: current.canManage,
                  providers: providerItems,
                  providerId: providerId,
                  busy: _busy,
                  onProviderChanged: (value) =>
                      setState(() => _selectedProvider = value),
                  onPreset: (amountFen) =>
                      setState(() => _topup.text = formatFen(amountFen)),
                  onSubmit: selectedProvider == null
                      ? null
                      : () => _topUp(catalog.topup, selectedProvider),
                ),
                const SizedBox(height: 12),
                BillingCard(
                  padding: EdgeInsets.zero,
                  child: Theme(
                    data: Theme.of(
                      context,
                    ).copyWith(dividerColor: Colors.transparent),
                    child: ExpansionTile(
                      title: Text(
                        i18n.t('billing:plans.rulesTitle'),
                        style: TextStyle(
                          fontSize: FontSizes.sm,
                          fontWeight: FontWeight.w500,
                          color: tokens.ink,
                        ),
                      ),
                      childrenPadding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
                      children: [
                        for (final key in [
                          'periods',
                          'yearly',
                          'balance',
                          'renewal',
                          'topup',
                        ])
                          Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '• ',
                                  style: TextStyle(color: tokens.n600),
                                ),
                                Expanded(
                                  child: Text(
                                    i18n.t(
                                      'billing:plans.rules.$key',
                                      vars: {
                                        'min': formatFen(
                                          catalog.topup.minAmountFen,
                                        ),
                                        'max': formatFen(
                                          catalog.topup.maxAmountFen,
                                        ),
                                      },
                                    ),
                                    style: TextStyle(
                                      fontSize: FontSizes.xs,
                                      height: 1.55,
                                      color: tokens.n600,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ],
            ],
            if (_operationFailed) ...[
              const SizedBox(height: 12),
              Text(
                i18n.t('billing:usage.paymentError'),
                style: TextStyle(fontSize: FontSizes.xs, color: tokens.danger),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _SubscriptionLine extends StatelessWidget {
  const _SubscriptionLine(this.subscription);

  final BillingSubscription subscription;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final i18n = I18nScope.of(context);
    return Wrap(
      spacing: 12,
      runSpacing: 5,
      alignment: WrapAlignment.spaceBetween,
      children: [
        Text(
          i18n.t(
            'billing:plans.activePlan',
            vars: {
              'name': i18n.t('billing:plans.names.${subscription.planId}'),
            },
          ),
          style: TextStyle(fontSize: FontSizes.xs, color: tokens.n600),
        ),
        if (subscription.endsAt != null)
          Text(
            i18n.t(
              'billing:plans.expires',
              vars: {
                'date': formatDateTime(subscription.endsAt!, i18n.language),
              },
            ),
            style: TextStyle(fontSize: FontSizes.xs, color: tokens.n600),
          ),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, required this.trailing});

  final String title;
  final Widget trailing;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          title,
          style: TextStyle(
            fontSize: FontSizes.lg,
            fontWeight: FontWeight.w500,
            color: tokens.ink,
          ),
        ),
        const SizedBox(height: 10),
        trailing,
      ],
    );
  }
}

class _CyclePicker extends StatelessWidget {
  const _CyclePicker({required this.value, required this.onChanged});

  final String value;
  final ValueChanged<String>? onChanged;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final i18n = I18nScope.of(context);
    return Container(
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: tokens.n200,
        borderRadius: BorderRadius.circular(Radii.full),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (final cycle in ['monthly', 'yearly'])
            GestureDetector(
              onTap: onChanged == null ? null : () => onChanged!(cycle),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 7,
                ),
                decoration: BoxDecoration(
                  color: value == cycle ? tokens.card : Colors.transparent,
                  borderRadius: BorderRadius.circular(Radii.full),
                ),
                child: Text(
                  i18n.t('billing:plans.cycles.$cycle'),
                  style: TextStyle(fontSize: FontSizes.xs, color: tokens.ink),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _PlanCard extends StatelessWidget {
  const _PlanCard({
    required this.plan,
    required this.cycle,
    required this.subscription,
    required this.enabled,
    required this.busy,
    required this.onPressed,
  });

  final BillingPlan plan;
  final String cycle;
  final BillingSubscription subscription;
  final bool enabled;
  final bool busy;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final i18n = I18nScope.of(context);
    final current = plan.id == subscription.planId;
    final scheduledStart = subscription.queued.isNotEmpty
        ? subscription.queued.last.endsAt
        : subscription.endsAt;
    String action;
    if (plan.id == 'free') {
      action = i18n.t(
        current ? 'billing:plans.current' : 'billing:plans.freeFallback',
      );
    } else if (!subscription.canManage) {
      action = i18n.t('billing:plans.managerOnly');
    } else {
      action = i18n.t(
        scheduledStart == null
            ? 'billing:plans.subscribe'
            : 'billing:plans.renew',
      );
    }
    return BillingCard(
      highlighted: plan.recommended,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  i18n.t('billing:plans.names.${plan.id}'),
                  style: TextStyle(
                    fontSize: FontSizes.base,
                    fontWeight: FontWeight.w500,
                    color: tokens.ink,
                  ),
                ),
              ),
              if (current || plan.recommended)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 9,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: plan.recommended ? tokens.ink : tokens.n200,
                    borderRadius: BorderRadius.circular(Radii.full),
                  ),
                  child: Text(
                    i18n.t(
                      current
                          ? 'billing:plans.current'
                          : 'billing:plans.recommended',
                    ),
                    style: TextStyle(
                      fontSize: FontSizes.xs,
                      color: plan.recommended ? tokens.bg : tokens.ink,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 15),
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.end,
            spacing: 5,
            children: [
              Text(
                '¥${formatFen(plan.priceFor(cycle))}',
                style: TextStyle(
                  fontSize: FontSizes.xl2,
                  fontWeight: FontWeight.w500,
                  color: tokens.ink,
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(bottom: 3),
                child: Text(
                  i18n.t('billing:plans.per.$cycle'),
                  style: TextStyle(fontSize: FontSizes.xs, color: tokens.n600),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            i18n.t(
              'billing:plans.allowance.${plan.creditPeriod}',
              vars: {'credits': formatCredits(plan.credits)},
            ),
            style: TextStyle(
              fontSize: FontSizes.sm,
              fontWeight: FontWeight.w500,
              color: tokens.ink,
            ),
          ),
          const SizedBox(height: 12),
          for (final label in [
            i18n.t('billing:plans.modelUsage'),
            i18n.t(
              plan.id == 'free'
                  ? 'billing:plans.weeklyGrant'
                  : 'billing:plans.monthlyGrant',
            ),
            if (plan.id != 'free') i18n.t('billing:plans.topupAvailable'),
          ])
            Padding(
              padding: const EdgeInsets.only(bottom: 7),
              child: Row(
                children: [
                  Icon(Icons.check, size: 15, color: tokens.n700),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      label,
                      style: TextStyle(
                        fontSize: FontSizes.xs,
                        color: tokens.n700,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 7),
          FilledButton(
            onPressed: enabled ? onPressed : null,
            style: billingPrimaryButton(tokens).copyWith(
              backgroundColor: WidgetStatePropertyAll(
                plan.recommended ? tokens.ink : tokens.n200,
              ),
              foregroundColor: WidgetStatePropertyAll(
                plan.recommended ? tokens.bg : tokens.ink,
              ),
            ),
            child: Text(
              busy && enabled ? i18n.t('billing:usage.creatingOrder') : action,
            ),
          ),
        ],
      ),
    );
  }
}

int? _parseFen(String raw) {
  final match = RegExp(r'^(\d+)(?:\.(\d{1,2}))?$').firstMatch(raw.trim());
  if (match == null) return null;
  final yuan = int.tryParse(match.group(1)!);
  if (yuan == null) return null;
  final fraction = match.group(2) ?? '';
  final fen = fraction.isEmpty ? 0 : int.parse(fraction.padRight(2, '0'));
  return yuan * 100 + fen;
}
