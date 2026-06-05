import sys,socket  
s=socket.socket()  
s.settimeout(5)  
try:  
"    s.connect(('134.175.97.26',22))"  
"    print('OK')"  
"except Exception as e:"  
"    print('ERR',e)"  
