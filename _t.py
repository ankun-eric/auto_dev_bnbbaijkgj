import socket  
s=socket.socket()  
s.settimeout(3)  
s.connect(('134.175.97.26',22))  
print('CONN_OK')  
s.settimeout(5)  
d=s.recv(256)  
print('RECV',len(d))  
s.close()  
