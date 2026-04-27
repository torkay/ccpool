"""cmaxctl — smart Claude Max account rotation.

Public surface:
    cmaxctl.cli:main          — entrypoint
    cmaxctl._version          — __version__

Library use is supported but not the primary path; most consumers should call
`cmax <subcommand>` from the shell.
"""
from cmaxctl._version import __version__

__all__ = ["__version__"]
