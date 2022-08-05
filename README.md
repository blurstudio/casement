# Casement

A Python library that provides useful functionality for managing Microsoft Windows systems.

## Features

* App Model Id management for shortcuts and inside python applications to allow for taskbar grouping.
* Finding, creating and moving shortcuts.
* Pinning shortcuts to the taskbar and start menu.
* Flashing a window to get a users attention.

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

# Installing

Casement can be installed by the standard pip command `pip install casement`.
There is also an optional extras_require option `pip install casement[pil]` to
allow creating shortcut icons by converting image files to .ico files.
