import os

import pytest

# Tests that write to the registry are disabled by default. Any test that is
# writing to the registry should use `@reg_write_skipif()`
ENABLE_ENV_VAR = 'CASEMENT_TEST_WRITE_ENV'
SKIP_ENV_VAR_WRITES = os.getenv(ENABLE_ENV_VAR) != '1'
ENV_VAR_REASON = "To enable registry write tests, set the env var `{}` to `1`.".format(
    ENABLE_ENV_VAR
)


def reg_write_skipif(**kwargs):
    """Decorator that skips test unless writing is explicitly enabled.

    Tests with this decorator will be marked as skipped unless the environment
    variable `CASEMENT_TEST_WRITE_ENV` is set to 1. It's intended that this is
    only enabled on the github action runner, and by developers that need to
    modify code modifying the registry and EnvVar setting/deleting features.
    """
    kwargs.setdefault('condition', os.getenv(ENABLE_ENV_VAR) != '1')
    kwargs.setdefault('reason', ENV_VAR_REASON)
    return pytest.mark.skipif(**kwargs)
