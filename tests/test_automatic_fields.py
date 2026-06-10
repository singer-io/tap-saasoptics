import unittest
from unittest.mock import MagicMock, patch

from tap_saasoptics.discover import discover
from tap_saasoptics.streams import STREAMS
from tap_saasoptics.sync import sync_endpoint

try:
    from .base import SaaSOpticsBaseTest
except ImportError:
    from base import SaaSOpticsBaseTest


class AutomaticFieldsIntegrationTest(SaaSOpticsBaseTest, unittest.TestCase):
    """
    Verify that primary keys and replication keys — the minimum 'automatic'
    fields — are always present in every synced record, without relying on
    schema.py marking them as automatic.
    """

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _run_sync_endpoint(self, stream_name, record):
        """Run sync_endpoint for *stream_name* with a single mocked record."""
        endpoint_config = STREAMS[stream_name]
        mock_client = MagicMock()
        mock_client.base_url = (
            "https://dummy-subdomain.saasoptics.com/dummy-account/api/v1.0"
        )
        mock_client.get.return_value = self._make_client_response([record])

        catalog = discover()

        sync_endpoint(
            client=mock_client,
            catalog=catalog,
            state={},
            start_date=self.default_start_date,
            stream_name=stream_name,
            path=endpoint_config.get("path", stream_name),
            endpoint_config=endpoint_config,
            static_params=endpoint_config.get("params", {}),
            bookmark_query_field_from=endpoint_config.get("bookmark_query_field_from"),
            bookmark_query_field_to=endpoint_config.get("bookmark_query_field_to"),
            bookmark_field=next(
                iter(endpoint_config.get("replication_keys", [])), None
            ),
            bookmark_type=endpoint_config.get("bookmark_type"),
            data_key=endpoint_config.get("data_key", "results"),
            id_fields=endpoint_config.get("key_properties"),
            days_interval=3650,
        )

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    @patch("tap_saasoptics.sync.singer.write_state")
    @patch("tap_saasoptics.sync.write_record")
    @patch("tap_saasoptics.sync.write_schema")
    @patch("tap_saasoptics.sync.transform_json")
    def test_primary_keys_present_in_every_synced_record(
        self,
        mock_transform_json,
        _mock_write_schema,
        mock_write_record,
        _mock_write_state,
    ):
        """
        For every stream, the primary key field(s) must appear in each
        record passed to write_record.
        """
        for stream_name, expected in self.expected_metadata().items():
            with self.subTest(stream=stream_name):
                record = self._generate_stream_record(stream_name)
                mock_transform_json.return_value = [record]
                mock_write_record.reset_mock()

                self._run_sync_endpoint(stream_name, record)

                self.assertGreater(
                    mock_write_record.call_count,
                    0,
                    msg=f"Stream '{stream_name}': write_record was never called",
                )
                for call in mock_write_record.call_args_list:
                    written_record = call.args[1]
                    for pk in expected[self.PRIMARY_KEYS]:
                        self.assertIn(
                            pk,
                            written_record,
                            msg=(
                                f"Stream '{stream_name}': primary key '{pk}' "
                                f"missing from synced record"
                            ),
                        )

    @patch("tap_saasoptics.sync.singer.write_state")
    @patch("tap_saasoptics.sync.write_record")
    @patch("tap_saasoptics.sync.write_schema")
    @patch("tap_saasoptics.sync.transform_json")
    def test_replication_keys_present_in_every_incremental_stream_record(
        self,
        mock_transform_json,
        _mock_write_schema,
        mock_write_record,
        _mock_write_state,
    ):
        """
        For every INCREMENTAL stream, the replication key field must appear
        in each record passed to write_record.
        """
        for stream_name, expected in self.expected_metadata().items():
            if expected[self.REPLICATION_METHOD] != "INCREMENTAL":
                continue
            with self.subTest(stream=stream_name):
                record = self._generate_stream_record(stream_name)
                mock_transform_json.return_value = [record]
                mock_write_record.reset_mock()

                self._run_sync_endpoint(stream_name, record)

                self.assertGreater(
                    mock_write_record.call_count,
                    0,
                    msg=f"Stream '{stream_name}': write_record was never called",
                )
                for call in mock_write_record.call_args_list:
                    written_record = call.args[1]
                    for rep_key in expected[self.REPLICATION_KEYS]:
                        self.assertIn(
                            rep_key,
                            written_record,
                            msg=(
                                f"Stream '{stream_name}': replication key "
                                f"'{rep_key}' missing from synced record"
                            ),
                        )
