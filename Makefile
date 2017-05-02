
.PHONY: all test test-mypy test-mech test-html

all:
	@# do nothing

test-mypy:
	@# Run MyPy
	@mypy --strict-optional src/*.py

test-mech: test-mypy
	@PYTHONPATH=$$(pwd -P)/src:$$PYTHONPATH test/test.py

test-html: test-mypy
	@PYTHONPATH=$$(pwd -P)/src:$$PYTHONPATH test/htmltree.py

test: test-mypy test-mech test-html

apidocs:
	@rm -rf docs/api
	@mkdir -p docs/api
	@sphinx-apidoc-3 -o ./docs/api -F -a -H Mechanize-Mini -A 'Jonas Kümmerlin <jonas@kuemmerlin.eu>' -V 0.1 ./src
	@make -C docs/api html
