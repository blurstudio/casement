import ctypes
from .enums import FlashTimes


def flash_window(hwnd, dw_flags=None, count=1, timeout=0):
    """Flashes the application depending on the os.

    On Windows this calls FlashWindowEx. See
    https://msdn.microsoft.com/en-us/library/ms679348(v=vs.85).aspx for documentation.

    Args:
        hwnd (int or None): Flash this hwnd id.
        dw_flags (casement.enums.FlashTimes): A enum value used to control the
            flashing behavior. See
            https://msdn.microsoft.com/en-us/library/ms679348(v=vs.85).aspx for more
            details. Defaults to FLASHW_TIMERNOFG.
        count (int): The number of times to flash the window. Defaults to 1.
        timeout (int): The rate at which the window is to be flashed in
            milliseconds. if zero is passed, the default cursor blink rate is used.
    """

    if dw_flags is None:
        dw_flags = FlashTimes.FLASHW_TIMERNOFG

    ctypes.windll.user32.FlashWindow(hwnd, int(dw_flags.value), count, timeout)
