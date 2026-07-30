import unittest
from unittest.mock import MagicMock, patch, call
from singer.utils import strptime_to_utc, strftime

from datetime import datetime, timezone
from tap_saasoptics.sync import (
    get_bookmark,
    write_bookmark,
    process_records,
    update_currently_syncing,
    sync_endpoint,
    sync,
)

from tap_saasoptics.sync import (
    write_schema,
    write_record,
    transform_datetime,
    process_records,
    sync_endpoint,
)


# ---------------------------------------------------------------------------
# get_bookmark
# ---------------------------------------------------------------------------

class TestGetBookmark(unittest.TestCase):
    """Unit tests for get_bookmark()."""

    def test_returns_default_when_state_is_empty(self):
        self.assertEqual(
            get_bookmark({}, "customers", "2025-01-01T00:00:00Z"),
            "2025-01-01T00:00:00Z",
        )

    def test_returns_default_when_no_bookmarks_key(self):
        self.assertEqual(
            get_bookmark({"other": "value"}, "customers", "2025-01-01T00:00:00Z"),
            "2025-01-01T00:00:00Z",
        )

    def test_returns_default_when_stream_not_bookmarked(self):
        state = {"bookmarks": {"other_stream": "2025-03-01T00:00:00Z"}}
        self.assertEqual(
            get_bookmark(state, "customers", "2025-01-01T00:00:00Z"),
            "2025-01-01T00:00:00Z",
        )

    def test_returns_existing_bookmark(self):
        state = {"bookmarks": {"customers": "2025-06-01T00:00:00Z"}}
        self.assertEqual(
            get_bookmark(state, "customers", "2025-01-01T00:00:00Z"),
            "2025-06-01T00:00:00Z",
        )

    def test_returns_none_when_state_is_none(self):
        self.assertIsNone(get_bookmark(None, "customers", None))


# ---------------------------------------------------------------------------
# write_bookmark
# ---------------------------------------------------------------------------

class TestWriteBookmark(unittest.TestCase):
    """Unit tests for write_bookmark()."""

    @patch("tap_saasoptics.sync.singer.write_state")
    def test_creates_bookmarks_key_if_missing(self, _mock_write_state):
        state = {}
        write_bookmark(state, "customers", "2025-05-01T00:00:00Z")
        self.assertIn("bookmarks", state)
        self.assertEqual(state["bookmarks"]["customers"], "2025-05-01T00:00:00Z")

    @patch("tap_saasoptics.sync.singer.write_state")
    def test_overwrites_existing_bookmark(self, _mock_write_state):
        state = {"bookmarks": {"customers": "2025-01-01T00:00:00Z"}}
        write_bookmark(state, "customers", "2025-09-01T00:00:00Z")
        self.assertEqual(state["bookmarks"]["customers"], "2025-09-01T00:00:00Z")

    @patch("tap_saasoptics.sync.singer.write_state")
    def test_calls_singer_write_state(self, mock_write_state):
        state = {}
        write_bookmark(state, "customers", "2025-05-01T00:00:00Z")
        mock_write_state.assert_called_once_with(state)


# ---------------------------------------------------------------------------
# process_records
# ---------------------------------------------------------------------------

