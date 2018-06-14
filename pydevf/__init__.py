from pydevf.version import __version__

__author__ = """Fabio Zadrozny"""
__email__ = 'fabiofz@gmail.com'

from pydevf._pydevf import (
    main,
    
    format_code,
    
    start_format_server,
    stop_format_server,
    format_code_server,
    
    start_daemon_server,
    format_code_using_daemon,
    exit_daemon,
)

if __name__ == '__main__':
    main()