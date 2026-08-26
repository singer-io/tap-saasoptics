# Changelog

## 1.2.1
  * SAC-32056: Measure branch coverage in CI, and cover the remaining conditional edges in `client.py`, `sync.py` and `__init__.py`.
  * SAC-32056: Fix SSRF in the SaaSOptics client. Validate the `server_subdomain` and `account_name` config values, reject request URLs (including paginated `next` URLs) outside of the SaaSOptics API base URL, stop following redirects, and stop logging the upstream response body.

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
