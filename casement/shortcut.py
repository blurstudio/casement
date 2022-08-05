r"""A interface for manipulating Windows shortcut files including pinned.

Pinning shortcuts to the start menu and task bar in windows is extremely complicated.
You can find and edit shortcuts in the User Pinned directory for for all users, but
adding, modifying or removing those shortcuts does not affect the pinned shortcuts.
You need to point to a copy of the pinned shortcut, and run windows verbs on that
shortcut.

Here is a example of pinning a shortcut to the start menu ::

    from casement.shortcut import Shortcut
    with Shortcut(r'C:\Users\Public\Desktop\My Shortcut.lnk') as sc:
        sc.pin_to_start_menu()

This class can not edit the pinned shortcuts, so if you want to update a existing
pinned shortcut you must unpin and then pin the shortcut. This will reset the position.
::

    from casement.shortcut import Shortcut
    sc = Shortcut(r'C:\Users\Public\Desktop\My Shortcut.lnk')
    start_menu, taskbar = sc.is_pinned()
    if start_menu:
        # Remove the existing shortcut from the start menu so it gets updated
        sc.unpin_from_start_menu()
    sc.pin_to_start_menu()

Shortcuts can not be pinned/unpinned from a network location, If this class is used
as a context manager it will copy the shortcut locally if it can't be pinned. It's
recommended to use the context manager if you are dealing with pinning to ensure
the pinning always works.
::

    from casement.shortcut import Shortcut
    with Shortcut(r'\\server\share\shortcut.lnk') as sc:
        print('In context:'.format(sc.is_pinned()))
    print('Outside context:'.format(sc.is_pinned()))

In this example the ``"In context"`` print will return the pinned status, but
the ``"Outside context"`` will raise a WindowsError because the shortcut is on
the network.

**Command line interface**

The features of this class can be used from the command line using ``casement
shortcut [command] [arguments]``.

To find shortcuts in common places with a given name::

    C:\\blur\dev\\casement>casement shortcut list "VLC media player.lnk"
    c:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\VideoLAN\\
        VLC media player.lnk
    c:\\Users\\Public\\Desktop\\VLC media player.lnk

Pinning/unpinning a shortcut to the taskbar ::

    C:\>casement shortcut pin "C:\\Users\\Public\\Desktop\\My Shortcut.lnk" -t
    C:\>casement shortcut unpin "C:\\Users\\Public\\Desktop\\My Shortcut.lnk" -t
"""

import errno
import glob
import logging
import os
import shutil
import six
import subprocess
import sys
import tempfile
import win32com.client
import winshell
from argparse import ArgumentParser

from .app_id import AppId


