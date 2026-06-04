echo "--- file present in gateway container? ---"
docker exec gateway-nginx ls -la /data/static/apk/ 2>&1 | tail -8
echo "--- is gateway-routes included in main conf? ---"
docker exec gateway-nginx sh -c 'grep -rn "gateway-routes" /etc/nginx/nginx.conf /etc/nginx/conf.d/*.conf 2>/dev/null | head'
echo "--- test internal curl from gateway itself ---"
docker exec gateway-nginx sh -c 'curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1/apk/ 2>&1'
echo "--- nginx -t ---"
docker exec gateway-nginx nginx -t 2>&1 | tail -4
echo "--- the catch-all in main conf precedence: show full main conf ---"
docker exec gateway-nginx sh -c 'cat /etc/nginx/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf'
