
.PHONY: all test test-mypy test-mech test-html coverage

all:
	@# do nothing

test-mypy:
	@# Run MyPy
	@mypy --check-untyped-defs --strict-optional src/mechanize_mini/*.py

test-mech: test-mypy
	@PYTHONPATH=$$(pwd -P)/src:$$PYTHONPATH test/minimech.py

test-html: test-mypy
	@PYTHONPATH=$$(pwd -P)/src:$$PYTHONPATH test/htmltree.py

test-forms: test-mypy
	@PYTHONPATH=$$(pwd -P)/src:$$PYTHONPATH test/forms.py

test: test-mypy test-mech test-html test-forms

coverage: test-mypy
	@PYTHONPATH="$$(pwd -P)/src:$$PYTHONPATH" python3-coverage run --branch --source "$$(pwd -P)/src/mechanize_mini" test/minimech.py
	@PYTHONPATH="$$(pwd -P)/src:$$PYTHONPATH" python3-coverage run -a --branch --source "$$(pwd -P)/src/mechanize_mini" test/htmltree.py
	@PYTHONPATH="$$(pwd -P)/src:$$PYTHONPATH" python3-coverage run -a --branch --source "$$(pwd -P)/src/mechanize_mini" test/forms.py
	@PYTHONPATH="$$(pwd -P)/src:$$PYTHONPATH" python3-coverage report -m


apidocs:
	@rm -rf docs/api
	@mkdir -p docs/api
	@sphinx-apidoc-3 -o ./docs/api -P -F -a -H Mechanize-Mini -A 'Jonas Kümmerlin <jonas@kuemmerlin.eu>' -V 0.1 ./src
	@echo "extensions.extend(['sphinx.ext.intersphinx', 'sphinx.ext.napoleon'])" >> docs/api/conf.py
	@echo "napoleon_use_ivar = True" >> docs/api/conf.py
	@echo "napoleon_include_init_with_doc = True" >> docs/api/conf.py
	@echo "intersphinx_mapping = {'python': ('https://docs.python.org/3', None)}" >> docs/api/conf.py
	@echo 'html_theme = "sphinx_rtd_theme";' >> docs/api/conf.py
	@make -C docs/api html
