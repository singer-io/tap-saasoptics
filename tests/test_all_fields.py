import unittest
from unittest.mock import MagicMock, patch, call

from tap_saasoptics.discover import discover
from tap_saasoptics.streams import STREAMS
from tap_saasoptics.sync import sync

try:
    from .base import SaaSOpticsBaseTest
except ImportError:
    from base import SaaSOpticsBaseTest


class AllFieldsIntegrationTest(SaaSOpticsBaseTest, unittest.TestCase):
    """
    Integration tests that verify every selected stream is synced and
    that Singer write_record is called with schema-valid records.
    """

    # ------------------------------------------------------------------
    # Helper: build a mock client whose .get() always returns one record
    # ------------------------------------------------------------------

    def _build_mock_client(self, stream_name, record, next_url=None):
        """
        Return a MagicMock SaaSOpticsClient whose get() returns a single-page
        response containing *record*.
        """
        mock_client = MagicMock()
        mock_client.base_url = "https://dummy-subdomain.saasoptics.com/dummy-account/api/v1.0"
        mock_client.get.return_value = self._make_client_response([record], next_url)
        return mock_client

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    @patch("tap_saasoptics.sync.singer.write_state")
    @patch("tap_saasoptics.sync.write_record")
    @patch("tap_saasoptics.sync.write_schema")
    @patch("tap_saasoptics.sync.sync_endpoint")
    def test_sync_calls_sync_endpoint_for_every_selected_stream(
        self,
        mock_sync_endpoint,
        _mock_write_schema,
        _mock_write_record,
        _mock_write_state,
    ):
        """sync() must call sync_endpoint once per selected stream."""
        mock_sync_endpoint.return_value = 1

        catalog = discover()
        catalog.get_selected_streams = lambda _state: catalog.streams

        mock_client = MagicMock()
        sync(client=mock_client, config=self.config, catalog=catalog, state=self.state)

        self.assertEqual(mock_sync_endpoint.call_count, len(STREAMS))

        synced_streams = {
            c.kwargs["stream_name"] for c in mock_sync_endpoint.call_args_list
        }
        self.assertEqual(synced_streams, set(STREAMS.keys()))

    @patch("tap_saasoptics.sync.singer.write_state")
    @patch("tap_saasoptics.sync.write_record")
    @patch("tap_saasoptics.sync.write_schema")
    @patch("tap_saasoptics.sync.transform_json")
    def test_every_stream_produces_at_least_one_record(
        self,
        mock_transform_json,
        _mock_write_schema,
        mock_write_record,
        _mock_write_state,
    ):
        """
        For each stream, sync_endpoint must call write_record at least once
        when the API returns a valid mock record.
        """
        from tap_saasoptics.sync import sync_endpoint

        for stream_name, endpoint_config in STREAMS.items():
            with self.subTest(stream=stream_name):
                record = self._generate_stream_record(stream_name)
                mock_transform_json.return_value = [record]

                mock_client = MagicMock()
                mock_client.base_url = (
                    "https://dummy-subdomain.saasoptics.com/dummy-account/api/v1.0"
                )
                mock_client.get.return_value = self._make_client_response([record])

                catalog = discover()
                state = {}
                mock_write_record.reset_mock()

                sync_endpoint(
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

                self.assertGreater(
                    mock_write_record.call_count,
                    0,
                    msg=f"Stream '{stream_name}': no records were written",
                )

    @patch("tap_saasoptics.sync.singer.write_state")
    @patch("tap_saasoptics.sync.write_record")
    @patch("tap_saasoptics.sync.write_schema")
    @patch("tap_saasoptics.sync.sync_endpoint")
    def test_sync_respects_selected_streams_subset(
        self,
        mock_sync_endpoint,
        _mock_write_schema,
        _mock_write_record,
        _mock_write_state,
    ):
        """sync() must only call sync_endpoint for streams in the selection."""
        mock_sync_endpoint.return_value = 0

        selected = ["customers", "contracts"]
        catalog = discover()
        catalog.get_selected_streams = lambda _state: [
            s for s in catalog.streams if s.stream in selected
        ]

        mock_client = MagicMock()
        sync(client=mock_client, config=self.config, catalog=catalog, state=self.state)

        self.assertEqual(mock_sync_endpoint.call_count, len(selected))
        synced_streams = {
            c.kwargs["stream_name"] for c in mock_sync_endpoint.call_args_list
        }
        self.assertEqual(synced_streams, set(selected))
