import unittest
from cgi import FieldStorage, MiniFieldStorage

from roundup import hyperdb
from roundup.date import Date, Interval
from roundup.cgi.actions import *
from roundup.cgi.client import add_message
from roundup.cgi.exceptions import Redirect, Unauthorised, SeriousError, FormError

from mocknull import MockNull

def true(*args, **kwargs):
    return 1

class ActionTestCase(unittest.TestCase):
    def setUp(self):
        self.form = FieldStorage(environ={'QUERY_STRING': ''})
        self.client = MockNull()
        self.client._ok_message = []
        self.client._error_message = []
        self.client.add_error_message = lambda x : add_message(
            self.client._error_message, x)
        self.client.add_ok_message = lambda x : add_message(
            self.client._ok_message, x)
        self.client.form = self.form
        self.client.base = "http://whoami.com/path/"
        class TemplatingUtils:
            pass
        self.client.instance.interfaces.TemplatingUtils = TemplatingUtils

class ShowActionTestCase(ActionTestCase):
    def assertRaisesMessage(self, exception, callable, message, *args,
                            **kwargs):
        """An extension of assertRaises, which also checks the exception
        message. We need this because we rely on exception messages when
        redirecting.
        """
        try:
            callable(*args, **kwargs)
        except exception as msg:
            self.assertEqual(str(msg), message)
        else:
            if hasattr(exception, '__name__'):
                excName = exception.__name__
            else:
                excName = str(exception)
            raise self.failureException, excName

    def testShowAction(self):
        self.client.base = 'BASE/'

        action = ShowAction(self.client)
        self.assertRaises(ValueError, action.handle)

        self.form.value.append(MiniFieldStorage('@type', 'issue'))
        self.assertRaises(SeriousError, action.handle)

        self.form.value.append(MiniFieldStorage('@number', '1'))
        self.assertRaisesMessage(Redirect, action.handle, 'BASE/issue1')

    def testShowActionNoType(self):
        action = ShowAction(self.client)
        self.assertRaises(ValueError, action.handle)
        self.form.value.append(MiniFieldStorage('@number', '1'))
        self.assertRaisesMessage(ValueError, action.handle,
            'No type specified')

class RetireActionTestCase(ActionTestCase):
    def testRetireAction(self):
        self.client.db.security.hasPermission = true
        self.client._ok_message = []
        RetireAction(self.client).handle()
        self.assert_(len(self.client._ok_message) == 1)

    def testNoPermission(self):
        self.assertRaises(Unauthorised, RetireAction(self.client).execute)

    def testDontRetireAdminOrAnonymous(self):
        self.client.db.security.hasPermission=true
        # look up the user class
        self.client.classname = 'user'
        # but always look up admin, regardless of nodeid
        self.client.db.user.get = lambda a,b: 'admin'
        self.assertRaises(ValueError, RetireAction(self.client).handle)
        # .. or anonymous
        self.client.db.user.get = lambda a,b: 'anonymous'
        self.assertRaises(ValueError, RetireAction(self.client).handle)

class RestoreActionTestCase(ActionTestCase):
    # This is a copy of the RetireActionTestCase. But what do these
    # actually test? I see no actual db or retire call or
    # class id. Testing db level restore is covered in the
    # db_test_base as part of retire.
    def testRestoreAction(self):
        self.client.db.security.hasPermission = true
        self.client._ok_message = []
        RestoreAction(self.client).handle()
        self.assert_(len(self.client._ok_message) == 1)

    def testNoPermission(self):
        self.assertRaises(Unauthorised, RestoreAction(self.client).execute)

class SearchActionTestCase(ActionTestCase):
    def setUp(self):
        ActionTestCase.setUp(self)
        self.action = SearchAction(self.client)

class StandardSearchActionTestCase(SearchActionTestCase):
    def testNoPermission(self):
        self.assertRaises(Unauthorised, self.action.execute)

    def testQueryName(self):
        self.assertEqual(self.action.getQueryName(), '')

        self.form.value.append(MiniFieldStorage('@queryname', 'foo'))
        self.assertEqual(self.action.getQueryName(), 'foo')

