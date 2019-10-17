class cException(Exception):
  def __init__(oSelf, sMessage, sDetails):
    oSelf.sMessage = sMessage;
    oSelf.sDetails = sDetails;
    Exception.__init__(oSelf, sMessage, sDetails);
  
  def __repr__(oSelf):
    return "<%s %s>" % (oSelf.__class__.__name__, oSelf);
  def __str__(oSelf):
    return "%s (%s)" % (oSelf.sMessage, oSelf.sDetails);