class TestProcessRecords(unittest.TestCase):
    """Unit tests for process_records()."""

    def _make_catalog(self, stream_name):
        """Return a minimal mock catalog for process_records()."""
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "modified": {"type": "string", "format": "date-time"},
                "name": {"type": "string"},
            },
        }
        stream = MagicMock()
        stream.schema.to_dict.return_value = schema
        stream.metadata = []

        catalog = MagicMock()
        catalog.get_stream.return_value = stream
        return catalog

    @patch("tap_saasoptics.sync.write_record")
    def test_writes_all_records_for_full_table(self, mock_write_record):
        """FULL_TABLE: all records must be written regardless of bookmark."""
        catalog = self._make_catalog("accounts")
        records = [
            {"id": "1", "name": "Acme"},
            {"id": "2", "name": "Beta"},
        ]
        from singer.utils import now
        max_bv, count = process_records(
            catalog=catalog,
            stream_name="accounts",
            records=records,
            time_extracted=now(),
            bookmark_field=None,
            bookmark_type=None,
            max_bookmark_value=None,
            last_datetime=None,
            last_integer=None,
        )
        self.assertEqual(count, 2)
        self.assertEqual(mock_write_record.call_count, 2)

    @patch("tap_saasoptics.sync.write_record")
    def test_filters_records_before_last_datetime(self, mock_write_record):
        """INCREMENTAL (datetime): records before last_datetime must be skipped."""
        catalog = self._make_catalog("customers")
        records = [
            {"id": "1", "modified": "2024-12-01T00:00:00Z"},  # before bookmark → skip
            {"id": "2", "modified": "2025-03-01T00:00:00Z"},  # after → include
            {"id": "3", "modified": "2025-06-01T00:00:00Z"},  # after → include
        ]
        from singer.utils import now
        _max_bv, count = process_records(
            catalog=catalog,
            stream_name="customers",
            records=records,
            time_extracted=now(),
            bookmark_field="modified",
            bookmark_type="datetime",
            max_bookmark_value="2025-01-01T00:00:00Z",
            last_datetime="2025-01-01T00:00:00Z",
            last_integer=None,
        )
        self.assertEqual(count, 2)
        self.assertEqual(mock_write_record.call_count, 2)

    @patch("tap_saasoptics.sync.write_record")
    def test_max_bookmark_value_is_advanced(self, _mock_write_record):
        """process_records() must return the highest bookmark seen across records."""
        catalog = self._make_catalog("customers")
        records = [
            {"id": "1", "modified": "2025-02-01T00:00:00Z"},
            {"id": "2", "modified": "2025-05-01T00:00:00Z"},
            {"id": "3", "modified": "2025-03-01T00:00:00Z"},
        ]
        from singer.utils import now
        max_bv, _ = process_records(
            catalog=catalog,
            stream_name="customers",
            records=records,
            time_extracted=now(),
            bookmark_field="modified",
            bookmark_type="datetime",
            max_bookmark_value="2025-01-01T00:00:00Z",
            last_datetime="2025-01-01T00:00:00Z",
            last_integer=None,
        )
        self.assertGreaterEqual(max_bv, "2025-05-01")

    @patch("tap_saasoptics.sync.write_record")
    def test_empty_records_returns_zero_count(self, _mock_write_record):
        catalog = self._make_catalog("customers")
        from singer.utils import now
        _max_bv, count = process_records(
            catalog=catalog,
            stream_name="customers",
            records=[],
            time_extracted=now(),
            bookmark_field="modified",
            bookmark_type="datetime",
            max_bookmark_value="2025-01-01T00:00:00Z",
            last_datetime="2025-01-01T00:00:00Z",
            last_integer=None,
        )
        self.assertEqual(count, 0)


# ---------------------------------------------------------------------------
# update_currently_syncing
# ---------------------------------------------------------------------------

class TestUpdateCurrentlySyncing(unittest.TestCase):
    """Unit tests for update_currently_syncing()."""

    @patch("tap_saasoptics.sync.singer.write_state")
    def test_sets_currently_syncing(self, _mock_write_state):
        state = {}
        update_currently_syncing(state, "customers")
        self.assertEqual(state.get("currently_syncing"), "customers")

    @patch("tap_saasoptics.sync.singer.write_state")
    def test_clears_currently_syncing_when_none(self, _mock_write_state):
        state = {"currently_syncing": "customers"}
        update_currently_syncing(state, None)
        self.assertNotIn("currently_syncing", state)


# ---------------------------------------------------------------------------
# sync_endpoint – no data case
# ---------------------------------------------------------------------------

