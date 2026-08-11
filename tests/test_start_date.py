import unittest
from unittest.mock import MagicMock, patch

from tap_saasoptics.discover import discover
from tap_saasoptics.sync import sync_endpoint

try:
    from .base import SaaSOpticsBaseTest
except ImportError:
    from base import SaaSOpticsBaseTest


class StartDateIntegrationTest(SaaSOpticsBaseTest, unittest.TestCase):
    """
    Integration tests that verify the tap uses `start_date` from the config
    when no prior bookmark exists in state.
    """

    def _run_sync_endpoint_for_customers(self, state):
        """Run sync_endpoint for the 'customers' stream with the given state."""
        stream_name = "customers"
        record = {"id": "1", "modified": "2025-02-01T00:00:00Z"}

        mock_client = MagicMock()
        mock_client.base_url = (
            "https://dummy-subdomain.saasoptics.com/dummy-account/api/v1.0"
        )
        mock_client.get.return_value = {"count": 1, "next": None, "results": [record]}

        catalog = discover()

        with patch("tap_saasoptics.sync.transform_json", return_value=[record]), \
             patch("tap_saasoptics.sync.singer.write_state"), \
             patch("tap_saasoptics.sync.write_schema"):
            sync_endpoint(
                client=mock_client,
                catalog=catalog,
                state=state,
                start_date=self.config["start_date"],
                stream_name=stream_name,
                path=stream_name,
                endpoint_config={
                    "key_properties": ["id"],
                    "replication_method": "INCREMENTAL",
                    "replication_keys": ["modified"],
                    "bookmark_query_field_from": "modified__gte",
                    "bookmark_query_field_to": "modified__lte",
                    "bookmark_type": "datetime",
                },
                static_params={},
                bookmark_query_field_from="modified__gte",
                bookmark_query_field_to="modified__lte",
                bookmark_field="modified",
                bookmark_type="datetime",
                data_key="results",
                id_fields=["id"],
                days_interval=3650,
            )

        return mock_client

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_start_date_used_as_window_start_when_no_bookmark(self):
        """
        When no bookmark exists the query param must equal start_date.
        """
        mock_client = self._run_sync_endpoint_for_customers(state={})

        call_kwargs = mock_client.get.call_args
        params_str = (
            call_kwargs.kwargs.get("params") or call_kwargs[1].get("params", "")
        ) or ""

        self.assertIn(
            "modified__gte",
            str(params_str),
            msg="modified__gte was not sent when no bookmark exists",
        )
        # The year from the default start date must appear in the query
        start_year = self.default_start_date[:4]
        self.assertIn(
            start_year,
            str(params_str),
            msg="start_date year was not found in the modified__gte query param",
        )

    def test_state_initialised_with_start_date_when_no_bookmark(self):
        """
        After syncing from scratch the bookmark written to state must equal
        the max record value (which is >= start_date).
        """
        state = {}
        self._run_sync_endpoint_for_customers(state)

        new_bookmark = state.get("bookmarks", {}).get("customers")
        self.assertIsNotNone(
            new_bookmark,
            msg="No bookmark was written to state after initial sync",
        )
        self.assertGreaterEqual(
            new_bookmark,
            self.default_start_date,
            msg="Initial bookmark must not be before start_date",
        )

    def test_custom_start_date_is_respected(self):
        """
        Changing start_date in config must change the query window when no
        prior bookmark exists.
        """
        self.config["start_date"] = "2025-06-15T00:00:00Z"

        stream_name = "customers"
        record = {"id": "1", "modified": "2025-07-01T00:00:00Z"}

        mock_client = MagicMock()
        mock_client.base_url = (
            "https://dummy-subdomain.saasoptics.com/dummy-account/api/v1.0"
        )
        mock_client.get.return_value = {"count": 1, "next": None, "results": [record]}

        catalog = discover()

        with patch("tap_saasoptics.sync.transform_json", return_value=[record]), \
             patch("tap_saasoptics.sync.singer.write_state"), \
             patch("tap_saasoptics.sync.write_schema"):
            sync_endpoint(
                client=mock_client,
                catalog=catalog,
                state={},
                start_date=self.config["start_date"],
                stream_name=stream_name,
                path=stream_name,
                endpoint_config={
                    "key_properties": ["id"],
                    "replication_method": "INCREMENTAL",
                    "replication_keys": ["modified"],
                    "bookmark_query_field_from": "modified__gte",
                    "bookmark_query_field_to": "modified__lte",
                    "bookmark_type": "datetime",
                },
                static_params={},
                bookmark_query_field_from="modified__gte",
                bookmark_query_field_to="modified__lte",
                bookmark_field="modified",
                bookmark_type="datetime",
                data_key="results",
                id_fields=["id"],
                days_interval=3650,
            )

        call_kwargs = mock_client.get.call_args_list[0]
        params_str = (
            call_kwargs.kwargs.get("params") or call_kwargs[1].get("params", "")
        ) or ""

        self.assertIn(
            "2025-06-15",
            str(params_str),
            msg="Custom start_date was not reflected in the first API request",
        )
