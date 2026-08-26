import re
from urllib.parse import urlsplit

import backoff
import requests
from requests.exceptions import ConnectionError
from singer import metrics
import singer

API_VERSION = 'v1.0'
SAASOPTICS_DOMAIN = 'saasoptics.com'

# A single DNS label: the tap only ever talks to <server_subdomain>.saasoptics.com,
# so anything that could alter the URL authority (dots, ports, credentials, URL
# delimiters, non-ASCII) is rejected.
SERVER_SUBDOMAIN_PATTERN = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$')

# A single URL path segment.
ACCOUNT_NAME_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')

LOGGER = singer.get_logger()


class Server5xxError(Exception):
    pass


class Server429Error(Exception):
    pass


class SaaSOpticsError(Exception):
    pass


class SaaSOpticsBadRequestError(SaaSOpticsError):
    pass


class SaaSOpticsUnauthorizedError(SaaSOpticsError):
    pass


class SaaSOpticsPaymentRequiredError(SaaSOpticsError):
    pass


class SaaSOpticsNotFoundError(SaaSOpticsError):
    pass


class SaaSOpticsConflictError(SaaSOpticsError):
    pass


class SaaSOpticsForbiddenError(SaaSOpticsError):
    pass


class SaaSOpticsInternalServiceError(SaaSOpticsError):
    pass


class SaaSOpticsConfigurationError(SaaSOpticsError):
    pass


class SaaSOpticsUnsafeUrlError(SaaSOpticsError):
    pass


def validate_server_subdomain(server_subdomain):
    """Validate the tenant supplied `server_subdomain` config value.

    The value is interpolated into the URL authority, so it must be a single
    SaaSOptics hostname label. The offending value is never echoed back.
    """
    if not isinstance(server_subdomain, str) or \
            not SERVER_SUBDOMAIN_PATTERN.match(server_subdomain):
        raise SaaSOpticsConfigurationError(
            'Invalid `server_subdomain` in config: it must be a single SaaSOptics '
            'hostname label containing only letters, digits and hyphens '
            '(no dots, ports, paths, query strings, or other URL delimiters).')
    return server_subdomain.lower()


def validate_account_name(account_name):
    """Validate the tenant supplied `account_name` config value.

    The value is interpolated into the URL path, so it must be a single path
    segment and must not be able to traverse out of the API base path.
    """
    if not isinstance(account_name, str) or \
            not ACCOUNT_NAME_PATTERN.match(account_name) or \
            '..' in account_name:
        raise SaaSOpticsConfigurationError(
            'Invalid `account_name` in config: it must be a single path segment '
            'containing only letters, digits, underscores, hyphens and dots.')
    return account_name


def validate_url(url, base_url):
    """Ensure `url` is inside the SaaSOptics API base URL before requesting it.

    Applied to every request, including the paginated `next` URLs returned by
    the upstream API, so that neither tenant config nor an upstream response can
    point the tap at an unrelated (for example, internal) host.
    """
    if not isinstance(url, str) or any(ord(char) < 0x20 or ord(char) == 0x7F for char in url):
        raise SaaSOpticsUnsafeUrlError(
            'Refusing to request a URL that is not a printable string.')

    base = urlsplit(base_url)
    try:
        parts = urlsplit(url)
        port = parts.port
        hostname = parts.hostname
    except ValueError as err:
        raise SaaSOpticsUnsafeUrlError('Refusing to request a malformed URL.') from err

    is_same_origin = (
        parts.scheme == 'https'
        and not parts.username
        and not parts.password
        and hostname == base.hostname
        and port in (None, 443))
    is_within_base_path = (
        parts.path == base.path or parts.path.startswith(base.path + '/'))

    if not (is_same_origin and is_within_base_path):
        raise SaaSOpticsUnsafeUrlError(
            'Refusing to request a URL outside of the SaaSOptics API base URL '
            'https://<server_subdomain>.{}/<account_name>/api/{}/.'.format(
                SAASOPTICS_DOMAIN, API_VERSION))

    return url


def raise_for_redirect(response):
    """Redirects are never followed; treat any 3xx as an error."""
    if 300 <= response.status_code < 400:
        raise SaaSOpticsUnsafeUrlError(
            'Refusing to follow a redirect from the SaaSOptics API '
            '(status_code = {}).'.format(response.status_code))


