import argparse
import unittest
from unittest.mock import MagicMock, patch

import tap_saasoptics.__init__ as tap_main


class TestMainModule(unittest.TestCase):
    @patch("tap_saasoptics.__init__.discover")
    @patch("tap_saasoptics.__init__.json.dump")
    def test_do_discover_writes_catalog_json(self, mock_dump, mock_discover):
        mock_catalog = MagicMock()
        mock_catalog.to_dict.return_value = {"streams": []}
        mock_discover.return_value = mock_catalog

        tap_main.do_discover()

        mock_discover.assert_called_once_with()
        mock_dump.assert_called_once()

    @patch("tap_saasoptics.__init__.sync")
    @patch("tap_saasoptics.__init__.do_discover")
    @patch("tap_saasoptics.__init__.SaaSOpticsClient")
    @patch("tap_saasoptics.__init__.singer.utils.parse_args")
    def test_main_runs_discover_mode(
        self,
        mock_parse_args,
        mock_client_cls,
        mock_do_discover,
        mock_sync,
    ):
        parsed_args = argparse.Namespace(
            config={
                "token": "token",
                "account_name": "acct",
                "server_subdomain": "sub",
                "user_agent": "ua",
                "start_date": "2025-01-01T00:00:00Z",
            },
            state=None,
            discover=True,
            catalog=None,
        )
        mock_parse_args.return_value = parsed_args

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        tap_main.main()

        mock_do_discover.assert_called_once_with()
        mock_sync.assert_not_called()

    @patch("tap_saasoptics.__init__.sync")
    @patch("tap_saasoptics.__init__.do_discover")
    @patch("tap_saasoptics.__init__.SaaSOpticsClient")
    @patch("tap_saasoptics.__init__.singer.utils.parse_args")
    def test_main_runs_sync_mode_with_state(
        self,
        mock_parse_args,
        mock_client_cls,
        mock_do_discover,
        mock_sync,
    ):
        parsed_args = argparse.Namespace(
            config={
                "token": "token",
                "account_name": "acct",
                "server_subdomain": "sub",
                "user_agent": "ua",
                "start_date": "2025-01-01T00:00:00Z",
            },
            state={"bookmarks": {"customers": "2025-01-01T00:00:00Z"}},
            discover=False,
            catalog={"streams": []},
        )
        mock_parse_args.return_value = parsed_args

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        tap_main.main()

        mock_do_discover.assert_not_called()
        mock_sync.assert_called_once_with(
            client=mock_client,
            config=parsed_args.config,
            catalog=parsed_args.catalog,
            state=parsed_args.state,
        )