class FakeFilterVarsTestCase(SearchActionTestCase):
    def setUp(self):
        SearchActionTestCase.setUp(self)
        self.client.db.classes.get_transitive_prop = lambda x: \
            hyperdb.Multilink('foo')

    def assertFilterEquals(self, expected):
        self.action.fakeFilterVars()
        self.assertEqual(self.form.getvalue('@filter'), expected)

    def testEmptyMultilink(self):
        self.form.value.append(MiniFieldStorage('foo', ''))
        self.form.value.append(MiniFieldStorage('foo', ''))

        self.assertFilterEquals(None)

    def testNonEmptyMultilink(self):
        self.form.value.append(MiniFieldStorage('foo', ''))
        self.form.value.append(MiniFieldStorage('foo', '1'))

        self.assertFilterEquals('foo')

    def testEmptyKey(self):
        self.form.value.append(MiniFieldStorage('foo', ''))
        self.assertFilterEquals(None)

    def testStandardKey(self):
        self.form.value.append(MiniFieldStorage('foo', '1'))
        self.assertFilterEquals('foo')

    def testStringKey(self):
        self.client.db.classes.getprops = lambda: {'foo': hyperdb.String()}
        self.form.value.append(MiniFieldStorage('foo', 'hello'))
        self.assertFilterEquals('foo')

    def testNumKey(self): # testing patch: http://hg.python.org/tracker/roundup/rev/98508a47c126
        for val in [ "-1000a", "test", "o0.9999", "o0", "1.00/10" ]:
            print "testing ", val
            self.client.db.classes.get_transitive_prop = lambda x: hyperdb.Number()
            self.form.value.append(MiniFieldStorage('foo', val)) # invalid numbers
            self.assertRaises(FormError, self.action.fakeFilterVars)
            del self.form.value[:]

        for val in [ "-1000.7738", "-556", "-0.9999", "-.456", "-5E-5", "0.00", "0",
                     "1.00", "0556", "7.56E2", "1000.7738"]:
            self.form.value.append(MiniFieldStorage('foo', val))
            self.action.fakeFilterVars() # this should run and return. No errors, nothing to check.
            del self.form.value[:]

    def testIntKey(self): # testing patch: http://hg.python.org/tracker/roundup/rev/98508a47c126
        for val in [ "-1000a", "test", "-5E-5", "0.9999", "0.0", "1.000", "0456", "1E4" ]:
            print "testing ", val
            self.client.db.classes.get_transitive_prop = lambda x: hyperdb.Integer()
            self.form.value.append(MiniFieldStorage('foo', val))
            self.assertRaises(FormError, self.action.fakeFilterVars)
            del self.form.value[:]

        for val in [ "-1000", "-512", "0", "1", "100", "248" ]: # no scientific notation apparently
            self.client.db.classes.get_transitive_prop = lambda x: hyperdb.Integer()
            self.form.value.append(MiniFieldStorage('foo', val))
            self.action.fakeFilterVars() # this should run and return. No errors, nothing to check.
            del self.form.value[:]

    def testTokenizedStringKey(self):
        self.client.db.classes.get_transitive_prop = lambda x: hyperdb.String()
        self.form.value.append(MiniFieldStorage('foo', 'hello world'))

        self.assertFilterEquals('foo')

        # The single value gets replaced with the tokenized list.
        self.assertEqual([x.value for x in self.form['foo']],
            ['hello', 'world'])

class CollisionDetectionTestCase(ActionTestCase):
    def setUp(self):
        ActionTestCase.setUp(self)
        self.action = EditItemAction(self.client)
        self.now = Date('.')
        # round off for testing
        self.now.second = int(self.now.second)

    def testLastUserActivity(self):
        self.assertEqual(self.action.lastUserActivity(), None)

        self.client.form.value.append(
            MiniFieldStorage('@lastactivity', str(self.now)))
        self.assertEqual(self.action.lastUserActivity(), self.now)

    def testLastNodeActivity(self):
        self.action.classname = 'issue'
        self.action.nodeid = '1'

        def get(nodeid, propname):
            self.assertEqual(nodeid, '1')
            self.assertEqual(propname, 'activity')
            return self.now
        self.client.db.issue.get = get

        self.assertEqual(self.action.lastNodeActivity(), self.now)

    def testCollision(self):
        # fake up an actual change
        self.action.classname = 'test'
        self.action.nodeid = '1'
        self.client.parsePropsFromForm = lambda: ({('test','1'):{1:1}}, [])
        self.failUnless(self.action.detectCollision(self.now,
            self.now + Interval("1d")))
        self.failIf(self.action.detectCollision(self.now,
            self.now - Interval("1d")))
        self.failIf(self.action.detectCollision(None, self.now))

