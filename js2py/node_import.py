"""Some extensions calling Node.js command by the shell command, and some extensions that could translate the Node.js
packages into python.
"""

import codecs
import hashlib
import logging
import os
import random
import subprocess
from shutil import rmtree

import six

from js2py.evaljs import translate_js, DEFAULT_HEADER
from js2py.translators.friendly_nodes import is_valid_py_name

__all__ = [
    'run_cmd',
    'get_module_dir',
    'get_module_version',
    'install_if_necessary',
    'get_module_py_path',
    'get_module_py_version',
    'translate_npm_module',
    'require'
]

DEPENDENCY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'node_dependencies')
PY_MODULE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'py_node_modules')

logger = logging.getLogger('JS Translator')


# ======================================= Node.js EXTENSIONS ===================================

def run_cmd(cmd, **kwargs):
    """Run shell command.

    Args:
        cmd (str): the command
        kwargs (dict): arguments to ``subprocess.check_output``

    Returns:
        2-tuple: ``(status_code, output)``. The former is a status code, 0 means no error occurs.
                 The latter is the output in string.
    """
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, **kwargs)
    out, err = p.communicate()
    if p.returncode == 0:
        return 0, out.decode('utf-8')
    return p.returncode, err.decode('utf-8')


def delete_path(path):
    """Delete whatever at the path if it exists. If it's a file, remove it and it's index file.
    If it's a directory, remove the whole directory.

    Args:
        path (str): the path
    """
    if os.path.exists(path):
        if os.path.isdir(path):
            rmtree(path)
        else:
            os.remove(path)


def _split_name_version(module_name):
    """Split package name and version.

    Args:
        module_name (str): the module name, ``(<@scope>/)<pkg_name>(@version)``

    Returns:

    """
    paths = module_name.split('@')
    if (len(paths) == 2 and paths[0] != '') or len(paths) == 3:
        return '@'.join(paths[:-1]), paths[-1]
    return module_name, ''


def get_module_version(module_name, cwd='.'):
    """Get the version of an installed Node.js module.

    Args:
        module_name (str): the module name, ``(<@scope>/)<pkg_name>(@version)``. The required version given here makes
                           no difference.
        cwd (str, optional): the directory to run the ``node`` command.

    Returns:
        str: the module version. If the module is not installed, raise ``NotImplementedError``.
    """
    pkg_name, _ = _split_name_version(module_name)
    status, module_version = run_cmd(f'cd {cwd};node -p "require(\'{pkg_name}/package.json\').version"')
    if status != 0:
        raise NotImplementedError(f'Cannot find module "{pkg_name}" in working directory {cwd}, '
                                  f'please install or link this Node.js package first.')
    return module_version.strip()


def get_module_dir(module_name, cwd='.'):
    """Get the directory of an installed Node.js module

    Args:
        module_name (str): the module name, ``(<@scope>/)<pkg_name>(@version)``.
        cwd (str, optional): the directory to run the ``node`` command.

    Returns:
        str: the module path. If the module is not installed or the installed version is not the same as the required
             version, raise ``NotImplementedError``.
    """
    install_version = get_module_version(module_name, cwd)
    pkg_name, require_version = _split_name_version(module_name)
    if require_version != '' and install_version != require_version:
        raise NotImplementedError(f'Module "{pkg_name}" is installed, but the installed version {install_version} is '
                                  f'not consistent with the required version {require_version}. Please install or link '
                                  f'the right version first.')
    status, module_index = run_cmd(f'cd {cwd};node -p "require.resolve(\'{pkg_name}\')"')
    module_path, _ = os.path.split(module_index)
    return module_path


def install_if_necessary(package, working_dir='.'):
    """Install a Node.js package if it's not installed

    Args:
        package (str): package name. If the package name is like ``<pkg_name>@<version>``, it would check the current
                       version installed and install the required version when the installed version is not consistent.
        working_dir (str, optional): the working directory

    Returns:
        str: the output of the ``npm install`` command if succeed.
    """
    try:
        _ = get_module_dir(package, working_dir)
    except NotImplementedError as e:
        cmd = f'cd {working_dir}; npm install {package}'
        code, output = run_cmd(cmd, cwd=working_dir)
        assert code == 0, f'Could not link required node_modules: {package}. Error message: {output}'
        return output
    return ''


# ======================================= JS2PY EXTENSIONS ===================================

