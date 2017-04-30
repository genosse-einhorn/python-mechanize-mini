
.PHONY: all test test-mypy test-mech test-html

all:
	@# do nothing

test-mypy:
	@# Run MyPy
	@mypy -s src/*.py

test-mech: test-mypy
	@PYTHONPATH=$$(pwd -P)/src:$$PYTHONPATH test/test.py

test-html: test-mypy
	@mypy src/htmltree_mini.py
	@PYTHONPATH=$$(pwd -P)/src:$$PYTHONPATH test/htmltree.py

test: test-mypy test-mech test-html
