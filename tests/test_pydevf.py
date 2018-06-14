# coding: utf-8
from __future__ import unicode_literals

import os
import pytest
import subprocess
import sys


class _Result(object):

    def __init__(self, exit_code, output, output_bytes):
        self.exit_code = exit_code
        self.output = output
        assert isinstance(output_bytes, bytes)
        self.output_bytes = output_bytes


class _Runner(object):

    def invoke(self, args=[], input=None):
        import pydevf
        process = subprocess.Popen(
            [sys.executable, pydevf.__file__] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        if input is not None and not isinstance(input, bytes):
            input = input.encode('utf-8')
        stdout, _ = process.communicate(input=input)
        return _Result(process.returncode, stdout.decode('utf-8'), stdout)


@pytest.fixture
def runner():
    return _Runner()


@pytest.fixture
def subdir(tmpdir):
    return tmpdir.mkdir("sub")


@pytest.fixture
def hello_file(subdir):
    p = subdir.join("hello.py")
    p.write("call_it(a,b)")
    return p


@pytest.fixture(params=[
        [],
        ['--no-daemon'],
    ], scope='session')
def mode(request):
    return request.param


@pytest.fixture(scope='session', autouse=True)
def teardown_daemon():
    yield
    import pydevf
    pydevf.exit_daemon()


def check_result(result, output=None, exit_code=0):
    if result.exit_code != exit_code:
        raise AssertionError('Expected exit code: %s. Found: %s.\nOutput: %s.' % (
            exit_code, result.exit_code, result.output))

    if output is not None:
        if isinstance(output, bytes):
            assert output == result.output_bytes
        else:
            assert output in result.output, '%s not in %s' % (output, result.output)


def test_command_line_basic(runner):
    result = runner.invoke()
    check_result(result, 'Nothing to do.')

    result = runner.invoke(['--help'])
    check_result(result, 'fnmatch-style')


def test_command_line_input(runner, mode):
    result = runner.invoke(args=['-'] + mode, input='call(a,b)')
    check_result(result, b'call(a, b)' + os.linesep.encode('ascii'))


def test_command_line_input_error(runner, mode):
    result = runner.invoke(args=['-'] + mode, input='call(a,b')
    check_result(result, exit_code=1)


def test_command_line_file(hello_file, runner, mode):
    result = runner.invoke(args=[str(hello_file)] + mode)
    check_result(result, output='')
    assert hello_file.read('rb') == b"call_it(a, b)" + os.linesep.encode('ascii')


def test_command_line_dir(subdir, hello_file, runner, mode):
    result = runner.invoke(args=[str(subdir)] + mode)
    check_result(result, output='')
    assert hello_file.read('rb') == b"call_it(a, b)" + os.linesep.encode('ascii')
