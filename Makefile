
.PHONY: all test test-mypy test-mech test-html coverage

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

coverage:
	@PYTHONPATH="$$(pwd -P)/src:$$PYTHONPATH" python3-coverage run --branch --source "$$(pwd -P)/src" test/test.py
	@PYTHONPATH="$$(pwd -P)/src:$$PYTHONPATH" python3-coverage run -a --branch --source "$$(pwd -P)/src" test/htmltree.py
	@PYTHONPATH="$$(pwd -P)/src:$$PYTHONPATH" python3-coverage report -m


apidocs:
	@rm -rf docs/api
	@mkdir -p docs/api
	@sphinx-apidoc-3 -o ./docs/api -F -a -H Mechanize-Mini -A 'Jonas Kümmerlin <jonas@kuemmerlin.eu>' -V 0.1 ./src
	@make -C docs/api html
