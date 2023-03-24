"""A multi-process capable publish-subscribe system."""
import warnings
import weakref
from typing import Dict, List, Any, Tuple

from .typing import Topic, Subscriber

__version__ = '0.0.1'


class PubSub:
    """A simple publish-subscribe messaging system.

    Topics are tuples used to represent a hierarchy, so if someone
    subscribes to topic 'a', then they will also receive messages
    published with the topic ('a', 'b').

    """

    def __init__(self) -> None:
        """Initialize a new PubSub instance."""
        self._subs: Dict[Tuple[str, ...],
                         List[weakref.ReferenceType[Subscriber]]] = {}

    def add_subscriber(self, topic: Topic, subscriber: Subscriber) -> None:
        """Add a subscriber to a topic.

        Args:
          topic (tuple): The topic to subscribe to.
          subscriber (callable): The callable to be called when a
              message is published to the subscribed topic.

        """

        if topic is None:
            topic = ()
        elif not isinstance(topic, tuple):
            topic = (topic,)

        if topic not in self._subs:
            self._subs[topic] = []

        ref = (weakref.WeakMethod(subscriber)
               if hasattr(subscriber, '__self__')
               else weakref.ref(subscriber))

        self._subs[topic].append(ref)

    def remove_subscriber(self, topic: Topic, subscriber: Subscriber) -> None:
        """Remove a subscriber from a topic.

        Args:
          topic (tuple or str or None): The topic to unsubscribe from.
          subscriber (callable): The callable to be unsubscribed.
        """
        if topic is None:
            topic = ()
        elif not isinstance(topic, tuple):
            topic = (topic,)

        try:
            subs = self._subs[topic]
        except KeyError:
            return

        for ref in subs:
            sub = ref()
            if sub == subscriber:
                subs.remove(ref)
                break

    def clear_subscribers(self) -> None:
        self._subs.clear()

    def publish(self, topic: Topic, **kwargs: Any) -> None:
        """Publish a message on a topic.

        If the topic is None, the message is published to all
        subscribers. Otherwise topic must be a string or topic tuple.

        Args:
          topic (tuple or str or None): The topic to publish the
            message on.
          kwargs: The keyword arguments to pass to the subscribers.

        """
        assert isinstance(topic, (str, tuple))

        if not isinstance(topic, tuple):
            topic = (topic,)

        orig_topic = tuple(topic)
        while True:
            try:
                subs = self._subs[topic]
            except KeyError:
                pass
            else:
                for ref in subs:
                    sub = ref()
                    if sub is None:
                        continue
                    try:
                        sub(orig_topic, **kwargs)
                    except TypeError as ex:
                        warnings.warn(f'Failed to send message to {sub}: {ex}')
            if not topic:
                break
            topic = topic[:-1]
