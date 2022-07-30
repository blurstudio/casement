""" Enables support for calling the casement cli using `python -m casement`
"""

from __future__ import absolute_import

import sys
import casement.cli

if __name__ == '__main__':
    # TODO: move casement cli to click
    # prog_name prevents __main__.py from being shown as the command name in the help
    # text. We don't know the exact command the user passed so we provide a generic
    # `python -m casement` command.
    # sys.exit(casement.cli.main(prog_name="python -m casement"))
    sys.exit(casement.cli.main())
