"""
Entry point for the Smart Attendance System.
Run this file to start the Flask server.

Serves over HTTPS by default (auto-generates a self-signed certificate)
so that mobile browsers on the local network can access the camera
for face verification via getUserMedia().
"""
import os
import sys
import socket
import ssl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import app


def get_local_ip():
    """Get the machine's local network IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate_self_signed_cert(cert_dir):
    """Generate a self-signed SSL certificate for HTTPS."""
    cert_file = os.path.join(cert_dir, "cert.pem")
    key_file = os.path.join(cert_dir, "key.pem")

    if os.path.exists(cert_file) and os.path.exists(key_file):
        return cert_file, key_file

    os.makedirs(cert_dir, exist_ok=True)

    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
        import ipaddress

        local_ip = get_local_ip()

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "SmartAttend Local Server"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SmartAttend"),
        ])

        san_list = [
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        ]
        try:
            san_list.append(x509.IPAddress(ipaddress.IPv4Address(local_ip)))
        except Exception:
            pass

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
            .sign(key, hashes.SHA256())
        )

        with open(key_file, "wb") as f:
            f.write(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            ))

        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        print("  ✅ SSL certificate generated successfully.")
        return cert_file, key_file

    except ImportError:
        print("  ⚠️  'cryptography' package not found. Installing...")
        os.system(f"{sys.executable} -m pip install cryptography")
        # Retry after install
        return generate_self_signed_cert(cert_dir)
if __name__ == '__main__':
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


    use_https = False
    if "--https" in sys.argv:
        use_https = True


    local_ip = get_local_ip()
    cert_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs")

    print("=" * 60)
    print("  Smart Attendance System using Face Recognition (InsightFace/ArcFace)")
    print("=" * 60)

    ssl_context = None
    protocol = "http"
    if use_https:
        try:
            ssl_context = 'adhoc'
            protocol = "https"
        except Exception as e:
            ssl_context = None
            protocol = "http"

    print(f"  Server starting at: {protocol}://{local_ip}:5000")

    print()
    print(f"  📍 Teacher Dashboard (local):")
    print(f"     {protocol}://127.0.0.1:5000/static/index.html")
    print()
    print(f"  📱 Student QR Check-In (network):")
    print(f"     {protocol}://{local_ip}:5000/static/student.html")
    print()
    if protocol == "https":
        print("  💡 Students: When your phone shows a security warning,")
        print("     tap 'Advanced' → 'Proceed' to continue. This is safe")
        print("     on your local network.")
    print("=" * 60)

    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port, ssl_context=ssl_context)
