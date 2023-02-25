import logging
import os
from contextlib import contextmanager

import win32api
import win32con
import win32file
import win32gui
from six.moves import winreg
from six.moves.collections_abc import MutableMapping

from .registry import REG_LOCATIONS, RegKey

_logger_modify = logging.getLogger(__name__ + ".modify")
_logger_broadcast = logging.getLogger(__name__ + ".broadcast")


class EnvVar(MutableMapping):
    """A dictionary like mapping of environment variables as defined in the
    registry. Stored environment variables are not expanded by default. You can
    use `normalize_path` for various path manipulation like expanding variables
    and dealing with short/long file paths.

    Arguments:
        system (bool, optional): Controls if this instance modifies system or
            user environment variables.

    Every time you set or delete a environment variable it will send the
    `WM_SETTINGCHANGE` message notifying other applications that system-wide
    settings have changed.
    See: https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-settingchange

    You can prevent this message from being sent every time you modify env vars
    by using the `EnvVar.delayed_broadcast()` with context:

        user_env = EnvVar(system=False)
        with EnvVar.delayed_broadcast():
            user_env['VAR_B'] = 'value b'
            user_env['VAR_C'] = 'value c'
            del user_env['VAR_A']

    By using `EnvVar.delayed_broadcast()` broadcast will only be called once,
    instead of three times.
    """

    # These class variables are used to control if broadcast sends its message
    _broadcast_enabled = True
    _broadcast_required = False

    def __init__(self, system=False):
        key, sub_key = REG_LOCATIONS["system" if system else "user"]['env_var']
        self.__reg__ = RegKey(key, sub_key)

    def __delitem__(self, key):
        entry = self.__reg__.entry(key)
        with self.delayed_broadcast():
            _logger_modify.debug('Deleting env var: "{}"'.format(key))
            entry.delete()
            type(self)._broadcast_required = True

    def __getitem__(self, key):
        entry = self.__reg__.entry(key)
        try:
            return entry.value()
        except OSError:
            raise KeyError(key)

    def __iter__(self):
        return iter(self.__reg__.entry_names())

    def __len__(self):
        reg_key = self.__reg__._key()
        if not reg_key:
            return 0

        _, count, _ = winreg.QueryInfoKey(reg_key)
        return count

    def __setitem__(self, key, value, value_type=winreg.REG_EXPAND_SZ):
        entry = self.__reg__.entry(key)
        with self.delayed_broadcast():
            _logger_modify.debug('Setting env var: "{}" to "{}"'.format(key, value))
            entry.set(value, value_type=value_type)
            type(self)._broadcast_required = True

    @classmethod
    def broadcast(cls):
        """Notify the system about the changes. Uses SendMessageTimeout to avoid
        hanging if applications fail to respond to the broadcast.
        """
        if cls._broadcast_enabled is False:
            _logger_broadcast.debug(
                'Skipping broadcasting that the environment was changed'
            )
            return

        _logger_broadcast.debug('Broadcasting that the environment was changed')
        win32gui.SendMessageTimeout(
            win32con.HWND_BROADCAST,
            win32con.WM_SETTINGCHANGE,
            0,
            'Environment',
            win32con.SMTO_ABORTIFHUNG,
            1000,
        )
        # Reset the needs broadcast variable now that we have broadcast
        cls._broadcast_required = False

    @classmethod
    @contextmanager
    def delayed_broadcast(cls):
        """Context manager that disables broadcast calls for each set/delete of
        environment variables. Only if any set/delete calls were made inside the
        with context, will it call broadcast.
        """
        try:
            current = cls._broadcast_enabled
            cls._broadcast_enabled = False
            yield
        finally:
            cls._broadcast_enabled = current
            if cls._broadcast_required:
                cls.broadcast()

    @classmethod
    def normalize_path(cls, path, expandvars=True, tilde=None, normpath=True):
        """Normalize a path handling short/long names, env vars and normpath.

        Args:
            path (str): Input path to expand.
            expandvars (bool, optional): Expand environment variables.
            tilde (bool, optional): Converts windows short paths(`C:\\PROGRA~1`).
                If True, short paths are expanded to full file paths. If False
                file paths are converted to short paths. Nothing is done if None.
            normpath (bool, optional): If True calls os.path.normpath.

        Returns:
            str: Input path with any tilde-shortenings expanded.

        Raises:
            pywintypes.error: Raised if path doesn't exist when tilde is not None.
        """
        if tilde:
            path = win32api.GetShortPathName(path)
        elif tilde is False:
            path = win32file.GetLongPathName(path)

        if expandvars:
            path = os.path.expandvars(path)

        if normpath:
            path = os.path.normpath(path)

        return path