def _init():
    """Install dependencies for JS interpreting"""
    if not os.path.exists(DEPENDENCY_PATH):
        os.makedirs(DEPENDENCY_PATH)
    assert subprocess.call(
        'node -v >/dev/null 2>&1', shell=True, cwd=DEPENDENCY_PATH
    ) == 0, 'You must have node installed! run: brew install node'
    package_json_path = os.path.join(DEPENDENCY_PATH, 'package.json')
    if not os.path.exists(package_json_path):
        with open(package_json_path, 'w') as fobj:
            fobj.write("{}")
    dependencies = [
        'babel-core',
        'babel-cli',
        'babel-preset-es2015',
        'babel-polyfill',
        'babelify',
        'browserify',
        'browserify-shim'
    ]
    for pkg in dependencies:
        install_if_necessary(pkg, DEPENDENCY_PATH)


ADD_TO_GLOBALS_FUNC = '''
;function addToGlobals(name, obj) {
    if (!Object.prototype.hasOwnProperty('_fake_exports')) {
        Object.prototype._fake_exports = {};
    }
    Object.prototype._fake_exports[name] = obj;
};
'''
# subprocess.call("""node -e 'require("browserify")'""", shell=True)
GET_FROM_GLOBALS_FUNC = '''
;function getFromGlobals(name) {
    if (!Object.prototype.hasOwnProperty('_fake_exports')) {
        throw Error("Could not find any value named "+name);
    }
    if (Object.prototype._fake_exports.hasOwnProperty(name)) {
        return Object.prototype._fake_exports[name];
    } else {
        throw Error("Could not find any value named "+name);
    }
};
'''


def _get_module_py_name(module_name):
    return module_name.replace('-', '_')


def _get_module_var_name(module_name):
    """Get the name of the python file"""
    pkg_name, _ = _split_name_version(module_name)
    cand = _get_module_py_name(pkg_name).rpartition('/')[-1]
    if not is_valid_py_name(cand):
        raise ValueError(
            "Invalid Python module name %s (generated from %s). Unsupported/invalid npm module specification?" % (
                repr(cand), repr(pkg_name)))
    return cand


def get_module_py_path(module_name):
    """Get the file path of the translated python file. It would be like: ``PY_MODULE_PATH/(<@scope>/)<pkg_name>.py``

    Examples:
        >>> get_module_py_path('ab-c')
        './py_modules/ab_c.py'
        >>> get_module_py_path('ab-c@1.0.0')
        './py_modules/ab_c.py'
        >>> get_module_py_path('@scop-e/ab-c@1.0.0')
        './py_modules/@scop_e/ab_c.py'

    Args:
        module_name (str): the module name, ``(<@scope>/)<pkg_name>(@version)``

    Returns:
        str: the python module file path
    """
    pkg_name, _ = _split_name_version(module_name)
    py_name = _get_module_py_name(pkg_name)
    module_py_path = os.path.join(PY_MODULE_PATH, f'{py_name}.py')
    return module_py_path


def get_module_py_version(module_name):
    """Get the version of the python module

    Args:
        module_name (str): in format `` [<@scope>/]<pkg>[<@version>]``. If version is provided, it would check whether
                           the current version installed is consistent with the required version. If not,
                           ``NotImplementedError`` will be raised.
    """
    pkg_name, _ = _split_name_version(module_name)
    mod_py_path = get_module_py_path(module_name)
    if not os.path.exists(mod_py_path):
        raise NotImplementedError(f'The python module of "{pkg_name}" does not exist!')
    with codecs.open(mod_py_path, "r", "utf-8") as f:
        header = f.readline().strip()
    version = header[11:]
    return version


