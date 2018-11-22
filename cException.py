class cException(Exception):
  def __init__(oSelf, sMessage, sDetails):
    oSelf.sMessage = sMessage;
    oSelf.sDetails = sDetails;
    Exception.__init__(oSelf, sMessage, sDetails);
