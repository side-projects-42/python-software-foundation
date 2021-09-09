# Copyright (c) 2003 Richard Jones (richard@mechanicalcat.net)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
#$Id: userauditor.py,v 1.3 2006/09/18 03:24:38 tobias-herp Exp $

import re
import urlparse

valid_username = re.compile(r'^[a-z0-9_.-]+$', re.IGNORECASE)


def audit_user_fields(db, cl, nodeid, newvalues):
    ''' Make sure user properties are valid.

        - email address has no spaces in it
        - roles specified exist
    '''
    if 'username' in newvalues:
        if not valid_username.match(newvalues['username']):
            raise ValueError(
                'Username must consist only of the letters a-z (any case), '
                'digits 0-9 and the symbols: ._-'
            )

    if newvalues.has_key('address') and ' ' in newvalues['address']:
        raise ValueError, 'Email address must not contain spaces'

    if newvalues.has_key('roles') and newvalues['roles']:
        roles = [x.lower().strip() for x in newvalues['roles'].split(',')]
        for rolename in roles:
            if not db.security.role.has_key(rolename):
                raise ValueError, 'Role "%s" does not exist'%rolename

        if None != nodeid and "admin" in roles:
            if not "admin" in [x.lower().strip() for x in cl.get(nodeid, 'roles').split(",")]:
                raise ValueError, "Only Admins may assign the Admin role!"

    if newvalues.get('homepage'):
        scheme = urlparse.urlparse(newvalues['homepage'])[0]
        if scheme not in ('http', 'https'):
            raise ValueError, "Invalid URL scheme in homepage URL"

def init(db):
    # fire before changes are made
    db.user.audit('set', audit_user_fields)
    db.user.audit('create', audit_user_fields)

# vim: set filetype=python ts=4 sw=4 et si
