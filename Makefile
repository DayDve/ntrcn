# Uses the project venv when present: python3 -m venv --system-site-packages .venv
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
BIN_DIR ?= $(HOME)/.local/bin
APPS_DIR ?= $(HOME)/.local/share/applications
DESKTOP_FILE := src/ntrcn/org.daydve.ntrcn.desktop
APP_ICON := src/ntrcn/icons/org.daydve.ntrcn.svg
ICONS_DIR ?= $(HOME)/.local/share/icons/hicolor/scalable/apps

.PHONY: help test lint format check run e2e pot translations install-user uninstall-user deb deb-check deb-test clean

help:
	@echo "make test           - run tests"
	@echo "make lint           - ruff + mypy"
	@echo "make format         - ruff format"
	@echo "make check          - lint + test"
	@echo "make run            - run ntrcn from the source tree with debug logging"
	@echo "make e2e            - live test on this desktop (types into its own window)"
	@echo "make pot            - extract UI strings into po/ntrcn.pot and update po/*.po"
	@echo "make translations   - compile po/*.po for running from the source tree"
	@echo "make install-user   - install ~/.local/bin/ntrcn (runs this checkout), menu entry, autostart"
	@echo "make uninstall-user - remove what install-user installed"
	@echo "make deb           - build the .deb in a Debian container (needs docker)"
	@echo "make deb-check     - compare the .deb contents with scripts/deb-contents.txt"
	@echo "make deb-test      - install the .deb into clean Debian, Ubuntu and KDE neon containers"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests scripts
	$(PYTHON) -m ruff format --check src tests scripts
	$(PYTHON) -m mypy src
	for po in po/*.po; do msgfmt --check -o /dev/null $$po || exit 1; done

format:
	$(PYTHON) -m ruff format src tests scripts

check: lint test

run: translations
	PYTHONPATH=src python3 -m ntrcn --debug

pot:
	xgettext --language=Python --keyword=_ --keyword=N_ --from-code=UTF-8 --package-name=ntrcn \
	  --msgid-bugs-address=https://github.com/DayDve/ntrcn/issues --add-comments=TRANSLATORS \
	  --sort-by-file -o po/ntrcn.pot src/ntrcn/*.py src/ntrcn/flags/*.py
	for po in po/*.po; do msgmerge --quiet --update --backup=none $$po po/ntrcn.pot; done

# Compiled catalogs are build output (not in git): src/ntrcn/locale/<lang>/LC_MESSAGES/ntrcn.mo
translations:
	for po in po/*.po; do \
	  lang=$$(basename $$po .po); mkdir -p src/ntrcn/locale/$$lang/LC_MESSAGES; \
	  msgfmt --check -o src/ntrcn/locale/$$lang/LC_MESSAGES/ntrcn.mo $$po || exit 1; \
	done

# Starts ntrcn from the source tree, drives it with scripts/e2e.py, then stops it.
# Another running ntrcn must be stopped first; the hotkey in the config must be Pause.
# Uses the first two Plasma layouts, whatever they are.
e2e:
	PYTHONPATH=src python3 -m ntrcn & pid=$$!; sleep 2; \
	PYTHONPATH=src python3 scripts/e2e.py; rc=$$?; kill $$pid; exit $$rc

install-user: translations
	install -d $(BIN_DIR) $(APPS_DIR) $(ICONS_DIR)
	printf '#!/bin/sh\nPYTHONPATH="%s/src" exec /usr/bin/python3 -m ntrcn "$$@"\n' "$(CURDIR)" > $(BIN_DIR)/ntrcn
	chmod +x $(BIN_DIR)/ntrcn
	install -m 644 $(DESKTOP_FILE) $(APPS_DIR)/
	install -m 644 $(APP_ICON) $(ICONS_DIR)/
	PATH="$(BIN_DIR):$$PATH" PYTHONPATH=src python3 -c 'from ntrcn import autostart; autostart.set_enabled(True)'

uninstall-user:
	rm -f $(BIN_DIR)/ntrcn $(APPS_DIR)/$(notdir $(DESKTOP_FILE)) $(ICONS_DIR)/$(notdir $(APP_ICON))
	PYTHONPATH=src python3 -c 'from ntrcn import autostart; autostart.set_enabled(False)'

DEB_BUILD_IMAGE ?= debian:trixie
DEB_TEST_IMAGES ?= debian:trixie ubuntu:25.10 ubuntu:26.04 invent-registry.kde.org/neon/docker-images/plasma:user
DEB_BUILD_DEPS := build-essential debhelper dh-python gettext pybuild-plugin-pyproject python3-all python3-setuptools

# Builds from a copy of the tree, so nothing on the host is touched.
deb:
	mkdir -p dist
	docker run --rm -e DEBIAN_FRONTEND=noninteractive -v "$(CURDIR)":/src:ro -v "$(CURDIR)/dist":/out $(DEB_BUILD_IMAGE) sh -euc '\
	  apt-get update -qq && apt-get install -y -qq --no-install-recommends $(DEB_BUILD_DEPS) >/dev/null; \
	  mkdir /build && tar -C /src --exclude=./.git --exclude=./.venv --exclude=./dist -cf - . | tar -C /build -xf -; \
	  cd /build && dpkg-buildpackage -us -uc -b >/out/build.log 2>&1 || { tail -40 /out/build.log; exit 1; }; \
	  cp /ntrcn_*.deb /out/ && chown $(shell id -u):$(shell id -g) /out/ntrcn_*.deb /out/build.log'
	ls dist/ntrcn_*.deb

# Fails if the package gains or loses a file.
deb-check:
	dpkg-deb -c dist/ntrcn_*.deb | awk '{print $$6}' | grep -v '/$$' | LC_ALL=C sort | diff -u scripts/deb-contents.txt -

deb-test:
	for image in $(DEB_TEST_IMAGES); do \
	  echo "== $$image"; \
	  docker run --rm --user root -v "$(CURDIR)/dist":/pkg:ro $$image sh -euc '\
	    export DEBIAN_FRONTEND=noninteractive; apt-get update -qq; \
	    apt-get install -y -qq /pkg/ntrcn_*.deb >/dev/null; ntrcn --version' || exit 1; \
	done

clean:
	rm -rf build dist src/*.egg-info src/ntrcn/locale .pytest_cache .mypy_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
