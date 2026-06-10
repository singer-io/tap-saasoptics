import unittest
from unittest.mock import MagicMock, patch

from tap_saasoptics.discover import discover
from tap_saasoptics.sync import sync_endpoint

try:
    from .base import SaaSOpticsBaseTest
except ImportError:
    from base import SaaSOpticsBaseTest


class BookmarkIntegrationTest(SaaSOpticsBaseTest, unittest.TestCase):
    """
    Integration tests for bookmark / state management.

    Verifies that:
    * An existing bookmark is forwarded as the window-start query parameter.
    * After a successful sync the bookmark is advanced to the max record value.
    * FULL_TABLE streams do not write a bookmark.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_incremental_sync(self, stream_name, records, initial_bookmark=None):
        """
        Run sync_endpoint for an INCREMENTAL stream and return the resulting state.
        """
        endpoint_config = {
            "key_properties": ["id"],
            "replication_method": "INCREMENTAL",
            "replication_keys": ["modified"],
            "bookmark_query_field_from": "modified__gte",
            "bookmark_query_field_to": "modified__lte",
            "bookmark_type": "datetime",
        }

        state = {}
        if initial_bookmark:
            state["bookmarks"] = {stream_name: initial_bookmark}

        mock_client = MagicMock()
        mock_client.base_url = (
            "https://dummy-subdomain.saasoptics.com/dummy-account/api/v1.0"
        )
        mock_client.get.return_value = {
            "count": len(records),
            "next": None,
            "results": records,
        }

        catalog = discover()

        with patch("tap_saasoptics.sync.transform_json", side_effect=lambda d, s, p: d.get(p, [])), \
             patch("tap_saasoptics.sync.singer.write_state"), \
             patch("tap_saasoptics.sync.write_schema"):
            sync_endpoint(
                client=mock_client,
                catalog=catalog,
                state=state,
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
                days_interval=60,
            )

        return state, mock_client

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    @patch("tap_saasoptics.sync.singer.write_state")
    @patch("tap_saasoptics.sync.write_schema")
    @patch("tap_saasoptics.sync.transform_json")
    def test_existing_bookmark_used_as_window_start(
        self, mock_transform_json, _mock_write_schema, _mock_write_state
    ):
        """
        When a bookmark exists in state it must be passed as the
        bookmark_query_field_from value in the first API request.
        """
        existing_bookmark = "2025-06-01T00:00:00Z"
        stream_name = "customers"
        record = {"id": "1", "modified": "2025-06-15T00:00:00Z"}
        mock_transform_json.return_value = [record]

        state = {"bookmarks": {stream_name: existing_bookmark}}

        mock_client = MagicMock()
        mock_client.base_url = (
            "https://dummy-subdomain.saasoptics.com/dummy-account/api/v1.0"
        )
        mock_client.get.return_value = {"count": 1, "next": None, "results": [record]}

        endpoint_config = {
            "key_properties": ["id"],
            "replication_method": "INCREMENTAL",
            "replication_keys": ["modified"],
            "bookmark_query_field_from": "modified__gte",
            "bookmark_query_field_to": "modified__lte",
            "bookmark_type": "datetime",
        }

        catalog = discover()
        sync_endpoint(
            client=mock_client,
            catalog=catalog,
            state=state,
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

        # The querystring passed to client.get must contain modified__gte=<bookmark>
        call_kwargs = mock_client.get.call_args_list[0]
        params_str = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params", "")
        self.assertIn(
            "modified__gte",
            str(params_str),
            msg="Existing bookmark was not forwarded as modified__gte",
        )
        self.assertIn(
            "2025-06-01",
            str(params_str),
            msg="Existing bookmark date value was not found in query params",
        )

    @patch("tap_saasoptics.sync.singer.write_state")
    @patch("tap_saasoptics.sync.write_schema")
    @patch("tap_saasoptics.sync.transform_json")
    def test_bookmark_advances_after_sync(
        self, mock_transform_json, _mock_write_schema, _mock_write_state
    ):
        """
        After sync_endpoint runs, the state bookmark must be >= the initial bookmark.
        """
        old_bookmark = "2025-01-01T00:00:00Z"
        stream_name = "customers"
        records = [
            {"id": "1", "modified": "2025-02-01T00:00:00Z"},
            {"id": "2", "modified": "2025-03-01T00:00:00Z"},
            {"id": "3", "modified": "2025-04-01T00:00:00Z"},
        ]
        mock_transform_json.return_value = records

        state = {"bookmarks": {stream_name: old_bookmark}}

        mock_client = MagicMock()
        mock_client.base_url = (
            "https://dummy-subdomain.saasoptics.com/dummy-account/api/v1.0"
        )
        mock_client.get.return_value = {
            "count": len(records),
            "next": None,
            "results": records,
        }

        endpoint_config = {
            "key_properties": ["id"],
            "replication_method": "INCREMENTAL",
            "replication_keys": ["modified"],
            "bookmark_query_field_from": "modified__gte",
            "bookmark_query_field_to": "modified__lte",
            "bookmark_type": "datetime",
        }

        catalog = discover()
        sync_endpoint(
            client=mock_client,
            catalog=catalog,
            state=state,
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

        new_bookmark = state.get("bookmarks", {}).get(stream_name)
        self.assertIsNotNone(new_bookmark, msg="Bookmark was not written to state")
        self.assertGreaterEqual(
            new_bookmark,
            old_bookmark,
            msg=f"Bookmark was not advanced: {new_bookmark!r} < {old_bookmark!r}",
        )

    @patch("tap_saasoptics.sync.singer.write_state")
    @patch("tap_saasoptics.sync.write_schema")
    @patch("tap_saasoptics.sync.transform_json")
    def test_full_table_stream_does_not_write_bookmark(
        self, mock_transform_json, _mock_write_schema, _mock_write_state
    ):
        """FULL_TABLE streams must not write a bookmark to state."""
        stream_name = "accounts"
        record = self._generate_stream_record(stream_name)
        mock_transform_json.return_value = [record]

        state = {}
        mock_client = MagicMock()
        mock_client.base_url = (
            "https://dummy-subdomain.saasoptics.com/dummy-account/api/v1.0"
        )
        mock_client.get.return_value = {"count": 1, "next": None, "results": [record]}

        endpoint_config = {
            "key_properties": ["id"],
            "replication_method": "FULL_TABLE",
        }

        catalog = discover()
        sync_endpoint(
            client=mock_client,
            catalog=catalog,
            state=state,
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

        self.assertNotIn(
            stream_name,
            state.get("bookmarks", {}),
            msg="FULL_TABLE stream must not write a bookmark",
        )