class LoginTestCase(ActionTestCase):
    def setUp(self):
        ActionTestCase.setUp(self)
        self.client._error_message = []

        # set the db password to 'right'
        self.client.db.user.get = lambda a,b: 'right'

        # unless explicitly overridden, we should never get here
        self.client.opendb = lambda a: self.fail(
            "Logged in, but we shouldn't be.")

    def assertRaisesMessage(self, exception, callable, message, *args,
                            **kwargs):
        """An extension of assertRaises, which also checks the exception
        message. We need this because we rely on exception messages when
        redirecting.
        """
        try:
            callable(*args, **kwargs)
        except exception as msg:
            self.assertEqual(str(msg), message)
        else:
            if hasattr(exception, '__name__'):
                excName = exception.__name__
            else:
                excName = str(exception)
            raise self.failureException, excName

    def assertLoginLeavesMessages(self, messages, username=None, password=None):
        if username is not None:
            self.form.value.append(MiniFieldStorage('__login_name', username))
        if password is not None:
            self.form.value.append(
                MiniFieldStorage('__login_password', password))

        LoginAction(self.client).handle()
        self.assertEqual(self.client._error_message, messages)

    def assertLoginRaisesRedirect(self, message, username=None, password=None, came_from=None):
        if username is not None:
            self.form.value.append(MiniFieldStorage('__login_name', username))
        if password is not None:
            self.form.value.append(
                MiniFieldStorage('__login_password', password))
        if came_from is not None:
            self.form.value.append(
                MiniFieldStorage('__came_from', came_from))

        self.assertRaisesMessage(Redirect, LoginAction(self.client).handle, message)

    def testNoUsername(self):
        self.assertLoginLeavesMessages(['Username required'])

    def testInvalidUsername(self):
        def raiseKeyError(a):
            raise KeyError
        self.client.db.user.lookup = raiseKeyError
        self.assertLoginLeavesMessages(['Invalid login'], 'foo')

    def testInvalidPassword(self):
        self.assertLoginLeavesMessages(['Invalid login'], 'foo', 'wrong')

    def testNoWebAccess(self):
        self.assertLoginLeavesMessages(['You do not have permission to login'],
                                        'foo', 'right')

    def testCorrectLogin(self):
        self.client.db.security.hasPermission = lambda *args, **kwargs: True

        def opendb(username):
            self.assertEqual(username, 'foo')
        self.client.opendb = opendb

        self.assertLoginLeavesMessages([], 'foo', 'right')

    def testCorrectLoginRedirect(self):
        self.client.db.security.hasPermission = lambda *args, **kwargs: True
        def opendb(username):
            self.assertEqual(username, 'foo')
        self.client.opendb = opendb

        # basic test with query
        self.assertLoginRaisesRedirect("http://whoami.com/path/issue?%40action=search",
                                 'foo', 'right', "http://whoami.com/path/issue?@action=search")

        # test that old messages are removed
        self.form.value[:] = []         # clear out last test's setup values
        self.assertLoginRaisesRedirect("http://whoami.com/path/issue?%40action=search",
                                 'foo', 'right', "http://whoami.com/path/issue?@action=search&@ok_messagehurrah+we+win&@error_message=blam")

        # test when there is no query
        self.form.value[:] = []         # clear out last test's setup values
        self.assertLoginRaisesRedirect("http://whoami.com/path/issue255",
                                 'foo', 'right', "http://whoami.com/path/issue255")

        # test if we are logged out; should kill the @action=logout
        self.form.value[:] = []         # clear out last test's setup values
        self.assertLoginRaisesRedirect("http://whoami.com/path/issue39?%40startwith=0&%40pagesize=50",
                                 'foo', 'right', "http://whoami.com/path/issue39?@action=logout&@pagesize=50&@startwith=0")

    def testInvalidLoginRedirect(self):
        self.client.db.security.hasPermission = lambda *args, **kwargs: True

        def opendb(username):
            self.assertEqual(username, 'foo')
        self.client.opendb = opendb

        # basic test with query
        self.assertLoginRaisesRedirect("http://whoami.com/path/issue?%40error_message=Invalid+login&%40action=search",
                                 'foo', 'wrong', "http://whoami.com/path/issue?@action=search")

        # test that old messages are removed
        self.form.value[:] = []         # clear out last test's setup values
        self.assertLoginRaisesRedirect("http://whoami.com/path/issue?%40error_message=Invalid+login&%40action=search",
                                 'foo', 'wrong', "http://whoami.com/path/issue?@action=search&@ok_messagehurrah+we+win&@error_message=blam")

        # test when there is no __came_from specified
        self.form.value[:] = []         # clear out last test's setup values
        # I am not sure why this produces three copies of the same error.
        # only one copy of the error is displayed to the user in the web interface.
        self.assertLoginLeavesMessages(['Invalid login', 'Invalid login', 'Invalid login'], 'foo', 'wrong')

        # test when there is no query
        self.form.value[:] = []         # clear out last test's setup values
        self.assertLoginRaisesRedirect("http://whoami.com/path/issue255?%40error_message=Invalid+login",
                                 'foo', 'wrong', "http://whoami.com/path/issue255")

