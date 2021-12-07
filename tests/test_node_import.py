"""
"""

import json
import os.path
import shutil
import unittest
from io import StringIO
from unittest.mock import patch

import six

from js2py.node_import import *

BASE_DIR = os.path.dirname(__file__)


class TestJs2Py(unittest.TestCase):
    def setUp(self):
        self.dirname = os.path.join(BASE_DIR, 'temp')
        if os.path.exists(self.dirname):
            shutil.rmtree(self.dirname)
        os.makedirs(self.dirname)
        with open(os.path.join(self.dirname, 'package.json'), 'w') as fobj:
            fobj.write('{}')
        self.py_dir = os.path.abspath(os.path.join(BASE_DIR, '../js2py/py_node_modules'))

    def test_run_cmd(self):
        code, output = run_cmd(f'node -p "require().version"')
        self.assertEqual(code, 1)
        code, output = run_cmd(f'echo 123')
        self.assertEqual(code, 0)
        self.assertEqual(output, '123\n')

    def test_node_extensions(self):
        package = 'crypto-js'
        with self.assertRaises(NotImplementedError) as cm:
            version = get_module_version(package, self.dirname)
        self.assertEqual(cm.exception.args[0], f'Cannot find module "crypto-js" in working directory {self.dirname}, '
                                               'please install or link this Node.js package first.')
        # install when the package is not installed
        output = install_if_necessary(package, self.dirname)
        self.assertNotEqual(output, '')
        self.assertTrue(os.path.exists(os.path.join(self.dirname, 'node_modules', package)))
        module_dir = get_module_dir(package, self.dirname)
        module_version = get_module_version(package, self.dirname)
        self.assertEqual(module_dir, os.path.join(self.dirname, 'node_modules', package))
        self.assertEqual(module_version, '4.1.1')
        # will do nothing if its installed
        output = install_if_necessary(package, self.dirname)
        self.assertEqual(output, '')
        # if the version is not the same, will install
        package = 'crypto-js@3.1.9-1'
        with self.assertRaises(NotImplementedError) as cm:
            module_dir = get_module_dir(package, self.dirname)
        self.assertEqual(cm.exception.args[0],
                         f'Module "crypto-js" is installed, but the installed version 4.1.1 is '
                         f'not consistent with the required version 3.1.9-1. Please install or link '
                         f'the right version first.')
        output = install_if_necessary(package, self.dirname)
        self.assertNotEqual(output, '')
        self.assertTrue(os.path.exists(os.path.join(self.dirname, 'node_modules/crypto-js')))
        module_dir = get_module_dir(package, self.dirname)
        module_version = get_module_version(package, self.dirname)
        self.assertEqual(module_dir, os.path.join(self.dirname, 'node_modules/crypto-js'))
        self.assertEqual(module_version, '3.1.9-1')

    def test_get_module_py_path(self):
        self.assertEqual(get_module_py_path('ab-c'), os.path.join(self.py_dir, 'ab_c.py'))
        self.assertEqual(get_module_py_path('ab-c@1.0.0'), os.path.join(self.py_dir, 'ab_c.py'))
        self.assertEqual(get_module_py_path('@scop-e/ab-c@1.0.0'), os.path.join(self.py_dir, '@scop_e/ab_c.py'))

    def check_translate_output(self, output):
        lines = output.getvalue().strip().split('\n')
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith('Bundled JS library dumped at: '))
        self.assertEqual(lines[1], 'Please wait, translating...')

    def test_translate_npm_module(self):
        package = 'crypto-js@3.1.9-1'
        package_path = os.path.join(self.py_dir, 'crypto_js.py')
        if os.path.exists(package_path):
            os.remove(package_path)
        # if not installed
        with self.assertRaises(NotImplementedError) as cm:
            translate_npm_module(package, cwd=self.dirname)
        self.assertEqual(cm.exception.args[0],
                         f'Cannot find module "crypto-js" in working directory {self.dirname}, '
                         'please install or link this Node.js package first.')
        install_if_necessary(package, self.dirname)
        with patch('sys.stdout', new=StringIO()) as output:
            translate_npm_module(package, False, cwd=self.dirname)
        self.assertTrue(os.path.exists(package_path))
        self.check_translate_output(output)
        if os.path.exists(package_path):
            os.remove(package_path)
        with patch('sys.stdout', new=StringIO()) as output:
            translate_npm_module(package, True, cwd=self.dirname)
        self.assertTrue(os.path.exists(package_path))
        self.check_translate_output(output)

    def test_require(self):
        def test_module(CryptoJS):
            data = [{'id': 1}, {'id': 2}]
            ciphertext = CryptoJS.AES.encrypt(json.dumps(data), 'secret key 123')
            bytes = CryptoJS.AES.decrypt(ciphertext.toString(), 'secret key 123')
            decryptedData = json.loads(bytes.toString(CryptoJS.enc.Utf8))
            self.assertListEqual(data, decryptedData)

        package = 'crypto-js'
        package_v = 'crypto-js@3.1.9-1'
        python_path = os.path.join(self.py_dir, 'crypto_js.py')
        if os.path.exists(python_path):
            os.remove(python_path)

        # Python module not exist, re-translate - JS package not installed, raise error
        with self.assertRaises(NotImplementedError) as cm:
            get_module_py_version(package_v)
        self.assertEqual(cm.exception.args[0],
                         f'The python module of "crypto-js" does not exist!')
        with self.assertRaises(NotImplementedError) as cm2:
            with self.assertLogs(level='WARNING') as cm:
                require(package_v, cwd=self.dirname)
        self.assertEqual(len(cm.records), 1)
        self.assertEqual(cm.records[0].message,
                         f'The python module of "crypto-js" does not exist!')
        self.assertEqual(cm2.exception.args[0], f'Cannot find module "crypto-js" in working directory {self.dirname}, '
                                                'please install or link this Node.js package first.')

        # Python module not exist, re-translate - JS package installed, version wrong
        install_if_necessary(package, self.dirname)
        with self.assertRaises(NotImplementedError) as cm2:
            with self.assertLogs(level='WARNING') as cm:
                require(package_v, cwd=self.dirname)
        self.assertEqual(len(cm.records), 1)
        self.assertEqual(cm.records[0].message,
                         f'The python module of "crypto-js" does not exist!')
        self.assertEqual(cm2.exception.args[0],
                         f'Module "crypto-js" is installed, but the installed version 4.1.1 is '
                         f'not consistent with the required version 3.1.9-1. Please install or link '
                         f'the right version first.')

        # Python module not exist, re-translate - JS package correctly installed
        with patch('sys.stdout', new=StringIO()) as output:
            with self.assertLogs(level='WARNING') as cm:
                require(package, cwd=self.dirname)
        self.assertEqual(len(cm.records), 1)
        self.assertEqual(cm.records[0].message,
                         f'The python module of "crypto-js" does not exist!')
        self.assertTrue(os.path.exists(python_path))
        self.check_translate_output(output)

        # Python module version wrong, re-translate
        install_if_necessary(package_v, self.dirname)
        with patch('sys.stdout', new=StringIO()) as output:
            with self.assertLogs(level='WARNING') as cm:
                CryptoJS = require(package_v, cwd=self.dirname)
        self.assertEqual(len(cm.records), 1)
        self.assertEqual(cm.records[0].message,
                         f'The python module of "crypto-js" is installed, but the version "4.1.1" is not '
                         f'consistent with the required version "3.1.9-1".')
        self.assertTrue(os.path.exists(python_path))
        self.check_translate_output(output)
        self.assertEqual(get_module_py_version(package), '3.1.9-1')
        test_module(CryptoJS)

        # Python module header wrong, re-translate
        with open(python_path, 'wb') as fobj:
            content = f"# version: 3.1.9-1\n123456"
            fobj.write(content.encode('utf-8') if six.PY3 else content)
        with patch('sys.stdout', new=StringIO()) as output:
            with self.assertLogs(level='WARNING') as cm:
                CryptoJS = require(package_v, cwd=self.dirname)
        self.assertEqual(len(cm.records), 1)
        self.assertEqual(cm.records[0].message,
                         f'The python module of "{package_v}" is installed, but there is something wrong with '
                         f'the header. Re-translation is needed.')
        self.assertTrue(os.path.exists(python_path))
        self.check_translate_output(output)
        test_module(CryptoJS)

        # All things right, no re-translate
        with patch('sys.stdout', new=StringIO()) as output:
            CryptoJS = require(package_v, cwd=self.dirname)
        self.assertEqual(output.getvalue(), '')
        self.assertTrue(os.path.exists(python_path))
        test_module(CryptoJS)
        if os.path.exists(python_path):
            os.remove(python_path)

    def tearDown(self):
        if os.path.exists(self.dirname):
            shutil.rmtree(self.dirname)
