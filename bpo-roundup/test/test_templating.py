import unittest
from cgi import FieldStorage, MiniFieldStorage

from roundup.cgi.templating import *
from test_actions import MockNull, true

class MockDatabase(MockNull):
    def getclass(self, name):
        return self.classes[name]

    # setup for csrf testing of otks database api
    storage = {}
    def set(self, key, **props):
        MockDatabase.storage[key] = {}
        MockDatabase.storage[key].update(props)

    def get(self, key, field, default=None):
        if key not in MockDatabase.storage:
            return default
        return MockDatabase.storage[key][field]

    def exists(self,key):
        return key in MockDatabase.storage

    def getOTKManager(self):
        return MockDatabase()

class TemplatingTestCase(unittest.TestCase):
    def setUp(self):
        self.form = FieldStorage()
        self.client = MockNull()
        self.client.db = db = MockDatabase()
        db.security.hasPermission = lambda *args, **kw: True
        self.client.form = self.form

        # add client props for testing anti_csrf_nonce
        self.client.session_api = MockNull(_sid="1234567890")
        self.client.db.getuid = lambda : 10
        self.client.db.config = {'WEB_CSRF_TOKEN_LIFETIME': 10 }

class HTMLDatabaseTestCase(TemplatingTestCase):
    def test_HTMLDatabase___getitem__(self):
        db = HTMLDatabase(self.client)
        self.assert_(isinstance(db['issue'], HTMLClass))
        # following assertions are invalid
        # since roundup/cgi/templating.py r1.173.
        # HTMLItem is function, not class,
        # but HTMLUserClass and HTMLUser are passed on.
        # these classes are no more.  they have ceased to be.
        #self.assert_(isinstance(db['user'], HTMLUserClass))
        #self.assert_(isinstance(db['issue1'], HTMLItem))
        #self.assert_(isinstance(db['user1'], HTMLUser))

    def test_HTMLDatabase___getattr__(self):
        db = HTMLDatabase(self.client)
        self.assert_(isinstance(db.issue, HTMLClass))
        # see comment in test_HTMLDatabase___getitem__
        #self.assert_(isinstance(db.user, HTMLUserClass))
        #self.assert_(isinstance(db.issue1, HTMLItem))
        #self.assert_(isinstance(db.user1, HTMLUser))

    def test_HTMLDatabase_classes(self):
        db = HTMLDatabase(self.client)
        db._db.classes = {'issue':MockNull(), 'user': MockNull()}
        db.classes()

class FunctionsTestCase(TemplatingTestCase):
    def test_lookupIds(self):
        db = HTMLDatabase(self.client)
        def lookup(key):
            if key == 'ok':
                return '1'
            if key == 'fail':
                raise KeyError, 'fail'
            return key
        db._db.classes = {'issue': MockNull(lookup=lookup)}
        prop = MockNull(classname='issue')
        self.assertEqual(lookupIds(db._db, prop, ['1','2']), ['1','2'])
        self.assertEqual(lookupIds(db._db, prop, ['ok','2']), ['1','2'])
        self.assertEqual(lookupIds(db._db, prop, ['ok', 'fail'], 1),
            ['1', 'fail'])
        self.assertEqual(lookupIds(db._db, prop, ['ok', 'fail']), ['1'])

    def test_lookupKeys(self):
        db = HTMLDatabase(self.client)
        def get(entry, key):
            return {'1': 'green', '2': 'eggs'}.get(entry, entry)
        shrubbery = MockNull(get=get)
        db._db.classes = {'shrubbery': shrubbery}
        self.assertEqual(lookupKeys(shrubbery, 'spam', ['1','2']),
            ['green', 'eggs'])
        self.assertEqual(lookupKeys(shrubbery, 'spam', ['ok','2']), ['ok',
            'eggs'])

