import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com',username='ubuntu',password='Newbang888',timeout=60)
DID='6b099ed3-7175-4a78-91f4-44570c84ed27'
for tbl in ['home_safety_device_binding','home_safety_alarm','home_safety_emergency_contact']:
    _,o,_=c.exec_command(f'docker exec {DID}-db mysql -uroot -pbini_health_2026 bini_health -e "DESC {tbl}" 2>&1')
    body=o.read().decode()
    has_member='member_id' in body
    has_mig='migrated_to_self' in body
    print(f'{tbl}: member_id={has_member} migrated_to_self={has_mig}')
    # print rows
    for line in body.splitlines():
        if 'member_id' in line or 'migrated_to_self' in line:
            print('  ', line)
c.close()
