from re import Pattern, compile

from loguru import logger


class Route(object):
    def __init__(
        self, host, dictionary, host_regex="Host(SNI)?(`(.*?)`)", *args, **kwargs
    ):  # noqa: W605
        super().__init__(*args, **kwargs)
        self.host = host
        self._dictionary = dictionary
        self.host_regex = (
            host_regex if isinstance(host_regex, Pattern) else compile(host_regex)
        )

        for key in self._dictionary.keys():
            if key not in self._keys:
                logger.warning(f"Unhandled key in {self.__class__}: {key}")
            logger.trace(
                '{}: {}"{}"', key, type(self._dictionary[key]), self._dictionary[key]
            )

    @property
    def _keys(self):
        return [
            "entryPoints",
            "middlewares",
            "name",
            "priority",
            "provider",
            "rule",
            "service",
            "status",
            "tls",
            "using",
        ]

    def __repr__(self):
        return f"{self.__class__}({self.name})"

    def __str__(self):
        return f"{self.name}: {self.rule}"

    @property
    def name(self):
        return self._dictionary["name"]

    @property
    def rule(self):
        return self._dictionary["rule"]

    @property
    def hosts(self):
        return list({match[1] for match in self.host_regex.findall(self.rule)})
