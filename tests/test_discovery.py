import unittest

from singer import metadata

from tap_saasoptics.discover import discover

try:
    from .base import SaaSOpticsBaseTest
except ImportError:
    from base import SaaSOpticsBaseTest


class DiscoveryIntegrationTest(SaaSOpticsBaseTest, unittest.TestCase):
    """Integration tests for catalog discovery."""

    def test_discovery_expected_streams_and_metadata(self):
        """
        discover() must return exactly the expected streams, and each stream's
        root-level Singer metadata must carry correct:
          - table-key-properties   (primary keys)
          - forced-replication-method
          - valid-replication-keys
        """
        catalog = discover()
        stream_map = {s.tap_stream_id: s for s in catalog.streams}
        expected_streams = self.expected_metadata()

        # 1. Correct set of streams returned
        self.assertEqual(
            set(stream_map.keys()),
            set(expected_streams.keys()),
        )

        for stream_name, stream_expected in expected_streams.items():
            with self.subTest(stream=stream_name):
                root_md = metadata.to_map(
                    stream_map[stream_name].metadata
                )[()]

                # 2. Primary keys
                self.assertEqual(
                    set(root_md.get("table-key-properties", [])),
                    stream_expected[self.PRIMARY_KEYS],
                )

                # 3. Replication method
                self.assertEqual(
                    root_md.get("forced-replication-method"),
                    stream_expected[self.REPLICATION_METHOD],
                )

                # 4. Replication keys
                raw = root_md.get("valid-replication-keys", [])
                actual_rep_keys = (
                    {raw} if isinstance(raw, str) else set(raw)
                )
                self.assertEqual(
                    actual_rep_keys,
                    stream_expected[self.REPLICATION_KEYS],
                )

    def test_discovery_stream_entries_have_schema(self):
        """Every catalog entry must have a non-empty schema with 'properties'."""
        catalog = discover()
        for stream in catalog.streams:
            with self.subTest(stream=stream.tap_stream_id):
                schema_dict = stream.schema.to_dict()
                self.assertIn(
                    "properties",
                    schema_dict,
                    msg=(
                        f"Stream '{stream.tap_stream_id}' schema "
                        f"missing 'properties'"
                    ),
                )
                self.assertGreater(
                    len(schema_dict["properties"]),
                    0,
                    msg=(
                        f"Stream '{stream.tap_stream_id}' schema "
                        f"has empty 'properties'"
                    ),
                )

    def test_discovery_stream_equals_tap_stream_id(self):
        """CatalogEntry.stream must equal CatalogEntry.tap_stream_id."""
        catalog = discover()
        for entry in catalog.streams:
            with self.subTest(stream=entry.tap_stream_id):
                self.assertEqual(entry.stream, entry.tap_stream_id)

    def test_discovery_catalog_entries_have_metadata(self):
        """Every catalog entry must carry non-empty metadata."""
        catalog = discover()
        for entry in catalog.streams:
            with self.subTest(stream=entry.tap_stream_id):
                self.assertTrue(
                    entry.metadata,
                    msg=(
                        f"CatalogEntry for '{entry.tap_stream_id}' "
                        f"has no metadata"
                    ),
                )
