#!/usr/bin/env python3

########################################################################
# Copyright (c) 2013 Joe Kopena <tjkopena@gmail.com>,
#                    Tom Wambold <tom5760@gmail.com>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
########################################################################

import os.path
import sys
import xml.etree.ElementTree as ET

from collections import defaultdict
from subprocess import Popen, PIPE, STDOUT

def error(*args, **kwargs):
    'Simpler print to stderr.'
    if 'file' not in kwargs:
        kwargs['file'] = sys.stderr
    print('ERROR:', *args, **kwargs)

class TestScript:
    def __init__(self):
        self.title = '<unknown>'
        self.author = '<unknown>'

        self.tests = []

    def execute(self):
        numFailures = 0

        for count, test in enumerate(self.tests, start=1):
            print('\n########################################################################')
            print('Test {}: {}'.format(count, test.id))
            print('Description:', test.description)
            print('Commmand:\n ', test.command)

            if test.execute():
                print('Status: PASSED')
            else:
                print('Status: FAILED')
                numFailures += 1

        print('\n########################################################################')
        if numFailures > 0:
            print('Some tests failed.')
        else:
            print('All tests passed.')

        return numFailures

class Test:
    def __init__(self):
        self.id = '<unknown>'
        self.description = ''
        self.command = None
        self.input = None

        self.pass_conditions = []
        self.fail_conditions = []

        # Set with a property
        self._expected = True

    @property
    def expected(self):
        return self._expected

    @expected.setter
    def expected(self, value):
        if isinstance(value, bool):
            self._expected = value
        elif value == 'fail':
            self._expected = False
        elif value == 'pass':
            self._expected = True
        else:
            raise SyntaxError('Unknown "expected" value "{}"'.format(value))

    def execute(self):
        passed = True

        # Command is intentionally run without checking to see if there
        # actually are any accept/fail conditions, so you can cheat and
        # have a dummy test to do any setup or teardown.  - tjkopena
        p = Popen([self.command], shell=True, stdout=PIPE, stdin=PIPE,
                universal_newlines=True)

        output = p.communicate(self.input)[0]
        print('Output:\n', output)
        print('Return code:', p.returncode)

        # Eventually there should be a map from tags to condition
        # functions.  The acceptance and failure batteries will just run
        # through the child notes and apply the appropriate function,
        # negating the result for the failure battery.  For
        # now... Hardcode!  - tjkopena

        #-- Run through battery of acceptance conditions
        for condition in self.pass_conditions:
            if not condition.check(p.returncode, output):
                if self.expected:
                    print('FAILED:', condition.error(p.returncode, output))
                passed = False

        #-- Run through battery of failure conditions
        for condition in self.fail_conditions:
            if condition.check(p.returncode, output):
                passed = False
            elif not self.expected:
                print('FAILED:', condition.error(p.returncode, output))

        return passed == self.expected

class TestCondition:
    def __init__(self):
        self.contains = None

        self._return_code = None

    @property
    def return_code(self):
        return self._return_code

    @return_code.setter
    def return_code(self, value):
        self._return_code = int(value)

    def check(self, return_code, output):
        if self.return_code is not None:
            return self.check_return_code(return_code)
        elif self.contains is not None:
            return self.check_contains(output)
        else:
            return False

    def check_return_code(self, value):
        return self.return_code == value

    def check_contains(self, value):
        return self.contains in value

    def error(self, return_code, output):
        if self.return_code is not None:
            return 'Return code {} != {}'.format(return_code, self.return_code)
        elif self.contains is not None:
            return 'Output does not contain ' + self.contains
        else:
            return '<unknown>'

def parse_xml_test(path):
    script = TestScript()

    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as e:
        error('Parse error on script {}: {}'.format(testScript, e))
        raise

    script.title = root.findtext('title', '<unknown>')
    script.author = root.findtext('author', '<unknown>')

    for t in root.findall('test'):
        test = Test()
        test.id = t.get('id', '<unknown>')
        test.description = t.findtext('description', '')
        test.expected = t.get('expected', True)
        test.input = t.findtext('input')

        test.command = t.findtext('command')
        if test.command is None:
            raise SyntaxError('Test {} has no command!'.format(test.id))

        test.pass_conditions.extend(parse_xml_conditions(t, 'pass'))
        test.fail_conditions.extend(parse_xml_conditions(t, 'fail'))

        script.tests.append(test)

    return script

def parse_xml_conditions(t, tag):
    conds = t.find(tag)
    if conds is None:
        return

    for c in conds:
        if c.text is None:
            error('Empty condition block in {}, skipping...'.format(test.id))
            continue

        condition = TestCondition()
        if c.tag == 'returncode':
            condition.return_code = c.text
        elif c.tag == 'contains':
            condition.contains = c.text
        else:
            raise SyntaxError('Unknown condition:', condition.tag)

        yield condition

def main(argv):
    if len(argv) == 0:
        error('Must provide test script filename.')
        return 1

    testScript = argv[0]

    if not os.path.isfile(testScript):
        error('Test script {} does not exist.'.format(testScript))
        return 1

    try:
        if testScript.endswith('.xml'):
            script = parse_xml_test(testScript)
        else:
            error('Unknown test filetype')
            return 1
    except:
        error('Error parsing script')
        raise

    print('beltsander executing {}: {} - {}'.format(
        testScript, script.title, script.author))

    return script.execute()

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
