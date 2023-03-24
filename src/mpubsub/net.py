"""Bridge: A class for connecting a PubSub to a Broker."""
import logging
import multiprocessing as mp
from collections import deque
from multiprocessing.connection import Client, Connection
from typing import Optional, Any, Deque, NoReturn

import mpubsub
from .typing import Topic, Message

__all__ = ['PubSub']

LOCAL_SUFFIX = '*local'

logger = logging.getLogger(__name__)


class PubSub(mpubsub.PubSub):
    """A PubSub with networking capabilities.

    The NetPubSub class is a PubSub-compatible object that allows the
    message exchange between other NetPubSub objects connected to the
    same broker.

    Args:
      address: The address of the broker to connect to.
      authkey: The authentication key to use when connecting to the
         broker. If `None` or omitted then
         `multiprocessing.current_process().authkey` will be used.

    """

    def __init__(self, address: Any, authkey: Optional[bytes] = None):
        super().__init__()
        self._conn: Optional[Connection] = None

        self._flushing = 0
        self._pending_send: Deque[Message] = deque()
        self._pending_publish: Deque[Message] = deque()

        self._address: Any
        self._authkey: bytes
        self.set_broker(address, authkey)

    def set_broker(self, address: Any,
                   authkey: Optional[bytes] = None) -> None:
        """Set the broker to connect to.

        This allow to change the address and _authkey_ used to connect
        to a broker.

        The NetPubSub must be disconnected, otherwise and exception
        will be raised.

        Args:
          address: The address of the broker to connect to.
          authkey: The authentication key to use when connecting to the
             broker. If `None` or omitted then
             `multiprocessing.current_process().authkey` will be used.

        Raises:
          RuntimeError: If connected to a broker.

        """
        if self._conn:
            raise RuntimeError('Cannot change broker on a connected pub-sub')
        self._address = address
        self._authkey = authkey or mp.current_process().authkey

    def connect(self) -> None:
        """Connect to a PubSub broker.

        Raises:
          RuntimeError: If not connected to a broker.

        """
        if self._conn:
            raise RuntimeError('Already connected')

        conn = Client(self._address, authkey=self._authkey)
        conn.send(...)
        res = conn.recv()
        if res is not ...:
            conn.close()
            raise RuntimeError(f'Expecting ... from client, got {res!r}')
        self._conn = conn
        logger.debug('Connected to broker at %r', self._address)

    def _check_connection(self) -> None:
        if not self._conn:
            raise RuntimeError('Not connected')

    def disconnect(self) -> None:
        """Disconnect from the remote PubSub broker.

        Raises:
          RuntimeError: If not connected to a broker.

        """
        self._check_connection()
        assert self._conn

        self._pending_send.clear()

        self._conn.send(False)
        self._conn.close()
        self._conn = None

    def publish(self, topic: Topic, **kwargs: Any) -> None:
        """Publish a message on a topic to this pub-sub and remote brokers.

        A topic tuple with '*local' as its last element will only be
        published locally.

        """
        if not self._conn or (topic
                              and isinstance(topic, tuple)
                              and topic[-1] == LOCAL_SUFFIX):
            # Not connected or local message.
            super().publish(topic, **kwargs)
            return

        self._pending_publish.append((topic, kwargs))
        self._pending_send.append((topic, kwargs))

        if not self._flushing:
            self._flush()

    def wait_forever(self) -> NoReturn:
        """Wait indefinitely for messages to be published.

        This method will block forever forwarding messages back and
        forth between the local and remote NetPubSubs.

        Raises:
          RuntimeError: If not connected to a broker.
        """
        self._check_connection()
        assert self._conn

        while True:
            self.poll(None)

    def poll(self, timeout: Optional[float] = 0) -> bool:
        """Check and dispatch new messages from the broker.

        This method will check the PubSub broker for new messages. If
        new messages are found, they will be published on the pub-sub.

        By default this method will return immediately with `True` or
        `False` indicating that no new messages were found. Pass a
        positive `timeout` value to make the method wait for that
        amount of seconds before returning. If you pass _None_ then
        the method will block until a message is forwarded.

        Note:
          This method is used by the bridge to check the broker and
          forward remote messages into the local PubSub. You *must*
          call this method (or `wait_forever()`) eventually, otherwise
          remote messages will never be forwarded.

        Args:
          timeout (float): How much time to wait in seconds.

        Raises:
          RuntimeError: If not connected to a broker.

        """
        self._check_connection()
        assert self._conn

        if not self._conn.poll(timeout):
            return False

        self._recv_all()

        if not self._flushing:
            self._flush()

        return True

    def _recv_all(self) -> None:
        assert self._conn
        while self._conn.poll():
            self._pending_publish.append(self._conn.recv())

    def _flush(self) -> None:
        assert self._conn

        assert not self._flushing, 'Already flushing'

        self._flushing = True

        while (self._pending_publish or self._pending_send) and self._conn:
            self._recv_all()

            try:
                msg = self._pending_send.popleft()
                self._conn.send(msg)
            except IndexError:
                pass
            except ValueError as ex:
                logger.error('Could not send: %s', ex)
            except ConnectionResetError:
                self._pending_send.clear()
                self._conn.close()
                self._conn = None
                break

            while True:
                try:
                    (topic, kwargs) = self._pending_publish.popleft()
                except IndexError:
                    break
                super().publish(topic, **kwargs)

        self._flushing = False
