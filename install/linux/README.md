# Linux packaging

| Path | Purpose |
|---|---|
| `debian/` | Debian packaging skeleton (`dpkg-buildpackage` compatible). Status: **skeleton**, never built end-to-end. |
| `arch/PKGBUILD` | Arch Linux package descriptor for AUR submission. Status: **skeleton**, never submitted. |
| `Dockerfile.test` + `run-tests-in-docker.sh` | Local Linux test validation. Status: **working** (used for Phase 2 acceptance). |

## Debian build (preview)

From the repo root:

```bash
# One-time: install build deps
sudo apt install debhelper-compat dh-python python3-all python3-setuptools

# Build
dpkg-buildpackage -us -uc -b
```

The resulting `.deb` lands in the parent directory.

## Arch build (preview)

```bash
cd install/linux/arch
makepkg -si
```

After first release, AUR submission goes via the `aur.archlinux.org/ccpool.git` git remote with the same PKGBUILD plus a `.SRCINFO` (generated via `makepkg --printsrcinfo > .SRCINFO`).

## Why both files exist as skeletons

ccpool ships first via Homebrew (macOS) + pip/pipx (universal). `.deb` and AUR are documented from day one so distro packagers can pick them up without reverse-engineering, but the maintenance burden of live-shipping them isn't justified at v1.0. Promote to "shipped" lanes when there's user demand or a contributor steps up.
