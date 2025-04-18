__all__ = ['DeprecatedFeatureWarning', 'Item', 'IntWithGranularity', 'ScraperException', 'EntityUnavailable', 'Scraper']


import abc
import copy
import dataclasses
import datetime
import enum
import functools
import json
import logging
import random
import requests
import requests.adapters
import time
import warnings
import urllib3

_logger = logging.getLogger(__name__)


class DeprecatedFeatureWarning(FutureWarning):
	pass


class _DeprecatedProperty:
	def __init__(self, name, repl, replStr):
		self.name = name
		self.repl = repl
		self.replStr = replStr

	def __get__(self, obj, objType):
		if obj is None: # if the access is through the class using _DeprecatedProperty rather than an instance of the class:
			return self
		warnings.warn(f'{self.name} is deprecated, use {self.replStr} instead', DeprecatedFeatureWarning, stacklevel = 2)
		return self.repl(obj)


def _json_serialise_datetime_enum(obj):
	'''A JSON serialiser that converts datetime.datetime and datetime.date objects to ISO-8601 strings and enum.Enum objects to their values.'''

	if isinstance(obj, (datetime.datetime, datetime.date)):
		return obj.isoformat()
	if isinstance(obj, enum.Enum):
		return obj.value
	raise TypeError(f'Object of type {type(obj)} is not JSON serializable')


def _json_dataclass_to_dict(obj, forBuggyIntParser = False):
	if isinstance(obj, _JSONDataclass) or dataclasses.is_dataclass(obj):
		out = {}
		out['_type'] = f'{type(obj).__module__}.{type(obj).__name__}'
		for field in dataclasses.fields(obj):
			assert field.name != '_type'
			if field.name.startswith('_'):
				continue
			out[field.name] = _json_dataclass_to_dict(getattr(obj, field.name), forBuggyIntParser = forBuggyIntParser)
		# Add properties
		for k in dir(obj):
			if isinstance(getattr(type(obj), k, None), (property, _DeprecatedProperty)):
				assert k != '_type'
				if k.startswith('_'):
					continue
				out[k] = _json_dataclass_to_dict(getattr(obj, k), forBuggyIntParser = forBuggyIntParser)
	elif isinstance(obj, (tuple, list)):
		return type(obj)(_json_dataclass_to_dict(x, forBuggyIntParser = forBuggyIntParser) for x in obj)
	elif isinstance(obj, dict):
		out = {_json_dataclass_to_dict(k, forBuggyIntParser = forBuggyIntParser): _json_dataclass_to_dict(v, forBuggyIntParser = forBuggyIntParser) for k, v in obj.items()}
	elif isinstance(obj, set):
		return {_json_dataclass_to_dict(v, forBuggyIntParser = forBuggyIntParser) for v in obj}
	else:
		return copy.deepcopy(obj)
	# Transform IntWithGranularity and handle buggy int parser output
	for key, value in list(out.items()): # Modifying the dict below, so make a copy first
		if isinstance(value, IntWithGranularity):
			out[key] = int(value)
			assert f'{key}.granularity' not in out, f'Granularity collision on {key}.granularity'
			out[f'{key}.granularity'] = value.granularity
		elif forBuggyIntParser and isinstance(value, int) and abs(value) > 2**53:
			assert f'{key}.str' not in out, f'Buggy int collision on {key}.str'
			out[f'{key}.str'] = str(value)
	return out


@dataclasses.dataclass
class _JSONDataclass:
	'''A base class for dataclasses for conversion to JSON'''

	def json(self, forBuggyIntParser = False):
		'''
		Convert the object to a JSON string

		If forBuggyIntParser is True, emit JSON for parsers that can't correctly decode integers exceeding the limits of double-precision IEEE 754 floating point numbers.
		Specifically, each field x containing an integer with a magnitude above 2**53 results in an additional field x.str with the value as a string.
		'''

		with warnings.catch_warnings():
			warnings.filterwarnings(action = 'ignore', category = DeprecatedFeatureWarning)
			out = _json_dataclass_to_dict(self, forBuggyIntParser = forBuggyIntParser)
		assert '_snscrape' not in out, 'Metadata collision on _snscrape'
		out['_snscrape'] = snscrape.version.__version__
		return json.dumps(out, default = _json_serialise_datetime_enum)


@dataclasses.dataclass
class Item(_JSONDataclass):
	'''An abstract base class for an item returned by the scraper.

	An item can really be anything. The string representation should be useful for the CLI output (e.g. a direct URL for the item).
	'''

	@abc.abstractmethod
	def __str__(self):
		pass


class IntWithGranularity(int):
	'''A number with an associated granularity

	For example, an IntWithGranularity(42000, 1000) represents a number on the order of 42000 with two significant digits, i.e. something counted with a granularity of 1000.
	'''

	def __new__(cls, value, granularity, *args, **kwargs):
		obj = super().__new__(cls, value, *args, **kwargs)
		obj.granularity = granularity
		return obj

	def __reduce__(self):
		return (IntWithGranularity, (int(self), self.granularity))


def _random_user_agent():
	def lerp(a1, b1, a2, b2, n):
		return (n - a1) / (b1 - a1) * (b2 - a2) + a2
	version = int(lerp(datetime.date(2023, 3, 7).toordinal(), datetime.date(2030, 9, 24).toordinal(), 111, 200, datetime.date.today().toordinal()))
	version += random.randint(-5, 1)
	version = max(version, 101)
	return f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36'
_DEFAULT_USER_AGENT = _random_user_agent()


