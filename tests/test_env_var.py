"""
By default all registry tests that actually modify the registry are skipped.
You must set the environment variable `CASEMENT_TEST_WRITE_ENV` to `1` to enable
running the skipped tests.

Environment variable modification tests should only affect casement specific
environment variables that don't affect anything. They should contain
`CASEMENT_DELETE_ME` in the name. When testing finishes all of these env var's
should be removed. All write tests should be done on user environment variables.

Here are the Environment variables that are modified when write testing is enabled.
- `CASEMENT_TEST_DELETE_ME_ENV_VAR`

Note: See test_registry.py to see how testing registry keys/entries are handled.
"""
from __future__ import absolute_import

import os

import pytest
import win32api

from casement.env_var import EnvVar
from casement.registry import RegKey

from . import ENV_VAR_REASON, SKIP_ENV_VAR_WRITES

TEST_VAR_NAME = 'CASEMENT_TEST_DELETE_ME_ENV_VAR'


def env_var(var_name):
    def decorator(function):
        def wrapper(*args, **kwargs):
            senv = EnvVar(True)
            uenv = EnvVar(False)
            # Ensure the test env var is cleaned up, in case a previous test failed
            # or was killed before the env var was removed normally.
            if var_name in senv:
                del senv[var_name]
            if var_name in uenv:
                del uenv[var_name]

            ret = function(*args, **kwargs)

            # Ensure the variables are cleaned up after the test runs
            if var_name in senv:
                del senv[var_name]
            if var_name in uenv:
                del uenv[var_name]
            return ret

        return wrapper

    return decorator


@pytest.mark.skipif(
    os.getenv("GITHUB_ACTIONS") == "true",
    reason="Github Actions doesn't support short names anymore.",
)
def test_expand_path():
    # Generate a short name path. This method needs a file that actually
    # exists on disk, and test_env_var.py is long enough to get ~'ed
    short_name = win32api.GetShortPathName(__file__)
    assert '~' in short_name

    # Check expandvars argument
    out = EnvVar.normalize_path('%HOMEPATH%', expandvars=True)
    assert out == os.path.expandvars('%HOMEPATH%')
    out = EnvVar.normalize_path('%HOMEPATH%', expandvars=False)
    assert out == '%HOMEPATH%'

    # Check tilde argument
    out = EnvVar.normalize_path(short_name, tilde=False)
    assert os.path.normpath(out) == __file__
    out = EnvVar.normalize_path(__file__, tilde=True)
    assert os.path.normpath(out) == os.path.normpath(short_name)

    # Check normpath argument
    fle = __file__.replace('\\', '/')
    out = EnvVar.normalize_path(fle, normpath=False)
    assert out == fle
    out = EnvVar.normalize_path(fle, normpath=True)
    assert out == __file__


@pytest.mark.skipif(SKIP_ENV_VAR_WRITES, reason=ENV_VAR_REASON)
@env_var(TEST_VAR_NAME)
def test_envvar_modify():
    uenv = EnvVar(system=False)
    # Ensure the env var is not set
    assert TEST_VAR_NAME not in uenv

    # Ensure the env var was set
    uenv[TEST_VAR_NAME] = 'TEST'
    assert uenv[TEST_VAR_NAME] == 'TEST'
    uenv[TEST_VAR_NAME] = 'TEST 2'
    assert uenv[TEST_VAR_NAME] == 'TEST 2'

    # Test iterating over the env var. We can't tell for sure what
    # env vars are set, but we at least know one is set at this point
    for key, value in uenv.items():
        if key == TEST_VAR_NAME:
            assert value == 'TEST 2'
            break
    else:
        raise AssertionError(
            '{} was not found when iterating over the user environment'.format(
                TEST_VAR_NAME
            )
        )

    # Test length support, again we only know at least one env var is set
    count = len(uenv)
    assert count >= 1

    # Ensure the env var is once again not set
    del uenv[TEST_VAR_NAME]
    assert TEST_VAR_NAME not in uenv

    # test edge case where the registry key doesn't exist
    bad = EnvVar(system=False)
    bad.__reg__ = RegKey('HKEY_CURRENT_USER', 'BadEnvironment')
    assert len(bad) == 0


class EnvVarPatch(EnvVar):
    """Replaces the broadcast classmethod with one that allows us to track
    every time its called."""

    count = 0

    @classmethod
    def broadcast(cls):
        """Enable us to check how many times broadcast was called."""
        if cls._broadcast_enabled is False:
            return
        cls._broadcast_required = False
        cls.count += 1


@pytest.mark.skipif(SKIP_ENV_VAR_WRITES, reason=ENV_VAR_REASON)
@env_var(TEST_VAR_NAME)
def test_broadcast():
    """This test tests that delayed_broadcast only calls broadcast in the outer
    most use of its with context, and only if a broadcast was required.
    """
    uenv = EnvVarPatch(system=False)

    # Test setting an env var broadcasts
    assert EnvVarPatch._broadcast_enabled is True
    assert EnvVarPatch._broadcast_required is False
    assert EnvVarPatch.count == 0
    uenv[TEST_VAR_NAME] = 'TEST'
    assert EnvVarPatch._broadcast_enabled is True
    assert EnvVarPatch._broadcast_required is False
    assert EnvVarPatch.count == 1

    # Test deleting an env var broadcasts
    EnvVarPatch.count = 0
    assert EnvVarPatch._broadcast_enabled is True
    assert EnvVarPatch._broadcast_required is False
    del uenv[TEST_VAR_NAME]
    assert EnvVarPatch._broadcast_enabled is True
    assert EnvVarPatch._broadcast_required is False
    assert EnvVarPatch.count == 1


@pytest.mark.skipif(SKIP_ENV_VAR_WRITES, reason=ENV_VAR_REASON)
@env_var(TEST_VAR_NAME)
def test_delayed_broadcast():
    """This test tests that delayed_broadcast only calls broadcast in the outer
    most use of its with context, and only if a broadcast was required.
    """
    uenv = EnvVarPatch(system=False)

    # Test that multiple set/delete calls only emit a single broadcast
    # when the outer with context exits.
    EnvVarPatch.count = 0
    with EnvVarPatch.delayed_broadcast():
        assert EnvVarPatch._broadcast_enabled is False
        assert EnvVarPatch._broadcast_required is False
        uenv[TEST_VAR_NAME] = 'TEST'
        assert EnvVarPatch._broadcast_enabled is False
        assert EnvVarPatch._broadcast_required is True
        assert EnvVarPatch.count == 0

    assert EnvVarPatch._broadcast_enabled is True
    assert EnvVarPatch._broadcast_required is False
    assert EnvVarPatch.count == 1

    # Test that no broadcast is made if no changes were made
    EnvVarPatch.count = 0
    with EnvVarPatch.delayed_broadcast():
        assert EnvVarPatch._broadcast_enabled is False
        assert EnvVarPatch._broadcast_required is False
        assert EnvVarPatch.count == 0

    assert EnvVarPatch._broadcast_enabled is True
    assert EnvVarPatch._broadcast_required is False
    assert EnvVarPatch.count == 0

    # Test that the real broadcast method respects _broadcast_enabled
    uenv = EnvVar(system=False)
    with EnvVar.delayed_broadcast():
        assert EnvVar._broadcast_enabled is False
        assert EnvVar._broadcast_required is False
        uenv[TEST_VAR_NAME] = 'TEST'
        assert EnvVar._broadcast_enabled is False
        assert EnvVar._broadcast_required is True

    assert EnvVar._broadcast_enabled is True
    assert EnvVar._broadcast_required is False
