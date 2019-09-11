import backoff
import requests
from requests.exceptions import ConnectionError
from singer import metrics
import singer

API_VERSION = 'v1.0'
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


ERROR_CODE_EXCEPTION_MAPPING = {
    400: SaaSOpticsBadRequestError,
    401: SaaSOpticsUnauthorizedError,
    402: SaaSOpticsPaymentRequiredError,
    403: SaaSOpticsForbiddenError,
    404: SaaSOpticsNotFoundError,
    409: SaaSOpticsForbiddenError,
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
            response = response.json()
            if ('error' in response) or ('errorCode' in response):
                message = '%s: %s' % (response.get('error', str(error)),
                                      response.get('message', 'Unknown Error'))
                error_code = response.get('error', {}).get('code')
                ex = get_exception_for_error_code(error_code)
                if response.status_code == 401 and 'Expired token' in message:
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
        self.__account_name = account_name
        self.__server_subdomain = server_subdomain
        self.__user_agent = user_agent
        self.__session = requests.Session()
        self.__verified = False
        self.base_url = 'https://{}.saasoptics.com/{}/api/{}'.format(
            server_subdomain, account_name, API_VERSION)

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
            url='{}/{}/'.format(self.base_url, 'billing_descriptions'),
            headers=headers)
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

        with metrics.http_request_timer(endpoint) as timer:
            response = self.__session.request(method, url, **kwargs)
            timer.tags[metrics.Tag.http_status_code] = response.status_code

        if response.status_code >= 500:
            raise Server5xxError()

        if response.status_code != 200:
            raise_for_error(response)

        return response.json()

    def get(self, path, **kwargs):
        return self.request('GET', path=path, **kwargs)

    def post(self, path, **kwargs):
        return self.request('POST', path=path, **kwargs)
