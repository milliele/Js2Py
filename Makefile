SHELL = /bin/sh

.PHONY: publish

publish:
	rm -rf dist build
	find js2py/py_node_modules -name "*.py" -not -name "__init__.py" | xargs rm -rf
	python setup.py sdist
	twine upload dist/*