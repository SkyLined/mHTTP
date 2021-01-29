# Offers a way to provide a value for a variable or argument that indicates
# there is no value provided. This is useful for optional function arguments
# that can have many different types of value, or which may not be provided.
# This module can be used to pass the concept of "not provided" as a value, and
# check if the caller did indeed provide "not provided" as a value.
# Example use:

# from mOptional import *;
# def fPrintVariableIfProvided(xzOptionalArgument = zNotProvided):
#   if fbIsProvided(xzOptionalArgument):
#     print repr(xzOptionalArgument);
#
# fPrintVariableIfProvided();     # does not print anything;
# fPrintVariableIfProvided(None); # prints "None";

# Various modules are expected to have local copies of this utility code.
# However, they should all agree on the value of "not provided". Therefore, the
# first copy of this code creates a global variable in the context of the
# __main__ module to store this value. Subsequent copies of this code will
# use that value as well, so they all agree on the value of "not provided".
import __main__;
if not hasattr(__main__, "__zNotProvided"):
  class czNotProvided(object):
    def __nonzero__(oSelf):
      # fbIsProvided() should be called to check if a value is provided.
      # example of bad code:
      #   not x;
      # replace with:
      #   not fbIsProvided(x)
      # The latter will throw the below assertion:
      raise AssertionError("You should not directly use this optional value as a boolean!");
    def __cmp__(oSelf):
      # fbIsProvided() should be called to check if a value is provided.
      # example bad code:
      #   x is zNotProvided;
      # replace with:
      #   not fbIsProvided(x)
      # The latter will throw the below assertion:
      raise AssertionError("You should not directly compare this optional value to anything!");
    def __repr__(oSelf):
      return "<not provided>";
    def __str__(oSelf):
      return "<not provided>";
  __main__.__zNotProvided = czNotProvided();
zNotProvided = __main__.__zNotProvided;

def fbIsProvided(xzValue):
  # We don't want the user to directly compare a value that may be `zNotProvided`
  # to any other value, so we won't do it ourselves either. But every value in
  # Python has a unique id, so we can compare ids.
  return id(xzValue) != id(zNotProvided);

def fxGetFirstProvidedValue(*txzValues):
  for xzValue in txzValues:
    if xzValue is not zNotProvided:
      return xzValue;
  raise AssertionError("No value has been provided");

def fxzGetFirstProvidedValueIfAny(*txzValues):
  for xzValue in txzValues:
    if xzValue is not zNotProvided:
      return xzValue;
  return zNotProvided;

def fx0GetFirstProvidedValueOrNone(*txzValues):
  for xzValue in txzValues:
    if xzValue is not zNotProvided:
      return xzValue;
  return None;

def fx0GetProvidedValueOrNone(xzValue):
  return xzValue if xzValue is not zNotProvided else None;