class HTMLClassTestCase(TemplatingTestCase) :

    def test_link(self):
        """Make sure lookup of a Link property works even in the
        presence of multiple values in the form."""
        def lookup(key) :
            self.assertEqual(key, key.strip())
            return "Status%s"%key
        self.form.list.append(MiniFieldStorage("status", "1"))
        self.form.list.append(MiniFieldStorage("status", "2"))
        status = hyperdb.Link("status")
        self.client.db.classes = dict \
            ( issue = MockNull(getprops = lambda : dict(status = status))
            , status  = MockNull(get = lambda id, name : id, lookup = lookup)
            )
        cls = HTMLClass(self.client, "issue")
        cls["status"]

    def test_multilink(self):
        """`lookup` of an item will fail if leading or trailing whitespace
           has not been stripped.
        """
        def lookup(key) :
            self.assertEqual(key, key.strip())
            return "User%s"%key
        self.form.list.append(MiniFieldStorage("nosy", "1, 2"))
        nosy = hyperdb.Multilink("user")
        self.client.db.classes = dict \
            ( issue = MockNull(getprops = lambda : dict(nosy = nosy))
            , user  = MockNull(get = lambda id, name : id, lookup = lookup)
            )
        cls = HTMLClass(self.client, "issue")
        cls["nosy"]

    def test_anti_csrf_nonce(self):
        '''call the csrf creation function and do basic length test

           Store the data in a mock db with the same api as the otk
           db. Make sure nonce is 64 chars long. Lookup the nonce in
           db and retrieve data. Verify that the nonce lifetime is
           correct (within 1 second of 1 week - lifetime), the uid is
           correct (1), the dummy sid is correct.

           Consider three cases:
             * create nonce via module function setting lifetime
             * create nonce via TemplatingUtils method setting lifetime
             * create nonce via module function with default lifetime

        '''

        # the value below is number of seconds in a week.
        week_seconds = 604800

        otks=self.client.db.getOTKManager()

        for test in [ 'module', 'template', 'default_time' ]:
            print "Testing:", test
            
            if test == 'module':
                # test the module function
                nonce1 = anti_csrf_nonce(self, self.client, lifetime=1)
                # lifetime * 60 is the offset
                greater_than = week_seconds - 1 * 60
            elif test == 'template':
                # call the function through the TemplatingUtils class
                cls = TemplatingUtils(self.client)
                nonce1 = cls.anti_csrf_nonce(lifetime=5)
                greater_than = week_seconds - 5 * 60
            elif test == 'default_time':
                # use the module function but with no lifetime
                nonce1 = anti_csrf_nonce(self, self.client)
                # see above for web nonce lifetime.
                greater_than = week_seconds - 10 * 60

            self.assertEqual(len(nonce1), 64)

            uid = otks.get(nonce1, 'uid', default=None)
            sid = otks.get(nonce1, 'sid', default=None)
            timestamp = otks.get(nonce1, '__timestamp', default=None)

            self.assertEqual(uid, 10) 
            self.assertEqual(sid, self.client.session_api._sid)

            now = time.time()

            print "now, timestamp, greater, difference", \
                     now, timestamp, greater_than, now - timestamp

        
            # lower bound of the difference is above. Upper bound
            # of difference is run time between time.time() in
            # the call to anti_csrf_nonce and the time.time() call
            # that assigns ts above. I declare that difference
            # to be less than 1 second for this to pass.
            self.assertEqual(True,
                       greater_than <= now - timestamp < (greater_than + 1) )

    def test_string_url_quote(self):
        ''' test that urlquote quotes the string '''
        p = StringHTMLProperty(self.client, 'test', '1', None, 'test', 'test string< foo@bar')
        self.assertEqual(p.url_quote(), 'test%20string%3C%20foo%40bar')

    def test_string_email(self):
        ''' test that email obscures the email '''
        p = StringHTMLProperty(self.client, 'test', '1', None, 'test', 'rouilj@foo.example.com')
        self.assertEqual(p.email(), 'rouilj at foo example ...')

    def test_string_plain_or_hyperlinked(self):
        ''' test that email obscures the email '''
        p = StringHTMLProperty(self.client, 'test', '1', None, 'test', 'A string <b> with rouilj@example.com embedded &lt; html</b>')
        self.assertEqual(p.plain(), 'A string <b> with rouilj@example.com embedded &lt; html</b>')
        self.assertEqual(p.plain(escape=1), 'A string &lt;b&gt; with rouilj@example.com embedded &amp;lt; html&lt;/b&gt;')
        self.assertEqual(p.plain(hyperlink=1), 'A string &lt;b&gt; with <a href="mailto:rouilj@example.com">rouilj@example.com</a> embedded &amp;lt; html&lt;/b&gt;')
        self.assertEqual(p.plain(escape=1, hyperlink=1), 'A string &lt;b&gt; with <a href="mailto:rouilj@example.com">rouilj@example.com</a> embedded &amp;lt; html&lt;/b&gt;')

        self.assertEqual(p.hyperlinked(), 'A string &lt;b&gt; with <a href="mailto:rouilj@example.com">rouilj@example.com</a> embedded &amp;lt; html&lt;/b&gt;')

    def test_string_field(self):
        p = StringHTMLProperty(self.client, 'test', '1', None, 'test', 'A string <b> with rouilj@example.com embedded &lt; html</b>')
        self.assertEqual(p.field(), '<input type="text" name="test1@test" value="A string &lt;b&gt; with rouilj@example.com embedded &amp;lt; html&lt;/b&gt;" size="30">')

    def test_string_multiline(self):
        p = StringHTMLProperty(self.client, 'test', '1', None, 'test', 'A string <b> with rouilj@example.com embedded &lt; html</b>')
        self.assertEqual(p.multiline(), '<textarea  name="test1@test" id="test1@test" rows="5" cols="40">A string &lt;b&gt; with rouilj@example.com embedded &amp;lt; html&lt;/b&gt;</textarea>')
        self.assertEqual(p.multiline(rows=300, cols=100, **{'class':'css_class'}), '<textarea class="css_class" name="test1@test" id="test1@test" rows="300" cols="100">A string &lt;b&gt; with rouilj@example.com embedded &amp;lt; html&lt;/b&gt;</textarea>')

    def test_url_match(self):
        '''Test the URL regular expression in StringHTMLProperty.
        '''
        def t(s, nothing=False, **groups):
            m = StringHTMLProperty.hyper_re.search(s)
            if nothing:
                if m:
                    self.assertEquals(m, None, '%r matched (%r)'%(s, m.groupdict()))
                return
            else:
                self.assertNotEquals(m, None, '%r did not match'%s)
            d = m.groupdict()
            for g in groups:
                self.assertEquals(d[g], groups[g], '%s %r != %r in %r'%(g, d[g],
                    groups[g], s))

        #t('123.321.123.321', 'url')
        t('http://localhost/', url='http://localhost/')
        t('http://roundup.net/', url='http://roundup.net/')
        t('http://richard@localhost/', url='http://richard@localhost/')
        t('http://richard:sekrit@localhost/',
            url='http://richard:sekrit@localhost/')
        t('<HTTP://roundup.net/>', url='HTTP://roundup.net/')
        t('www.a.ex', url='www.a.ex')
        t('foo.a.ex', nothing=True)
        t('StDevValidTimeSeries.GetObservation', nothing=True)
        t('http://a.ex', url='http://a.ex')
        t('http://a.ex/?foo&bar=baz\\.@!$%()qwerty',
            url='http://a.ex/?foo&bar=baz\\.@!$%()qwerty')
        t('www.foo.net', url='www.foo.net')
        t('richard@com.example', email='richard@com.example')
        t('r@a.com', email='r@a.com')
        t('i1', **{'class':'i', 'id':'1'})
        t('item123', **{'class':'item', 'id':'123'})
        t('www.user:pass@host.net', email='pass@host.net')
        t('user:pass@www.host.net', url='user:pass@www.host.net')
        t('123.35', nothing=True)
        t('-.3535', nothing=True)

    def test_url_replace(self):
        p = StringHTMLProperty(self.client, 'test', '1', None, 'test', '')
        def t(s): return p.hyper_re.sub(p._hyper_repl, s)
        ae = self.assertEqual
        ae(t('item123123123123'), 'item123123123123')
        ae(t('http://roundup.net/'),
           '<a href="http://roundup.net/" rel="nofollow">http://roundup.net/</a>')
        ae(t('&lt;HTTP://roundup.net/&gt;'),
           '&lt;<a href="HTTP://roundup.net/" rel="nofollow">HTTP://roundup.net/</a>&gt;')
        ae(t('&lt;http://roundup.net/&gt;.'),
            '&lt;<a href="http://roundup.net/" rel="nofollow">http://roundup.net/</a>&gt;.')
        ae(t('&lt;www.roundup.net&gt;'),
           '&lt;<a href="http://www.roundup.net" rel="nofollow">www.roundup.net</a>&gt;')
        ae(t('(www.roundup.net)'),
           '(<a href="http://www.roundup.net" rel="nofollow">www.roundup.net</a>)')
        ae(t('foo http://msdn.microsoft.com/en-us/library/ms741540(VS.85).aspx bar'),
           'foo <a href="http://msdn.microsoft.com/en-us/library/ms741540(VS.85).aspx" rel="nofollow">'
           'http://msdn.microsoft.com/en-us/library/ms741540(VS.85).aspx</a> bar')
        ae(t('(e.g. http://en.wikipedia.org/wiki/Python_(programming_language))'),
           '(e.g. <a href="http://en.wikipedia.org/wiki/Python_(programming_language)" rel="nofollow">'
           'http://en.wikipedia.org/wiki/Python_(programming_language)</a>)')
        ae(t('(e.g. http://en.wikipedia.org/wiki/Python_(programming_language)).'),
           '(e.g. <a href="http://en.wikipedia.org/wiki/Python_(programming_language)" rel="nofollow">'
           'http://en.wikipedia.org/wiki/Python_(programming_language)</a>).')
        ae(t('(e.g. http://en.wikipedia.org/wiki/Python_(programming_language))&gt;.'),
           '(e.g. <a href="http://en.wikipedia.org/wiki/Python_(programming_language)" rel="nofollow">'
           'http://en.wikipedia.org/wiki/Python_(programming_language)</a>)&gt;.')
        ae(t('(e.g. http://en.wikipedia.org/wiki/Python_(programming_language&gt;)).'),
           '(e.g. <a href="http://en.wikipedia.org/wiki/Python_(programming_language" rel="nofollow">'
           'http://en.wikipedia.org/wiki/Python_(programming_language</a>&gt;)).')
        for c in '.,;:!':
            # trailing punctuation is not included
            ae(t('http://roundup.net/%c ' % c),
               '<a href="http://roundup.net/" rel="nofollow">http://roundup.net/</a>%c ' % c)
            # but it's included if it's part of the URL
            ae(t('http://roundup.net/%c/' % c),
               '<a href="http://roundup.net/%c/" rel="nofollow">http://roundup.net/%c/</a>' % (c, c))

