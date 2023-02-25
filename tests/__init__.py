import os

# Tests that write to the registry are disabled by default. Any test that is
# writing to the registry should use `pytest.mark.skipif` checking the env var
# `CASEMENT_TEST_WRITE_ENV`. It's intended that this is only enabled on the
# github action runner, and by developers that need to modify code modifying the
# registry and EnvVar setting/deleting features.
ENABLE_ENV_VAR = 'CASEMENT_TEST_WRITE_ENV'
SKIP_ENV_VAR_WRITES = os.getenv(ENABLE_ENV_VAR) != '1'
ENV_VAR_REASON = "To enable registry write tests, set the env var `{}` to `1`.".format(
    ENABLE_ENV_VAR
)
