from __future__ import unicode_literals

code1 = '''
class A( object ):
    def method(self,a,b,c):
        pass
'''

code1_expected = '''

class A(object):

    def method(self, a, b, c):
        pass
'''

code_error = '''
class A( object ):
    def method(self:
        pass
'''


def test_code_format():
    from pydevf import format_code
    new_contents = format_code(code1)
    assert (repr(new_contents)) == repr(code1_expected)


def test_code_format_error():
    import pytest
    from pydevf import format_code

    with pytest.raises(RuntimeError):
        format_code(code_error)


def test_format_multiple():
    import pytest
    from pydevf import start_format_server
    from pydevf import format_code_server
    from pydevf import stop_format_server

    process = start_format_server()

    for _ in range(3):
        new_contents = format_code_server(process, code1)
        assert (repr(new_contents)) == repr(code1_expected)

        with pytest.raises(RuntimeError):
            format_code_server(process, code_error)

    stop_format_server(process)


def test_format_daemon():
    import os.path
    import pydevf
    from pydevf import exit_daemon
    from pydevf import format_code_using_daemon
    pydevf.DEBUG_FILE = os.path.join(os.path.dirname(__file__), '__debug_test_output__.txt')
    import pytest
    for i in range(5):
        if i == 3:
            exit_daemon()
            # Give it some time to finish before starting another one.
            import time
            time.sleep(1)
        assert format_code_using_daemon(code1) == code1_expected

        with pytest.raises(RuntimeError):
            format_code_using_daemon(code_error)
