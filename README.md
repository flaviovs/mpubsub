A pub-sub architecture with remote capabilities for Python
==========================================================

_mpubsub_ implements a publish-subscribe messaging architecture in
Python that can be used by local and remote processes. Remote
publishers or subscribers can join any time to exchange messages.

Features:
- Extremally fast and compact pub-sub object — the entire local
  pub-sub module has about 100 lines, including docstring
  documentation for all public methods.
- All batteries included — _mpubsub_ only uses Python’s standard
  library modules. No external dependencies needed.
- Remote connections — subscribers are transparently notified of
  topics published on remote pub-sub objects. Messages published
  locally are forwarded to remote pub-subs.
- Local topic support — messages can be flagged for local delivery
  only.
- OOP interface — you can have multiple independent pub-sub objects on
  the same program.
- Remote authentication — _mpubsub_ uses the same authentication
  mechanism used by the (multiprocessing
  module)[https://docs.python.org/3.7/library/multiprocessing.html] to
  authenticate remote connections.

_mpubsub_ requires Python 3.7 or above.


Installation
------------

    pip install mpubsub


Architecture
------------

_mpubsub_ consists of three classes: _PubSub_, _NetPubSub_, and
_Broker_.

The _PubSub_ class is an efficient implementation of the
publish-subscribe messaging pattern for same-process publishers and
subscribers. This class alone can be used to implement pub-sub in an
application when no remote capabilities are needed.

The _NetPubSub_ is a networking-capable version of _PubSub_. A process
can connect a _NetPubSub_ to a _mpubsub_ message broker so that
messages published locally are forwarded to all other pub-subs
connected to the same broker. Likewise, all subscribers of the local
pub-sub object receive messages published to the broker.

The _Broker_ class implements the _mpubsub_ message broker. The broker
coordinates message passing between remote publishers and subscribers.


## The PubSub class

The PubSub class provides an interface for publishers and subscribers
to interact with the messaging system. Publishers can post messages to
a topic, and subscribers receive messages for the subscribed topic.

### Topics

Topics are Python tuples, and those tuple-topics are handled
hierarchically. For example, if the topic _(‘foo’, ‘bar’)_ is
published, then subscribers are notified in the following order:

1. All _(‘foo’, ‘bar’)_ subscribers
2. All _(‘foo’,)_ subscribers — NB: a one-element tuple
3. All catch-all subscribers

For convenience, you can subscribe to, and publish string
topics. Internally, those are transformed to a single tuple topic (in
other words, publishing or subscribing to `'foo'` is the same as
publishing or subscribing`('foo',)`).

When subscribing, the empty tuple is the _catch-all_
topic. Subscribers to this topic will get all messages published on
the _PubSub_ object.

When publishing, the empty tuple is the _broadcast_ topic. Messages
published with the broadcast topic are sent to all subscribers in the
pub-sub.

You can pass _None_ instead of `()` to mean the catch-all/broadcast
topic. In all cases, subscribers callbacks **always** get tuples as
their first parameter.

Note: _mpubsub_ does **not** validate topic types for performance
reasons. Due to implementation details, other pickable, hashable
objects _may_ “work” as topic values, but this is not supported. It is
up to the callers to ensure that only tuples of strings are used as
topics (sole strings and _None_ are fine, since they’re translated to
tuples following the rules outlined above).


### Messages

Topics can carry additional _key=value_ data, called _the
message_. Those are mapped directly to keyword arguments when a
subscriber is called.

_mpubsub_ will issue warnings if a subscriber does not support a
keyword argument present in a message.


## The _NetPubSub_ Class

The _NetPubSub_ is a subclass of _PubSub_ that adds remote
capabilities to it. Beside all _PubSub_ methods, it also provides
methods to connect and disconnect the pub-sub to a broker.


## The _Broker_ Class

The Broker class acts as the intermediary between publishers and
subscribers in remote pub-subs. It listens for incoming connections
from _NetPubSub_ objects, and coordinate message forwarding between
them.

Notice that the broker run asynchronously in relation to remote
_NetPubSub_ object. You can start a broker using
[multiprocessing](https://docs.python.org/3.7/library/multiprocessing.html#multiprocessing.connection.Listener)
or as a separate Python script. Using threads is not supported.


Examples
-------

## Local pub-sub example

First import the class and create a _PubSub_ object:

    >>> from mpubsub import PubSub
    >>>
    >>> pubsub = PubSub()

Create two functions that just print their parameters. Those will be
our example subscribers:

    >>> def subscriber_1(topic, message):
    ...     print(f'Received by subscriber 1: {message}')
    >>>

    >>> def subscriber_2(topic, message):
    ...     print(f'Received by subscriber 2: {message}')
    >>>

Add the subscribers to the pub-sub object:

    >>> pubsub.add_subscriber('hello', subscriber_1)
    >>> pubsub.add_subscriber('hello', subscriber_2)

Now publish some data:

    >>> pubsub.publish('hello', message='foo')
    Received by subscriber 1: foo
    Received by subscriber 2: foo

To unsubscribe, just call `remove_subscriber()` with the same
parameters:

    >>> pubsub.remove_subscriber('hello', subscriber_2)
    >>> pubsub.publish('hello', message='foo')
    Received by subscriber 1: foo

To unsubscribe all subscribers, call `clear_subscribers()`:

    >>> pubsub.clear_subscribers()
    >>> pubsub.publish('hello', message='foo')


## Remote pub-sub example

See [demo.py](demo.py) for an example of how to use _mpubsub_ to
implement remote pub-subs.


Remote pub-subs addresses
-------------------------

_mpubsub_ connects to remote pub-subs using [multiprocessing
Connection](https://docs.python.org/3.7/library/multiprocessing.html#connection-objects)
objects. Address used by _NetPubSub_ and _Broker_ classes have the
same format and semantincs as described in the Python’s documentation.


Standalone broker
-----------------

You can start a standalone broker with the following command:

    python -m mpubsub.broker $HOME/.mpubsub.pckl

The broker’s address and _authkey_ are pickled as a tuple _(address,
authkey)_, and saved to the file provided in the command line. Clients
can read this file to unpickle the values and connect to the
broker. Run `python -m mpubsub.broker --help` for usage information.


Security
--------

* _mpubsub_ uses _multiprocessing_’s authentication keys to
  authenticate connections. If you pass _None_ to the broker,
  `multiprocessing.current_process().authkey` will be used. The
  _mpubsub_ broker does not support unauthenticated connections. See
  [the relevant
  documentation](https://docs.python.org/3.7/library/multiprocessing.html#multiprocessing-auth-keys)
  for more details about Python’s _multiprocessing_ authentication
  mechanism.

* The authentication used by _multiprocessing_ protects **only**
  against unauthorized connections. Message contents are transmitted
  in plain text, and because of that anyone on the network(s) where
  connection packets travel can see the contents of published topic
  and messages. Is advisable to use remote connections **only on
  trusted networks**.

* All data received from authenticated connections are unpickled
  automatically. This opens the possibility of remote code execution,
  therefore you should connect pub-subs only to brokers you trust. See
  [the relevant warning in the Python’s
  documentation](https://docs.python.org/3.7/library/multiprocessing.html#connection-objects).


Questions? Critics? Suggestions?
--------------------------------
Visit https://github.com/flaviovs/mpubsub