class Shortcut(object):
    default_paths = (
        '{mount}\\Users\\*\\AppData\\Roaming\\Microsoft\\Internet Explorer\\Quick Launch\\User Pinned\\TaskBar',  # noqa: B950
        '{mount}\\Users\\*\\AppData\\Roaming\\Microsoft\\Internet Explorer\\Quick Launch\\User Pinned\\StartMenu',  # noqa: B950
        '{mount}\\Users\\*\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs',
        '{mount}\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\*',
        '{mount}\\Users\\*\\Desktop',
    )
    """ Paths the find_shortcuts classmethod searches by default. """

    default_ignored_paths = ('{mount}\\Users\\All Users',)
    """ Paths the find_shortcuts classmethod ignores by default. """

    def __init__(self, filename):
        self.dirname = os.path.dirname(filename)
        self.basename = os.path.basename(filename)
        # We can't do anything with this file if it doesn't exist.
        self._exists()

    def __enter__(self):
        """If a shortcut can't be pinned, copy it locally while inside this context"""
        self._dirname_backup = None
        try:
            start_menu, taskbar = self.is_pinned()
        except WindowsError:
            # the shortcut can not be pinned, copy it to a tempdir
            self._dirname_backup = self.dirname
            dirname = tempfile.mkdtemp()
            shutil.copy2(os.path.join(self._dirname_backup, self.basename), dirname)
            # Update the class so it uses the tempdir until we exit
            self.dirname = dirname
            # This will raise a WindowsError if we still can't pin the shortcut.
            # This could happen if tempfile is configured to use a network location.
            start_menu, taskbar = self.is_pinned()
        return self

    def __exit__(self, type, value, traceback):
        """Remove the tempfile and restore the dirname"""
        if self._dirname_backup is not None:
            # If we copied the shortcut locally cleanup the temp files and reset
            shutil.rmtree(self.dirname)
            self.dirname = self._dirname_backup
            self._dirname_backup = None

    def _exists(self):
        """Raises a WindowsError if self.filename does not exist."""
        if not os.path.isfile(self.filename):
            # We can't get the verb of a file that does not exist on disk.
            msg = 'No such file'
            raise WindowsError(errno.ENOENT, msg, self.filename)

    def _run_verb(self, verb_name):
        """Run the verb with this name.

        Args:
            verb_name (str): The exact name of the verb, including & symbols.
                For example `Pin to Start Men&u`.

        Returns:
            bool: If the verb was found and run.
        """
        for verb in self.file_verbs():
            if verb.Name == verb_name:
                verb.DoIt()
                return True
        return False

    @staticmethod
    def clear_icon_cache():
        """Triggers a clearing of the windows explorer icon cache."""
        subprocess.Popen(['ie4uinit.exe', '-ClearIconCache'])

    def copy(self, target):
        """Copy this shortcut to/over the target.

        If target is a pinned shortcut for the current user, this will unpin the
        existing pinned shortcut if it exists, then pin ``self.filename`` to the
        target location. This will reset the position of the shortcut to the end
        of the pinned shortcuts.

        If target is a directory name, the copied shortcut will have the same name
        as ``self.filename``, If target is a filename, the shortcut will have the
        new filename.

        Args:
            target (str): The filename or dirname to copy the shortcut to.

        Raises:
            WindowsError: If path is a pinned location, but not for the current
                user, this error is raised as ``errno.EPERM``. Pinned paths can
                only be modified for the current user.
        """
        if not os.path.exists(self.filename):
            raise IOError('Source link does not exist: "{}"'.format(self.filename))

        is_start_menu, is_taskbar = self.path_in_pin_dir(target)
        # We are copying to the user's pinned folder, don't copy the link, pin it.
        start_menu, taskbar = self.is_pinned()
        if is_start_menu:
            # If currently pinned, unpin it then re-pin it
            if start_menu:
                self.unpin_from_start_menu()
            self.pin_to_start_menu()
        elif is_taskbar:
            if taskbar:
                self.unpin_from_taskbar()
            self.pin_to_taskbar()
        else:
            # Otherwise just copy the file using the file system
            if os.path.isfile(target):
                logging.debug('Removing existing {}'.format(target))
                os.remove(target)
            logging.debug('Copying {} -> {}'.format(self.filename, target))
            shutil.copy2(self.filename, target)

    @classmethod
    def create(
        cls,
        title,
        args,
        startin=None,
        target=None,
        icon=None,
        icon_source=None,
        icon_filename=None,
        path=None,
        description='',
        common=1,
        app_id=None,
    ):
        """Creates a shortcut.

        Args:
            title (str): the title for the shortcut
            args (str): argument string to pass to target command
            startin (str, optional): path where the shortcut should run target command.
                If None(default) then the dirname for the first argument in args
                is used. If args is empty, then the dirname of target is used.
            target (str, optional): the target for the shortcut. If None(default)
                this will default to sys.executable.
            icon (str, optional): path to the icon the shortcut should use.
                Ignored if icon_source is passed.
            icon_source (str, optional): path to a source image file that will
                be copied/converted and used as the shortcut icon. The file extension
                will be changed to .ico if that file exists. If not a .ico file
                Pillow(PIL) will be used to convert the image file to a .ico file
                and the .ico file is copied to `%PROGRAMDATA%` if common is 1
                otherwise it will be copied to `%APPDATA%`. These icons will be
                stored inside the casement/icons folder. You can install Pillow
                when installing casement with 'pip install casement[pil]'.
            icon_filename (str, optional): the name of the icon generated by
                icon_source. If not specified, title is used.
            path (str or list, optional): path where the shortcut should be created. On
                windows, if a list is passed it must have at least one string in
                it and the list will be passed to os.path.join. The first string
                in the list will be replaced if a key is used. `start menu` or
                `start-menu` is replaced with the path to the start menu. `desktop`
                is replaced with the path to the desktop. If None the desktop
                path is used.
            description (str, optional): helpful description for the shortcut
            common (int, optional): If auto generating the path, this controls
                if the path is generated for the user or shared. 1(default) is
                the public shared folder, while 0 is the users folder. See path
                to control if the auto-generated path is for the desktop or start menu.
            app_id (str, optional): Whether to set app ID on shortcut or not
        """
        if isinstance(path, (list, tuple)):
            base = path[0]
            if base in ('start menu', 'start-menu'):
                base = os.path.join(winshell.start_menu(common), 'Programs')
            elif base == 'desktop':
                base = winshell.desktop(common)
            # Add the remaining path structure
            path = os.path.join(base, *path[1:])
        elif not path:
            path = winshell.desktop(common)

        # Create any missing folders in the path structure
        if path and not os.path.exists(path):
            os.makedirs(path)

        if not target:
            target = sys.executable

        if not startin:
            # Set the start in directory to the directory of the first args if passed
            # otherwise use the target directory
            if args:
                if isinstance(args, (list, tuple)):
                    startin = os.path.dirname(args[0])
                else:
                    startin = os.path.dirname(args)
            else:
                startin = os.path.dirname(target)

        if icon_source:
            # On Windows "PROGRAMDATA" for all users, "APPDATA" for per user.
            # See: https://www.microsoft.com/en-us/wdsi/help/folder-variables
            dirname = 'PROGRAMDATA' if 1 == common else 'APPDATA'
            dirname = os.getenv(dirname)
            dirname = os.path.join(dirname, 'casement', 'icons')
            if not os.path.exists(dirname):
                os.makedirs(dirname)

            output = os.path.abspath(
                os.path.join(dirname, (icon_filename or title) + '.ico')
            )
            basename, extension = os.path.splitext(icon_source)
            ico = basename + '.ico'
            if os.path.exists(ico):
                shutil.copyfile(ico, output)
            else:
                from PIL import Image

                Image.open(icon_source).save(output)
            icon = output if os.path.exists(output) else None

        shortcut = os.path.join(path, title + '.lnk')
        # If the shortcut description is longer than 260 characters, the target may end
        # up with random unicode characters, and the icon is not set properly. The
        # Properties dialog only shows 259 characters in the description, so we limit
        # the description to 259 characters.
        description = description[:259]

        # If args is a list, convert it to a string using subprocess
        if not isinstance(args, six.string_types):
            args = subprocess.list2cmdline(args)

        kwargs = dict(
            Arguments=args,
            StartIn=startin,
            Description=description,
        )

        if icon:
            kwargs["Icon"] = (icon, 0)

        winshell.CreateShortcut(shortcut, target, **kwargs)

        if app_id:
            AppId.set_for_shortcut(shortcut, app_id)

        # Attempt to clear the windows icon cache so icon changes are displayed now
        cls.clear_icon_cache()

    @property
    def filename(self):
        """The source shortcut filename this class uses as its source."""
        return os.path.join(self.dirname, self.basename)

    def file_verbs(self):
        """Iterator of the verbs windows exposes for filename."""
        obj_shell = win32com.client.Dispatch('Shell.Application')
        folder = obj_shell.Namespace(self.dirname)
        item = folder.ParseName(self.basename)
        # It's possible that the file was removed.
        self._exists()
        for verb in item.Verbs():
            yield verb

    @classmethod
    def find_shortcuts(
        cls,
        link_name,
        mount='C:',
        paths=default_paths,
        ignored_paths=default_ignored_paths,
    ):
        """Find shortcuts with a given name in known locations.

        Each path in paths and ignored_paths will have ``{mount=mount}``
        str.formatted into it before checking for files. Mount can be used to search
        other computer file systems, but will not work for pinned items.

        Args:
            link_name (str): The name of the shortcut you want to find.
                For example: "My Shortcut.lnk" Glob strings can be used.
            mount (str, optional): The mount point str.formatted into each path
                in paths and ignored_paths. Defaults to "C:".
            paths (list, optional): A list of folder paths to search for the given
                link_name.
            ignored_paths (list, optional): A list of folder paths that should be
                ignored if any shortcuts are found in them. On windows 7 there are a few
                paths that are found when globing that don't actually exist.
        """
        # Force glob to get the correct case of the link on windows.
        # https://stackoverflow.com/a/7133137
        link_name = '{}[{}]'.format(link_name[:-1], link_name[-1])
        links = []
        ignored = []
        for path in paths:
            path = path.format(mount=mount)
            for f in glob.glob(os.path.join(path, link_name)):
                if [i for i in ignored_paths if i in f]:
                    ignored.append(f)
                    continue
                links.append(f)
        return links, ignored

    def is_pinned(self):
        """Returns if the shortcut is currently pinned to the start_menu or taskbar
        for the current user.

        Returns:
            start_menu (bool): If the shortcut is pinned to the start menu.
            taskbar (bool): If the shortcut is pinned to the taskbar.

        Raises:
            WindowsError: If no pinning verbs were found for ``self.filename``,
                this error is raised as ``errno.EPERM``.
        """
        start_menu = None
        taskbar = None
        for verb in self.file_verbs():
            name = verb.Name
            if name == 'Pin to Start Men&u':
                start_menu = False
            elif name == 'Unpin from Start Men&u':
                start_menu = True
            elif name == 'Pin to Tas&kbar':
                taskbar = False
            elif name == 'Unpin from Tas&kbar':
                taskbar = True
            if start_menu is not None and taskbar is not None:
                # Early Out: We found the info we are looking for
                break
        # If we didn't find any of the verbs, then we can't pin this shortcut.
        if start_menu is None or taskbar is None:
            msg = "Shortcut does not support pinning"
            raise WindowsError(errno.EPERM, msg, self.filename)
        return start_menu, taskbar

    def move(self, target):
        """Move this shortcut to/over the target.

        If target is a pinned shortcut for the current user, this will unpin the
        existing pinned shortcut if it exists, then pin ``self.filename`` to the
        target location. This will reset the position of the shortcut to the end
        of the pinned shortcuts. This does not remove `self.filename`.

        If target is a directory name, the copied shortcut will have the same name
        as ``self.filename``, If target is a filename, the shortcut will have the
        new filename.

        Args:
            target (str): The filename or dirname to copy the shortcut to.

        Raises:
            WindowsError: If path is a pinned location, but not for the current
                user, this error is raised as ``errno.EPERM``. Pinned paths can
                only be modified for the current user.
        """
        if not os.path.exists(self.filename):
            raise IOError('Source link does not exist: "{}"'.format(self.filename))
        self.path_in_pin_dir(self.filename)

        is_start_menu, is_taskbar = self.path_in_pin_dir(target)
        # We are copying to the user's pinned folder, don't copy the link, pin it.
        start_menu, taskbar = self.is_pinned()
        if is_start_menu:
            # If currently pinned, unpin it then re-pin it
            if start_menu:
                self.unpin_from_start_menu()
            self.pin_to_start_menu()
        elif is_taskbar:
            if taskbar:
                self.unpin_from_taskbar()
            self.pin_to_taskbar()
        else:
            # Otherwise just copy the file using the file system
            if os.path.isfile(target):
                logging.debug('Removing existing {}'.format(target))
                os.remove(target)
            logging.debug('Renaming {} -> {}'.format(self.filename, target))
            os.rename(self.filename, target)

    @classmethod
    def path_in_pin_dir(cls, path, current_user=True):
        """Check if the provided path is in a pinned directory.

        Args:
            path (str): The file to check.
            current_user (bool, optional): If True, the default, raise a
                WindowsError if the path is inside a pinned directory, but
                that directory is not for the current windows user.

        Raises:
            WindowsError: If path is a pinned location, but not for the current
                user, this error is raised as ``errno.EPERM``. Pinned paths can
                only be modified for the current user. This can be suppressed by
                passing ``False`` to the current_user argument.
        """

        def normalize(path):
            return os.path.normcase(os.path.normpath(path))

        pin_structure = os.path.join(
            'Microsoft',
            'Internet Explorer',
            'Quick Launch',
            'User Pinned',
        )
        app_data = normalize(os.path.expandvars('%APPDATA%'))
        pin_dir = normalize(
            os.path.join(
                app_data,
                pin_structure,
            )
        )
        # path could be a filename or a dirname
        norm_dir = normalize(path)
        if norm_dir.endswith('.lnk'):
            norm_dir = os.path.dirname(norm_dir)

        is_start_menu = norm_dir == os.path.join(pin_dir, 'startmenu')
        is_taskbar = norm_dir == os.path.join(pin_dir, 'taskbar')
        is_current = norm_dir.startswith(app_data)
        if current_user and pin_structure in path and not is_current:
            msg = 'Pinned paths can only be modified for the current user'
            raise WindowsError(errno.EPERM, msg, path)
        return is_start_menu, is_taskbar

    def pin_to_start_menu(self):
        """Pin to the start menu. If already pinned, nothing is done.

        Returns:
            bool: If the pin verb was found and run.
        """
        logging.debug('Pining "{}" to start menu'.format(self.basename))
        return self._run_verb('Pin to Start Men&u')

    def pin_to_taskbar(self):
        """Pin to the taskbar. If already pinned, nothing is done.

        Returns:
            bool: If the pin verb was found and run.
        """
        logging.debug('Pining "{}" to taskbar'.format(self.basename))
        return self._run_verb('Pin to Tas&kbar')

    def unpin_from_start_menu(self):
        """Un-Pin from the start menu.

        Returns:
            bool: If the pin verb was found and run.
        """
        logging.debug('Un-pining "{}" from start menu'.format(self.basename))
        return self._run_verb('Unpin from Start Men&u')

    def unpin_from_taskbar(self):
        """Un-Pin from the taskbar.

        Returns:
            bool: If the pin verb was found and run.
        """
        logging.debug('Un-pining "{}" from taskbar'.format(self.basename))
        return self._run_verb('Unpin from Tas&kbar')


