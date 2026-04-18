#!/bin/bash
BASE="https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
for p in / /points /points/records /invite /unified-orders /tcm /profile/edit /login /admin/points/rules /api/health /api/points/summary /api/points/tasks /api/users/invite-stats /api/users/share-link /api/admin/points/rules; do
  code=$(curl -sk -o /dev/null -w "%{http_code}" "$BASE$p")
  echo "$code $p"
done
