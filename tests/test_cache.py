import mock

from . import BaseTestCase

from freon.cache import Cache
from freon.backends.redis import RedisBackend
from freon.serializers.msgpack import MsgpackSerializer


class CacheTestCase(BaseTestCase):
    def setUp(self):
        self.cache = Cache()
        self.cache.backend = self.mock_backend = mock.create_autospec(RedisBackend)
        self.cache.serializer = self.mock_serializer = mock.create_autospec(MsgpackSerializer)


class LoadBackendTests(CacheTestCase):
    def test_initialization(self):
        from freon.backends.memory import MemoryBackend

        backend = self.cache._load_backend('memory')
        assert isinstance(backend, MemoryBackend) is True


class LoadSerializerTests(CacheTestCase):
    def test_initialization(self):
        from freon.serializers.json import JsonSerializer

        serializer = self.cache._load_serializer('json')
        assert isinstance(serializer, JsonSerializer) is True


class GetTests(CacheTestCase):
    def test_with_existing_expired_key(self):
        self.mock_backend.get.return_value = ('bar', True)
        self.mock_serializer.loads.return_value = 'bar'
        assert self.cache.get('foo') == 'bar'

    def test_with_existing_not_expired_key(self):
        self.mock_backend.get.return_value = ('bar', False)
        self.mock_serializer.loads.return_value = 'bar'
        assert self.cache.get('foo') == 'bar'

    def test_with_not_existing_key(self):
        self.mock_backend.get.return_value = (None, True)
        self.mock_serializer.loads.return_value = None
        assert self.cache.get('foo') is None

    def test_value_is_deserialized(self):
        self.mock_backend.get.return_value = ('bar', True)
        self.mock_serializer.loads.return_value = 'baz'
        assert self.cache.get('foo') == 'baz'
        self.mock_serializer.loads.assert_called_once_with('bar')


class SetTests(CacheTestCase):
    def test_does_not_set_key_if_lock_not_acquired(self):
        self.mock_backend.get_lock.return_value.acquire.return_value = False
        self.mock_backend.set.assert_not_called()

    def test_returns_none_if_lock_not_acquired(self):
        self.mock_backend.get_lock.return_value.acquire.return_value = False
        assert self.cache.set('foo', 'bar') is None

    def test_string_value(self):
        self.mock_backend.get_lock.return_value.acquire.return_value = True
        self.cache.set('foo', 'bar')
        self.mock_serializer.dumps.assert_called_once_with('bar')

    def test_callable_value(self):
        self.mock_backend.get_lock.return_value.acquire.return_value = True
        self.cache.set('foo', lambda: 'bar')
        self.mock_serializer.dumps.assert_called_once_with('bar')

    def test_integer_ttl(self):
        self.mock_backend.get_lock.return_value.acquire.return_value = True
        self.cache.set('foo', 'bar', 123)
        self.mock_backend.set.assert_called_once_with(mock.ANY, mock.ANY, 123)

    def test_callable_ttl(self):
        self.mock_backend.get_lock.return_value.acquire.return_value = True
        self.cache.set('foo', 'bar', lambda _: 123)
        self.mock_backend.set.assert_called_once_with(mock.ANY, mock.ANY, 123)

    def test_default_ttl(self):
        self.mock_backend.get_lock.return_value.acquire.return_value = True
        self.cache.default_ttl = 123
        self.cache.set('foo', 'bar')
        self.mock_backend.set.assert_called_once_with(mock.ANY, mock.ANY, 123)

    def test_set_key(self):
        self.mock_backend.get_lock.return_value.acquire.return_value = True
        self.mock_serializer.dumps.return_value = 'bar'
        self.cache.set('foo', 'bar', 123)
        self.mock_backend.set.assert_called_with('foo', 'bar', 123)

    def test_return_cached_value_if_successful(self):
        self.mock_backend.get_lock.return_value.acquire.return_value = True
        self.mock_backend.set.return_value = True
        assert self.cache.set('foo', 'bar') == 'bar'

    def test_return_none_if_unsuccessful(self):
        self.mock_backend.get_lock.return_value.acquire.return_value = True
        self.mock_backend.set.return_value = False
        assert self.cache.set('foo', 'bar') is None

    def test_lock_is_released(self):
        self.mock_backend.get_lock.return_value.acquire.return_value = True
        self.cache.set('foo', 'bar')
        self.mock_backend.get_lock.return_value.release.assert_called()


@mock.patch.object(Cache, 'set')
class GetOrSetTests(CacheTestCase):
    def test_with_existing_expired_key_call_set(self, mock_set):
        self.mock_backend.get.return_value = ('bar', True)
        self.cache.get_or_set('foo', 'baz')
        mock_set.assert_called_once_with('foo', 'baz', None)

    def test_with_existing_expired_key_return_new_cached_value_if_successful(self, mock_set):
        self.mock_backend.get.return_value = ('bar', True)
        mock_set.return_value = 'baz'
        assert self.cache.get_or_set('foo', 'baz') == 'baz'

    def test_with_existing_expired_key_return_none_if_unsuccessful(self, mock_set):
        self.mock_backend.get.return_value = ('bar', True)
        mock_set.return_value = None
        assert self.cache.get_or_set('foo', 'baz') is None

    def test_with_existing_not_expired_key_does_not_call_set(self, mock_set):
        self.mock_backend.get.return_value = ('bar', False)
        self.mock_serializer.loads.return_value = 'bar'
        self.cache.get_or_set('foo', 'baz')
        mock_set.assert_not_called()

    def test_with_existing_not_expired_key_return_cached_value(self, mock_set):
        self.mock_backend.get.return_value = ('bar', False)
        self.mock_serializer.loads.return_value = 'bar'
        assert self.cache.get_or_set('foo', 'baz') == 'bar'

    def test_with_not_existing_key_call_set(self, mock_set):
        self.mock_backend.get.return_value = (None, True)
        self.mock_serializer.loads.return_value = None
        self.cache.get_or_set('foo', 'baz')
        mock_set.assert_called_once_with('foo', 'baz', None)

    def test_with_not_existing_key_return_new_cached_value_if_successful(self, mock_set):
        self.mock_backend.get.return_value = (None, True)
        self.mock_serializer.loads.return_value = None
        mock_set.return_value = 'baz'
        assert self.cache.get_or_set('foo', 'baz') == 'baz'

    def test_with_not_existing_key_return_none_if_unsuccessful(self, mock_set):
        self.mock_backend.get.return_value = (None, True)
        self.mock_serializer.loads.return_value = None
        mock_set.return_value = None
        assert self.cache.get_or_set('foo', 'baz') is None