def translate_npm_module(module_name, include_polyfill=False, cwd='.'):
    """Translate installed Node.js module to Python, and save the Python code in the path of this
    package in "{PY_MODULE_PATH}/(<@scope>/)<pkg_name>.py"

    Notes:
        The Node.js package MUST be installed/linked first!

    Args:
        module_name (str): in format `` [<@scope>/]<pkg>[<@version>]``. If version is provided, it would check whether
                           the current version installed is consistent with the required version. If not,
                           ``NotImplementedError`` will be raised.
        include_polyfill (bool, optional): whether to include the "babel/polyfill" when translating ES6 to ES5
        cwd (str, optional): the working directory to find the installed Node.js module. **We MUST be able to find
                             the module when we run command ``node -p "require(\'{pkg_name}/package.json\').version"``
                             in this working directory.**
    """
    var_name = _get_module_var_name(module_name)
    module_version = get_module_version(module_name, cwd)
    module_path = get_module_dir(module_name, cwd)

    _init()
    module_hash = hashlib.sha1(module_name.encode("utf-8")).hexdigest()[:15]
    version = random.randrange(10000000000000)
    in_file_name = 'in_%s_%d.js' % (module_hash, version)
    out_file_name = 'out_%s_%d.js' % (module_hash, version)
    try:
        code = ADD_TO_GLOBALS_FUNC
        if include_polyfill:
            code += "\n;require('babel-polyfill');\n"
        code += """
            var module_temp_love_python = require(%s);
            addToGlobals(%s, module_temp_love_python);
            """ % (repr(module_path), repr(module_name))
        with open(os.path.join(DEPENDENCY_PATH, in_file_name), 'wb') as f:
            f.write(code.encode('utf-8') if six.PY3 else code)

        # convert the module
        assert subprocess.call(
            '''node -e "(require('browserify')('./%s').bundle(function (err,data) {if (err) {console.log(err);throw new Error(err);};fs.writeFile('%s', require('babel-core').transform(data, {'presets': require('babel-preset-es2015')}).code, ()=>{});}))"'''
            % (in_file_name, out_file_name),
            shell=True,
            cwd=DEPENDENCY_PATH,
        ) == 0, 'Error when converting module to the js bundle'

        os.remove(os.path.join(DEPENDENCY_PATH, in_file_name))
        with codecs.open(os.path.join(DEPENDENCY_PATH, out_file_name), "r",
                         "utf-8") as f:
            js_code = f.read()
        print("Bundled JS library dumped at: %s" % os.path.join(DEPENDENCY_PATH, out_file_name))
        if len(js_code) < 50:
            raise RuntimeError("Candidate JS bundle too short - likely browserify issue.")
        js_code += GET_FROM_GLOBALS_FUNC
        js_code += ';var %s = getFromGlobals(%s);%s' % (
            var_name, repr(module_name), var_name)
        print('Please wait, translating...')
        py_code = translate_js(js_code)

        py_path = get_module_py_path(module_name)
        with open(py_path, 'wb') as f:
            py_code = f"# version: {module_version}\n" + py_code
            f.write(py_code.encode('utf-8') if six.PY3 else py_code)

        os.remove(os.path.join(DEPENDENCY_PATH, out_file_name))
    except Exception as e:
        delete_path(os.path.join(DEPENDENCY_PATH, in_file_name))
        delete_path(os.path.join(DEPENDENCY_PATH, out_file_name))
        raise e


def _load_python_code(module_name):
    """Load the python code, and check the version"""
    pkg_name, require_version = _split_name_version(module_name)
    mod_py_path = get_module_py_path(module_name)
    if not os.path.exists(mod_py_path):
        raise NotImplementedError(f'The python module of "{pkg_name}" does not exist!')
    with codecs.open(mod_py_path, "r", "utf-8") as f:
        header = f.readline().strip()
        py_code = f.read()
    version = header[11:]
    if require_version != '' and version != require_version:
        raise NotImplementedError(
            f'The python module of "{pkg_name}" is installed, but the version "{version}" is not '
            f'consistent with the required version "{require_version}".')
    if not py_code.startswith(DEFAULT_HEADER):
        raise NotImplementedError(
            f'The python module of "{module_name}" is installed, but there is something wrong with '
            f'the header. Re-translation is needed.')
    return py_code


def require(module_name, context=None, include_polyfill=True, cwd='.'):
    """Load installed Node.js module from its python code.

    1. If the module is NOT installed, please install it by ``npm`` command first.
    2. If the module is installed but not correctly translated to Python. Will retry translating.

    Args:
        module_name (str): the module name
        context (dict, optional): some context should be delivered by ``exec``
        include_polyfill (bool, optional): the ``include_polyfill`` argument for
                                           :class:`asp.utils.js2py_ext.translate_npm_module`. Only effective when
                                           re-translation occurs.
        cwd (str, optional): the working directory to find the installed JS module. Only effective when re-translation
                             occurs.

    Returns:
        js2py.JsObjectWrapper: the JS module
    """
    try:
        py_code = _load_python_code(module_name)
    except NotImplementedError as e:
        logger.warning(str(e))
        translate_npm_module(module_name, include_polyfill=include_polyfill, cwd=cwd)
        py_code = _load_python_code(module_name)
    # py_code = py_code[len(DEFAULT_HEADER):]
    context = {} if context is None else context
    exec(py_code, context)
    pkg_name, _ = _split_name_version(module_name)
    return context['var'][_get_module_var_name(pkg_name)].to_py()