class EditItemActionTestCase(ActionTestCase):
    def setUp(self):
        ActionTestCase.setUp(self)
        self.result = []
        self.new_id = 16
        class AppendResult:
            def __init__(inner_self, name):
                inner_self.name = name
            def __call__(inner_self, *args, **kw):
                self.result.append((inner_self.name, args, kw))
                if inner_self.name == 'set':
                    return kw
                self.new_id+=1
                return str(self.new_id)

        self.client.db.security.hasPermission = true
        self.client.classname = 'issue'
        self.client.base = 'http://tracker/'
        self.client.nodeid = '4711'
        self.client.template = 'item'
        self.client.db.classes.create = AppendResult('create')
        self.client.db.classes.set = AppendResult('set')
        self.client.db.classes.getprops = lambda: \
            ({'messages':hyperdb.Multilink('msg')
             ,'content':hyperdb.String()
             ,'files':hyperdb.Multilink('file')
             ,'msg':hyperdb.Link('msg')
             })
        self.action = EditItemAction(self.client)

    def testMessageAttach(self):
        expect = \
            [ ('create',(),{'content':'t'})
            , ('set',('4711',), {'messages':['23','42','17']})
            ]
        self.client.db.classes.get = lambda a, b:['23','42']
        self.client.parsePropsFromForm = lambda: \
            ( {('msg','-1'):{'content':'t'},('issue','4711'):{}}
            , [('issue','4711','messages',[('msg','-1')])]
            )
        try :
            self.action.handle()
        except Redirect as msg:
            pass
        self.assertEqual(expect, self.result)

    def testMessageMultiAttach(self):
        expect = \
            [ ('create',(),{'content':'t2'})
            , ('create',(),{'content':'t'})
            , ('set',('4711',), {'messages':['23','42','17','18']})
            ]
        self.client.db.classes.get = lambda a, b:['23','42']
        self.client.parsePropsFromForm = lambda: \
            ( {('msg','-1'):{'content':'t'},('msg','-2'):{'content':'t2'}
              , ('issue','4711'):{}}
            , [('issue','4711','messages',[('msg','-1'),('msg','-2')])]
            )
        try :
            self.action.handle()
        except Redirect as msg:
            pass
        self.assertEqual(expect, self.result)

    def testFileAttach(self):
        expect = \
            [('create',(),{'content':'t','type':'text/plain','name':'t.txt'})
            ,('set',('4711',),{'files':['23','42','17']})
            ]
        self.client.db.classes.get = lambda a, b:['23','42']
        self.client.parsePropsFromForm = lambda: \
            ( {('file','-1'):{'content':'t','type':'text/plain','name':'t.txt'}
              ,('issue','4711'):{}
              }
            , [('issue','4711','messages',[('msg','-1')])
              ,('issue','4711','files',[('file','-1')])
              ,('msg','-1','files',[('file','-1')])
              ]
            )
        try :
            self.action.handle()
        except Redirect as msg:
            pass
        self.assertEqual(expect, self.result)

    def testLinkExisting(self):
        expect = [('set',('4711',),{'messages':['23','42','1']})]
        self.client.db.classes.get = lambda a, b:['23','42']
        self.client.parsePropsFromForm = lambda: \
            ( {('issue','4711'):{},('msg','1'):{}}
            , [('issue','4711','messages',[('msg','1')])]
            )
        try :
            self.action.handle()
        except Redirect as msg:
            pass
        self.assertEqual(expect, self.result)

    def testLinkNewToExisting(self):
        expect = [('create',(),{'msg':'1','title':'TEST'})]
        self.client.db.classes.get = lambda a, b:['23','42']
        self.client.parsePropsFromForm = lambda: \
            ( {('issue','-1'):{'title':'TEST'},('msg','1'):{}}
            , [('issue','-1','msg',[('msg','1')])]
            )
        try :
            self.action.handle()
        except Redirect as msg:
            pass
        self.assertEqual(expect, self.result)

# vim: set et sts=4 sw=4 :
