# Homebrew formula

`cmaxctl.rb` is the canonical Homebrew formula. It lives here for reference and review; the live tap is at [`github.com/torkay/homebrew-cmaxctl`](https://github.com/torkay/homebrew-cmaxctl).

## Releasing a new version

The `release.yml` workflow handles this automatically:

1. PyPI publishes the new sdist via OIDC trusted publishing.
2. The `bump-homebrew` job runs `brew bump-formula-pr` against the tap.
3. CI runs `brew test cmaxctl` on the formula PR.

Manual override (when the auto-bump misses or the formula needs hand-tweaking):

```bash
brew bump-formula-pr \
  --version=1.0.1 \
  --url=https://files.pythonhosted.org/packages/source/c/cmaxctl/cmaxctl-1.0.1.tar.gz \
  cmaxctl
```

## Local testing

To install from this checkout (without the tap):

```bash
brew install --build-from-source ./install/homebrew/cmaxctl.rb
```

Note this requires `caam` to also be available (see the `depends_on` line).
