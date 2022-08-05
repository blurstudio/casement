import sys
import logging
import importlib
from argparse import ArgumentParser


class CasementParser(object):
    '''
    To implement a cli for casement, create a submodule with the name of your
    cli command. For example to add a ``casement test echo`` command, you would
    create casement\test.py with the following code::

        import argparse
        from argparse import ArgumentParser

        class _CLI(object):
            def __init__(self, args):
                # Parse the command and create the parser casement will use
                parser = ArgumentParser()
                parser.add_argument('command')
                args = parser.parse_args(args)
                # This will be added to args passed to the run command
                self.command = args.command
                # Create self.parser by calling the requested function
                getattr(self, args.command)()

            def echo(self):
                """Creates a ArgumentParser to handle the echo command as self.parser"""
                self.parser = ArgumentParser(
                    usage='casement shortcut test [-h] [-v] text',
                )
                self.parser.add_argument('text', nargs=argparse.REMAINDER)

            def run(self, args):
                """Do something with the arguments parsed from self.parser"""
                if args.command == 'echo':
                    print('ECHO: {}'.format(' '.join(args.text)))
    '''

    def __init__(self):
        self.target_cli = None
        self._base_parser = ArgumentParser(
            description='Windows management tool',
            usage="casement <command> [<args>]\n\n"
            "Valid commands are:\n"
            "    shortcut or sc: Manage windows shortcuts.",
        )
        self._base_parser.add_argument('command', help='Command to run')
        args = self._base_parser.parse_args(sys.argv[1:2])

        # Convert short command names to full command names
        short_names = {
            'sc': 'shortcut',
        }
        self.command = short_names.get(args.command, args.command)
        # use dispatch pattern to invoke method with same name
        try:
            module = importlib.import_module(
                '.{}'.format(self.command), package='casement'
            )
        except ImportError:
            self._base_parser.print_help()
            sys.exit(1)
        # parse_args defaults to [1:] for args, but we need to remove
        # the 2 levels of commands for proper validation
        self.args_list = sys.argv[3:]

        self.target_cli = module._CLI(sys.argv[2:3])
        for action in self.target_cli.parser._actions:
            if action.dest == 'verbose':
                break
        else:
            self.target_cli.parser.add_argument(
                '-v', '--verbose', action='store_true', help='Give more output.'
            )

    def parse_args(self):
        """Parse sub-command arguments adding global options."""
        args = self.target_cli.parser.parse_args(self.args_list)
        # Add command to the args from the target_cli
        try:
            args.command = self.target_cli.command
        except AttributeError:
            args.command = None
        return args


def main():
    casement = CasementParser()
    args = casement.parse_args()
    logging.basicConfig(
        format='%(message)s', level=logging.DEBUG if args.verbose else logging.INFO
    )

    casement.target_cli.run(args)
