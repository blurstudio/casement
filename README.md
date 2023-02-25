# Casement

A Python library that provides useful functionality for managing Microsoft Windows systems.

## Features

* App Model Id management for shortcuts and inside python applications to allow for taskbar grouping.
* Finding, creating and moving shortcuts.
* Pinning shortcuts to the taskbar and start menu.
* Flashing a window to get a users attention.
* Windows Registry reading and modification.
* Windows environment variable interface via registry allowing for permanent modification.

## Shortcut management

A interface for manipulating Windows shortcut files including pinned.

Pinning shortcuts to the start menu and task bar in windows is extremely complicated.
You can find and edit shortcuts in the User Pinned directory for for all users, but
adding, modifying or removing those shortcuts does not affect the pinned shortcuts.
You need to point to a copy of the pinned shortcut, and run windows verbs on that
shortcut.

Here is a example of pinning a shortcut to the start menu:
```python
from casement.shortcut import Shortcut
with Shortcut(r'C:\Users\Public\Desktop\My Shortcut.lnk') as sc:
    sc.pin_to_start_menu()
```
### Command line interface

The features of this class can be used from the command line using ``casement shortcut
[command] [arguments]``.

To find shortcuts in common places with a given name:
```
    C:\blur\dev\casement>casement shortcut list "VLC media player.lnk"
    c:\ProgramData\Microsoft\Windows\Start Menu\Programs\VideoLAN\VLC media player.lnk
    c:\Users\Public\Desktop\VLC media player.lnk
```

Pinning/unpinning a shortcut to the taskbar:
```
    C:\blur\dev\casement>casement shortcut pin "C:\Users\Public\Desktop\My Shortcut.lnk" -t
    C:\blur\dev\casement>casement shortcut unpin "C:\Users\Public\Desktop\My Shortcut.lnk" -t
```

# Environment Variables

Access and modify environment variables stored in the registry using
`casement.env_var.EnvVar`. This lets you access the raw un-expanded file registry
values unlike what you see with os.environ. You can permanently modify the
environment variables for the system.
```python
from casement.env_var import EnvVar

user_env = EnvVar(system=False)
user_env['VARIABLE_A'] = 'C:\\PROGRA~1'
expanded = user_env.normalize_path(user_env['VARIABLE_A'], tilde=False)
assert expanded == 'C:\\Program Files'
if 'VARIABLE_A' in user_env:
    del user_env['VARIABLE_A']
```

# Windows Registry

Read and modify registry keys with `casement.registry.RegKey`.
```py
from casement.registry import RegKey

reg = RegKey('HKLM', 'Software\\Autodesk\\Maya')
for ver in reg.child_names():
    # Attempt to access a specific sub-key that exists if ver is an version key
    child = reg.child('{}\\Setup\\InstallPath'.format(ver))
    if child.exists():
        print(ver, child.entry('MAYA_INSTALL_LOCATION').value())
```

There is a map of common registry locations like environment variables and classes.

```python
from casement.registry import RegKey, REG_LOCATIONS

# Access to the user and system keys driving `HKEY_CLASSES_ROOT`
classes_system = RegKey(*REG_LOCATIONS['system']['classes'])
classes_user = RegKey(*REG_LOCATIONS['user']['classes'])

# Access to the user and system key controlling persistent Environment Variables
env_var_system = RegKey(*REG_LOCATIONS['system']['env_var'])
env_var_user = RegKey(*REG_LOCATIONS['user']['env_var'])

# Uninstall key for "Add/Remove Programs"
uninstall_system = RegKey(*REG_LOCATIONS['system']['uninstall'])
```

# Installing

Casement can be installed by the standard pip command `pip install casement`.
There is also an optional extras_require option `pip install casement[pil]` to
allow creating shortcut icons by converting image files to .ico files.
