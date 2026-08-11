import unittest

from tap_saasoptics.transform import denest_auditentry, transform_json


class TestTransform(unittest.TestCase):
    def test_denest_auditentry_moves_keys_with_prefix(self):
        payload = {
            "results": [
                {
                    "id": 1,
                    "auditentry": {"modified": "2025-01-01T00:00:00Z", "user": "u1"},
                },
                {"id": 2},
            ]
        }

        output = denest_auditentry(payload, "results")

        self.assertEqual(output["results"][0]["auditentry_modified"], "2025-01-01T00:00:00Z")
        self.assertEqual(output["results"][0]["auditentry_user"], "u1")
        self.assertNotIn("auditentry", output["results"][0])
        self.assertEqual(output["results"][1], {"id": 2})

    def test_transform_json_denests_for_invoices(self):
        payload = {
            "results": [
                {
                    "id": 1,
                    "auditentry": {"modified": "2025-01-01T00:00:00Z"},
                }
            ]
        }

        output = transform_json(payload, "invoices", "results")

        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["auditentry_modified"], "2025-01-01T00:00:00Z")

    def test_transform_json_returns_original_when_path_missing(self):
        payload = {"count": 0, "next": None}

        output = transform_json(payload, "accounts", "results")

        self.assertEqual(output, payload)
