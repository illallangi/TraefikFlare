from collections.abc import Sequence
from json import dumps

from loguru import logger

from requests import get as http_get

from .route import Route


class RouteCollection(Sequence):
    def __init__(self, host, per_page=20, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.host = host
        self._routes = []
        for page in forever(start=1):
            url = self.host.url / 'api' / 'tcp' / 'routers' % {'search': '', 'status': '', 'per_page': per_page, 'page': page}
            logger.debug(f'HTTP GET {url}')

            response = http_get(url)
            if response.status_code != 200:
                raise Exception(f'HTTP GET returned status code {response.status_code}, expected 200')
            if response.headers.get("Content-Type", "") != "application/json":
                raise Exception(f'HTTP GET returned Content-Type "{response.headers.get("Content-Type", "")}", expected "application/json"')
            logger.debug(f'HTTP {response.status_code}\n{dumps(dict(response.headers), indent=2)}\n{dumps(response.json(), indent=2)}')

            self._routes += [Route(self.host, route) for route in response.json()]

            if int(response.headers.get('X-Next-Page', '1')) == 1:
                break

        for page in forever(start=1):
            url = self.host.url / 'api' / 'http' / 'routers' % {'search': '', 'status': '', 'per_page': per_page, 'page': page}
            logger.debug(f'HTTP GET {url}')

            response = http_get(url)
            if response.status_code != 200:
                raise Exception(f'HTTP GET returned status code {response.status_code}, expected 200')
            if response.headers.get("Content-Type", "") != "application/json":
                raise Exception(f'HTTP GET returned Content-Type "{response.headers.get("Content-Type", "")}", expected "application/json"')
            logger.debug(f'HTTP {response.status_code}\n{dumps(dict(response.headers), indent=2)}\n{dumps(response.json(), indent=2)}')

            self._routes += [Route(self.host, route) for route in response.json()]

            if int(response.headers.get('X-Next-Page', '1')) == 1:
                break

    def __repr__(self):
        return f'{self.__class__}({self.host})[{self.__len__()}]'

    def __str__(self):
        return f'{self.__len__()} Route(s)'

    def __iter__(self):
        return self._routes.__iter__()

    def __getitem__(self, key):
        return list(self._routes).__getitem__(key)

    def __len__(self):
        return list(self._routes).__len__()

    @property
    def hosts(self):
        return list({host for route in self for host in route.hosts})


def forever(start=0):
    count = start
    while True:
        yield count
        count += 1
