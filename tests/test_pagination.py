import unittest
from unittest.mock import MagicMock, patch, call

from tap_saasoptics.discover import discover
from tap_saasoptics.sync import sync_endpoint

try:
    from .base import SaaSOpticsBaseTest
except ImportError:
    from base import SaaSOpticsBaseTest


class PaginationIntegrationTest(SaaSOpticsBaseTest, unittest.TestCase):
    """
    Integration tests that verify sync_endpoint follows 'next' URLs and
    accumulates records across multiple API pages.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_paginated_client(self, pages):
        """
        Return a MagicMock client whose get() returns pages in sequence.

        *pages* is a list of (records_list, next_url_or_None) tuples.
        """
        base_url = "https://dummy-subdomain.saasoptics.com/dummy-account/api/v1.0"

        responses = [
            {"count": sum(len(p[0]) for p in pages), "next": nxt, "results": recs}
            for recs, nxt in pages
        ]

        mock_client = MagicMock()
        mock_client.base_url = base_url
        mock_client.get.side_effect = responses
        return mock_client

    def _make_records(self, stream_name, n, start_date_offset=0):
        """Generate *n* schema-valid records for *stream_name*."""
        dates = [
            f"2025-{(i + 1 + start_date_offset):02d}-01T00:00:00Z"
            for i in range(n)
        ]
        return [
            self._generate_stream_record(stream_name, date_value=d) for d in dates
        ]

    def _call_sync_endpoint(self, mock_client, catalog, state, stream_name,
                            endpoint_config):
        """Wrapper that calls sync_endpoint with standard INCREMENTAL config."""
        with patch("tap_saasoptics.sync.transform_json",
                   side_effect=lambda d, s, p: d.get(p, [])), \
             patch("tap_saasoptics.sync.singer.write_state"), \
             patch("tap_saasoptics.sync.write_schema"):
            return sync_endpoint(
                client=mock_client,
                catalog=catalog,
                state=state,
                start_date=self.default_start_date,
                stream_name=stream_name,
                path=endpoint_config.get("path", stream_name),
                endpoint_config=endpoint_config,
                static_params=endpoint_config.get("params", {}),
                bookmark_query_field_from=endpoint_config.get(
                    "bookmark_query_field_from"
                ),
                bookmark_query_field_to=endpoint_config.get(
                    "bookmark_query_field_to"
                ),
                bookmark_field=next(
                    iter(endpoint_config.get("replication_keys", [])), None
                ),
                bookmark_type=endpoint_config.get("bookmark_type"),
                data_key=endpoint_config.get("data_key", "results"),
                id_fields=endpoint_config.get("key_properties"),
                days_interval=60,
            )

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    @patch("tap_saasoptics.sync.write_record")
    def test_pagination_all_pages_processed(self, mock_write_record):
        """
        When the API returns two pages, every record from both pages must
        be written via write_record.
        """
        stream_name = "customers"
        endpoint_config = {
            "key_properties": ["id"],
            "replication_method": "INCREMENTAL",
            "replication_keys": ["modified"],
            "bookmark_query_field_from": "modified__gte",
            "bookmark_query_field_to": "modified__lte",
            "bookmark_type": "datetime",
        }

        page1_records = [
            {"id": "1", "modified": "2025-01-15T00:00:00Z"},
            {"id": "2", "modified": "2025-02-15T00:00:00Z"},
        ]
        page2_records = [
            {"id": "3", "modified": "2025-03-15T00:00:00Z"},
            {"id": "4", "modified": "2025-04-15T00:00:00Z"},
        ]

        base_url = (
            "https://dummy-subdomain.saasoptics.com/dummy-account/api/v1.0"
        )
        page2_url = f"{base_url}/customers/?page=2"

        mock_client = self._build_paginated_client([
            (page1_records, page2_url),
            (page2_records, None),
        ])

        catalog = discover()

        with patch("tap_saasoptics.sync.transform_json",
                   side_effect=lambda d, s, p: d.get(p, [])), \
             patch("tap_saasoptics.sync.singer.write_state"), \
             patch("tap_saasoptics.sync.write_schema"):
            sync_endpoint(
                client=mock_client,
                catalog=catalog,
                state={},
                start_date=self.default_start_date,
                stream_name=stream_name,
                path=stream_name,
                endpoint_config=endpoint_config,
                static_params={},
                bookmark_query_field_from="modified__gte",
                bookmark_query_field_to="modified__lte",
                bookmark_field="modified",
                bookmark_type="datetime",
                data_key="results",
                id_fields=["id"],
                days_interval=3650,
            )

        # client.get was called for page1 (by path) and page2 (by next url)
        self.assertEqual(mock_client.get.call_count, 2)
        # write_record was called for all 4 records
        self.assertEqual(mock_write_record.call_count, 4)

    @patch("tap_saasoptics.sync.write_record")
    def test_single_page_response_processed_correctly(self, mock_write_record):
        """
        When the API returns a single page with no next URL, all records
        on that page must be written and get() must be called exactly once.
        """
        stream_name = "items"
        endpoint_config = {
            "key_properties": ["id"],
            "replication_method": "INCREMENTAL",
            "replication_keys": ["modified"],
            "bookmark_query_field_from": "modified__gte",
            "bookmark_query_field_to": "modified__lte",
            "bookmark_type": "datetime",
        }
        records = [
            {"id": "1", "modified": "2025-01-10T00:00:00Z"},
            {"id": "2", "modified": "2025-01-20T00:00:00Z"},
            {"id": "3", "modified": "2025-01-30T00:00:00Z"},
        ]

        mock_client = self._build_paginated_client([(records, None)])
        catalog = discover()

        with patch("tap_saasoptics.sync.transform_json",
                   side_effect=lambda d, s, p: d.get(p, [])), \
             patch("tap_saasoptics.sync.singer.write_state"), \
             patch("tap_saasoptics.sync.write_schema"):
            sync_endpoint(
                client=mock_client,
                catalog=catalog,
                state={},
                start_date=self.default_start_date,
                stream_name=stream_name,
                path=stream_name,
                endpoint_config=endpoint_config,
                static_params={},
                bookmark_query_field_from="modified__gte",
                bookmark_query_field_to="modified__lte",
                bookmark_field="modified",
                bookmark_type="datetime",
                data_key="results",
                id_fields=["id"],
                days_interval=3650,
            )

        self.assertEqual(mock_client.get.call_count, 1)
        self.assertEqual(mock_write_record.call_count, 3)

    @patch("tap_saasoptics.sync.write_record")
    def test_empty_response_writes_no_records(self, mock_write_record):
        """
        When the API returns an empty results list, write_record must not
        be called at all.
        """
        stream_name = "billing_descriptions"
        endpoint_config = {
            "key_properties": ["id"],
            "replication_method": "FULL_TABLE",
        }

        mock_client = MagicMock()
        mock_client.base_url = (
            "https://dummy-subdomain.saasoptics.com/dummy-account/api/v1.0"
        )
        mock_client.get.return_value = {"count": 0, "next": None, "results": []}

        catalog = discover()

        with patch("tap_saasoptics.sync.transform_json",
                   side_effect=lambda d, s, p: d.get(p, [])), \
             patch("tap_saasoptics.sync.singer.write_state"), \
             patch("tap_saasoptics.sync.write_schema"):
            sync_endpoint(
                client=mock_client,
                catalog=catalog,
                state={},
                start_date=self.default_start_date,
                stream_name=stream_name,
                path=stream_name,
                endpoint_config=endpoint_config,
                static_params={},
                bookmark_query_field_from=None,
                bookmark_query_field_to=None,
                bookmark_field=None,
                bookmark_type=None,
                data_key="results",
                id_fields=["id"],
                days_interval=60,
            )

        mock_write_record.assert_not_called()

    @patch("tap_saasoptics.sync.write_record")
    def test_three_page_pagination(self, mock_write_record):
        """Verify that three API pages are all consumed correctly."""
        stream_name = "revenue_entries"
        endpoint_config = {
            "key_properties": ["id"],
            "replication_method": "INCREMENTAL",
            "replication_keys": ["modified"],
            "bookmark_query_field_from": "modified__gte",
            "bookmark_query_field_to": "modified__lte",
            "bookmark_type": "datetime",
        }

        base_url = (
            "https://dummy-subdomain.saasoptics.com/dummy-account/api/v1.0"
        )
        page2_url = f"{base_url}/revenue_entries/?page=2"
        page3_url = f"{base_url}/revenue_entries/?page=3"

        page1 = [{"id": "1", "modified": "2025-01-05T00:00:00Z"}]
        page2 = [{"id": "2", "modified": "2025-02-05T00:00:00Z"},
                 {"id": "3", "modified": "2025-03-05T00:00:00Z"}]
        page3 = [{"id": "4", "modified": "2025-04-05T00:00:00Z"}]

        mock_client = self._build_paginated_client([
            (page1, page2_url),
            (page2, page3_url),
            (page3, None),
        ])

        catalog = discover()

        with patch("tap_saasoptics.sync.transform_json",
                   side_effect=lambda d, s, p: d.get(p, [])), \
             patch("tap_saasoptics.sync.singer.write_state"), \
             patch("tap_saasoptics.sync.write_schema"):
            sync_endpoint(
                client=mock_client,
                catalog=catalog,
                state={},
                start_date=self.default_start_date,
                stream_name=stream_name,
                path=stream_name,
                endpoint_config=endpoint_config,
                static_params={},
                bookmark_query_field_from="modified__gte",
                bookmark_query_field_to="modified__lte",
                bookmark_field="modified",
                bookmark_type="datetime",
                data_key="results",
                id_fields=["id"],
                days_interval=3650,
            )

        self.assertEqual(mock_client.get.call_count, 3)
        self.assertEqual(mock_write_record.call_count, 4)