ERROR_CODE_EXCEPTION_MAPPING = {
    400: SaaSOpticsBadRequestError,
    401: SaaSOpticsUnauthorizedError,
    402: SaaSOpticsPaymentRequiredError,
    403: SaaSOpticsForbiddenError,
    404: SaaSOpticsNotFoundError,
    409: SaaSOpticsConflictError,
    500: SaaSOpticsInternalServiceError}


def get_exception_for_error_code(error_code):
    return ERROR_CODE_EXCEPTION_MAPPING.get(error_code, SaaSOpticsError)

def raise_for_error(response):
    try:
        response.raise_for_status()
    except (requests.HTTPError, requests.ConnectionError) as error:
        try:
            content_length = len(response.content)
            if content_length == 0:
                # There is nothing we can do here since SaaSOptics has neither sent
                # us a 2xx response nor a response content.
                return
            status_code = response.status_code
            response = response.json()
            if ('error' in response) or ('errorCode' in response):
                message = '%s: %s' % (response.get('error', str(error)),
                                      response.get('message', 'Unknown Error'))
                error_code = response.get('error', {}).get('code')
                ex = get_exception_for_error_code(error_code)
                if status_code == 401 and 'Expired token' in message:
                    LOGGER.error("Your API token has expired as per SaaSOptics’s security \
                        policy. \n Please re-authenticate your connection to generate a new token \
                        and resume extraction.")
                raise ex(message)
            else:
                raise SaaSOpticsError(error)
        except (ValueError, TypeError):
            raise SaaSOpticsError(error)


class SaaSOpticsClient(object):
    def __init__(self,
                 token,
                 account_name,
                 server_subdomain,
                 user_agent=None):
        self.__token = token
        self.__account_name = validate_account_name(account_name)
        self.__server_subdomain = validate_server_subdomain(server_subdomain)
        self.__user_agent = user_agent
        self.__session = requests.Session()
        self.__verified = False
        self.base_url = 'https://{}.{}/{}/api/{}'.format(
            self.__server_subdomain, SAASOPTICS_DOMAIN, self.__account_name, API_VERSION)

    def validate_url(self, url):
        return validate_url(url, self.base_url)

    def __enter__(self):
        self.__verified = self.check_token()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.__session.close()

    @backoff.on_exception(backoff.expo,
                          Server5xxError,
                          max_tries=5,
                          factor=2)
    def check_token(self):
        if self.__token is None:
            raise Exception('Error: Missing access_token.')
        headers = {}
        if self.__user_agent:
            headers['User-Agent'] = self.__user_agent
        headers['Authorization'] = 'Token {}'.format(self.__token)
        headers['Accept'] = 'application/json'
        response = self.__session.get(
            # Simple endpoint that returns 1 Account record (to check API/token access):
            url=self.validate_url('{}/{}/'.format(self.base_url, 'billing_descriptions')),
            headers=headers,
            allow_redirects=False)
        raise_for_redirect(response)
        if response.status_code != 200:
            LOGGER.error('Error status_code = {}'.format(response.status_code))
            raise_for_error(response)
        else:
            resp = response.json()
            if 'results' in resp:
                return True
            else:
                return False


    @backoff.on_exception(backoff.expo,
                          (Server5xxError, ConnectionError, Server429Error),
                          max_tries=5,
                          factor=2)
    def request(self, method, path=None, url=None, **kwargs):
        if not self.__verified:
            self.__verified = self.check_token()

        if not url and path:
            url = '{}/{}/'.format(self.base_url, path)

        url = self.validate_url(url)

        if 'endpoint' in kwargs:
            endpoint = kwargs['endpoint']
            del kwargs['endpoint']
        else:
            endpoint = None

        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        kwargs['headers']['Authorization'] = 'Token {}'.format(self.__token)
        kwargs['headers']['Accept'] = 'application/json'

        if self.__user_agent:
            kwargs['headers']['User-Agent'] = self.__user_agent

        if method == 'POST':
            kwargs['headers']['Content-Type'] = 'application/json'

        # Redirects are never followed: an upstream redirect could otherwise point
        # the tap at an arbitrary (for example, internal) host.
        kwargs['allow_redirects'] = False

        with metrics.http_request_timer(endpoint) as timer:
            response = self.__session.request(method, url, **kwargs)
            timer.tags[metrics.Tag.http_status_code] = response.status_code

        if response.status_code >= 500:
            raise Server5xxError()

        raise_for_redirect(response)

        if response.status_code != 200:
            raise_for_error(response)

        return response.json()

    def get(self, path, **kwargs):
        return self.request('GET', path=path, **kwargs)

    def post(self, path, **kwargs):
        return self.request('POST', path=path, **kwargs)
