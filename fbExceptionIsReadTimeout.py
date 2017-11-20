import socket, ssl;

def fbExceptionIsReadTimeout(oException):
  return (
    oException.__class__ == socket.timeout
    or (oException.__class__ == ssl.SSLError and oException.message == "The read operation timed out")
  );