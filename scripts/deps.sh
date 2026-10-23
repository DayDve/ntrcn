#!/bin/sh
# Installs and removes the run-time dependencies of ntrcn with the distribution's package
# manager. Run as root (the Makefile calls it through sudo).
#
#   deps.sh install   install what is missing, marked as dependencies, and remember it
#   deps.sh remove    remove what `install` added, as long as nothing else needs it
#
# Only packages that `install` added are ever removed: whatever was there before stays, and
# so does anything another package came to depend on or the user installed explicitly
# since. Every removal is checked with a dry run first and skipped if it would take any
# other package with it.
set -eu

STATE_DIR=/var/lib/ntrcn
STATE_FILE=$STATE_DIR/installed-packages

family() {
    . /etc/os-release
    for word in ${ID:-} ${ID_LIKE:-}; do
        case $word in
            debian | ubuntu) echo debian; return ;;
            fedora) echo fedora; return ;;
            suse | opensuse) echo suse; return ;;
            arch) echo arch; return ;;
        esac
    done
}

FAMILY=$(family)
if [ -z "$FAMILY" ]; then
    echo "Unknown distribution: install and remove the dependencies listed in README.md by hand." >&2
    exit 0
fi

case $FAMILY in
    # The Qt SVG icon plugin is qt6-svg-plugins in Debian and Ubuntu, part of qt6-svg in neon.
    debian) svg_plugin=qt6-svg-plugins
        apt-cache show qt6-svg-plugins >/dev/null 2>&1 || svg_plugin=qt6-svg
        PACKAGES="python3-pyside6.qtwidgets python3-pyside6.qtsvg python3-pyside6.qtnetwork
        $svg_plugin python3-evdev python3-dbus wl-clipboard libxkbcommon0 libhunspell-1.7-0
        gettext" ;;
    fedora) PACKAGES="python3-pyside6 python3-evdev python3-dbus wl-clipboard libxkbcommon hunspell
        gettext" ;;
    suse) PACKAGES="python3-pyside6 python3-evdev python3-dbus-python wl-clipboard libxkbcommon0
        libhunspell-1_7-0 gettext-runtime" ;;
    arch) PACKAGES="pyside6 qt6-svg python-evdev python-dbus wl-clipboard libxkbcommon hunspell
        gettext" ;;
esac

# Names of all installed packages, one per line, sorted.
installed() {
    case $FAMILY in
        debian) dpkg-query -W -f '${db:Status-Abbrev} ${Package}\n' | awk '/^ii/ {print $2}' ;;
        fedora | suse) rpm -qa --qf '%{NAME}\n' ;;
        arch) pacman -Qq ;;
    esac | sort -u
}

# Lines of $1 that are also in $2 (both sorted).
common() { printf '%s\n' "$1" | comm -12 - "$2"; }

install_packages() {
    before=$(mktemp)
    installed > "$before"
    case $FAMILY in
        debian) apt-get install -y $PACKAGES ;;
        fedora) dnf install -y $PACKAGES ;;
        suse) zypper --non-interactive install $PACKAGES ;;
        arch) pacman -S --needed --noconfirm --asdeps $PACKAGES ;;
    esac
    added=$(installed | comm -13 "$before" -)
    rm -f "$before"
    [ -n "$added" ] || return 0
    # Mark the packages we asked for as dependencies too (what they pulled in already is);
    # pacman did it with --asdeps, zypper cannot.
    asked=$(mktemp)
    printf '%s\n' $PACKAGES | sort -u > "$asked"
    marked=$(common "$added" "$asked")
    rm -f "$asked"
    if [ -n "$marked" ]; then
        case $FAMILY in
            debian) apt-mark auto $marked >/dev/null ;;
            fedora) dnf mark dependency -y $marked >/dev/null ;;
        esac
    fi
    # Keep what earlier runs added as well.
    mkdir -p "$STATE_DIR"
    { [ -f "$STATE_FILE" ] && cat "$STATE_FILE"; printf '%s\n' "$added"; } | sort -u > "$STATE_FILE.new"
    mv "$STATE_FILE.new" "$STATE_FILE"
}

# Packages nothing needs any more, as the package manager sees it.
unneeded() {
    case $FAMILY in
        debian) apt-get -s autoremove | awk '/^Remv / {print $2}' ;;
        fedora) dnf repoquery --unneeded --qf '%{name}\n' 2>/dev/null ;;
        arch) pacman -Qdtq || true ;;
        suse)
            zypper --quiet packages --unneeded | awk -F'|' 'NR > 2 {gsub(/ /, "", $3); print $3}'
            # Packages we asked for are not marked as dependencies on openSUSE: count one as
            # unneeded when removing it would take nothing else with it.
            for package in $(common "$(installed)" "$STATE_FILE"); do
                [ "$(removal_set "$package")" = "$package" ] && echo "$package"
            done
            ;;
    esac | sort -u
}

# What removing the given packages would remove, sorted; nothing is removed.
removal_set() {
    case $FAMILY in
        debian) apt-get -s remove "$@" | awk '/^Remv / {print $2}' ;;
        fedora) dnf remove --assumeno --setopt=clean_requirements_on_remove=False "$@" 2>/dev/null |
                    awk '/^Removing/ {on = 1; next} /^$|^Transaction/ {on = 0} on {print $1}' ;;
        suse) zypper --non-interactive remove --dry-run "$@" 2>/dev/null |
                  awk '/following .*package.* going to be REMOVED/ {on = 1; next} /^$/ {on = 0} on' |
                  tr ' ' '\n' ;;
        # -s takes along the dependencies nothing else needs, cycles included.
        arch) pacman -Rsp --print-format '%n' "$@" ;;
    esac | grep -v '^$' | sort -u
}

remove_packages() {
    [ -f "$STATE_FILE" ] || { echo "No dependencies were installed by ntrcn."; return 0; }
    removed=""
    while :; do
        unneeded_file=$(mktemp)
        unneeded > "$unneeded_file"
        candidates=$(common "$(installed)" "$STATE_FILE" | comm -12 - "$unneeded_file")
        rm -f "$unneeded_file"
        [ -n "$candidates" ] || break
        others=$(removal_set $candidates | comm -23 - "$STATE_FILE")
        if [ -n "$others" ]; then
            echo "Not removing the dependencies: that would also remove" $others >&2
            return 0
        fi
        case $FAMILY in
            debian) apt-get remove -y $candidates ;;
            fedora) dnf remove -y --setopt=clean_requirements_on_remove=False $candidates ;;
            suse) zypper --non-interactive remove $candidates ;;
            arch) pacman -Rs --noconfirm $candidates ;;
        esac
        removed="$removed $(echo $candidates)"
    done
    rm -rf "$STATE_DIR"
    echo "Removed:${removed:- nothing}"
}

case ${1:-} in
    install) install_packages ;;
    remove) remove_packages ;;
    *) echo "usage: $0 install|remove" >&2; exit 2 ;;
esac
