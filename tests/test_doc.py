import doctest
from pathlib import Path

import mpubsub


def load_tests(_loader, tests, _ignore):  # type: ignore[no-untyped-def]
    tests.addTests(doctest.DocFileSuite('../README.md'))

    tests.addTests(doctest.DocTestSuite(mpubsub))
    for path in Path(mpubsub.__file__).parent.glob('*.py'):
        module = path.stem
        if module != '__init__':
            tests.addTests(doctest.DocTestSuite(f'mpubsub.{module}'))

    return tests
