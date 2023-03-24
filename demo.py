# mypy: disable-error-code="no-untyped-def,arg-type"
import argparse
import logging
import random
import secrets
import time
import multiprocessing as mp
from typing import Dict

from mpubsub.net import PubSub
from mpubsub.broker import Broker

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname).1s %(processName)s: %(message)s')

logger = logging.getLogger(__name__)


# Now let's start a few publishers. Each one has its own PubSub
# object, and a Bridge connected to the broker.
def publisher(address, delay_min, delay_max, n):
    logger.info('Starting up')
    pubsub = PubSub(address)

    pubsub.connect()

    stop = False

    def panic_callback(topic):
        nonlocal stop
        logger.critical('PANIC received from %s', topic[1])
        stop = True

    pubsub.add_subscriber('PANIC', panic_callback)

    msg = 0
    while not stop:
        msg += 1
        logger.info('Publishing: %r', msg)
        pubsub.publish(('demo', f'PUB{n}'), msg=msg)
        if delay_max:
            time.sleep(delay_min + (random.random() * delay_max))

    pubsub.disconnect()


def subscriber(address, n):
    logger.info('Starting up')

    pubsub = PubSub(address)

    msg_sequence: Dict[str, int] = {}

    stop = False

    def panic_callback(topic):
        nonlocal stop
        logger.critical('PANIC received from %s', topic[1])
        stop = True

    def message_callback(topic, msg):
        publisher = topic[1]

        logger.info('Got %r from %s', msg, publisher)

        if publisher.startswith('PUB'):
            expected = msg_sequence.get(publisher, 1)
            if msg != expected:
                logger.critical('Expecting message %d from %r, got %r',
                                expected, publisher, msg)
                pubsub.publish(('PANIC', f'sub{n}'))
            msg_sequence[publisher] = msg + 1

        # Let the subscriber publish something at 5% probability.
        if random.random() < 0.05:
            msg = secrets.token_hex(4)
            logger.info("I've decided to publish %r", msg)
            pubsub.publish(('demo', f'sub{n}'), msg=msg)

        # Also publish something locally at 5% probability.
        if random.random() < 0.05:
            logger.info("I'm gonna publish a local message")
            pubsub.publish(('demo', f'sub{n}', '*local'),
                           msg='This is a local message')

    pubsub.add_subscriber('demo', message_callback)
    pubsub.add_subscriber('PANIC', panic_callback)

    pubsub.connect()
    while not stop:
        pubsub.poll(None)
    pubsub.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--delay-min',
                        type=float,
                        default=5,
                        help='minimum random delay')
    parser.add_argument('--delay-max',
                        type=float,
                        default=10,
                        help='maximum random delay; pass 0 for no delay')
    parser.add_argument('-p', '--publishers',
                        type=int,
                        default=3,
                        help='publishers to spawn')
    parser.add_argument('-s', '--subscribers',
                        type=int,
                        default=3,
                        help='subscribers to spawn')
    parser.add_argument('-w', '--wait',
                        type=float,
                        default=0.2,
                        help=('seconds to wait per subscriber before '
                              'starting publishers'))
    args = parser.parse_args()

    logger.info('Starting demo with %d publishers and %d subscribers',
                args.publishers, args.subscribers)

    mp.set_start_method('spawn')

    processes = []

    # Get the broker object.
    broker = Broker(None)

    # Grab its address.
    address = broker.address

    # Start the broker in a separate process.
    broker_process = mp.Process(target=broker.start, name='broker')
    broker_process.start()
    processes.append(broker_process)

    # Start subscribers.
    for n in range(args.subscribers):
        proc = mp.Process(target=subscriber, name=f'sub{n}', args=(address, n))
        proc.start()
        processes.append(proc)

    # Give some time for the subscribers to connect before the
    # publishers, otherwise they might miss messages and fail message
    # tracking.
    logger.info('Waiting for all subscribers to start')
    time.sleep(args.subscribers * args.wait)

    # Start publishers.
    for n in range(args.publishers):
        proc = mp.Process(target=publisher, name=f'PUB{n}',
                          args=(address, min(args.delay_min, args.delay_max),
                                args.delay_max, n))
        proc.start()
        processes.append(proc)

    for process in processes:
        process.join()


if __name__ == '__main__':
    main()
