import unittest
from typing import List, Tuple

from mpubsub import PubSub
from mpubsub.typing import Topic


class TestPubSub(unittest.TestCase):
    def setUp(self) -> None:
        self.pubsub = PubSub()
        self.messages: List[Tuple[Topic, str]] = []

    def _subscriber(self, topic: Topic, message: str) -> None:
        self.messages.append((topic, message))

    def test_publish_and_subscribe(self) -> None:
        # Subscribe to a topic and publish a message
        self.pubsub.add_subscriber(('a', 'b', 'c'), self._subscriber)
        self.pubsub.publish(('a', 'b', 'c'), message='hello')

        # Check that the subscriber received the message
        self.assertEqual(self.messages, [(('a', 'b', 'c'), 'hello')])

    def test_publish_and_subscribe_str(self) -> None:
        self.pubsub.add_subscriber('foo', self._subscriber)
        self.pubsub.publish('foo', message='hello')
        self.pubsub.publish(('foo',), message='hello')
        self.assertEqual(len(self.messages), 2)

    def test_remove_subscriber_method(self) -> None:
        # Subscribe to a topic, then unsubscribe and publish a message
        self.pubsub.add_subscriber(('a', 'b', 'c'), self._subscriber)
        self.pubsub.remove_subscriber(('a', 'b', 'c'), self._subscriber)
        self.pubsub.publish(('a', 'b', 'c'), message='hello')

        # Check that the subscriber did not receive the message
        self.assertEqual(self.messages, [])

    def test_remove_subscriber_func(self) -> None:
        calls = 0

        def subscriber(_topic: Topic) -> None:
            nonlocal calls
            calls += 1

        self.pubsub.add_subscriber('foo', subscriber)
        self.pubsub.remove_subscriber('foo', subscriber)
        self.pubsub.publish('foo')
        self.assertEqual(0, calls)

    def test_remove_subscriber_str(self) -> None:
        self.pubsub.add_subscriber('foo', self._subscriber)
        self.pubsub.remove_subscriber('foo', self._subscriber)
        self.pubsub.publish('foo')
        self.assertEqual(len(self.messages), 0)

    def test_publish_to_parent_topic(self) -> None:
        # Subscribe to a parent topic and publish a message to a child topic
        self.pubsub.add_subscriber(('a', 'b'), self._subscriber)
        self.pubsub.publish(('a', 'b', 'c'), message='hello')

        # Check that the subscriber received the message
        self.assertEqual(self.messages, [(('a', 'b', 'c'), 'hello')])

    def test_publish_to_multiple_subscribers(self) -> None:
        # Subscribe two subscribers to the same topic and publish a message
        def subscriber1(topic: Topic, message: str) -> None:
            assert isinstance(topic, tuple)
            self.messages.append((topic + ('subscriber1',), message))

        def subscriber2(topic: Topic, message: str) -> None:
            assert isinstance(topic, tuple)
            self.messages.append((topic + ('subscriber2',), message))

        self.pubsub.add_subscriber(('a', 'b'), subscriber1)
        self.pubsub.add_subscriber(('a', 'b'), subscriber2)
        self.pubsub.publish(('a', 'b'), message='hello')

        # Check that both subscribers received the message
        self.assertEqual(self.messages, [
            ((('a', 'b', 'subscriber1'), 'hello')),
            ((('a', 'b', 'subscriber2'), 'hello')),
        ])

    def test_subscribe_to_all_topics(self) -> None:
        # Subscribe to a parent topic and publish a message to a child topic
        self.pubsub.add_subscriber(None, self._subscriber)

        self.pubsub.publish(('a', 'b', 'c'), message='hello1')
        self.pubsub.publish(('x', 'y', 'z'), message='hello1')

        # Check that the subscriber received the message
        self.assertEqual(self.messages,
                         [
                             (('a', 'b', 'c'), 'hello1'),
                             (('x', 'y', 'z'), 'hello1'),
                         ])

    def test_subscribe_unknown_kwargs(self) -> None:
        self.pubsub.add_subscriber('foo', self._subscriber)
        with self.assertWarns(Warning):
            self.pubsub.publish('foo', unkown_kwarg=123)
        self.assertEqual(self.messages, [])
