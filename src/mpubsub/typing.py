from typing import Tuple, Union, Callable, Dict, Any

Topic = Union[Tuple[str, ...], str, None]

Subscriber = Callable[..., None]

Message = Tuple[Topic, Dict[str, Any]]
