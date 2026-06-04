import datetime, secrets
tag = f"ios-v{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"
print(tag)
with open('_ios_tag_build.txt','w') as f:
    f.write(tag)
