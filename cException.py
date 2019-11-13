class cException(Exception):
  def __init__(oSelf, sMessage, xDetails):
    oSelf.sMessage = sMessage;
    oSelf.xDetails = xDetails;
    Exception.__init__(oSelf, (sMessage, xDetails));
  
  def __repr__(oSelf):
    return "<%s %s>" % (oSelf.__class__.__name__, oSelf);
  def __str__(oSelf):
    sDetails = str(oSelf.xDetails) if not hasattr(oSelf.xDetails, "fsToString") else oSelf.xDetails.fsToString();
    return "%s (%s)" % (oSelf.sMessage, sDetails);