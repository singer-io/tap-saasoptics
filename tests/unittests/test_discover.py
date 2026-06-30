import unittest
from unittest.mock import MagicMock

from tap_saasoptics.discover import discover
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