class TestSyncEndpointNoData(unittest.TestCase):
    """Unit tests for the no-data early-exit path in sync_endpoint()."""

    @patch("tap_saasoptics.sync.singer.write_state")
    @patch("tap_saasoptics.sync.write_schema")
    def test_returns_zero_when_api_returns_no_data(
        self, _mock_write_schema, _mock_write_state
    ):
        mock_client = MagicMock()
        mock_client.base_url = (
            "https://dummy-subdomain.saasoptics.com/dummy-account/api/v1.0"
        )
        mock_client.get.return_value = {}

        from tap_saasoptics.discover import discover
        catalog = discover()

        total = sync_endpoint(
            client=mock_client,
            catalog=catalog,
            state={},
            start_date="2025-01-01T00:00:00Z",
            stream_name="accounts",
            path="accounts",
            endpoint_config={"key_properties": ["id"], "replication_method": "FULL_TABLE"},
            static_params={},
            bookmark_query_field_from=None,
            bookmark_query_field_to=None,
            bookmark_field=None,
            bookmark_type=None,
            data_key="results",
            id_fields=["id"],
            days_interval=60,
        )

        self.assertEqual(total, 0)


# ---------------------------------------------------------------------------
# sync – top-level orchestration
# ---------------------------------------------------------------------------

class TestSync(unittest.TestCase):
    """Unit tests for the top-level sync() function."""

    @patch("tap_saasoptics.sync.singer.write_state")
    @patch("tap_saasoptics.sync.update_currently_syncing")
    @patch("tap_saasoptics.sync.sync_endpoint")
    def test_sync_calls_sync_endpoint_for_each_selected_stream(
        self, mock_sync_endpoint, mock_update_syncing, _mock_write_state
    ):
        """sync() must call sync_endpoint exactly once per selected stream."""
        mock_sync_endpoint.return_value = 0

        stream_a = MagicMock()
        stream_a.stream = "customers"
        stream_b = MagicMock()
        stream_b.stream = "contracts"

        catalog = MagicMock()
        catalog.get_selected_streams.return_value = [stream_a, stream_b]

        config = {
            "token": "dummy",
            "account_name": "acc",
            "server_subdomain": "sub",
            "start_date": "2025-01-01T00:00:00Z",
        }

        mock_client = MagicMock()
        sync(client=mock_client, config=config, catalog=catalog, state={})

        self.assertEqual(mock_sync_endpoint.call_count, 2)
        synced = {c.kwargs["stream_name"] for c in mock_sync_endpoint.call_args_list}
        self.assertEqual(synced, {"customers", "contracts"})

    @patch("tap_saasoptics.sync.singer.write_state")
    @patch("tap_saasoptics.sync.sync_endpoint")
    def test_sync_does_nothing_when_no_streams_selected(
        self, mock_sync_endpoint, _mock_write_state
    ):
        """sync() must not call sync_endpoint when no streams are selected."""
        catalog = MagicMock()
        catalog.get_selected_streams.return_value = []

        config = {
            "token": "dummy",
            "account_name": "acc",
            "server_subdomain": "sub",
            "start_date": "2025-01-01T00:00:00Z",
        }

        mock_client = MagicMock()
        sync(client=mock_client, config=config, catalog=catalog, state={})

        mock_sync_endpoint.assert_not_called()

    @patch("tap_saasoptics.sync.singer.write_state")
    @patch("tap_saasoptics.sync.update_currently_syncing")
    @patch("tap_saasoptics.sync.sync_endpoint")
    def test_currently_syncing_cleared_after_each_stream(
        self, mock_sync_endpoint, mock_update_syncing, _mock_write_state
    ):
        """
        sync() must call update_currently_syncing(state, None) after each
        stream to clear the currently_syncing flag.
        """
        mock_sync_endpoint.return_value = 0

        stream_a = MagicMock()
        stream_a.stream = "customers"

        catalog = MagicMock()
        catalog.get_selected_streams.return_value = [stream_a]

        config = {
            "token": "dummy",
            "account_name": "acc",
            "server_subdomain": "sub",
            "start_date": "2025-01-01T00:00:00Z",
        }

        mock_client = MagicMock()
        sync(client=mock_client, config=config, catalog=catalog, state={})

        # update_currently_syncing called with stream name, then with None
        calls = mock_update_syncing.call_args_list
        self.assertEqual(calls[0], call({}, "customers"))
        self.assertEqual(calls[1], call({}, None))