'''
class HTMLPermissions:
    def is_edit_ok(self):
    def is_view_ok(self):
    def is_only_view_ok(self):
    def view_check(self):
    def edit_check(self):

def input_html4(**attrs):
def input_xhtml(**attrs):

class HTMLInputMixin:
    def __init__(self):

class HTMLClass(HTMLInputMixin, HTMLPermissions):
    def __init__(self, client, classname, anonymous=0):
    def __repr__(self):
    def __getitem__(self, item):
    def __getattr__(self, attr):
    def designator(self):
    def getItem(self, itemid, num_re=re.compile('-?\d+')):
    def properties(self, sort=1, cansearch=True):
    def list(self, sort_on=None):
    def csv(self):
    def propnames(self):
    def filter(self, request=None, filterspec={}, sort=(None,None),
    def classhelp(self, properties=None, label='(list)', width='500',
    def submit(self, label="Submit New Entry"):
    def history(self):
    def renderWith(self, name, **kwargs):

class HTMLItem(HTMLInputMixin, HTMLPermissions):
    def __init__(self, client, classname, nodeid, anonymous=0):
    def __repr__(self):
    def __getitem__(self, item):
    def __getattr__(self, attr):
    def designator(self):
    def is_retired(self):
    def submit(self, label="Submit Changes"):
    def journal(self, direction='descending'):
    def history(self, direction='descending', dre=re.compile('\d+')):
    def renderQueryForm(self):

class HTMLUserPermission:
    def is_edit_ok(self):
    def is_view_ok(self):
    def _user_perm_check(self, type):

class HTMLUserClass(HTMLUserPermission, HTMLClass):

class HTMLUser(HTMLUserPermission, HTMLItem):
    def __init__(self, client, classname, nodeid, anonymous=0):
    def hasPermission(self, permission, classname=_marker):

class HTMLProperty(HTMLInputMixin, HTMLPermissions):
    def __init__(self, client, classname, nodeid, prop, name, value,
    def __repr__(self):
    def __str__(self):
    def __cmp__(self, other):
    def is_edit_ok(self):
    def is_view_ok(self):

class StringHTMLProperty(HTMLProperty):
    def _hyper_repl(self, match):
    def hyperlinked(self):
    def plain(self, escape=0, hyperlink=0):
    def stext(self, escape=0):
    def field(self, size = 30):
    def multiline(self, escape=0, rows=5, cols=40):
    def email(self, escape=1):

class PasswordHTMLProperty(HTMLProperty):
    def plain(self):
    def field(self, size = 30):
    def confirm(self, size = 30):

class NumberHTMLProperty(HTMLProperty):
    def plain(self):
    def field(self, size = 30):
    def __int__(self):
    def __float__(self):

class IntegerHTMLProperty(HTMLProperty):
    def plain(self):
    def field(self, size = 30):
    def __int__(self):

class BooleanHTMLProperty(HTMLProperty):
    def plain(self):
    def field(self):

class DateHTMLProperty(HTMLProperty):
    def plain(self):
    def now(self):
    def field(self, size = 30):
    def reldate(self, pretty=1):
    def pretty(self, format=_marker):
    def local(self, offset):

class IntervalHTMLProperty(HTMLProperty):
    def plain(self):
    def pretty(self):
    def field(self, size = 30):

class LinkHTMLProperty(HTMLProperty):
    def __init__(self, *args, **kw):
    def __getattr__(self, attr):
    def plain(self, escape=0):
    def field(self, showid=0, size=None):
    def menu(self, size=None, height=None, showid=0, additional=[],

class MultilinkHTMLProperty(HTMLProperty):
    def __init__(self, *args, **kwargs):
    def __len__(self):
    def __getattr__(self, attr):
    def __getitem__(self, num):
    def __contains__(self, value):
    def reverse(self):
    def plain(self, escape=0):
    def field(self, size=30, showid=0):
    def menu(self, size=None, height=None, showid=0, additional=[],

def make_sort_function(db, classname, sort_on=None):
    def sortfunc(a, b):

def find_sort_key(linkcl):

def handleListCGIValue(value):

class ShowDict:
    def __init__(self, columns):
    def __getitem__(self, name):

class HTMLRequest(HTMLInputMixin):
    def __init__(self, client):
    def _post_init(self):
    def updateFromURL(self, url):
    def update(self, kwargs):
    def description(self):
    def __str__(self):
    def indexargs_form(self, columns=1, sort=1, group=1, filter=1,
    def indexargs_url(self, url, args):
    def base_javascript(self):
    def batch(self):

class Batch(ZTUtils.Batch):
    def __init__(self, client, sequence, size, start, end=0, orphan=0,
    def __getitem__(self, index):
    def propchanged(self, property):
    def previous(self):
    def next(self):

#class TemplatingUtils:
#    def __init__(self, client):
#    def Batch(self, sequence, size, start, end=0, orphan=0, overlap=0):

class NoTemplate(Exception):
class Unauthorised(Exception):
    def __init__(self, action, klass):
    def __str__(self):

class Loader:
    def __init__(self, dir):
    def precompileTemplates(self):
    def load(self, name, extension=None):
    def __getitem__(self, name):

class RoundupPageTemplate(PageTemplate.PageTemplate):
    def getContext(self, client, classname, request):
    def render(self, client, classname, request, **options):
    def __repr__(self):
'''

# vim: set et sts=4 sw=4 :
