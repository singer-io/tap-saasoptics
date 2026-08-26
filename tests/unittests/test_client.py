import unittest
from unittest.mock import MagicMock, patch, PropertyMock

import requests

from tap_saasoptics.client import (
    SaaSOpticsClient,
    SaaSOpticsBadRequestError,
    SaaSOpticsConflictError,
    SaaSOpticsUnauthorizedError,
    SaaSOpticsForbiddenError,
    SaaSOpticsNotFoundError,
    SaaSOpticsInternalServiceError,
    SaaSOpticsError,
    Server5xxError,
    raise_for_error,
    raise_for_redirect,
    get_exception_for_error_code,
    SaaSOpticsConfigurationError,
    SaaSOpticsUnsafeUrlError,
    validate_account_name,
    validate_server_subdomain,
    validate_url,
)


class TestGetExceptionForErrorCode(unittest.TestCase):
    """Unit tests for the error-code → exception-class mapping."""

    def test_400_maps_to_bad_request(self):
        self.assertIs(get_exception_for_error_code(400), SaaSOpticsBadRequestError)

    def test_401_maps_to_unauthorized(self):
        self.assertIs(get_exception_for_error_code(401), SaaSOpticsUnauthorizedError)

    def test_403_maps_to_forbidden(self):
        self.assertIs(get_exception_for_error_code(403), SaaSOpticsForbiddenError)

    def test_404_maps_to_not_found(self):
        self.assertIs(get_exception_for_error_code(404), SaaSOpticsNotFoundError)
    
    def test_409_maps_to_conflict(self):
        self.assertIs(get_exception_for_error_code(409), SaaSOpticsConflictError)

    def test_500_maps_to_internal_service_error(self):
        self.assertIs(
            get_exception_for_error_code(500), SaaSOpticsInternalServiceError
        )

    def test_unknown_code_maps_to_base_error(self):
        self.assertIs(get_exception_for_error_code(418), SaaSOpticsError)


class TestRaiseForError(unittest.TestCase):
    """Unit tests for raise_for_error()."""

    def _make_response(self, status_code, json_body=None, content=b"error"):
        resp = MagicMock(spec=requests.Response)
        resp.status_code = status_code
        resp.content = content
        resp.json.return_value = json_body or {}
        http_error = requests.HTTPError(response=resp)
        resp.raise_for_status.side_effect = http_error
        return resp

    def test_empty_content_does_not_raise(self):
        """An empty response body should be silently ignored."""
        resp = self._make_response(400, content=b"")
        # Should not raise
        raise_for_error(resp)

    def test_raises_saasoptics_error_on_unknown_json(self):
        """An unrecognised JSON payload should raise SaaSOpticsError."""
        resp = self._make_response(400, json_body={"other": "field"})
        with self.assertRaises(SaaSOpticsError):
            raise_for_error(resp)

    def test_raises_correct_exception_for_error_json(self):
        """A JSON body with 'error' / 'message' fields must map to the right exception."""
        resp = self._make_response(
            401,
            json_body={"error": {"code": 401}, "message": "Unauthorized"},
        )
        with self.assertRaises(SaaSOpticsError):
            raise_for_error(resp)

    def test_raises_saasoptics_error_when_json_parse_fails(self):
        """JSON parse errors should be wrapped in SaaSOpticsError."""
        resp = self._make_response(500)
        resp.json.side_effect = ValueError("bad json")

        with self.assertRaises(SaaSOpticsError):
            raise_for_error(resp)


