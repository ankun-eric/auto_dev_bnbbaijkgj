#!/bin/bash
set -e
DEPLOY_ID=6b099ed3-7175-4a78-91f4-44570c84ed27
PROJECT_DIR=/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
GIT_URL=https://kun-an:pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git
cd \$PROJECT_DIR
git remote -v
git remote set-url origin \$GIT_URL 2>/dev/null || git remote add origin \$GIT_URL
echo FETCHING...
git fetch --depth 1 origin master
echo RESETTING...
git reset --hard origin/master
echo COMMIT:
git log --oneline -3
echo UPDATE_DONE
