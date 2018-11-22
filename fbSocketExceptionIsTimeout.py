import socket, ssl;

def fbSocketExceptionIsTimeout(oException):
  return (
    oException.__class__ == socket.timeout
    or (oException.__class__ == socket.error and oException.errno == 10035) # WSAEWOULDBLOCK 0x80072733 A non-blocking socket operation could not be completed immediately.
    or (oException.__class__ == ssl.SSLError and oException.message == "The read operation timed out")
    or (oException.__class__ == ssl.SSLWantReadError and oException.errno == 2)
  );