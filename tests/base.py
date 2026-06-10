from tap_saasoptics.schema import get_schemas


class SaaSOpticsBaseTest:
    """
    Base class for tap-saasoptics mock integration tests.

    Provides expected stream metadata, setUp/tearDown helpers, and utilities
    for generating schema-valid mock records without hitting the real API.
    """

    default_start_date = "2025-01-01T00:00:00Z"

    # Constants used as keys in expected_metadata()
    PRIMARY_KEYS = "primary_keys"
    REPLICATION_METHOD = "replication_method"
    REPLICATION_KEYS = "replication_keys"
    OBEYS_START_DATE = "obeys_start_date"

    @classmethod
    def expected_metadata(cls):
        """Return a dict of stream_name -> expected Singer metadata properties."""
        return {
            "customers": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "INCREMENTAL",
                cls.REPLICATION_KEYS: {"modified"},
                cls.OBEYS_START_DATE: True,
            },
            "contracts": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "INCREMENTAL",
                cls.REPLICATION_KEYS: {"modified"},
                cls.OBEYS_START_DATE: True,
            },
            "invoices": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "INCREMENTAL",
                cls.REPLICATION_KEYS: {"auditentry_modified"},
                cls.OBEYS_START_DATE: True,
            },
            "items": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "INCREMENTAL",
                cls.REPLICATION_KEYS: {"modified"},
                cls.OBEYS_START_DATE: True,
            },
            "transactions": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "INCREMENTAL",
                cls.REPLICATION_KEYS: {"modified"},
                cls.OBEYS_START_DATE: True,
            },
            "billing_descriptions": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "FULL_TABLE",
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
            },
            "accounts": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "FULL_TABLE",
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
            },
            "auto_renewal_profiles": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "FULL_TABLE",
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
            },
            "billing_methods": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "FULL_TABLE",
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
            },
            "country_codes": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "FULL_TABLE",
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
            },
            "currency_codes": {
                cls.PRIMARY_KEYS: {"code"},
                cls.REPLICATION_METHOD: "FULL_TABLE",
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
            },
            "payment_terms": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "FULL_TABLE",
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
            },
            "registers": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "INCREMENTAL",
                cls.REPLICATION_KEYS: {"modified"},
                cls.OBEYS_START_DATE: True,
            },
            "revenue_entries": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "INCREMENTAL",
                cls.REPLICATION_KEYS: {"modified"},
                cls.OBEYS_START_DATE: True,
            },
            "revenue_recognition_methods": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "FULL_TABLE",
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
            },
            "sales_orders": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "FULL_TABLE",
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
            },
            "deleted_contracts": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "INCREMENTAL",
                cls.REPLICATION_KEYS: {"deleted"},
                cls.OBEYS_START_DATE: True,
            },
            "deleted_transactions": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "INCREMENTAL",
                cls.REPLICATION_KEYS: {"deleted"},
                cls.OBEYS_START_DATE: True,
            },
            "deleted_invoices": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "INCREMENTAL",
                cls.REPLICATION_KEYS: {"deleted"},
                cls.OBEYS_START_DATE: True,
            },
            "deleted_revenue_entries": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "INCREMENTAL",
                cls.REPLICATION_KEYS: {"deleted"},
                cls.OBEYS_START_DATE: True,
            },
        }

    def setUp(self):
        """Populate self.config and self.state with safe test defaults."""
        self.config = {
            "token": "dummy-token",
            "account_name": "dummy-account",
            "server_subdomain": "dummy-subdomain",
            "user_agent": "test-agent/1.0",
            "start_date": self.default_start_date,
        }
        self.state = {}

    # ------------------------------------------------------------------
    # Schema-aware mock-data helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _schema_type(schema):
        """Return the concrete JSON-schema type, collapsing null-unions."""
        schema_type = schema.get("type", "object")
        if isinstance(schema_type, list):
            non_null = [t for t in schema_type if t != "null"]
            return non_null[0] if non_null else "null"
        return schema_type

    @staticmethod
    def _generate_value(schema, date_value="2025-01-01T00:00:00Z"):
        """Recursively generate one valid mock value for a JSON-schema fragment."""
        # Handle anyOf by choosing the first non-null sub-schema.
        # This covers fields like {"anyOf": [{"type": "null"}, {"type": "string",
        # "format": "date-time"}]} which have no top-level "type" key.
        if "anyOf" in schema:
            non_null = [
                s for s in schema["anyOf"]
                if s.get("type") != "null"
            ]
            if non_null:
                return SaaSOpticsBaseTest._generate_value(
                    non_null[0], date_value=date_value
                )
            return None

        if "enum" in schema and schema["enum"]:
            return schema["enum"][0]

        schema_type = SaaSOpticsBaseTest._schema_type(schema)

        if schema_type == "object":
            properties = schema.get("properties", {})
            required = set(schema.get("required", []))
            return {
                key: SaaSOpticsBaseTest._generate_value(val, date_value=date_value)
                for key, val in properties.items()
                if key in required
                or SaaSOpticsBaseTest._schema_type(val) != "null"
            }

        if schema_type == "array":
            item_schema = schema.get("items", {"type": "string"})
            return [SaaSOpticsBaseTest._generate_value(
                item_schema, date_value=date_value
            )]

        if schema_type == "string":
            fmt = schema.get("format")
            if fmt == "date-time":
                return date_value
            if fmt == "email":
                return "mock@example.com"
            return "mock"

        return {"integer": 1, "number": 1.0, "boolean": True}.get(schema_type)

    @staticmethod
    def _generate_stream_record(stream_name, date_value="2025-01-01T00:00:00Z"):
        """Generate one schema-valid record dict for the given stream."""
        schemas, _ = get_schemas()
        return SaaSOpticsBaseTest._generate_value(
            schemas[stream_name], date_value=date_value
        )

    def _make_client_response(self, records, next_url=None):
        """Return a dict that mimics a paginated SaaSOptics API page response."""
        return {
            "count": len(records),
            "next": next_url,
            "results": records,
        }
