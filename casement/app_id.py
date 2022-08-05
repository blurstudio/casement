import ctypes
import os
import pythoncom
from ctypes import wintypes
from win32com.propsys import propsys
from win32com.shell import shellcon


class AppId(object):
    @staticmethod
    def for_shortcut(shortcut):
        """Gets the AppUserModel.ID for the given shortcut.

        This will allow windows to group windows with the same app id on a shortcut
        pinned to the taskbar. Use :py:meth:`AppId.for_application` to set the
        app id for a running application.
        """
        if os.path.exists(shortcut):
            # These imports won't work inside python 2 DCC's
            from win32com.propsys import propsys

            # Original info from https://stackoverflow.com/a/61714895
            key = propsys.PSGetPropertyKeyFromName("System.AppUserModel.ID")
            store = propsys.SHGetPropertyStoreFromParsingName(shortcut)
            return store.GetValue(key).GetValue()

    @staticmethod
    def set_for_shortcut(shortcut, app_id):
        """Sets AppUserModel.ID info for a windows shortcut.

        Note: This doesn't seem to work on a pinned taskbar shortcut. Set it on
        a desktop shortcut then pin that shortcut.

        This will allow windows to group windows with the same app id on a shortcut
        pinned to the taskbar. Use :py:meth:`AppId.set_for_application` to set
        the app id for a running application.

        Args:
            shortcut (str): The .lnk filename to set the app id on.
            app_id (str): The app id to set on the shortcut
        """
        if os.path.exists(shortcut):
            # Original info from https://stackoverflow.com/a/61714895
            key = propsys.PSGetPropertyKeyFromName("System.AppUserModel.ID")
            store = propsys.SHGetPropertyStoreFromParsingName(
                shortcut, None, shellcon.GPS_READWRITE, propsys.IID_IPropertyStore
            )

            new_value = propsys.PROPVARIANTType(app_id, pythoncom.VT_BSTR)
            store.SetValue(key, new_value)
            store.Commit()

    @staticmethod
    def for_application():
        """Returns the current Windows 7+ app user model id used for taskbar
        grouping."""

        lp_buffer = wintypes.LPWSTR()
        app_user_model_id = (
            ctypes.windll.shell32.GetCurrentProcessExplicitAppUserModelID
        )
        app_user_model_id(ctypes.cast(ctypes.byref(lp_buffer), wintypes.LPWSTR))
        appid = lp_buffer.value
        ctypes.windll.kernel32.LocalFree(lp_buffer)
        return appid

    @staticmethod
    def set_for_application(appid, prefix=None):
        """Controls Windows taskbar grouping.

        Specifies a Explicit App User Model ID that Windows 7+ uses to control
        grouping of windows on the taskbar.  This must be set before any ui is
        displayed. The best place to call it is in the first widget to be displayed
        __init__ method.

        See :py:meth:`AppId.set_for_shortcut` to set the app id on a windows shortcut.

        Args:
            appid (str): The id of the application. Should use full camel-case.
                http://msdn.microsoft.com/en-us/library/dd378459%28v=vs.85%29.aspx#how
            prefix (str, optional): The prefix attached to the id.
        """

        # https://stackoverflow.com/a/27872625
        if prefix:
            appid = u'%s.%s' % (prefix, appid)
        return not ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
