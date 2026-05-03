import time, secrets
ts = time.strftime("%Y%m%d-%H%M%S")
ts2 = time.strftime("%Y%m%d_%H%M%S")
rnd = secrets.token_hex(2)
print(f"android-v{ts}-{rnd}")
print(f"ios-v{ts}-{rnd}")
print(f"mp_{ts2}_{rnd}")
