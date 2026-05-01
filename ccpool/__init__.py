"""ccpool — smart Claude Max account rotation.

Public surface:
    ccpool.cli:main          — entrypoint
    ccpool._version          — __version__

Library use is supported but not the primary path; most consumers should call
`ccpool <subcommand>` from the shell.
"""
from ccpool._version import __version__

__all__ = ["__version__"]
