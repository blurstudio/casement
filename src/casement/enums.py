from enum import Enum


class FlashTimes(Enum):
    """Windows flags for casement.utils.flashWindow().

    https://docs.microsoft.com/en-us/windows/desktop/api/winuser/ns-winuser-flashwinfo
    """

    "'Stop flashing. The system restores the window to its original state.'"
    FLASHW_STOP = 0
    "Flash the window caption."
    FLASHW_CAPTION = 0x00000001
    "Flash the taskbar button."
    FLASHW_TRAY = 0x00000002
    """Flash both the window caption and taskbar button. This is equivalent
    to setting the ``FLASHW_CAPTION | FLASHW_TRAY flags``."""
    FLASHW_ALL = 0x00000003
    "Flash continuously, until the ``FLASHW_STOP`` flag is set."
    FLASHW_TIMER = 0x00000004
    "Flash continuously until the window comes to the foreground."
    FLASHW_TIMERNOFG = 0x0000000C
