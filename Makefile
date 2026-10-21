PYTHON ?= python

.PHONY: test test-html

test:
	$(PYTHON) scripts/run_tests.py

test-html:
	$(PYTHON) scripts/run_tests.py --html
