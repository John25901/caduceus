#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
read -r -p "URL du depot GitHub prive: " REPO_URL
[[ -n "$REPO_URL" ]]
[[ -d .git ]] || git init
git add .
if ! git diff --cached --quiet; then git commit -m "CADUCEUS V2.6 deploy"; fi
git branch -M main
if git remote get-url origin >/dev/null 2>&1; then git remote set-url origin "$REPO_URL"; else git remote add origin "$REPO_URL"; fi
git push -u origin main