class _CLI(object):
    def __init__(self, args=None):
        self._parser = None
        self._base_parser = ArgumentParser(
            description='Pretends to be git',
            usage="casement shortcut <command> [<args>]\n\n"
            "Valid commands are:\n"
            "   appid:  Manage app model id for a shortcut.\n"
            "   copy:   Copy a shortcut to a new location.\n"
            "   create: Create a shortcut on disk.\n"
            "   list:   Find all shortcuts in expected locations with a given name.\n"
            "   move:   Rename a shortcut to a given file name and path.\n"
            "   pin:    Pin the shortcut to the current user's start menu and taskbar\n"
            "   unpin:  Un-Pin the shortcut to the current user's start menu and "
            "taskbar",
        )
        self._base_parser.add_argument('command', help='Command to run')

        args = self._base_parser.parse_args(args)
        if not hasattr(self, args.command):
            self._base_parser.print_help()
            sys.exit(1)

        self.command = args.command
        # use dispatch pattern to invoke method with same name
        getattr(self, args.command)()

    def appid(self):
        """Parse copy command line arguments"""
        self.parser = ArgumentParser(
            description='View or set the app model id for a shortcut.',
            usage='casement shortcut appid [-h] [-v] source',
        )
        self.parser.add_argument('source', help='The shortcut to operate on.')
        self.parser.add_argument(
            '-s',
            '--set',
            help="Change the shortcut's app id to this.",
        )

    def copy(self):
        """Parse copy command line arguments"""
        self.parser = ArgumentParser(
            description='Copy the the shortcut to the given target. Removes the target '
            'if it already exists and is a file. If target is a pinned shortcut '
            'location, then target is un-pinned if needed and re-pinned.',
            usage='casement shortcut copy [-h] [-v] source target',
        )
        self.parser.add_argument('source', help='Full path of the shortcut to copy.')
        self.parser.add_argument(
            'target', help='Directory or filename to copy source to.'
        )

    def create(self):
        """Parse copy command line arguments"""
        self.parser = ArgumentParser(
            description='Create a shortcut at the given target.',
            usage='casement shortcut create [-h] [-v] title target source',
        )
        self.parser.add_argument('title', help='The title for the shortcut.')
        self.parser.add_argument(
            'target', help='The target for the shortcut. Defaults to sys.executable.'
        )
        self.parser.add_argument(
            'source',
            help='File path where the shortcut is created. If you start the path '
            'with "start-menu" it will be replaced with the path to the start menu. '
            'Similarly "desktop" will be replaced with the path to the desktop. '
            'Defaults to desktop.',
        )
        self.parser.add_argument(
            '--args', default="", help='Argument string to pass to target command.'
        )
        self.parser.add_argument(
            '-p',
            '--public',
            action='store_true',
            help='If using "start-menu" or "desktop" for path, create the shortcut '
            'in the public location not the user location. This may require '
            'administrative privileges.',
        )
        self.parser.add_argument(
            '--startin',
            help='Working directory the target is run from. The dirname of target '
            'is used if not provided.',
        )
        self.parser.add_argument(
            '--app-id',
            help='Set the app model id of the shortcut allowing it to be used for '
            'taskbar grouping. See casement.app_id.AppId.set_for_application.',
        )
        self.parser.add_argument(
            '--icon', help='Path to the icon the shortcut uses for its icon.'
        )
        self.parser.add_argument(
            '--icon-source',
            help='Source image path that is copied/converted. If not a .ico file, '
            'Pillow will be used to convert the image to a .ico file. The file is '
            'saved to "casement/icons" in "%%PROGRAMDATA%%" if common is 1 otherwise '
            '"%%APPDATA%%".',
        )
        self.parser.add_argument(
            '--icon-filename',
            help='The .icon filename used by --icon-source. Defaults to title.',
        )
        self.parser.add_argument(
            '--description',
            default="",
            help='Helpful description for the shortcut.',
        )

    def list(self):
        """Parse list command line arguments"""
        self.parser = ArgumentParser(
            description='Find icons for the given icon name.',
            usage='casement shortcut list [-h] [-v] name',
        )
        # prefixing the argument with -- means it's optional
        self.parser.add_argument(
            'name',
            help="A list of shortcuts with that name "
            "in known paths will be printed in this case. The --mount argument can "
            "be used to find shortcuts on other file systems.",
        )
        self.parser.add_argument(
            '-m',
            '--mount',
            default='c:',
            help='Search all paths relative to this drive letter. Lets you specify a '
            'remote share. Defaults to C:',
        )

    def move(self):
        """Parse move command line arguments"""
        self.parser = ArgumentParser(
            description='Rename the shortcut to the given target. Removes the target '
            'if it already exists and is a file. If target is a pinned shortcut '
            'location, then target is un-pinned if needed and re-pinned. See pin '
            'command for details.',
            usage='casement shortcut move [-h] [-v] source target',
        )
        self.parser.add_argument('source', help='Full path of the shortcut to move.')
        self.parser.add_argument(
            'target', help='Directory or filename to move source to.'
        )

    def pin(self):
        """Parse pin command line arguments"""
        self.parser = ArgumentParser(
            description="Pin or re-pin link to the current user's start menu or "
            "taskbar. Re-pinning does not preserver order. The current pinned "
            "status is printed if -s and -t are not passed.",
            usage='casement shortcut pin [-s] [-t] [-h] [-v] source',
        )
        self.parser.add_argument(
            'source',
            help="The full path to the shortcut. "
            "For example C:\\Users\\Public\\Desktop\\Treegrunt.lnk.",
        )
        self.parser.add_argument(
            '-s',
            '--start-menu',
            action='store_true',
            help="Update the current user's start menu.",
        )
        self.parser.add_argument(
            '-t',
            '--taskbar',
            action='store_true',
            help="Update the current user's taskbar.",
        )

    def unpin(self):
        """Parse unpin command line arguments"""
        self.parser = ArgumentParser(
            description="Un-pin link from the current user's start menu.",
            usage='casement shortcut unpin [-h] [-v] source target',
        )
        self.parser.add_argument(
            'source',
            help="The full path to the shortcut. "
            "For example C:\\Users\\Public\\Desktop\\Treegrunt.lnk.",
        )
        self.parser.add_argument(
            '-s',
            '--start-menu',
            action='store_true',
            help="Update the current user's start menu.",
        )
        self.parser.add_argument(
            '-t',
            '--taskbar',
            action='store_true',
            help="Update the current user's taskbar.",
        )

    def run(self, args):
        if args.command == 'list':
            links, ignored = Shortcut.find_shortcuts(args.name, mount=args.mount)
            if args.verbose and ignored:
                logging.debug('---- Ignored shortcuts ----')
                for link in ignored:
                    logging.debug(link)
            logging.debug('---- Found Shortcuts ----')
            for link in links:
                logging.info(link)
            return True
        elif args.command == 'appid':
            if args.set:
                AppId.set_for_shortcut(args.source, args.set)
            else:
                print(AppId.for_shortcut(args.source))
            return True
        elif args.command == 'create':
            if args.source in ("desktop", "start-menu"):
                args.source = [args.source]
            Shortcut.create(
                args.title,
                args.args,
                startin=args.startin,
                target=args.target,
                icon=args.icon,
                icon_source=args.icon_source,
                icon_filename=args.icon_filename,
                path=args.source,
                description=args.description,
                common=int(args.public),
                app_id=args.app_id,
            )
            return True

        shortcut = Shortcut(args.source)
        if args.command == 'pin':
            start_menu, taskbar = shortcut.is_pinned()
            if not (args.start_menu and args.taskbar):
                logging.info('"{}" is pinned to:'.format(args.source))
                logging.info('Start Menu: {}'.format(start_menu))
                logging.info('Taskbar: {}'.format(taskbar))
            if args.start_menu:
                if start_menu:
                    # unpin the item so it is updated by re-pinning it
                    shortcut.unpin_from_start_menu()
                shortcut.pin_to_start_menu()
            if args.taskbar:
                if taskbar:
                    # unpin the item so it is updated by re-pinning it
                    shortcut.unpin_from_taskbar()
                shortcut.pin_to_taskbar()
        elif args.command == 'unpin':
            if args.start_menu:
                shortcut.unpin_from_start_menu()
            if args.taskbar:
                shortcut.unpin_from_taskbar()
        elif args.command == 'copy':
            shortcut.copy(args.target)
        elif args.command == 'move':
            shortcut.move(args.target)
