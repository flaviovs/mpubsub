# pylint: disable=too-few-public-methods
import gc
import unittest

from mpubsub import PubSub
from mpubsub.typing import Topic


class PubSubTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pubsub = PubSub()

    def test_weakref_function(self) -> None:
        calls = 0

        def callback(_topic: Topic) -> None:
            nonlocal calls
            calls += 1

        self.pubsub.add_subscriber(('a',), callback)
        self.pubsub.publish(('a',))
        self.assertEqual(calls, 1)

        del callback

        gc.collect()
        self.pubsub.publish(('a',))
        self.assertEqual(calls, 1)

    def test_weakref_bound_method(self) -> None:
        calls = 0

        class TestObject:
            def callback(self, _topic: Topic) -> None:
                nonlocal calls
                calls += 1

        obj = TestObject()
        self.pubsub.add_subscriber(('a',), obj.callback)
        self.pubsub.publish(('a',))
        self.assertEqual(calls, 1)

        del obj
        gc.collect()
        self.pubsub.publish(('a',))
        self.assertEqual(calls, 1)
