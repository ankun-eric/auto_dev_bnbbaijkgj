"""Run new pytest test. Use --no-header --confcutdir to bypass conftest if needed,
or install aiosqlite to make conftest work."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
BACKEND_CT = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"


def run(c, cmd, timeout=600):
    print(f"\n$ {cmd[:300]}")
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    rc = o.channel.recv_exit_status()
    if out.strip():
        print(out[-5000:])
    if err.strip():
        print("ERR:", err[-1500:])
    print(f"[exit={rc}]")
    return rc, out, err


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PWD, look_for_keys=False, allow_agent=False, timeout=30)
    try:
        # Install pytest + aiosqlite into the new container (was lost on rebuild)
        run(c, f"docker exec {BACKEND_CT} pip install -q -i https://mirrors.cloud.tencent.com/pypi/simple/ --trusted-host mirrors.cloud.tencent.com pytest pytest-asyncio aiosqlite 2>&1 | tail -5", timeout=300)
        run(c, f"docker exec {BACKEND_CT} pytest --version")

        # Run target tests. Use --noconftest? Better: just run the new test alone with a directory that doesn't have conftest dependency.
        # The new test only imports sanitize_attachment_hint from app.utils.ai_output_sanitizer.
        # We can copy it to /tmp, run it standalone.
        run(c, f"docker exec {BACKEND_CT} cp /app/tests/test_ai_home_actionbar_and_attachment_filter_20260517.py /tmp/test_attach.py")
        run(c, f"docker exec -w /app {BACKEND_CT} python -m pytest /tmp/test_attach.py -v --no-header --tb=short 2>&1 | tail -50", timeout=600)

        # Also run with full discovery but only this file (conftest will load, hence aiosqlite needed)
        print("\n=== Full conftest discovery test ===")
        run(c, f"docker exec -w /app {BACKEND_CT} python -m pytest tests/test_ai_home_actionbar_and_attachment_filter_20260517.py -v --tb=short 2>&1 | tail -50", timeout=600)
    finally:
        c.close()


if __name__ == "__main__":
    main()
