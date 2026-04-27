#!/usr/bin/env bash
# Run the cmaxctl Linux test suite inside a fresh Ubuntu container.
#
# Usage:
#   ./install/linux/run-tests-in-docker.sh                  # ubuntu 24.04
#   ./install/linux/run-tests-in-docker.sh 22.04            # pin version
#   CMAXCTL_TEST_LINUX_KEYRING=1 ./run-tests-in-docker.sh  # opt-in keyring lane
#
# Builds the image once, mounts the repo read-write so wheels build in tree.
set -euo pipefail

UBUNTU_VERSION="${1:-24.04}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TAG="cmaxctl-test:${UBUNTU_VERSION}"

echo "→ building $TAG (this is cached after first run)"
docker build \
    --build-arg "UBUNTU_VERSION=${UBUNTU_VERSION}" \
    -f "${REPO_ROOT}/install/linux/Dockerfile.test" \
    -t "$TAG" \
    "$REPO_ROOT"

echo "→ running pytest in container"
docker run --rm \
    -e "CMAXCTL_TEST_LINUX_KEYRING=${CMAXCTL_TEST_LINUX_KEYRING:-0}" \
    -v "${REPO_ROOT}:/repo" \
    -w /repo \
    "$TAG"
