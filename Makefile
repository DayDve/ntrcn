# Uses the project venv when present: python3 -m venv --system-site-packages .venv
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PREFIX ?= /usr/local
# udev reads rules from /etc and /usr/lib only, never from /usr/local.
UDEV_RULES_DIR ?= /etc/udev/rules.d
LIB_DIR := $(DESTDIR)$(PREFIX)/lib/ntrcn
BIN_DIR := $(DESTDIR)$(PREFIX)/bin
APPS_DIR := $(DESTDIR)$(PREFIX)/share/applications
ICONS_DIR := $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps
DESKTOP_FILE := src/ntrcn/org.daydve.ntrcn.desktop
APP_ICON := src/ntrcn/icons/org.daydve.ntrcn.svg
UDEV_RULE := src/ntrcn/70-ntrcn-uinput.rules
# Root is needed only for the steps that write outside the home directory.
SUDO := $(if $(filter 0,$(shell id -u)),,sudo)
# Reload udev rules only where udev runs (not in containers or with DESTDIR).
UDEV_RUNNING := [ -z "$(DESTDIR)" ] && [ -S /run/udev/control ]

.PHONY: help test lint format check run e2e pot translations install update uninstall deb deb-check deb-test clean

help:
	@echo "make test           - run tests"
	@echo "make lint           - ruff + mypy"
	@echo "make format         - ruff format"
	@echo "make check          - lint + test"
	@echo "make run            - run ntrcn from the source tree with debug logging"
	@echo "make e2e            - live test on this desktop (types into its own window)"
	@echo "make pot            - extract UI strings into po/ntrcn.pot and update po/*.po"
	@echo "make translations   - compile po/*.po for running from the source tree"
	@echo "make install        - install the dependencies, ntrcn into $(PREFIX) and the udev rule"
	@echo "make update         - git pull (in a clone) and install again"
	@echo "make uninstall      - remove all that, dependencies other packages need are kept"
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

# A plain copy of the package with a launcher: no pip, dependencies come from the distribution
# (scripts/deps.sh). Translations are compiled straight into the installed copy, so nothing in
# the checkout becomes owned by root. With DESTDIR (for packagers) only the files are installed.
# Reading keyboards needs the input group; joining it takes effect at the next login.
install:
	[ -n "$(DESTDIR)" ] || $(SUDO) sh scripts/deps.sh install
	$(SUDO) rm -rf $(LIB_DIR)
	$(SUDO) install -d $(LIB_DIR) $(BIN_DIR) $(APPS_DIR) $(ICONS_DIR) $(DESTDIR)$(UDEV_RULES_DIR)
	tar -C src --exclude=__pycache__ --exclude=locale -cf - ntrcn | $(SUDO) tar -C $(LIB_DIR) -xf -
	for po in po/*.po; do \
	  lang=$$(basename $$po .po); dir=$(LIB_DIR)/ntrcn/locale/$$lang/LC_MESSAGES; \
	  $(SUDO) install -d $$dir && msgfmt -o - $$po | $(SUDO) tee $$dir/ntrcn.mo >/dev/null || exit 1; \
	done
	printf '#!/bin/sh\nPYTHONPATH="%s" exec /usr/bin/python3 -m ntrcn "$$@"\n' "$(PREFIX)/lib/ntrcn" | \
	  $(SUDO) install -m 755 /dev/stdin $(BIN_DIR)/ntrcn
	$(SUDO) install -m 644 $(DESKTOP_FILE) $(APPS_DIR)/
	$(SUDO) install -m 644 $(APP_ICON) $(ICONS_DIR)/
	$(SUDO) install -m 644 $(UDEV_RULE) $(DESTDIR)$(UDEV_RULES_DIR)/
	if $(UDEV_RUNNING); then $(SUDO) udevadm control --reload && $(SUDO) udevadm trigger /dev/uinput; fi
	[ -n "$(DESTDIR)" ] || [ "$$(id -u)" = 0 ] || ! getent group input >/dev/null || \
	  id -nG | grep -qw input || \
	  { $(SUDO) usermod -aG input "$$(id -un)" && echo "Log out and back in to start using ntrcn."; }

# In a git clone pulls first; an unpacked source archive is installed as it is. A fresh make
# reads the Makefile as pulled.
update:
	[ ! -d .git ] || git pull --ff-only
	$(MAKE) install
	! pgrep -fx '/usr/bin/python3 -m ntrcn( .*)?' >/dev/null || echo "Restart ntrcn to use the new version."

uninstall:
	$(SUDO) rm -rf $(LIB_DIR)
	$(SUDO) rm -f $(BIN_DIR)/ntrcn $(APPS_DIR)/$(notdir $(DESKTOP_FILE)) \
	  $(ICONS_DIR)/$(notdir $(APP_ICON)) $(DESTDIR)$(UDEV_RULES_DIR)/$(notdir $(UDEV_RULE))
	if $(UDEV_RUNNING); then $(SUDO) udevadm control --reload; fi
	[ -n "$(DESTDIR)" ] || $(SUDO) sh scripts/deps.sh remove

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
