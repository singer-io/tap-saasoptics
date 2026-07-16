import unittest
from unittest.mock import MagicMock, patch

from tap_saasoptics.discover import (
    discover,
    _check_stream_access,
    _apply_access_checks,
)
from tap_saasoptics.client import SaaSOpticsForbiddenError
from tap_saasoptics.streams import STREAMS


class TestDiscover(unittest.TestCase):
    """Unit tests for discover()."""

    def test_discover_returns_catalog_with_all_streams_without_client(self):
        """discover() must return a Catalog containing all STREAMS entries."""
        catalog = discover()
        stream_names = {s.tap_stream_id for s in catalog.streams}
        self.assertEqual(stream_names, set(STREAMS.keys()))

    def test_discover_excludes_inaccessible_streams(self):
        """discover(client) must exclude streams that raise forbidden."""
        restricted_streams = {'customers', 'contracts'}

        mock_client = MagicMock()

        def _get_side_effect(path, **_kwargs):
            if path in restricted_streams:
                raise SaaSOpticsForbiddenError('Forbidden')
            return {'results': []}

        mock_client.get.side_effect = _get_side_effect

        catalog = discover(mock_client)
        stream_names = {s.tap_stream_id for s in catalog.streams}

        self.assertEqual(stream_names, set(STREAMS.keys()) - restricted_streams)

    def test_discover_raises_when_no_stream_is_accessible(self):
        """discover(client) must fail if all streams are inaccessible."""
        mock_client = MagicMock()
        mock_client.get.side_effect = SaaSOpticsForbiddenError('Forbidden')

        with self.assertRaises(SaaSOpticsForbiddenError):
            discover(mock_client)

    def test_discover_catalog_entry_stream_equals_tap_stream_id(self):
        """CatalogEntry.stream must equal CatalogEntry.tap_stream_id."""
        catalog = discover()
        for entry in catalog.streams:
            with self.subTest(stream=entry.tap_stream_id):
                self.assertEqual(entry.stream, entry.tap_stream_id)


class TestAccessChecks(unittest.TestCase):
    """Unit tests for discovery access-check helpers."""

    def test_check_stream_access_returns_false_and_logs_on_forbidden(self):
        """_check_stream_access() should return False and log warning on 403."""
        client = MagicMock()
        client.get.side_effect = SaaSOpticsForbiddenError('Forbidden')

        with patch('tap_saasoptics.discover.LOGGER') as mock_logger:
            result = _check_stream_access(client, 'customers', {'path': 'customers'})

        self.assertFalse(result)
        mock_logger.warning.assert_called_once_with(
            "Excluding unauthorized stream '%s' from catalog. API error: %s",
            'customers',
            client.get.side_effect,
        )

    def test_apply_access_checks_includes_pruned_children_in_consolidated_warning(self):
        """Consolidated warning should include inaccessible parents and pruned child streams."""
        client = MagicMock()
        schemas = {'parent_stream': {}, 'child_stream': {}, 'other_stream': {}}
        field_metadata = {'parent_stream': [], 'child_stream': [], 'other_stream': []}

        test_streams = {
            'parent_stream': {'path': 'parent_stream'},
            'child_stream': {'path': 'child_stream', 'parent': 'parent_stream'},
            'other_stream': {'path': 'other_stream'},
        }

        with patch('tap_saasoptics.discover.STREAMS', test_streams), \
             patch('tap_saasoptics.discover._check_stream_access') as mock_check, \
             patch('tap_saasoptics.discover.LOGGER') as mock_logger:
            mock_check.side_effect = lambda _client, stream_name, _cfg: stream_name != 'parent_stream'

            _apply_access_checks(client, schemas, field_metadata)

        self.assertNotIn('parent_stream', schemas)
        self.assertNotIn('child_stream', schemas)
        self.assertIn('other_stream', schemas)

        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        self.assertTrue(any("Excluding unauthorized stream(s) from catalog:" in call for call in warning_calls))
        self.assertTrue(any('parent_stream, child_stream' in call for call in warning_calls))

    def test_apply_access_checks_raises_with_expected_message_when_no_stream_access(self):
        """No accessible streams should raise exact 403 error message."""
        client = MagicMock()
        schemas = {'customers': {}, 'contracts': {}}
        field_metadata = {'customers': [], 'contracts': []}

        test_streams = {
            'customers': {'path': 'customers'},
            'contracts': {'path': 'contracts'},
        }

        with patch('tap_saasoptics.discover.STREAMS', test_streams), \
             patch('tap_saasoptics.discover._check_stream_access', return_value=False):
            with self.assertRaises(SaaSOpticsForbiddenError) as ctx:
                _apply_access_checks(client, schemas, field_metadata)

        self.assertEqual(
            str(ctx.exception),
            "HTTP-error-code: 403, Error: The credentials do not have 'read' access to any supported streams.",
        )
