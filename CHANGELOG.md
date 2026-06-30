# Changelog

## 1.3.0
  * Exclude inaccessible streams during discovery and fail discovery when no streams are accessible.

## 1.2.0
  * Upgrade python version to 3.12 [#12](https://github.com/singer-io/tap-saasoptics/pull/12)
  * Add mock-integration tests

## 1.1.2
  * Bump depenedencies [#10](https://github.com/singer-io/tap-saasoptics/pull/10)

## 1.1.1
  * Add `deleted_revenue_entries` stream. Fix `singer-check-tap` issues with `contracts` date-time fields.

## 1.1.0
  * Add `deleted_` streams for deleted `contracts`, `invoices`, and `transactions` [#2](https://github.com/singer-io/tap-saasoptics/pull/2)

## 1.0.0
  * Preparing for v1.0.0 release

## 0.0.2
  * Fix `date_window_size` config parameter; store as string, cast to integer.

## 0.0.1
  * Initial commit
