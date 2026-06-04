echo '=== care-card routes ==='
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python -c "from app.main import app; print('\n'.join(sorted(r.path for r in app.routes if 'care-card' in getattr(r,'path',''))))"
echo '=== tables ==='
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python -c "from app.api.care_card_v1 import CareEmergencyContact, CareCardExtra; print(CareEmergencyContact.__tablename__, CareCardExtra.__tablename__)"
echo '=== public bad token via gateway ==='
curl -s -w '\nHTTP=%{http_code}\n' https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/care-card/public/nope
