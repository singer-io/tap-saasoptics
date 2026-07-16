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
    get_exception_for_error_code,
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

    @patch("tap_saasoptics.client.requests.Session")
    def test_check_token_raises_clear_error_on_connection_failure(self, mock_session_cls):
        """check_token() should raise a clear SaaSOpticsError on TLS/connection failures."""
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.exceptions.SSLError("handshake failure")
        mock_session_cls.return_value = mock_session

        client = self._make_client()
        client._SaaSOpticsClient__session = mock_session

        with self.assertRaises(SaaSOpticsError) as caught:
            client.check_token()

        self.assertIn(
            'Invalid SaaSOptics credentials or API endpoint. Check token, account_name, server_subdomain, and network config.',
            str(caught.exception),
        )


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

        result = client.request("GET", url="https://example.com/api/v1.0/customers/")
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
            client.request("GET", url="https://example.com/api/v1.0/customers/")

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
            client.request("GET", url="https://example.com/api/v1.0/unknown/")

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

        client.get(path="billing_descriptions", url="https://example.com/api/v1.0/billing_descriptions/")
        call_args = mock_session.request.call_args
        self.assertEqual(call_args[0][0], "GET")
