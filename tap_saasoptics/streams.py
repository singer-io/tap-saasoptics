# streams: API URL endpoints to be called
# properties:
#   <root node>: Plural stream name for the endpoint
#   path: API endpoint relative path, when added to the base URL, creates the full path,
#       default = stream_name
#   key_properties: Primary key fields for identifying an endpoint record.
#   replication_method: INCREMENTAL or FULL_TABLE
#   replication_keys: bookmark_field(s), typically a date-time, used for filtering the results
#        and setting the state
#   params: Query, sort, and other endpoint specific parameters; default = {}
#   data_key: JSON element containing the results list for the endpoint; default = 'results'
#   bookmark_query_field_from: From date-time field used for filtering the query
#   bookmark_query_field_to: To date-time field used for filtering the query
#   bookmark_type: Data type for bookmark, integer or datetime

STREAMS = {
    'customers': {
        'key_properties': ['id'],
        'replication_method': 'INCREMENTAL',
        'replication_keys': ['modified'],
        'bookmark_query_field_from': 'modified__gte',
        'bookmark_query_field_to': 'modified__lte',
        'bookmark_type': 'datetime'
    },
    'contracts': {
        'key_properties': ['id'],
        'replication_method': 'INCREMENTAL',
        'replication_keys': ['modified'],
        'bookmark_query_field_from': 'modified__gte',
        'bookmark_query_field_to': 'modified__lte',
        'bookmark_type': 'datetime'
    },
    'invoices': {
        'key_properties': ['id'],
        'replication_method': 'INCREMENTAL',
        'replication_keys': ['auditentry_modified'],
        'bookmark_query_field_from': 'auditentry__modified__gte',
        'bookmark_query_field_to': 'auditentry__modified__lte',
        'bookmark_type': 'datetime'
    },
    'items': {
        'key_properties': ['id'],
        'replication_method': 'INCREMENTAL',
        'replication_keys': ['modified'],
        'bookmark_query_field_from': 'modified__gte',
        'bookmark_query_field_to': 'modified__lte',
        'bookmark_type': 'datetime'
    },
    'transactions': {
        'key_properties': ['id'],
        'replication_method': 'INCREMENTAL',
        'replication_keys': ['modified'],
        'bookmark_query_field_from': 'auditentry__modified__gte',
        'bookmark_query_field_to': 'auditentry__modified__lte',
        'bookmark_type': 'datetime'
    },
    'billing_descriptions': {
        'key_properties': ['id'],
        'replication_method': 'FULL_TABLE'
    },
    'accounts': {
        'key_properties': ['id'],
        'replication_method': 'FULL_TABLE'
    },
    'auto_renewal_profiles': {
        'key_properties': ['id'],
        'replication_method': 'FULL_TABLE'
    },
    'billing_methods': {
        'key_properties': ['id'],
        'replication_method': 'FULL_TABLE'
    },
    'country_codes': {
        'key_properties': ['id'],
        'replication_method': 'FULL_TABLE'
    },
    'currency_codes': {
        'key_properties': ['code'],
        'replication_method': 'FULL_TABLE'
    },
    'payment_terms': {
        'key_properties': ['id'],
        'replication_method': 'FULL_TABLE'
    },
    'registers': {
        'key_properties': ['id'],
        'replication_method': 'INCREMENTAL',
        'replication_keys': ['modified'],
        'bookmark_query_field_from': 'modified__gte',
        'bookmark_query_field_to': 'modified__lte',
        'bookmark_type': 'datetime'
    },
    'revenue_entries': {
        'key_properties': ['id'],
        'replication_method': 'INCREMENTAL',
        'replication_keys': ['modified'],
        'bookmark_query_field_from': 'modified__gte',
        'bookmark_query_field_to': 'modified__lte',
        'bookmark_type': 'datetime'
    },
    'revenue_recognition_methods': {
        'key_properties': ['id'],
        'replication_method': 'FULL_TABLE'
    },
    'sales_orders': {
        'key_properties': ['id'],
        'replication_method': 'FULL_TABLE'
    }
}
