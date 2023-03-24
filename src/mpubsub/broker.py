import logging
import threading
import multiprocessing as mp
import multiprocessing.connection as mpc
from typing import Any, Tuple, NoReturn, Set, Optional, List

from .typing import Message

__all__ = ['Broker']

logger = logging.getLogger(__name__)


class Broker:
    """A broker that connects publishers and subscribers.

    This class represents a broker that connects publishers and
    subscribers for mpubsub. The broker listen to incoming connections
    and forward messages to all the subscribers.

    The broker uses interprocess communications to talk to publishers
    and subscribers. When creating the broker you must pass an address
    to listen on. Omitting or passing None will make the broker select
    the most efficient (local) address for the machine.

    Clients must present an authentication key to connect to the
    broker. The auhtentication key is passed in the `authkey`
    parameter. If omitted or `None`,
    `multiprocessing.current_process().authkey` is used.

    See [Listener and
    Clients](https://docs.python.org/3.7/library/multiprocessing.html#module-multiprocessing.connection)
    for more info about `address` and `authkey` semantics.

    Attributes:

      address: The address where the broker should listen on.
      authkey: The secret key for authenticating clients.
      backlog: See
        https://docs.python.org/3.7/library/multiprocessing.html#multiprocessing.connection.Listener
      timeout: Client connection imeout.

    """
    def __init__(self,
                 address: Any = None,
                 authkey: Optional[bytes] = None,
                 backlog: int = 1,
                 timeout: float = 0.5):
        self._authkey = authkey or mp.current_process().authkey
        self._listener = mpc.Listener(address,
                                      backlog=backlog, authkey=self._authkey)
        self._clients: Set[mpc.Connection] = set()
        self._timeout = timeout
        self._local_connection: Optional[mpc.Connection] = None

    @property
    def address(self) -> Any:
        """The address that the broker is listening on."""
        return self._listener.address

    def start(self) -> NoReturn:
        """Start the broker to listen for incoming connections.

        This method starts the broker to listen for incoming
        connections and forward the messages to all connected clients.

        """
        logger.debug('Starting up broker at %r', self._listener.address)

        clients_lock = threading.Lock()

        # Start the broker thread.
        broker_t = threading.Thread(target=self._broker,
                                    name='_broker_t',
                                    args=(clients_lock,))
        broker_t.start()

        #
        # Broker protocol:
        #
        # True (INIT) - new control connection.
        # None (NEWCONN) - new connection added.
        # Ellipsis (NEWPUBSUB) - client init message.
        # False (STOP) - broker main thread stop / client disconnect
        # Message (MSG) - pub-sub message
        #
        # All messages are acknowledged with the same input value,
        # except for STOP and MSG when no ACK is sent.
        #

        # Get the control connection.
        control = mpc.Client(self._listener.address, authkey=self._authkey)

        # Establish the control connection.
        control.send(True)
        control.recv()

        # The main thread just keep accepting connections and adding
        # then to the client list.
        while True:
            try:
                conn = self._listener.accept()
            except mp.AuthenticationError:
                logger.error('Authentication error')
                continue
            except KeyboardInterrupt:
                control.send(False)  # Tell the broker thread to stop.
                control.recv()
                broker_t.join()
                raise

            if not conn.poll(self._timeout):
                logger.warning('Client connection timeout')
                conn.close()
                continue

            msg = conn.recv()
            if msg is not ...:
                logger.error('Expecting ... from client, got %r', msg)
                conn.close()
                continue

            conn.send(...)

            with clients_lock:
                self._clients.add(conn)

            control.send(None)
            control.recv()

    def _get_control_conn(self,
                          pending: List[Tuple[mpc.Connection,
                                              Message]]) -> mpc.Connection:

        # Get the control connection set up.  Note: we do not need to
        # lock self._clients here, because at this point the main
        # thread is blocked by recv().
        while True:
            conn = self._listener.accept()

            self._clients.add(conn)

            msg = conn.recv()
            if msg is True:
                # INIT: it is the control connection.
                conn.send(True)
                return conn

            if msg is ...:
                # NEWPUBSUB: a NetPubSub is connecting.
                conn.send(...)
            elif msg is False:
                # STOP: a NetPubSub is disconnecting.
                self._clients.remove(conn)
                conn.close()
            else:
                # An early message from a connected client.
                pending.append((conn, msg))

    def _broker(self, clients_lock: threading.Lock) -> None:

        # A deque of messages pending to be delivered. New messages
        # are added to the right (via .append()).
        pending: List[Tuple[mpc.Connection, Message]] = []

        # The control connection. If signals the main forwarding loop
        # to end when set to None.
        control: Optional[mpc.Connection] = None

        # A set to hold closed connections.
        closed: Set[mpc.Connection] = set()

        control = self._get_control_conn(pending)

        # Now start the main broker loop.
        while True:
            with clients_lock:
                if not self._clients:
                    break
                clients = self._clients.copy()

            conns = mpc.wait(clients)

            closed.clear()
            for conn in conns:
                assert isinstance(conn, mpc.Connection)
                try:
                    msg = conn.recv()
                except EOFError:
                    msg = None
                except OSError as ex:
                    logger.debug('%s from %s: %s',
                                 conn, ex.__class__.__name__, ex)
                    msg = None

                if conn is control:
                    control.send(msg)
                    if msg is False:
                        control = None  # Time to exit.
                    else:
                        # New connection.
                        assert msg is None, f'Got {msg}'
                elif msg is None or msg is False:
                    closed.add(conn)
                    conn.close()
                else:
                    pending.append((conn, msg))

            if not control:
                logger.debug('Exiting broker thread')
                break

            with clients_lock:
                self._clients -= closed

            # At least the control connection should be there.
            assert clients

            # Now forward all pending messages.
            self._send(control, clients_lock, pending)

        with clients_lock:
            for conn in self._clients:
                conn.close()
            self._clients.clear()

    def _send(self, control: mpc.Connection,
              clients_lock: threading.Lock,
              pending: List[Tuple[mpc.Connection, Message]]) -> None:

        closed: Set[mpc.Connection] = set()

        with clients_lock:
            clients = self._clients.copy()

        for conn, (topic, kwargs) in pending:
            for other_conn in clients:
                if (other_conn is conn
                        or other_conn is control
                        or other_conn in closed):
                    continue

                try:
                    other_conn.send((topic, kwargs))
                except ConnectionError:
                    other_conn.close()
                    closed.add(other_conn)
                except ValueError as ex:
                    logger.critical('Could not send: %s', ex)

        pending.clear()

        with clients_lock:
            self._clients -= closed


def main() -> None:
    # pylint: disable=import-outside-toplevel
    import argparse
    import pickle
    import secrets
    import sys
    # pylint: enable=import-outside-toplevel

    parser = argparse.ArgumentParser(description='''

    Write the server address and authkey as a picked tuple to a file,
    so other pub-subs can connect to it. To read the file, clients can
    use "import pickle; (address, authkey) = pickle.load(FILENAME)".

    ''')

    parser.add_argument('--overwrite',
                        help='overwrite the file, if it already exists',
                        action='store_true')
    parser.add_argument('filename',
                        help='file name to write server address and authkey')
    args = parser.parse_args()

    authkey = secrets.token_bytes()
    broker = Broker(authkey=authkey)

    try:
        with open(args.filename, 'wb' if args.overwrite else 'xb') as fd:
            pickle.dump((broker.address, authkey), fd)
    except FileExistsError:
        sys.exit(f'{args.filename} already exists; '
                 'pass --overwrite to overwrite')

    broker.start()


if __name__ == '__main__':
    main()
