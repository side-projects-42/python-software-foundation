import re
import binascii
import email
from email import quoprimime, base64mime

## please import this file if you are using the email module
#
# a "monkey patch" to unify the behaviour of python 2.5 2.6 2.7
# when generating header files, see http://bugs.python.org/issue1974
# and https://hg.python.org/cpython/rev/5deb27042e5a/
# can go away once the minimum requirement is python 2.7
_oldheaderinit = email.Header.Header.__init__
def _unifiedheaderinit(self, *args, **kw):
    # override continuation_ws
    kw['continuation_ws'] = ' '
    _oldheaderinit(self, *args, **kw)
email.Header.Header.__dict__['__init__'] = _unifiedheaderinit
##

# Match encoded-word strings in the form =?charset?q?Hello_World?=
ecre = re.compile(r'''
  =\?                   # literal =?
  (?P<charset>[^?]*?)   # non-greedy up to the next ? is the charset
  \?                    # literal ?
  (?P<encoding>[qb])    # either a "q" or a "b", case insensitive
  \?                    # literal ?
  (?P<encoded>.*?)      # non-greedy up to the next ?= is the encoded string
  \?=                   # literal ?=
  ''', re.VERBOSE | re.IGNORECASE | re.MULTILINE)


# Fixed header parser, see my proposed patch and discussions:
# http://bugs.python.org/issue1079 "decode_header does not follow RFC 2047"
# http://bugs.python.org/issue1467619 "Header.decode_header eats up spaces"
# This implements the decode_header specific parts of my proposed patch
# backported to python2.X
def decode_header(header):
    """Decode a message header value without converting charset.

    Returns a list of (string, charset) pairs containing each of the decoded
    parts of the header.  Charset is None for non-encoded parts of the header,
    otherwise a lower-case string containing the name of the character set
    specified in the encoded string.

    header may be a string that may or may not contain RFC2047 encoded words,
    or it may be a Header object.

    An email.errors.HeaderParseError may be raised when certain decoding error
    occurs (e.g. a base64 decoding exception).
    """
    # If it is a Header object, we can just return the encoded chunks.
    if hasattr(header, '_chunks'):
        return [(_charset._encode(string, str(charset)), str(charset))
                    for string, charset in header._chunks]
    # If no encoding, just return the header with no charset.
    if not ecre.search(header):
        return [(header, None)]
    # First step is to parse all the encoded parts into triplets of the form
    # (encoded_string, encoding, charset).  For unencoded strings, the last
    # two parts will be None.
    words = []
    for line in header.splitlines():
        parts = ecre.split(line)
        first = True
        while parts:
            unencoded = parts.pop(0)
            if first:
                unencoded = unencoded.lstrip()
                first = False
            if unencoded:
                words.append((unencoded, None, None))
            if parts:
                charset = parts.pop(0).lower()
                encoding = parts.pop(0).lower()
                encoded = parts.pop(0)
                words.append((encoded, encoding, charset))
    # Now loop over words and remove words that consist of whitespace
    # between two encoded strings.
    import sys
    droplist = []
    for n, w in enumerate(words):
        if n>1 and w[1] and words[n-2][1] and words[n-1][0].isspace():
            droplist.append(n-1)
    for d in reversed(droplist):
        del words[d]

    # The next step is to decode each encoded word by applying the reverse
    # base64 or quopri transformation.  decoded_words is now a list of the
    # form (decoded_word, charset).
    decoded_words = []
    for encoded_string, encoding, charset in words:
        if encoding is None:
            # This is an unencoded word.
            decoded_words.append((encoded_string, charset))
        elif encoding == 'q':
            word = quoprimime.header_decode(encoded_string)
            decoded_words.append((word, charset))
        elif encoding == 'b':
            paderr = len(encoded_string) % 4   # Postel's law: add missing padding
            if paderr:
                encoded_string += '==='[:4 - paderr]
            try:
                word = base64mime.decode(encoded_string)
            except binascii.Error:
                raise email.errors.HeaderParseError('Base64 decoding error')
            else:
                decoded_words.append((word, charset))
        else:
            raise AssertionError('Unexpected encoding: ' + encoding)
    # Now convert all words to bytes and collapse consecutive runs of
    # similarly encoded words.
    collapsed = []
    last_word = last_charset = None
    for word, charset in decoded_words:
        if isinstance(word, str):
            pass
        if last_word is None:
            last_word = word
            last_charset = charset
        elif charset != last_charset:
            collapsed.append((last_word, last_charset))
            last_word = word
            last_charset = charset
        elif last_charset is None:
            BSPACE = b' '
            last_word += BSPACE + word
        else:
            last_word += word
    collapsed.append((last_word, last_charset))
    return collapsed
