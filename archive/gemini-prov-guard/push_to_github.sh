#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/mazharulmd/HCI.git"
BRANCH_NAME="research/prov-guard-hci-defense"

echo "=== Pushing PROV-Guard Research Project to ${REPO_URL} (Branch: ${BRANCH_NAME}) ==="

# Ensure we are on the feature branch
git checkout -B "${BRANCH_NAME}"

# Configure remote origin
if git remote get-url origin >/dev/null 2>&1; then
    git remote set-url origin "${REPO_URL}"
else
    git remote add origin "${REPO_URL}"
fi

# Push the branch to GitHub
git push -u origin "${BRANCH_NAME}" --force

echo "=== Successfully pushed branch '${BRANCH_NAME}' to ${REPO_URL}! ==="
