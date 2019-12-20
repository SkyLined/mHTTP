import socket;

def fbSocketExceptionIsClosedConnection(oException):
  return (
    (oException.__class__ == socket.error and oException.errno in [
      9, # (forgot to write down the error details!)
      10038, # WSAENOTSOCK 0x80072736 An operation was attempted on something that is not a socket
      10052, # WSAENETRESET 0x80072744 The connection has been broken due to keep-alive activity detecting a failure while the operation was in progress.
      10053, # WSAECONNABORTED 0x80072745 An established connection was aborted by the software in your host machine.
      10054, # WSAECONNRESET 0x80072746 An existing connection was forcibly closed by the remote host
    ])
  );