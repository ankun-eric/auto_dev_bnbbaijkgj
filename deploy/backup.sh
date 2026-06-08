#!/bin/bash
set -e
DEPLOY_ID=6b099ed3-7175-4a78-91f4-44570c84ed27
BACKUP_TAG="backup-$(date +%Y%m%d%H%M%S)"
echo "备份tag: $BACKUP_TAG"

BE_IMG=$(docker inspect --format='{{.Image}}' ${DEPLOY_ID}-backend 2>/dev/null || echo '')
H5_IMG=$(docker inspect --format='{{.Image}}' ${DEPLOY_ID}-h5 2>/dev/null || echo '')
ADMIN_IMG=$(docker inspect --format='{{.Image}}' ${DEPLOY_ID}-admin 2>/dev/null || echo '')

if [ -n "$BE_IMG" ]; then
  docker tag $BE_IMG ${DEPLOY_ID}-backend:$BACKUP_TAG && echo "backup: backend -> $BACKUP_TAG"
fi
if [ -n "$H5_IMG" ]; then
  docker tag $H5_IMG ${DEPLOY_ID}-h5:$BACKUP_TAG && echo "backup: h5 -> $BACKUP_TAG"
fi
if [ -n "$ADMIN_IMG" ]; then
  docker tag $ADMIN_IMG ${DEPLOY_ID}-admin:$BACKUP_TAG && echo "backup: admin -> $BACKUP_TAG"
fi

echo "BACKUP_TAG=$BACKUP_TAG"
echo "备份完成"
