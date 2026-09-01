import unittest

from singer import metadata

from tap_saasoptics.schema import get_schemas
from tap_saasoptics.streams import STREAMS


class TestSchemaMetadata(unittest.TestCase):
    def test_replication_keys_are_automatic(self):
        _schemas, field_metadata = get_schemas()

        for stream_name, stream_config in STREAMS.items():
            replication_keys = stream_config.get("replication_keys", []) or []
            if not replication_keys:
                continue

            metadata_map = metadata.to_map(field_metadata[stream_name])
            for replication_key in replication_keys:
                breadcrumb = ("properties", replication_key)
                inclusion = metadata_map.get(breadcrumb, {}).get("inclusion")
                self.assertEqual(
                    inclusion,
                    "automatic",
                    msg=(
                        f"stream={stream_name}, replication_key={replication_key}, "
                        f"inclusion={inclusion}"
                    ),
                )


if __name__ == "__main__":
    unittest.main()
