import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/models/billing.dart';
import '../../workspace/state/active_workspace_store.dart';
import '../api/billing_api.dart';

void _watchWorkspace(Ref ref) {
  ref.watch(
    activeWorkspaceProvider.select((value) => value.valueOrNull?.currentId),
  );
}

void _poll(Ref ref, Duration interval) {
  final timer = Timer.periodic(interval, (_) => ref.invalidateSelf());
  ref.onDispose(timer.cancel);
}

final billingBalanceProvider = FutureProvider.autoDispose<CreditBalance>((ref) {
  _watchWorkspace(ref);
  _poll(ref, const Duration(seconds: 15));
  return ref.watch(billingApiProvider).getBalance();
});

final billingPlansProvider = FutureProvider.autoDispose<BillingPlans>((ref) {
  _watchWorkspace(ref);
  return ref.watch(billingApiProvider).getPlans();
});

final billingSubscriptionProvider =
    FutureProvider.autoDispose<BillingSubscription>((ref) {
      _watchWorkspace(ref);
      _poll(ref, const Duration(seconds: 15));
      return ref.watch(billingApiProvider).getSubscription();
    });

final billingProvidersProvider =
    FutureProvider.autoDispose<List<PaymentProviderInfo>>((ref) {
      _watchWorkspace(ref);
      return ref.watch(billingApiProvider).getProviders();
    });

class BillingUsageQuery {
  const BillingUsageQuery({
    this.page = 1,
    this.pageSize = 20,
    this.dateFrom,
    this.dateTo,
    this.timezone,
  });

  final int page;
  final int pageSize;
  final DateTime? dateFrom;
  final DateTime? dateTo;
  final String? timezone;

  @override
  bool operator ==(Object other) =>
      other is BillingUsageQuery &&
      other.page == page &&
      other.pageSize == pageSize &&
      other.dateFrom == dateFrom &&
      other.dateTo == dateTo &&
      other.timezone == timezone;

  @override
  int get hashCode => Object.hash(page, pageSize, dateFrom, dateTo, timezone);
}

final billingSummaryProvider = FutureProvider.autoDispose
    .family<BillingSummary, BillingUsageQuery>((ref, query) {
      _watchWorkspace(ref);
      _poll(ref, const Duration(seconds: 15));
      return ref
          .watch(billingApiProvider)
          .getSummary(
            dateFrom: query.dateFrom,
            dateTo: query.dateTo,
            timezone: query.timezone,
          );
    });

final billingUsageProvider = FutureProvider.autoDispose
    .family<PagedResult<UsageEntry>, BillingUsageQuery>((ref, query) {
      _watchWorkspace(ref);
      _poll(ref, const Duration(seconds: 15));
      return ref
          .watch(billingApiProvider)
          .getUsage(
            page: query.page,
            pageSize: query.pageSize,
            dateFrom: query.dateFrom,
            dateTo: query.dateTo,
            timezone: query.timezone,
          );
    });

class BillingOrderQuery {
  const BillingOrderQuery({
    this.page = 1,
    this.pageSize = 10,
    this.status,
    this.provider,
    this.orderId,
    this.dateFrom,
    this.dateTo,
    this.timezone,
  });

  final int page;
  final int pageSize;
  final String? status;
  final String? provider;
  final String? orderId;
  final DateTime? dateFrom;
  final DateTime? dateTo;
  final String? timezone;

  @override
  bool operator ==(Object other) =>
      other is BillingOrderQuery &&
      other.page == page &&
      other.pageSize == pageSize &&
      other.status == status &&
      other.provider == provider &&
      other.orderId == orderId &&
      other.dateFrom == dateFrom &&
      other.dateTo == dateTo &&
      other.timezone == timezone;

  @override
  int get hashCode => Object.hash(
    page,
    pageSize,
    status,
    provider,
    orderId,
    dateFrom,
    dateTo,
    timezone,
  );
}

final billingOrdersProvider = FutureProvider.autoDispose
    .family<PagedResult<PaymentOrder>, BillingOrderQuery>((ref, query) {
      _watchWorkspace(ref);
      // Pending cashiers need quick reconciliation; a 5s poll is bounded to the
      // currently visible page, matching web behavior.
      _poll(ref, const Duration(seconds: 5));
      return ref
          .watch(billingApiProvider)
          .getOrders(
            page: query.page,
            pageSize: query.pageSize,
            status: query.status,
            provider: query.provider,
            orderId: query.orderId,
            dateFrom: query.dateFrom,
            dateTo: query.dateTo,
            timezone: query.timezone,
          );
    });

String newPaymentRequestKey() {
  final random = Random.secure();
  final entropy = List<int>.generate(24, (_) => random.nextInt(256));
  return base64UrlEncode(entropy).replaceAll('=', '');
}

void invalidateBilling(WidgetRef ref) {
  ref.invalidate(billingBalanceProvider);
  ref.invalidate(billingPlansProvider);
  ref.invalidate(billingSubscriptionProvider);
  ref.invalidate(billingProvidersProvider);
  ref.invalidate(billingSummaryProvider);
  ref.invalidate(billingUsageProvider);
  ref.invalidate(billingOrdersProvider);
}
