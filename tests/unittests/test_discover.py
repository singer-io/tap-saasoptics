import unittest

from tap_saasoptics.discover import discover
from tap_saasoptics.streams import STREAMS


class TestDiscover(unittest.TestCase):
    """Unit tests for discover()."""

    def test_discover_returns_catalog_with_all_streams(self):
        """discover() must return a Catalog containing all STREAMS entries."""
        catalog = discover()
        stream_names = {s.tap_stream_id for s in catalog.streams}
        self.assertEqual(stream_names, set(STREAMS.keys()))

    def test_discover_catalog_entry_stream_equals_tap_stream_id(self):
        """CatalogEntry.stream must equal CatalogEntry.tap_stream_id."""
        catalog = discover()
        for entry in catalog.streams:
            with self.subTest(stream=entry.tap_stream_id):
                self.assertEqual(entry.stream, entry.tap_stream_id)