class TestSaaSOpticsClientCheckToken(unittest.TestCase):
    """Unit tests for SaaSOpticsClient.check_token()."""

    def _make_client(self):
        return SaaSOpticsClient(
            token="test-token",
            account_name="test-account",
            server_subdomain="test-subdomain",
            user_agent="test-agent/1.0",
        )

    @patch("tap_saasoptics.client.requests.Session")
    def test_check_token_returns_true_on_success(self, mock_session_cls):
        """check_token() must return True when the API returns 200 with results."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"id": 1}]}
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        client = self._make_client()
        client._SaaSOpticsClient__session = mock_session

        result = client.check_token()
        self.assertTrue(result)

    @patch("tap_saasoptics.client.requests.Session")
    def test_check_token_returns_false_when_no_results_key(self, mock_session_cls):
        """check_token() must return False when response has no 'results' key."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        client = self._make_client()
        client._SaaSOpticsClient__session = mock_session

        result = client.check_token()
        self.assertFalse(result)

    @patch("tap_saasoptics.client.requests.Session")
    def test_check_token_raises_on_non_200(self, mock_session_cls):
        """check_token() must raise when the API responds with a non-200 status."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.content = b"Unauthorized"
        mock_response.json.return_value = {}
        http_error = requests.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        client = self._make_client()
        client._SaaSOpticsClient__session = mock_session

        with self.assertRaises(Exception):
            client.check_token()


class TestSaaSOpticsClientRequest(unittest.TestCase):
    """Unit tests for SaaSOpticsClient.request()."""

    def _make_verified_client(self):
        """Return a client instance already marked as verified."""
        client = SaaSOpticsClient(
            token="test-token",
            account_name="test-account",
            server_subdomain="test-subdomain",
            user_agent="test-agent/1.0",
        )
        client._SaaSOpticsClient__verified = True
        return client

    @patch("tap_saasoptics.client.requests.Session")
    def test_request_returns_json_on_200(self, mock_session_cls):
        """request() must return the parsed JSON body on a 200 response."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"count": 1, "results": []}
        mock_session.request.return_value = mock_response
        mock_session_cls.return_value = mock_session

        client = self._make_verified_client()
        client._SaaSOpticsClient__session = mock_session

        result = client.request("GET", url="https://test-subdomain.saasoptics.com/test-account/api/v1.0/customers/")
        self.assertEqual(result, {"count": 1, "results": []})

    @patch("tap_saasoptics.client.requests.Session")
    def test_request_raises_server5xx_error_on_500(self, mock_session_cls):
        """request() must raise Server5xxError for any 5xx status code."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_session.request.return_value = mock_response
        mock_session_cls.return_value = mock_session

        client = self._make_verified_client()
        client._SaaSOpticsClient__session = mock_session

        with self.assertRaises(Server5xxError):
            client.request("GET", url="https://test-subdomain.saasoptics.com/test-account/api/v1.0/customers/")

    @patch("tap_saasoptics.client.requests.Session")
    def test_request_raises_for_4xx_error(self, mock_session_cls):
        """request() must raise a SaaSOpticsError subclass for 4xx responses."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.content = b"Not Found"
        mock_response.json.return_value = {}
        http_error = requests.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error
        mock_session.request.return_value = mock_response
        mock_session_cls.return_value = mock_session

        client = self._make_verified_client()
        client._SaaSOpticsClient__session = mock_session

        with self.assertRaises(SaaSOpticsError):
            client.request("GET", url="https://test-subdomain.saasoptics.com/test-account/api/v1.0/unknown/")

    @patch("tap_saasoptics.client.requests.Session")
    def test_get_delegates_to_request(self, mock_session_cls):
        """client.get() must call client.request() with method='GET'."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_session.request.return_value = mock_response
        mock_session_cls.return_value = mock_session

        client = self._make_verified_client()
        client._SaaSOpticsClient__session = mock_session

        client.get(path="billing_descriptions", url="https://test-subdomain.saasoptics.com/test-account/api/v1.0/billing_descriptions/")
        call_args = mock_session.request.call_args
        self.assertEqual(call_args[0][0], "GET")

    @patch("tap_saasoptics.client.metrics.http_request_timer")
    def test_request_calls_check_token_when_unverified(self, mock_timer):
        timer_cm = MagicMock()
        timer_cm.__enter__.return_value = MagicMock(tags={})
        timer_cm.__exit__.return_value = False
        mock_timer.return_value = timer_cm

        client = SaaSOpticsClient("test-token", "test-account", "test-subdomain")
        client._SaaSOpticsClient__session = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"results": []}
        client._SaaSOpticsClient__session.request.return_value = response
        client.check_token = MagicMock(return_value=True)

        client.request("GET", url="https://test-subdomain.saasoptics.com/test-account/api/v1.0/customers/")

        client.check_token.assert_called_once_with()


class TestClientAdditional(unittest.TestCase):
    def test_context_manager_enters_and_exits(self):
        client = SaaSOpticsClient("token", "acct", "sub", "ua")
        client.check_token = MagicMock(return_value=True)
        client._SaaSOpticsClient__session = MagicMock()

        with client as entered:
            self.assertIs(entered, client)

        client.check_token.assert_called_once_with()
        client._SaaSOpticsClient__session.close.assert_called_once_with()

    def test_check_token_raises_when_token_missing(self):
        client = SaaSOpticsClient(None, "acct", "sub", "ua")
        with self.assertRaises(Exception):
            client.check_token()

    @patch("tap_saasoptics.client.metrics.http_request_timer")
    def test_request_builds_url_from_path_and_sets_headers_for_post(self, mock_timer):
        timer_cm = MagicMock()
        timer_cm.__enter__.return_value = MagicMock(tags={})
        timer_cm.__exit__.return_value = False
        mock_timer.return_value = timer_cm

        client = SaaSOpticsClient("token", "acct", "sub", "ua")
        client._SaaSOpticsClient__verified = True
        client._SaaSOpticsClient__session = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"ok": True}
        client._SaaSOpticsClient__session.request.return_value = response

        result = client.request("POST", path="accounts", endpoint="accounts")

        self.assertEqual(result, {"ok": True})
        call_kwargs = client._SaaSOpticsClient__session.request.call_args.kwargs
        self.assertEqual(
            client._SaaSOpticsClient__session.request.call_args.args[1],
            "https://sub.saasoptics.com/acct/api/v1.0/accounts/",
        )
        self.assertEqual(call_kwargs["headers"]["Content-Type"], "application/json")
        self.assertEqual(call_kwargs["headers"]["Authorization"], "Token token")
        self.assertEqual(call_kwargs["headers"]["User-Agent"], "ua")

    @patch("tap_saasoptics.client.LOGGER.error")
    def test_raise_for_error_logs_expired_token_message(self, mock_log):
        response = MagicMock()
        response.status_code = 401
        response.content = b"expired"
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        response.json.return_value = {
            "error": {"code": 401},
            "message": "Expired token in account",
        }

        with self.assertRaises(SaaSOpticsUnauthorizedError):
            raise_for_error(response)

        mock_log.assert_called_once()

    @patch("tap_saasoptics.client.SaaSOpticsClient.request")
    def test_post_delegates_to_request(self, mock_request):
        mock_request.return_value = {"ok": True}
        client = SaaSOpticsClient("token", "acct", "sub")

        result = client.post("accounts", json={"x": 1})

        self.assertEqual(result, {"ok": True})
        mock_request.assert_called_once_with("POST", path="accounts", json={"x": 1})


class TestValidateServerSubdomain(unittest.TestCase):
    """Unit tests for validate_server_subdomain() (SSRF hardening)."""

    def test_valid_subdomain_is_lowercased(self):
        self.assertEqual(validate_server_subdomain("MyCo-1"), "myco-1")

    def test_invalid_subdomains_are_rejected(self):
        invalid = [
            "",
            "evil.example.com/stitch-repro?tail=",
            "evil.example.com",
            "evil.example.com:8447",
            "sub/path",
            "sub?query",
            "sub#fragment",
            "sub%2fpath",
            "user@host",
            "-leading-hyphen",
            "trailing-hyphen-",
            "sub.",
            "ёж",
            "a" * 64,
            None,
            123,
        ]
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(SaaSOpticsConfigurationError):
                    validate_server_subdomain(value)

    def test_error_message_does_not_echo_the_value(self):
        secret = "evil.example.com/stitch-repro?tail="
        with self.assertRaises(SaaSOpticsConfigurationError) as ctx:
            validate_server_subdomain(secret)
        self.assertNotIn(secret, str(ctx.exception))


class TestValidateAccountName(unittest.TestCase):
    """Unit tests for validate_account_name()."""

    def test_valid_account_names_are_returned_unchanged(self):
        for value in ["acme", "acme_co", "acme-co", "acme.co", "Acme1"]:
            with self.subTest(value=value):
                self.assertEqual(validate_account_name(value), value)

    def test_invalid_account_names_are_rejected(self):
        invalid = [
            "",
            ".",
            "..",
            "acme/../other",
            "acme..co",
            "acme/co",
            "acme?co",
            "acme#co",
            "acme%2f",
            ".acme",
            "a" * 129,
            None,
            [],
        ]
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(SaaSOpticsConfigurationError):
                    validate_account_name(value)


class TestValidateUrl(unittest.TestCase):
    """Unit tests for validate_url() (SSRF hardening)."""

    BASE_URL = "https://sub.saasoptics.com/acct/api/v1.0"

    def test_allowed_urls(self):
        allowed = [
            "https://sub.saasoptics.com/acct/api/v1.0",
            "https://sub.saasoptics.com/acct/api/v1.0/accounts/",
            "https://sub.saasoptics.com/acct/api/v1.0/accounts/?limit=100",
            "https://SUB.saasoptics.com/acct/api/v1.0/accounts/",
            "https://sub.saasoptics.com:443/acct/api/v1.0/accounts/",
        ]
        for url in allowed:
            with self.subTest(url=url):
                self.assertEqual(validate_url(url, self.BASE_URL), url)

    def test_rejected_urls(self):
        rejected = [
            "http://app-smart-schema-registry.central.internal.lan/subjects",
            "https://app-smart-schema-registry.central.internal.lan/subjects",
            "http://sub.saasoptics.com/acct/api/v1.0/accounts/",
            "https://sub.saasoptics.com.evil.example.com/acct/api/v1.0/accounts/",
            "https://sub.saasoptics.com:8447/acct/api/v1.0/accounts/",
            "https://user:pass@sub.saasoptics.com/acct/api/v1.0/accounts/",
            "https://sub.saasoptics.com/acct/api/v1.0evil/accounts/",
            "https://sub.saasoptics.com/other/api/v1.0/accounts/",
            "https://127.0.0.1/acct/api/v1.0/accounts/",
            "file:///etc/passwd",
            "https://sub.saasoptics.com/acct/api/v1.0/\x00accounts/",
            None,
            42,
        ]
        for url in rejected:
            with self.subTest(url=url):
                with self.assertRaises(SaaSOpticsUnsafeUrlError):
                    validate_url(url, self.BASE_URL)

    def test_malformed_url_is_rejected(self):
        with self.assertRaises(SaaSOpticsUnsafeUrlError):
            validate_url("https://sub.saasoptics.com:notaport/acct/api/v1.0/", self.BASE_URL)

    def test_client_validate_url_uses_its_own_base_url(self):
        client = SaaSOpticsClient("token", "acct", "sub", "ua")
        url = "https://sub.saasoptics.com/acct/api/v1.0/accounts/"
        self.assertEqual(client.validate_url(url), url)
        with self.assertRaises(SaaSOpticsUnsafeUrlError):
            client.validate_url("https://evil.example.com/acct/api/v1.0/accounts/")


class TestRedirectsAreNotFollowed(unittest.TestCase):
    """Redirects must never be followed (SSRF hardening)."""

    def test_raise_for_redirect_raises_on_3xx(self):
        for status_code in (301, 302, 303, 307, 308):
            with self.subTest(status_code=status_code):
                response = MagicMock()
                response.status_code = status_code
                with self.assertRaises(SaaSOpticsUnsafeUrlError):
                    raise_for_redirect(response)

    def test_raise_for_redirect_is_a_noop_on_200(self):
        response = MagicMock()
        response.status_code = 200
        self.assertIsNone(raise_for_redirect(response))

    def test_check_token_disables_redirects_and_raises_on_302(self):
        client = SaaSOpticsClient("token", "acct", "sub", "ua")
        session = MagicMock()
        response = MagicMock()
        response.status_code = 302
        session.get.return_value = response
        client._SaaSOpticsClient__session = session

        with self.assertRaises(SaaSOpticsUnsafeUrlError):
            client.check_token()

        self.assertIs(session.get.call_args.kwargs["allow_redirects"], False)

    @patch("tap_saasoptics.client.metrics.http_request_timer")
    def test_request_disables_redirects_and_raises_on_302(self, mock_timer):
        timer_cm = MagicMock()
        timer_cm.__enter__.return_value = MagicMock(tags={})
        timer_cm.__exit__.return_value = False
        mock_timer.return_value = timer_cm

        client = SaaSOpticsClient("token", "acct", "sub", "ua")
        client._SaaSOpticsClient__verified = True
        session = MagicMock()
        response = MagicMock()
        response.status_code = 302
        session.request.return_value = response
        client._SaaSOpticsClient__session = session

        with self.assertRaises(SaaSOpticsUnsafeUrlError):
            client.request("GET", path="accounts")

        self.assertIs(session.request.call_args.kwargs["allow_redirects"], False)

    @patch("tap_saasoptics.client.metrics.http_request_timer")
    def test_request_ignores_caller_supplied_allow_redirects(self, mock_timer):
        timer_cm = MagicMock()
        timer_cm.__enter__.return_value = MagicMock(tags={})
        timer_cm.__exit__.return_value = False
        mock_timer.return_value = timer_cm

        client = SaaSOpticsClient("token", "acct", "sub", "ua")
        client._SaaSOpticsClient__verified = True
        session = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"results": []}
        session.request.return_value = response
        client._SaaSOpticsClient__session = session

        client.request("GET", path="accounts", allow_redirects=True)

        self.assertIs(session.request.call_args.kwargs["allow_redirects"], False)

    @patch("tap_saasoptics.client.metrics.http_request_timer")
    def test_request_rejects_url_outside_the_base_url(self, mock_timer):
        client = SaaSOpticsClient("token", "acct", "sub", "ua")
        client._SaaSOpticsClient__verified = True
        session = MagicMock()
        client._SaaSOpticsClient__session = session

        with self.assertRaises(SaaSOpticsUnsafeUrlError):
            client.request("GET", url="http://app-smart-schema-registry.central.internal.lan/subjects")

        session.request.assert_not_called()


class TestClientConstruction(unittest.TestCase):
    """The client must refuse to be built with an unsafe config."""

    def test_base_url_is_built_from_validated_values(self):
        client = SaaSOpticsClient("token", "Acme_1", "MyCo", "ua")
        self.assertEqual(
            client.base_url, "https://myco.saasoptics.com/Acme_1/api/v1.0")

    def test_unsafe_server_subdomain_raises(self):
        with self.assertRaises(SaaSOpticsConfigurationError):
            SaaSOpticsClient("token", "acct", "evil.example.com/repro?tail=", "ua")

    def test_unsafe_account_name_raises(self):
        with self.assertRaises(SaaSOpticsConfigurationError):
            SaaSOpticsClient("token", "../../evil", "sub", "ua")


class TestClientBranchCoverage(unittest.TestCase):
    """Cover the remaining conditional edges in client.py."""

    def test_check_token_omits_user_agent_header_when_not_configured(self):
        client = SaaSOpticsClient("token", "acct", "sub")
        session = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"results": []}
        session.get.return_value = response
        client._SaaSOpticsClient__session = session

        self.assertTrue(client.check_token())
        self.assertNotIn("User-Agent", session.get.call_args.kwargs["headers"])

    @patch("tap_saasoptics.client.metrics.http_request_timer")
    def test_request_reuses_caller_supplied_headers(self, mock_timer):
        timer_cm = MagicMock()
        timer_cm.__enter__.return_value = MagicMock(tags={})
        timer_cm.__exit__.return_value = False
        mock_timer.return_value = timer_cm

        client = SaaSOpticsClient("token", "acct", "sub", "ua")
        client._SaaSOpticsClient__verified = True
        session = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"results": []}
        session.request.return_value = response
        client._SaaSOpticsClient__session = session

        client.request("GET", path="accounts", headers={"X-Test": "1"})

        headers = session.request.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Test"], "1")
        self.assertEqual(headers["Authorization"], "Token token")

    def test_check_token_returns_false_when_results_key_is_absent(self):
        client = SaaSOpticsClient("token", "acct", "sub", "ua")
        session = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"detail": "no results key"}
        session.get.return_value = response
        client._SaaSOpticsClient__session = session

        self.assertFalse(client.check_token())
