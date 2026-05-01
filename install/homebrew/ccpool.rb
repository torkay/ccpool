# Documentation: https://docs.brew.sh/Formula-Cookbook
#                https://rubydoc.brew.sh/Formula
#
# Tap layout: this file is shipped from the ccpool repo for reference.
# The live Homebrew formula lives at github.com/torkay/homebrew-ccpool.
# When cutting a release, copy this file into the tap repo and bump
# `url` + `sha256` to the new sdist.

class Ccpool < Formula
  include Language::Python::Virtualenv

  desc "Smart Claude Max account rotation. Zero daemons. Zero lock-in."
  homepage "https://github.com/torkay/ccpool"
  # Placeholder URL — set on first release. The release.yml workflow uploads
  # sdists to PyPI, then `brew bump-formula-pr` rewrites these two lines.
  url "https://files.pythonhosted.org/packages/source/c/ccpool/ccpool-1.0.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "MIT"
  head "https://github.com/torkay/ccpool.git", branch: "main"

  depends_on "python@3.12"
  depends_on "Dicklesworthstone/coding_agent_account_manager/caam"

  def install
    virtualenv_install_with_resources
    # bin/ccpool shell dispatcher uses python3 + relative imports
    bin.install "bin/ccpool"
  end

  def caveats
    <<~EOS
      ccpool requires the `claude` CLI from Anthropic.

      Install it from:
        https://docs.claude.com/en/docs/claude-code/setup

      First-time setup:
        ccpool setup

      Day-to-day, alias `claude` -> `ccpool` in your shell rc; the setup
      command can do this for you.
    EOS
  end

  test do
    # `ccpool version` exits 0 and prints a version string when caam is on PATH.
    # In Homebrew's test sandbox caam may not be available; we test the
    # python module import instead.
    output = shell_output("#{bin}/ccpool help")
    assert_match "ccpool setup", output
    system Formula["python@3.12"].opt_bin/"python3.12", "-c", "import ccpool"
  end
end
