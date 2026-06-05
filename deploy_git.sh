#!/bin/bash
set -e
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
git add 'h5-web/src/app/(ai-chat)/ai-home/page.tsx' 'h5-web/src/app/care-ai-home/page.tsx'
git commit -m "feat: H5 AI首页模式切换入口优化 - 标准模式+关怀模式"
git push codeup master
echo "GIT_PUSH_OK"