class TestSyncAdditional(unittest.TestCase):
    @patch("tap_saasoptics.sync.singer.write_schema", side_effect=OSError("boom"))
    def test_write_schema_reraises_oserror(self, _mock_write_schema):
        stream = MagicMock()
        stream.schema.to_dict.return_value = {"type": "object", "properties": {}}
        stream.key_properties = ["id"]
        catalog = MagicMock()
        catalog.get_stream.return_value = stream

        with self.assertRaises(OSError):
            write_schema(catalog, "accounts")

    @patch("tap_saasoptics.sync.singer.messages.write_record", side_effect=OSError("boom"))
    def test_write_record_reraises_oserror(self, _mock_write_record):
        with self.assertRaises(OSError):
            write_record("accounts", {"id": 1}, time_extracted=datetime.now(timezone.utc))

    def test_transform_datetime_normalizes_datetime_string(self):
        output = transform_datetime("2025-01-01T00:00:00Z")
        self.assertEqual(output, "2025-01-01T00:00:00.000000Z")


    @patch("tap_saasoptics.sync.process_records")
    @patch("tap_saasoptics.sync.transform_json")
    @patch("tap_saasoptics.sync.write_bookmark")
    @patch("tap_saasoptics.sync.write_schema")
    @patch("tap_saasoptics.sync.utils.now")
    def test_sync_endpoint_builds_datetime_window_query_and_updates_bookmark(
        self,
        mock_now,
        _mock_write_schema,
        mock_write_bookmark,
        mock_transform_json,
        mock_process_records,
    ):
        mock_now.return_value = datetime(2025, 1, 2, tzinfo=timezone.utc)
        mock_transform_json.return_value = [{"id": "1", "modified": "2025-01-01T12:00:00Z"}]
        mock_process_records.return_value = ("2025-01-01T12:00:00.000000Z", 1)

        client = MagicMock()
        client.base_url = "https://dummy.saasoptics.com/acct/api/v1.0"
        client.get.return_value = {"count": 1, "next": None, "results": [{"id": "1"}]}

        catalog = MagicMock()
        state = {"bookmarks": {"customers": "2025-01-01T00:00:00Z"}}

        total = sync_endpoint(
            client=client,
            catalog=catalog,
            state=state,
            start_date="2024-12-01T00:00:00Z",
            stream_name="customers",
            path="customers",
            endpoint_config={"key_properties": ["id"]},
            static_params={"ordering": "modified"},
            bookmark_query_field_from="modified__gte",
            bookmark_query_field_to="modified__lte",
            bookmark_field="modified",
            bookmark_type="datetime",
            data_key="results",
            id_fields=["id"],
            days_interval=1,
        )

        self.assertEqual(total, 1)
        params_sent = client.get.call_args.kwargs["params"]
        self.assertIn("modified__gte=2025-01-01T00:00:00.000000Z", params_sent)
        self.assertIn("modified__lte=2025-01-02T00:00:00.000000Z", params_sent)
        mock_write_bookmark.assert_called_once()

    @patch("tap_saasoptics.sync.process_records")
    @patch("tap_saasoptics.sync.transform_json", return_value=[])
    @patch("tap_saasoptics.sync.write_schema")
    @patch("tap_saasoptics.sync.utils.now")
    def test_sync_endpoint_exits_when_transformation_empty(
        self,
        mock_now,
        _mock_write_schema,
        _mock_transform_json,
        mock_process_records,
    ):
        mock_now.return_value = datetime(2025, 1, 2, tzinfo=timezone.utc)
        client = MagicMock()
        client.base_url = "https://dummy.saasoptics.com/acct/api/v1.0"
        client.get.return_value = {"count": 1, "next": None, "results": [{"id": "1"}]}

        total = sync_endpoint(
            client=client,
            catalog=MagicMock(),
            state={},
            start_date="2025-01-01T00:00:00Z",
            stream_name="accounts",
            path="accounts",
            endpoint_config={"key_properties": ["id"]},
            static_params={},
            bookmark_query_field_from=None,
            bookmark_query_field_to=None,
            bookmark_field=None,
            bookmark_type=None,
            data_key="results",
            id_fields=["id"],
            days_interval=60,
        )

        self.assertEqual(total, 0)
        mock_process_records.assert_not_called()