class _HTTPSAdapter(requests.adapters.HTTPAdapter):
	def init_poolmanager(self, *args, **kwargs):
		super().init_poolmanager(*args, **kwargs)
		#FIXME: Uses private urllib3.PoolManager attribute pool_classes_by_scheme.
		try:
			self.poolmanager.pool_classes_by_scheme['https'].ConnectionCls = _HTTPSConnection
		except (AttributeError, KeyError) as e:
			_logger.debug(f'Could not install TLS cipher logger: {type(e).__module__}.{type(e).__name__} {e!s}')


class _HTTPSConnection(urllib3.connection.HTTPSConnection):
	def connect(self, *args, **kwargs):
		conn = super().connect(*args, **kwargs)
		#FIXME: Uses undocumented attribute self.sock and beyond.
		try:
			_logger.debug(f'Connected to: {self.sock.getpeername()}')
		except AttributeError:
			# self.sock might be a urllib3.util.ssltransport.SSLTransport, which lacks getpeername.
			pass
		try:
			_logger.debug(f'Connection cipher: {self.sock.cipher()}')
		except AttributeError:
			# Shouldn't be possible, but better safe than sorry.
			pass
		return conn


class ScraperException(Exception):
	pass


class EntityUnavailable(ScraperException):
	'''The target entity of the scrape is unavailable, possibly because it does not exist or was suspended.'''


class Scraper:
	'''An abstract base class for a scraper.'''

	name = None

	def __init__(self, *, retries = 3, proxies = None):
		self._retries = retries
		self._proxies = proxies
		self._session = requests.Session()
		self._session.mount('https://', _HTTPSAdapter())

	@abc.abstractmethod
	def get_items(self):
		'''Iterator yielding Items.'''

		pass

	def _get_entity(self):
		'''Get the entity behind the scraper, if any.

		This is the method implemented by subclasses for doing the actual retrieval/entity object creation. For accessing the scraper's entity, use the entity property.
		'''

		return None

	@functools.cached_property
	def entity(self):
		return self._get_entity()

	def _request(self, method, url, params = None, data = None, headers = None, timeout = 10, responseOkCallback = None, allowRedirects = True, proxies = None):
		if not headers:
			headers = {}
		if 'User-Agent' not in headers:
			headers['User-Agent'] = _DEFAULT_USER_AGENT
		proxies = proxies or self._proxies or {}
		errors = []
		for attempt in range(self._retries + 1):
			# The request is newly prepared on each retry because of potential cookie updates.
			req = self._session.prepare_request(requests.Request(method, url, params = params, data = data, headers = headers))
			environmentSettings = self._session.merge_environment_settings(req.url, proxies, None, None, None)
			_logger.info(f'Retrieving {req.url}')
			_logger.debug(f'... with headers: {headers!r}')
			if data:
				_logger.debug(f'... with data: {data!r}')
			if environmentSettings:
				_logger.debug(f'... with environmentSettings: {environmentSettings!r}')
			try:
				r = self._session.send(req, allow_redirects = allowRedirects, timeout = timeout, **environmentSettings)
			except requests.exceptions.RequestException as exc:
				if attempt < self._retries:
					retrying = ', retrying'
					level = logging.INFO
				else:
					retrying = ''
					level = logging.ERROR
				_logger.log(level, f'Error retrieving {req.url}: {exc!r}{retrying}')
				errors.append(repr(exc))
			else:
				redirected = f' (redirected to {r.url})' if r.history else ''
				_logger.info(f'Retrieved {req.url}{redirected}: {r.status_code}')
				_logger.debug(f'... with response headers: {r.headers!r}')
				if r.history:
					for i, redirect in enumerate(r.history):
						_logger.debug(f'... request {i}: {redirect.request.url}: {redirect.status_code} (Location: {redirect.headers.get("Location")})')
						_logger.debug(f'... ... with response headers: {redirect.headers!r}')
				if responseOkCallback is not None:
					success, msg = responseOkCallback(r)
					errors.append(msg)
				else:
					success, msg = (True, None)
				msg = f': {msg}' if msg else ''

				if success:
					_logger.debug(f'{req.url} retrieved successfully{msg}')
					return r
				else:
					if attempt < self._retries:
						retrying = ', retrying'
						level = logging.INFO
					else:
						retrying = ''
						level = logging.ERROR
					_logger.log(level, f'Error retrieving {req.url}{msg}{retrying}')
			if attempt < self._retries:
				sleepTime = 1.0 * 2**attempt # exponential backoff: sleep 1 second after first attempt, 2 after second, 4 after third, etc.
				_logger.info(f'Waiting {sleepTime:.0f} seconds')
				time.sleep(sleepTime)
		else:
			msg = f'{self._retries + 1} requests to {req.url} failed, giving up.'
			_logger.fatal(msg)
			_logger.fatal(f'Errors: {", ".join(errors)}')
			raise ScraperException(msg)
		raise RuntimeError('Reached unreachable code')

	def _get(self, *args, **kwargs):
		return self._request('GET', *args, **kwargs)

	def _post(self, *args, **kwargs):
		return self._request('POST', *args, **kwargs)

	@classmethod
	def _cli_setup_parser(cls, subparser):
		pass

	@classmethod
	def _cli_from_args(cls, args):
		return cls._cli_construct(args)

	@classmethod
	def _cli_construct(cls, argparseArgs, *args, **kwargs):
		return cls(*args, **kwargs, retries = argparseArgs.retries)
