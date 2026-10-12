.PHONY: test validate build
# All targets are nonprivileged. No install target.
test:
	python3 -m unittest discover -s tests -v
validate:
	python3 scripts/validate.py
build:
	python3 scripts/build.py
