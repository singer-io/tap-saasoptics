# tap-saasoptics

This is a [Singer](https://singer.io) tap that produces JSON-formatted data
following the [Singer
spec](https://github.com/singer-io/getting-started/blob/master/SPEC.md).

This tap:

- Pulls raw data from the [SaaSOptics v1.0 API](xxx)
- Extracts the following resources:
  - [Customers](https://saasoptics.zendesk.com/hc/en-us/articles/115013751587-Customers-CRUD-)
  - [Contracts](https://saasoptics.zendesk.com/hc/en-us/articles/115013751607-Contracts-CRUD-)
  - [Invoices](https://saasoptics.zendesk.com/hc/en-us/articles/115013918148-Invoices-CRUD-)
  - [Items](https://saasoptics.zendesk.com/hc/en-us/articles/115013751567-Items-R-)
  - [Transactions](https://saasoptics.zendesk.com/hc/en-us/articles/360000066333-Transactions-CRUD-)
  - [Billing Desriptions](https://saasoptics.zendesk.com/hc/en-us/articles/115013751807-Billing-Line-Item-Descriptions-R-)
  - [Accounts](https://saasoptics.zendesk.com/hc/en-us/articles/115013751507-Accounts-R-)
  - [Auto Renewal Profiles](https://saasoptics.zendesk.com/hc/en-us/articles/115013918268-Auto-Renewal-Profiles-R-)
  - [Billing Methods](https://saasoptics.zendesk.com/hc/en-us/articles/115003604433-Billing-Methods-R-)
  - [Country Codes](https://saasoptics.zendesk.com/hc/en-us/articles/115003604453-Country-Codes-R-)
  - [Currency Codes](https://saasoptics.zendesk.com/hc/en-us/articles/115003604473-Currency-Codes-R-)
  - [Payment Terms](https://saasoptics.zendesk.com/hc/en-us/articles/115003642673-Payment-Terms-R-)
  - [Registers](https://saasoptics.zendesk.com/hc/en-us/articles/115013751707-Registers-R-)
  - [Revenue Entries](https://saasoptics.zendesk.com/hc/en-us/articles/115003674273-Revenue-Entries-R-)
  - [Revenue Recognition Methods](https://saasoptics.zendesk.com/hc/en-us/articles/115003617774-Revenue-Recognition-Methods-R-)
  - [Sales Orders](https://saasoptics.zendesk.com/hc/en-us/articles/360000738813-Sales-Orders-CR-)
- Outputs the schema for each resource
- Incrementally pulls data based on the input state


## Streams

[customers](https://saasoptics.zendesk.com/hc/en-us/articles/115013751587-Customers-CRUD-)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/customers/
- Primary key fields: id
- Foreign key fields: currency, payment_terms, parent
- Replication strategy: INCREMENTAL (query filtered)
  - Bookmark query fields: modified__gte, modified__lte
  - Bookmark: modified (date-time)
- Transformations: none

[contracts](https://saasoptics.zendesk.com/hc/en-us/articles/115013751607-Contracts-CRUD-)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/contracts/
- Primary key fields: id
- Foreign key fields: parent_id, payment_terms, customer, register
- Replication strategy: INCREMENTAL (query filtered)
  - Bookmark query fields: modified__gte, modified__lte
  - Bookmark: modified (date-time)
- Transformations: none

[invoices](https://saasoptics.zendesk.com/hc/en-us/articles/115013918148-Invoices-CRUD-)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/invoices/
- Primary key fields: id
- Foreign key fields: contract, item, transaction, 
- Replication strategy: INCREMENTAL (query filtered)
  - Bookmark query fields: auditentry__modified__gte, auditentry__modified__lte
  - Bookmark: modified (date-time)
- Transformations: none

[items](https://saasoptics.zendesk.com/hc/en-us/articles/115013751567-Items-R-)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/items/
- Primary key fields: id
- Foreign key fields: asset_account, billing_method, income_account, liability_account, revenue_recognition_method, 
- Replication strategy: INCREMENTAL (query filtered)
  - Bookmark query fields: modified__gte, modified__lte
  - Bookmark: modified (date-time)
- Transformations: none
  
[transactions](https://saasoptics.zendesk.com/hc/en-us/articles/360000066333-Transactions-CRUD-)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/transactions/
- Primary key fields: id
- Foreign key fields: autorenewal_profile, billing_method, contract, item, renew_using_item, 
- Replication strategy: INCREMENTAL (query filtered)
  - Bookmark query fields: auditentry__modified__gte, auditentry__modified__lte
  - Bookmark: modified (date-time)
- Transformations: none

[billing_descriptions](https://saasoptics.zendesk.com/hc/en-us/articles/115013751807-Billing-Line-Item-Descriptions-R-)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/billing_descriptions/
- Primary key fields: id
- Foreign key fields: none
- Replication strategy: FULL_TABLE
- Transformations: none

[accounts](https://saasoptics.zendesk.com/hc/en-us/articles/115013751507-Accounts-R-)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/accounts/
- Primary key fields: id
- Foreign key fields: none
- Replication strategy: FULL_TABLE
- Transformations: none

[auto_renewal_profiles](https://saasoptics.zendesk.com/hc/en-us/articles/115013918268-Auto-Renewal-Profiles-R-)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/auto_renewal_profiles/
- Primary key fields: id
- Foreign key fields: none
- Replication strategy: FULL_TABLE
- Transformations: none
  
[billing_methods](https://saasoptics.zendesk.com/hc/en-us/articles/115003604433-Billing-Methods-R-)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/billing_methods/
- Primary key fields: id
- Foreign key fields: none
- Replication strategy: FULL_TABLE
- Transformations: none

[country_codes](https://saasoptics.zendesk.com/hc/en-us/articles/115003604453-Country-Codes-R-)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/country_codes/
- Primary key fields: id
- Foreign key fields: none
- Replication strategy: FULL_TABLE
- Transformations: none

[currency_codes](https://saasoptics.zendesk.com/hc/en-us/articles/115003604473-Currency-Codes-R-)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/currency_codes/
- Primary key fields: code
- Foreign key fields: none
- Replication strategy: FULL_TABLE
- Transformations: none

[payment_terms](https://saasoptics.zendesk.com/hc/en-us/articles/115003642673-Payment-Terms-R-)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/payment_terms/
- Primary key fields: id
- Foreign key fields: none
- Replication strategy: FULL_TABLE
- Transformations: none

[registers](https://saasoptics.zendesk.com/hc/en-us/articles/115013751707-Registers-R-)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/registers/
- Primary key fields: id
- Foreign key fields: none
- Replication strategy: INCREMENTAL (query filtered)
  - Bookmark query fields: modified__gte, modified__lte
  - Bookmark: modified (date-time)
- Transformations: none

[revenue_entries](https://saasoptics.zendesk.com/hc/en-us/articles/115003674273-Revenue-Entries-R-)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/revenue_entries/
- Primary key fields: id
- Foreign key fields: transaction
- Replication strategy: INCREMENTAL (query filtered)
  - Bookmark query fields: modified__gte, modified__lte
  - Bookmark: modified (date-time)
- Transformations: none

[revenue_recognition_methods](https://saasoptics.zendesk.com/hc/en-us/articles/115003617774-Revenue-Recognition-Methods-R-)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/revenue_recognition_methods/
- Primary key fields: id
- Foreign key fields: none
- Replication strategy: FULL_TABLE
- Transformations: none

[sales_orders](https://saasoptics.zendesk.com/hc/en-us/articles/360000738813-Sales-Orders-CR-) and [sales_order_line_items](https://saasoptics.zendesk.com/hc/en-us/articles/360000751354)
- Endpoint: https://{server_subdomain}.saasoptics.com/{account_name}/api/v1.0/sales_orders/
- Primary key fields: id
- Foreign key fields: none
- Replication strategy: INCREMENTAL (query all, filter results)
  - Bookmark: created (date-time)
  - RECOMMENDATION: Include in initial load, then deactivate this endpoint. This table/endpoint contains historical sales orders only. It may contain A LOT of records that never/rarely change.
- Transformations: none

## Quick Start

1. Install

    Clone this repository, and then install using setup.py. We recommend using a virtualenv:

    ```bash
    > virtualenv -p python3 venv
    > source venv/bin/activate
    > python setup.py install
    OR
    > cd .../tap-saasoptics
    > pip install .
    ```
2. Dependent libraries
    The following dependent libraries were installed.
    ```bash
    > pip install singer-python
    > pip install singer-tools
    > pip install target-stitch
    > pip install target-json
    
    ```
    - [singer-tools](https://github.com/singer-io/singer-tools)
    - [target-stitch](https://github.com/singer-io/target-stitch)

3. Create your tap's `config.json` file. The `server_subdomain` is everything before `.saasoptics.com.` in the SaaSOptics URL.  The `account_name` is everything between `.saasoptics.com.` and `api` in the SaaSOptics URL. The `date_window_size` is the integer number of days (between the from and to dates) for date-windowing through the date-filtered endpoints (default = 60).

    ```json
    {
        "token": "YOUR_API_TOKEN",
        "account_name": "YOUR_ACCOUNT_NAME",
        "server_subdomain": "YOUR_SERVER_SUBDOMAIN",
        "start_date": "2019-01-01T00:00:00Z",
        "user_agent": "tap-saasoptics <api_user_email@your_company.com>",
        "date_window_size": "60"
    }
    ```
    
    Optionally, also create a `state.json` file. `currently_syncing` is an optional attribute used for identifying the last object to be synced in case the job is interrupted mid-stream. The next run would begin where the last job left off.

    ```json
    {
        "currently_syncing": "registers",
        "bookmarks": {
            "customers": "2019-06-11T13:37:51Z",
            "contracts": "2019-06-19T19:48:42Z",
            "invoices": "2019-06-18T18:23:53Z",
            "items": "2019-06-20T00:52:44Z",
            "transactions": "2019-06-19T19:48:45Z",
            "registers": "2019-06-11T13:37:56Z",
            "revenue_entries": "2019-06-19T19:48:47Z"
        }
    }
    ```

4. Run the Tap in Discovery Mode
    This creates a catalog.json for selecting objects/fields to integrate:
    ```bash
    tap-saasoptics --config config.json --discover > catalog.json
    ```
   See the Singer docs on discovery mode
   [here](https://github.com/singer-io/getting-started/blob/master/docs/DISCOVERY_MODE.md#discovery-mode).

5. Run the Tap in Sync Mode (with catalog) and [write out to state file](https://github.com/singer-io/getting-started/blob/master/docs/RUNNING_AND_DEVELOPING.md#running-a-singer-tap-with-a-singer-target)

    For Sync mode:
    ```bash
    > tap-saasoptics --config tap_config.json --catalog catalog.json > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```
    To load to json files to verify outputs:
    ```bash
    > tap-saasoptics --config tap_config.json --catalog catalog.json | target-json > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```
    To pseudo-load to [Stitch Import API](https://github.com/singer-io/target-stitch) with dry run:
    ```bash
    > tap-saasoptics --config tap_config.json --catalog catalog.json | target-stitch --config target_config.json --dry-run > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```

6. Test the Tap
    
    While developing the saasoptics tap, the following utilities were run in accordance with Singer.io best practices:
    Pylint to improve [code quality](https://github.com/singer-io/getting-started/blob/master/docs/BEST_PRACTICES.md#code-quality):
    ```bash
    > pylint tap_saasoptics -d missing-docstring -d logging-format-interpolation -d too-many-locals -d too-many-arguments
    ```
    Pylint test resulted in the following score:
    ```bash
    Your code has been rated at 9.83/10
    ```

    To [check the tap](https://github.com/singer-io/singer-tools#singer-check-tap) and verify working:
    ```bash
    > tap-saasoptics --config tap_config.json --catalog catalog.json | singer-check-tap > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```
    Check tap resulted in the following:
    ```bash
    The output is valid.
    It contained 8240 messages for 16 streams.

        16 schema messages
    8108 record messages
        116 state messages

    Details by stream:
    +-----------------------------+---------+---------+
    | stream                      | records | schemas |
    +-----------------------------+---------+---------+
    | billing_methods             | 23      | 1       |
    | contracts                   | 49      | 1       |
    | sales_orders                | 223     | 1       |
    | auto_renewal_profiles       | 6       | 1       |
    | invoices                    | 182     | 1       |
    | payment_terms               | 15      | 1       |
    | currency_codes              | 153     | 1       |
    | customers                   | 190     | 1       |
    | billing_descriptions        | 8       | 1       |
    | transactions                | 550     | 1       |
    | registers                   | 0       | 1       |
    | accounts                    | 356     | 1       |
    | country_codes               | 250     | 1       |
    | revenue_recognition_methods | 27      | 1       |
    | revenue_entries             | 6003    | 1       |
    | items                       | 73      | 1       |
    +-----------------------------+---------+---------+
    ```
---

Copyright &copy; 2019 Stitch
