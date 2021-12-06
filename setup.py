try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

long_desc = '''Translates JavaScript to Python code. Js2Py is able to translate and execute virtually any JavaScript code.

Js2Py is written in pure python and does not have any dependencies. Basically an implementation of JavaScript core in pure python.


    import js2py

    f = js2py.eval_js( "function $(name) {return name.length}" )

    f("Hello world")

    # returns 11

Now also supports ECMA 6 through js2py.eval_js6(js6_code)!

More examples at: https://github.com/PiotrDabkowski/Js2Py
'''

# rm -rf dist build && python3 setup.py sdist bdist_wheel
# twine upload dist/*
setup(
    name='Js2Py_Ext',
    version='0.72',
    packages=['js2py', 'js2py.utils', 'js2py.prototypes', 'js2py.translators',
              'js2py.constructors', 'js2py.host', 'js2py.es6', 'js2py.internals',
              'js2py.internals.prototypes', 'js2py.internals.constructors', 'js2py.py_node_modules'],
    install_requires=['tzlocal>=1.2', 'six>=1.10', 'pyjsparser>=2.5.1'],
    license='MIT',
    author='Milliele',
    author_email='milliele@qq.com',
    description='Forked from Js2py 0.71 (https://github.com/PiotrDabkowski/Js2Py). '
                'Optimize Node.js module import and console logging.',
    long_description=long_desc
)
