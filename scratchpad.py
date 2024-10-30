import socket

conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
conn.setblocking(False)
conn.settimeout(1)
conn.connect(('10.1.38.200', 5025))
conn.send(b'*IDN?\n')
data = conn.recv(1024)

resp = ''
more_data = True
conn.send(b'*IDN?\n')
while more_data:
    try:
        data = conn.recv(1024)
        if len(data) > 0:
            for d in data:
                resp += d
                if d == '\n':  # \r
                    more_data = False
                    break
    except Exception as e:
        raise e

conn.close()
#
# conn.send(bytes('*CLS', 'utf-8'))
# conn.send(b'SYSTem:VERSion?')
# conn.send(b'SYSTem:ERRor?')
# conn.send(b'SYSTem:HISTory? LAST')
# conn.send(b'SYST:ETIM?')
# conn.send(b'*IDN?\n')
# conn.send(b'FREQuency?\n')
# data = conn.recv(1024)

import socketscpi
conn = socketscpi.SocketInstrument('10.1.38.200')