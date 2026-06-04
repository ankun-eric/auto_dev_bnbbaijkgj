import ssl, socket, datetime, sys
from cryptography import x509
from cryptography.hazmat.backends import default_backend

hostname = '6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com'

try:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with socket.create_connection((hostname, 443), timeout=15) as sock:
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            der = ssock.getpeercert(binary_form=True)
            if der:
                cert = x509.load_der_x509_certificate(der, default_backend())
                print(f"Subject: {cert.subject.rfc4514_string()}")
                print(f"Issuer: {cert.issuer.rfc4514_string()}")
                print(f"NotBefore: {cert.not_valid_before}")
                print(f"NotAfter: {cert.not_valid_after}")
                days = (cert.not_valid_after - datetime.datetime.utcnow()).days
                print(f"DaysRemaining: {days}")
                try:
                    san_ext = cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                    sans = san_ext.value.get_values_for_type(x509.DNSName)
                    print(f"SAN: {sans}")
                except:
                    print("SAN: N/A")
            else:
                print("ERROR: cert binary is None")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
