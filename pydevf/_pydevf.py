'''
Code-formatting using API:

There are 3 modes of operation:

1. Always spawning a new java process through the call to:

format_code(code_to_format)

2. Creating the java process once and then using it for multiple calls through:

process = start_format_server()
format_code_server(process, code_to_format)
format_code_server(process, code_to_format)
stop_format_server(process)

3. Creating a python daemon process which manages a java process for multiple
calls through:

format_code_using_daemon(code_to_format)
format_code_using_daemon(code_to_format)

# Optional as the daemon is meant to be kept alive for invocations in different
# processess.
exit_daemon()
'''

from __future__ import unicode_literals

import os.path
import re
import sys
import tempfile
import threading
import traceback
import weakref

import click

from .version import __version__

click.disable_unicode_literals_warning = True

_MUTEX_NAME = 'pydev_code_formatter'

if sys.version_info[0] < 3:
    text_type = unicode  # noqa @UndefinedVariable
else:
    text_type = str

target_jar = os.path.join(os.path.dirname(__file__), 'pydev_formatter.jar')
if not os.path.exists(target_jar):
    sys.stderr.write('%s must exist.\n' % (target_jar,))
    sys.exit(1)

_process_lock = threading.Lock()
_read_lock = threading.Lock()
_write_lock = threading.Lock()

# Simple handling: start process and call format_code.

if sys.platform == 'win32':
    java_executable = 'javaw.exe'
else:
    java_executable = 'java'

debug_opts = ['-Xdebug', '-Xrunjdwp:transport=dt_socket,address=8000,server=y,suspend=n']
debug_opts = []


