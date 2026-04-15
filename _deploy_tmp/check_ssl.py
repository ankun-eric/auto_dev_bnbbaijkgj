import ssl, socket

hostname = 'newbb.test.bangbangvip.com'
ctx = ssl.create_default_context()
with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
    s.connect((hostname, 443))
    cert = s.getpeercert()
    subject = dict(x[0] for x in cert.get('subject', ()))
    issuer = dict(x[0] for x in cert.get('issuer', ()))
    print("SSL Certificate Info:")
    print(f"  CN: {subject.get('commonName', 'N/A')}")
    print(f"  Issuer: {issuer.get('organizationName', 'N/A')}")
    print(f"  Not Before: {cert.get('notBefore', 'N/A')}")
    print(f"  Not After: {cert.get('notAfter', 'N/A')}")
    print(f"  Protocol: {s.version()}")
    print("  Status: VALID")