def _create_process(mode):
    import subprocess

    process = subprocess.Popen(
        [java_executable] + debug_opts + ['-Xverify:none', '-jar', target_jar, mode],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    if sys.platform == "win32":
        # must read streams as binary on windows
        import msvcrt
        msvcrt.setmode(process.stdout.fileno(), os.O_BINARY)
        msvcrt.setmode(process.stdin.fileno(), os.O_BINARY)
    return process


def format_code(code_to_format):
    '''
    Formats one code snippet and finishes the process.

    :param unicode|bytes code_to_format:
        The code to be formatted.
    '''
    _check_java_in_path()
    process = _create_process('-single')

    input_in_bytes = isinstance(code_to_format, bytes)

    if not input_in_bytes:
        code_to_format = code_to_format.encode(encoding='utf_8', errors='strict')

    new_contents = process.communicate(input=code_to_format)[0]
    if not input_in_bytes:
        new_contents = new_contents.decode('utf-8')

    if process.returncode != 0:
        raise RuntimeError('Unable to format. process.returncode == %s' % (
            process.returncode,))
    return new_contents


def start_daemon_server():
    debug('Code formatter daemon main_server.')
    socket_started = []

    def start_daemon_inner():
        debug('Actually initialize code formatter daemon.')
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', 0))
        # Get a port to an unused socket.
        _addr, port = sock.getsockname()
        socket_started.append(sock)
        return port

    port_mutex = PortMutex(_MUTEX_NAME, start_daemon_inner)
    sys.stdout.write(str(port_mutex.port) + '\n')
    sys.stdout.flush()
    debug('Gotten port: %s.' % (port_mutex.port,))

    if port_mutex.get_mutex_aquired():
        # If we acquired the mutex, this is the process that'll be live
        # answering the messages (other processes will just print the
        # port to be used and will exit).
        process = start_format_server()
        sock = socket_started[0]
        while True:
            sock.listen(1)
            client_sock, _addr = sock.accept()
            debug('Accepted client. Will start handling.')
            t = threading.Thread(target=_start_handling, args=(process, client_sock, port_mutex))
            t.start()
    else:
        debug('Mutex not acquired.')


def exit_daemon():
    debug('exit daemon')
    write_to_stream, _read_from_stream = _connect_to_daemon_process(create_if_not_there=False)
    if write_to_stream is None:
        return  # No deamon running
    _write(write_to_stream, 'exit daemon', [('Operation', 'exit_daemon')])


def format_code_using_daemon(code_to_format):
    '''
    :param unicode code_to_format:
    '''
    input_as_bytes = isinstance(code_to_format, bytes)
    write_to_stream, read_from_stream = _connect_to_daemon_process()

    # Ok, if gotten here the daemon process is already live and
    # answering (and sock is the socket we want to work with).
    # Ask our code to be formatted now.
    _write(write_to_stream, code_to_format, [('Operation', 'format')])
    header, body = _read(read_from_stream, decode=not input_as_bytes)
    debug('here Result from formatting: %s - %s' % (header, body))
    if 'Result' not in header:
        raise RuntimeError('Result not in header. Header:\n%s\nBody:%s\n' % (
            header, body))

    if header['Result'] != 'Ok':
        raise RuntimeError('%s\n%s' % (header, body))
    _write(write_to_stream, '', [('Operation', 'exit_client')])
    return body


def start_format_server():
    '''
    Starts a format server so that it can be reused among multiple invocations
    (uses the process stdin/stdout to communicate with it).
    '''
    _check_java_in_path()
    process = _create_process('-multiple')

    return process


def stop_format_server(process):
    '''
    Stops a given format server.
    '''
    process.kill()


def format_code_server(process, code_to_format):
    '''
    Formats code using a server previously started (which can be used
    among multiple invocations).

    :param unicode code_to_format:
        The code to be formatted.
    '''
    debug('Getting lock to format code.')
    with _process_lock:
        if process.returncode is not None:
            raise RuntimeError('Formatting server process already exited. Output: %s' % (
                process.communicate(),))

        input_as_bytes = isinstance(code_to_format, bytes)
        debug('Writing code to format to server.')
        _write(process.stdin, code_to_format)
        debug('Written code to format to server.')
        header, body = _read(process.stdout, decode=not input_as_bytes)
        debug('Read formatted code from server.')
        if header['Result'] != 'Ok':
            raise RuntimeError('%s\n%s' % (header, body))

    return body


class Null:
    """
    Gotten from: http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/68205
    License: PSF License
    Copyright: Dinu C. Gherman
    """

    def __init__(self, *args, **kwargs):
        return None

    def __call__(self, *args, **kwargs):
        return self

    def __getattr__(self, mname):
        if len(mname) > 4 and mname[:2] == '__' and mname[-2:] == '__':
            # Don't pretend to implement special method names.
            raise AttributeError(mname)
        return self

    def __setattr__(self, name, value):
        return self

    def __delattr__(self, name):
        return self

    def __repr__(self):
        return "<Null>"

    def __str__(self):
        return "Null"

    def __len__(self):
        return 0

    def __getitem__(self):
        return self

    def __setitem__(self, *args, **kwargs):
        pass

    def write(self, *args, **kwargs):
        pass

    def __nonzero__(self):
        return 0

    __bool__ = __nonzero__

    def __iter__(self):
        return iter(())

    def __enter__(self, *args, **kwargs):
        pass

    def __exit__(self, *args, **kwargs):
        pass


NULL = Null()  # Constant instance

#===================================================================================================
# Based on SystemMutex but providing a port
#===================================================================================================

'''
Based on the ServerMutex

To use, create a PortMutex, check if it was acquired (get_mutex_aquired()) and if acquired the
mutex is kept until the instance is collected or release_mutex is called.

I.e.:

mutex = PortMutex('my_unique_name')
if mutex.get_mutex_aquired():
    print('acquired')
else:
    print('not acquired')
port = mutex.port
'''


def check_valid_mutex_name(mutex_name):
    # To be windows/linux compatible we can't use non-valid filesystem names
    # (as on linux it's a file-based lock).

    regexp = re.compile(r'[\*\?"<>|/\\:]')
    result = regexp.findall(mutex_name)
    if result is not None and len(result) > 0:
        raise AssertionError('Mutex name is invalid: %s' % (mutex_name,))


if sys.platform == 'win32':

    class _PortMutex(object):

        def __init__(self, mutex_name, on_create_server):
            check_valid_mutex_name(mutex_name)
            filename = os.path.join(tempfile.gettempdir(), mutex_name)
            try:
                os.unlink(filename)
            except Exception:
                pass
            try:
                handle = os.open(filename, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                # Ok, mutex gotten (no exception raised). Go on and start the
                # server (which should return the port).
                port = on_create_server()
                os.write(handle, str(port).encode('ascii'))
                os.lseek(handle, 0, os.SEEK_SET)
                os.fsync(handle)
                self._port = port
            except Exception:
                self._release_mutex = NULL
                self._acquired = False
                # Unable to get mutex: check in which port the server is running.
                for _ in range(25):
                    import io
                    import time
                    if not os.path.exists(filename):
                        time.sleep(.1)
                        continue

                    with io.open(filename, 'rb') as stream:
                        contents = stream.read().strip()
                        try:
                            self._port = int(contents)
                        except ValueError:
                            time.sleep(.1)
                            continue
                        else:
                            break
                else:
                    raise RuntimeError(
                        'Unable to get lock and unable to get port to server running.')
            else:

                def release_mutex(*args, **kwargs):

                    # Note: can't use self here!

                    if not getattr(release_mutex, 'called', False):
                        release_mutex.called = True
                        # Clear what was written before
                        os.write(handle, b'          ')
                        os.fsync(handle)
                        try:
                            os.close(handle)
                        except Exception:
                            traceback.print_exc()
                        try:
                            # Removing is optional as we'll try to remove on startup anyways (but
                            # let's do it to keep the filesystem cleaner).
                            os.unlink(filename)
                        except Exception:
                            pass

                # Don't use __del__: this approach doesn't have as many pitfalls.
                self._ref = weakref.ref(self, release_mutex)

                self._release_mutex = release_mutex
                self._acquired = True

        def get_mutex_aquired(self):
            return self._acquired

        def release_mutex(self):
            self._release_mutex()

        @property
        def port(self):
            return self._port

else:  # Linux
    import fcntl

    class _PortMutex(object):

        def __init__(self, mutex_name, on_create_server):
            check_valid_mutex_name(mutex_name)
            filename = os.path.join(tempfile.gettempdir(), mutex_name)
            try:
                try:
                    handle = open(filename, 'rb+')
                except Exception:  # File does not exist.
                    handle = open(filename, 'wb+')
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Clear anything that may be on the file if we didn't create it
                # but still got the lock.
                handle.write(b' ' * 100)
                handle.seek(0)
                handle.flush()
                # Ok, mutex gotten (no exception raised). Go on and start the
                # server (which should return the port).
                port = on_create_server()
                handle.write(str(port).encode('ascii'))
                handle.flush()
                self._port = port

            except Exception:
                # Unable to get mutex: check in which port the server is running.
                for _ in range(25):
                    import io
                    with io.open(filename, 'rb') as stream:
                        contents = stream.read()
                        try:
                            self._port = int(contents.strip())
                            break
                        except ValueError:
                            import time
                            time.sleep(.1)
                            continue
                else:
                    raise RuntimeError(
                        'Unable to get lock and unable to get port to server running.')

                self._release_mutex = NULL
                self._acquired = False
                try:
                    handle.close()
                except Exception:
                    pass
            else:

                def release_mutex(*args, **kwargs):
                    # Note: can't use self here!
                    if not getattr(release_mutex, 'called', False):
                        release_mutex.called = True
                        # Clear data on file before releasing lock.
                        handle.seek(0)
                        handle.write(b' ' * 100)
                        handle.flush()
                        try:
                            fcntl.flock(handle, fcntl.LOCK_UN)
                        except Exception:
                            traceback.print_exc()
                        try:
                            handle.close()
                        except Exception:
                            traceback.print_exc()
                        try:
                            # Removing is pretty much optional (but let's do it to keep the
                            # filesystem cleaner).
                            os.unlink(filename)
                        except Exception:
                            pass

                # Don't use __del__: this approach doesn't have as many pitfalls.
                self._ref = weakref.ref(self, release_mutex)

                self._release_mutex = release_mutex
                self._acquired = True

        def get_mutex_aquired(self):
            return self._acquired

        def release_mutex(self):
            self._release_mutex()

        @property
        def port(self):
            return self._port


def PortMutex(*args, **kwargs):
    for i in range(3):
        try:
            # Note: in a racing condition we may throw exceptions (i.e.:
            # if process a had a mutex and process b failed but when process
            # be went to actually get the port, the mutex is released and
            # made invalid -- so, we have to retry -- which would properly
            # get the mutex this time around).
            return _PortMutex(*args, **kwargs)
        except Exception:
            if i == 2:
                raise
            continue

#===================================================================================================
# End Mutex
#===================================================================================================


#===================================================================================================
# Debug helpers
#===================================================================================================
_pid = os.getpid()
_pid_msg = '%s: ' % (_pid,)

_debug_lock = threading.Lock()

DEBUG = os.getenv('DEBUG_PYDEVF', 'False') in ('1', 'True', 'true')
DEBUG_FILE = os.path.join(os.path.dirname(__file__), '__debug_output__.txt')


def debug(msg):
    if DEBUG:
        with _debug_lock:
            _pid_prefix = _pid_msg
            if isinstance(msg, bytes):
                _pid_prefix = _pid_prefix.encode('utf-8')

                if not msg.endswith(b'\r') and not msg.endswith(b'\n'):
                    msg += b'\n'
                mode = 'a+b'
            else:
                if not msg.endswith('\r') and not msg.endswith('\n'):
                    msg += '\n'
                mode = 'a+'
            with open(DEBUG_FILE, mode) as stream:
                stream.write(_pid_prefix)
                stream.write(msg)


def debug_exception(msg=None):
    if DEBUG:
        if msg:
            debug(msg)

        with _debug_lock:
            with open(DEBUG_FILE, 'a+') as stream:
                _pid_prefix = _pid_msg
                if isinstance(msg, bytes):
                    _pid_prefix = _pid_prefix.encode('utf-8')
                stream.write(_pid_prefix)

                traceback.print_exc(file=stream)

#===================================================================================================
# End debug helpers
#===================================================================================================


def _read(stream, decode=True):
    '''
    :param file-like stream:
    :return tuple(dict,unicode):
        Returns the header and message read.
    '''
    try:
        headers = {}
        while True:
            # Interpret the http protocol headers
            line = stream.readline()  # The trailing \r\n should be there.
            if DEBUG:
                debug('Read: %s' % (line,))

            if not line:  # EOF
                return headers, None
            line = line.strip().decode('ascii')
            if not line:  # Read just a new line without any contents
                break
            try:
                name, value = line.split(': ', 1)
            except ValueError:
                raise RuntimeError('Invalid header line: {}.'.format(line))
            headers[name] = value

        if not headers:
            raise RuntimeError('Got message without headers.')

        size = int(headers['Content-Length'])
        if size == 0:
            if decode:
                body = ''
            else:
                body = b''
        else:
            # Get the actual contents to be formatted.
            body = stream.read(size)
            if decode:
                body = body.decode('utf-8')
    except Exception:
        debug_exception()
        raise
    if DEBUG:
        debug('Read: header: %s\nbody: %s' % (headers, body))
    return headers, body


def _write(stream, msg, additional_headers=None):
    '''
    Writes a message (using an http-like protocol where we write the headers
    and message content length with \r\n terminators and an empty line to
    signa that the header finished).

    :param file-like stream:
    :param unicode msg:
    :param list(tuple(unicode,unicode)) additional_headers:
    '''
    with _write_lock:
        if DEBUG:
            debug('Write: %s - additional_headers: %s' % (msg, additional_headers))

        if isinstance(msg, bytes):
            as_bytes = msg
        else:
            as_bytes = msg.encode(encoding='utf_8', errors='strict')
        header = 'Content-Length: %s\r\n' % (len(as_bytes),)
        stream.write(header.encode(encoding='utf_8', errors='strict'))
        if additional_headers:
            for header, val in additional_headers:

                header = header.replace('\r', '\\r')
                header = header.replace('\n', '\\n')

                val = val.replace('\r', '\\r')
                val = val.replace('\n', '\\n')

                stream.write(header.encode('ascii'))
                stream.write(': '.encode('ascii'))
                stream.write(val.encode('utf-8', errors='strict'))
                stream.write('\r\n'.encode('ascii'))

        stream.write('\r\n'.encode('ascii'))
        stream.flush()
        stream.write(as_bytes)
        stream.flush()


def _start_handling(process, socket, port_mutex):
    try:
        read_from_stream = socket.makefile('rb')
        write_to_stream = socket.makefile('wb')
        while True:
            debug('On receive loop.')
            header, body = _read(read_from_stream)
            debug('Received: %s - %s' % (header, body))
            if body is None:
                debug('Client exited.')
                break  # Client exited (without calling exit_client).

            operation = header['Operation']
            if operation == 'format':
                debug('Operation: Format code.')
                try:
                    formatted = format_code_server(process, body)
                except Exception:
                    debug_exception()
                    if sys.version_info[0] < 3:
                        from StringIO import StringIO
                        s = StringIO()
                    else:
                        from io import StringIO
                        s = StringIO()
                    traceback.print_exc(file=s)
                    v = s.getvalue()
                    if isinstance(v, bytes):
                        v = v.decode('utf-8', errors='replace')
                    _write(
                        write_to_stream, s.getvalue(), additional_headers=[('Result', 'Error')])
                else:
                    debug('Formatted code (returning it).')
                    _write(write_to_stream, formatted, additional_headers=[('Result', 'Ok')])

            elif operation == 'ping':
                debug('Operation: ping (answer pong).')
                _write(write_to_stream, 'pong')

            elif operation == 'exit_client':
                debug('Stop handling client.')
                break

            elif operation == 'exit_daemon':
                debug('Exit daemon.')
                stop_format_server(process)
                port_mutex.release_mutex()
                os._exit(1)
                break

            else:
                raise AssertionError('Error: unhandled operation: %s' % (operation,))
    except Exception:
        debug_exception()
        raise
    finally:
        debug('Stop handling client.')


try:
    TimeoutError
except NameError:

    class TimeoutError(Exception):  # @ReservedAssignment
        pass

_checked_java_in_path = False


def _check_java_in_path():
    global _checked_java_in_path
    if _checked_java_in_path:
        return
    path = os.environ.get('PATH')
    dirs_in_path = path.split(os.path.pathsep)
    for dir_in_path in dirs_in_path:
        if os.path.exists(os.path.join(dir_in_path, java_executable)):
            break
    else:
        raise AssertionError('Did not find %s in\n%s' % (
            java_executable, '\n'.join(dirs_in_path)))

    _checked_java_in_path = True


def _connect_to_daemon_process(attempt=0, create_if_not_there=True):
    debug('connect attempt: %s' % (attempt,))

    port_mutex = PortMutex(_MUTEX_NAME, lambda:-1)
    port_to_use = -1
    if not port_mutex.get_mutex_aquired():
        # We didn't acquire the mutex (so, it may be from a live server
        # or another temporary which returns -1).
        port_to_use = port_mutex.port
        check_java_in_path = False
    else:
        check_java_in_path = True
        # Was able to acquire mutex (which means there's no server up).
        if not create_if_not_there:
            return None, None

    # Always release the mutex here as soon as possible because this one
    # is never the 'real' daemon.
    port_mutex.release_mutex()

    if check_java_in_path:
        _check_java_in_path()

    if port_to_use == -1:
        # Release it and launch process which will keep the mutex live.
        DETACHED_PROCESS = 8
        import subprocess
        kwargs = {}
        if sys.platform == 'win32':
            kwargs['creationflags'] = DETACHED_PROCESS
        daemon_process = subprocess.Popen(
            [sys.executable, os.path.dirname(__file__), '--start-daemon'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            **kwargs
        )
        line1 = daemon_process.stdout.readline()
        try:
            port_to_use = int(line1.strip())
        except Exception:
            print(line1)
            for line in daemon_process.stdout.readlines():
                print(line)
            raise

    import socket
    import time

    # Ok, gotten the port, let's check if it's already live.
    initial_time = time.time()
    max_time = initial_time + 5

    def did_timeout():
        return time.time() > max_time

    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('127.0.0.1', port_to_use))

            # Create file-like streams.
            write_to_stream = sock.makefile('wb')
            read_from_stream = sock.makefile('rb')

            _write(write_to_stream, 'ping', additional_headers=[('Operation', 'ping')])
            debug('wait for pong...')
            header, body = _read(read_from_stream)
            if body == 'pong':
                break
            else:
                raise RuntimeError('Waiting for pong. Found: %s - %s' % (header, body))
        except Exception:
            if did_timeout():
                if attempt < 2:
                    return _connect_to_daemon_process(attempt + 1)
                raise
        else:
            if did_timeout():
                if attempt < 2:
                    return _connect_to_daemon_process(attempt + 1)
                else:
                    raise TimeoutError('Unable to start and connect to daemon.')
        time.sleep(.1)
    return write_to_stream, read_from_stream

#===================================================================================================
# Main command line handling
#===================================================================================================


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option(
    '--include',
    type=str,
    default='*.py, *.pyw',
    help='fnmatch-style files to include (comma separated).',
    show_default=True,
)
@click.option(
    '--exclude-dirs',
    type=str,
    default='*.git, *.hg, *.svn',
    help='fnmatch-style dirs to exclude (comma separated).',
    show_default=True,
)
@click.option(
    '--no-daemon',
    help='Do not automatically start a daemon service to be used among multiple processes.',
    default=False,
    is_flag=True,
)
@click.option(
    '--start-daemon',
    help='Starts daemon service to be used among multiple processes.',
    default=False,
    is_flag=True,
)
@click.option(
    '--stop-daemon',
    help='Stops a daemon service previously started in another process.',
    default=False,
    is_flag=True,
)
@click.option(
    '-v',
    '--verbose',
    is_flag=True,
    help='Enable verbose mode.',
)
@click.version_option(version=__version__)
@click.argument(
    'source',
    nargs=-1,
    type=click.Path(
        exists=True, file_okay=True, dir_okay=True, readable=True, allow_dash=True
    ),
    is_eager=True,
)
@click.pass_context
def main(
        ctx, include='*.py', exclude_dirs=None, verbose=False, source=None, no_daemon=False,
        start_daemon=False, stop_daemon=False
    ):
    from functools import partial
    import fnmatch

    out = partial(click.secho, bold=True, err=True)
    err = partial(click.secho, fg='red', err=True)

    include = include.strip()
    if include:
        include = [x.strip() for x in include.split(',')]

    exclude_dirs = exclude_dirs.strip()
    if exclude_dirs:
        exclude_dirs = [x.strip() for x in exclude_dirs.split(',')]

    def include_file(filename):
        if not include:
            return True
        for pat in include:
            if fnmatch.fnmatch(filename, pat):
                return True
        return False

    def exclude_directory(filename):
        if not exclude_dirs:
            return False
        for pat in exclude_dirs:
            if fnmatch.fnmatch(filename, pat):
                return True
        return False

    if start_daemon:
        start_daemon_server()
        ctx.exit(0)

    if stop_daemon:
        exit_daemon()
        out('Daemon process stopped.')
        ctx.exit(0)

    if not source:
        out('No files to format. Nothing to do.')
        ctx.exit(0)

    def on_finish():
        pass

    try:
        if no_daemon:
            process = start_format_server()
            do_format = lambda code_to_format: format_code_server(process, code_to_format)

            def on_finish():
                stop_format_server(process)

        else:
            do_format = format_code_using_daemon

        if source == ('-',):
            if sys.version_info[0] > 2:
                read_from = sys.stdin.buffer
                write_to = sys.stdout.buffer
            else:
                if sys.platform == "win32":
                    # must read streams as binary on windows
                    import msvcrt
                    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
                    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)

                read_from = sys.stdin
                write_to = sys.stdout

            contents_as_bytes = read_from.read()
            try:
                output = do_format(contents_as_bytes)
            except Exception as e:
                err('Error formatting contents: %s' % (str(e)))
                ctx.exit(1)
            else:
                write_to.write(output)
                write_to.flush()
            ctx.exit(0)

        else:
            format_files = []
            for entry in source:
                if os.path.isfile(entry):
                    format_files.append(entry)
                else:
                    for root, dirs, files in os.walk(entry):
                        for filename in files:
                            if include_file(os.path.basename(filename)):
                                format_files.append(os.path.join(root, filename))

                        new_dirs = []
                        for directory in dirs:
                            if not exclude_directory(os.path.basename(directory)):
                                new_dirs.append(directory)
                        dirs[:] = new_dirs[:]

            total = len(format_files)
            for i, entry in enumerate(format_files):
                if verbose:
                    out('Format file: %s (%s of %s)' % (entry, i + 1, total))
                with open(entry, 'rb') as stream:
                    contents = stream.read()

                new_contents = do_format(contents)
                with open(entry, 'wb') as stream:
                    stream.write(new_contents)

            ctx.exit(0)

    finally:
        on_finish()


if __name__ == '__main__':
    main()
