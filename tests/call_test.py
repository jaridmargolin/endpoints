from . import TestCase, skipIf, SkipTest
import os

import testdata

import endpoints
from endpoints.http import Request, Response
from endpoints.call import Controller, Router
from endpoints.exception import CallError
from endpoints.interface import BaseInterface


class Call(BaseInterface):
    """This is just a wrapper to get access to the Interface handling code"""
    def __init__(self, controller_prefix, contents):
        super(Call, self).__init__(
            controller_prefix=controller_prefix,
            request_class=Request,
            response_class=Response,
            router_class=Router
        )

        if isinstance(contents, dict):
            d = {}
            for k, v in contents.items():
                if k:
                    d[".".join([controller_prefix, k])] = v
                else:
                    d[controller_prefix] = v
            self.controllers = testdata.create_modules(d)

        else:
            self.controller = testdata.create_module(controller_prefix, contents=contents)

        self.method = "GET"

    def create_request(self, path):
        req = self.request_class()
        req.method = self.method
        req.path = path
        return req

    def handle(self, path):
        """This isn't technically needed but just makes it explicit you pass in the
        path you want and this will translate that and handle the request

        :param path: string, full URI you are requesting (eg, /foo/bar)
        """
        return super(Call, self).handle(path)


def create_modules(controller_prefix):
    d = {
        controller_prefix: os.linesep.join([
            "from endpoints import Controller",
            "class Default(Controller):",
            "    def GET(*args, **kwargs): pass",
            ""
        ]),
        "{}.default".format(controller_prefix): os.linesep.join([
            "from endpoints import Controller",
            "class Default(Controller):",
            "    def GET(*args, **kwargs): pass",
            ""
        ]),
        "{}.foo".format(controller_prefix): os.linesep.join([
            "from endpoints import Controller",
            "class Default(Controller):",
            "    def GET(*args, **kwargs): pass",
            "",
            "class Bar(Controller):",
            "    def GET(*args, **kwargs): pass",
            "    def POST(*args, **kwargs): pass",
            ""
        ]),
        "{}.foo.baz".format(controller_prefix): os.linesep.join([
            "from endpoints import Controller",
            "class Default(Controller):",
            "    def GET(*args, **kwargs): pass",
            "",
            "class Che(Controller):",
            "    def GET(*args, **kwargs): pass",
            ""
        ]),
        "{}.foo.boom".format(controller_prefix): os.linesep.join([
            "from endpoints import Controller",
            "",
            "class Bang(Controller):",
            "    def GET(*args, **kwargs): pass",
            ""
        ]),
    }
    r = testdata.create_modules(d)

    s = set(d.keys())
    return s


class ControllerTest(TestCase):
    def test_cors(self):
        class Cors(Controller):
            def POST(self): pass

        res = Response()
        req = Request()
        c = Cors(req, res)
        self.assertTrue(c.OPTIONS)
        self.assertFalse('Access-Control-Allow-Origin' in c.response.headers)

        req.set_header('Origin', 'http://example.com')
        c = Cors(req, res)
        self.assertEqual(req.get_header('Origin'), c.response.get_header('Access-Control-Allow-Origin')) 

        req.set_header('Access-Control-Request-Method', 'POST')
        req.set_header('Access-Control-Request-Headers', 'xone, xtwo')
        c = Cors(req, res)
        c.OPTIONS()
        self.assertEqual(req.get_header('Origin'), c.response.get_header('Access-Control-Allow-Origin'))
        self.assertEqual(req.get_header('Access-Control-Request-Method'), c.response.get_header('Access-Control-Allow-Methods')) 
        self.assertEqual(req.get_header('Access-Control-Request-Headers'), c.response.get_header('Access-Control-Allow-Headers')) 

        c = Cors(req, res)
        c.POST()
        self.assertEqual(req.get_header('Origin'), c.response.get_header('Access-Control-Allow-Origin')) 

    def test_bad_typeerror(self):
        """There is a bug that is making the controller method is throw a 404 when it should throw a 500"""
        controller_prefix = "badtyperr"
        c = Call(controller_prefix, [
            "from endpoints import Controller",
            "class Default(Controller):",
            "    def GET(self):",
            "        raise TypeError('This should not cause a 404')"
        ])
        res = c.handle('/')
        self.assertEqual(500, res.code)

        controller_prefix = "badtyperr2"
        c = Call(controller_prefix, [
            "from endpoints import Controller",
            "class Bogus(object):",
            "    def handle_controller(self, foo):",
            "        pass",
            "",
            "class Default(Controller):",
            "    def GET(self):",
            "        b = Bogus()",
            "        b.handle_controller()",
        ])
        res = c.handle('/')
        self.assertEqual(500, res.code)


class RouterTest(TestCase):
    def get_http_instances(self, path="", method="GET"):
        req = Request()
        req.method = method
        req.path = path
        res = Response()
        return req, res

    def test_mixed_modules_packages(self):
        # make sure a package with modules and other packages will resolve correctly
        controller_prefix = "mmp"
        r = testdata.create_modules({
            controller_prefix: os.linesep.join([
                "from endpoints import Controller",
                "class Default(Controller): pass",
            ]),
            "{}.foo".format(controller_prefix): os.linesep.join([
                "from endpoints import Controller",
                "class Default(Controller): pass",
            ]),
            "{}.foo.bar".format(controller_prefix): os.linesep.join([
                "from endpoints import Controller",
                "class Default(Controller): pass",
            ]),
            "{}.che".format(controller_prefix): os.linesep.join([
                "from endpoints import Controller",
                "class Default(Controller): pass",
            ]),
        })
        r = Router(controller_prefix)
        self.assertEqual(set(['mmp.foo', 'mmp', 'mmp.foo.bar', 'mmp.che']), r.controllers)

        # make sure just a file will resolve correctly
        controller_prefix = "mmp2"
        testdata.create_module(controller_prefix, os.linesep.join([
            "from endpoints import Controller",
            "class Bar(Controller): pass",
        ]))
        r = Router(controller_prefix)
        self.assertEqual(set(['mmp2']), r.controllers)

    def test_routing_module(self):
        controller_prefix = "callback_info"
        contents = [
            "from endpoints import Controller",
            "class Bar(Controller):",
            "    def GET(*args, **kwargs): pass"
        ]
        testdata.create_module("{}.foo".format(controller_prefix), contents=contents)
        r = Router(controller_prefix)
        self.assertTrue(controller_prefix in r.controllers)
        self.assertEqual(2, len(r.controllers))

    def test_routing_package(self):
        controller_prefix = "routepack"
        contents = [
            "from endpoints import Controller",
            "",
            "class Default(Controller):",
            "    def GET(self): pass",
            "",
        ]
        f = testdata.create_package(controller_prefix, contents=contents)

        r = Router(controller_prefix)
        self.assertTrue(controller_prefix in r.controllers)
        self.assertEqual(1, len(r.controllers))

    def test_routing(self):
        """there was a bug that caused errors raised after the yield to return another
        iteration of a body instead of raising them"""
        controller_prefix = "routing1"
        contents = [
            "from endpoints import Controller",
            "class Default(Controller):",
            "    def GET(self): pass",
            "",
            "class Foo(Controller):",
            "    def GET(self): pass",
            "",
            "class Bar(Controller):",
            "    def GET(self): pass",
        ]
        testdata.create_module(controller_prefix, contents=contents)

        r = Router(controller_prefix)
        info = r.find(*self.get_http_instances())
        self.assertEqual(info['module_name'], controller_prefix)
        self.assertEqual(info['class_name'], "Default")

        r = Router(controller_prefix)
        info = r.find(*self.get_http_instances("/foo/che/baz"))
        self.assertEqual(2, len(info['method_args']))
        self.assertEqual(info['class_name'], "Foo")

    def test_controllers(self):
        controller_prefix = "get_controllers"
        s = create_modules(controller_prefix)

        r = Router(controller_prefix)
        controllers = r.controllers
        self.assertEqual(s, controllers)

        # just making sure it always returns the same list
        controllers = r.controllers
        self.assertEqual(s, controllers)

    def test_default_match_with_path(self):
        """when the default controller is used, make sure it falls back to default class
        name if the path bit fails to be a controller class name"""
        controller_prefix = "nomodcontroller2"
        c = Call(controller_prefix, {"nmcon": [
            "from endpoints import Controller",
            "class Default(Controller):",
            "    def GET(self, *args, **kwargs):",
            "        return args[0]"
        ]})
        res = c.handle('/nmcon/8')
        self.assertEqual('"8"', res.body)

    def test_no_match(self):
        """make sure a controller module that imports a class with the same as
        one of the query args doesen't get picked up as the controller class"""
        controller_prefix = "nomodcontroller"
        contents = {
            "{}.nomod".format(controller_prefix): [
                "class Nomodbar(object): pass",
                ""
            ],
            controller_prefix: [
                "from endpoints import Controller",
                "from nomod import Nomodbar",
                "class Default(Controller):",
                "    def GET(): pass",
                ""
            ]
        }
        testdata.create_modules(contents)

        path = '/nomodbar' # same name as one of the non controller classes
        r = Router(controller_prefix)
        info = r.find(*self.get_http_instances(path))
        self.assertEqual('Default', info['class_name'])
        self.assertEqual('nomodcontroller', info['module_name'])
        self.assertEqual('nomodbar', info['method_args'][0])

    def test_import_error(self):

        controller_prefix = "importerrorcontroller"
        c = Call(controller_prefix, [
            "from endpoints import Controller",
            "from does_not_exist import FairyDust",
            "class Default(Controller):",
            "    def GET(): pass",
            ""
        ])
        res = c.handle('/')
        self.assertEqual(404, res.code)

    def test_get_controller_info_default(self):
        """I introduced a bug on 1-12-14 that caused default controllers to fail
        to be found, this makes sure that bug is squashed"""
        controller_prefix = "controller_info_default"
        r = testdata.create_modules({
            controller_prefix: os.linesep.join([
                "from endpoints import Controller",
                "class Default(Controller):",
                "    def GET(): pass",
                ""
            ])
        })

        r = Router(controller_prefix)
        info = r.find(*self.get_http_instances("/"))
        self.assertEqual('Default', info['class_name'])
        self.assertTrue(issubclass(info['class'], Controller))

    def test_callback_info(self):
        controller_prefix = "callback_info"
        req, res = self.get_http_instances("/foo/bar")
        req.query_kwargs = {u'foo': u'bar', u'che': u'baz'}

        r = Router(controller_prefix)

        with self.assertRaises(ImportError):
            d = r.find(req, res)

        contents = [
            "from endpoints import Controller",
            "class Bar(Controller):",
            "    def GET(*args, **kwargs): pass"
        ]
        testdata.create_module("{}.foo".format(controller_prefix), contents=contents)

        # if it succeeds, then it passed the test :)
        d = r.find(req, res)

    def test_get_controller_info(self):
        controller_prefix = "controller_info_advanced"
        s = create_modules(controller_prefix)

        ts = [
            {
                'in': dict(method="GET", path="/foo/bar/happy/sad"),
                'out': {
                    'module_name': "controller_info_advanced.foo",
                    'class_name': 'Bar',
                    'method_args': ['happy', 'sad'],
                    'method_name': "GET",
                }
            },
            {
                'in': dict(method="GET", path="/"),
                'out': {
                    'module_name': "controller_info_advanced",
                    'class_name': 'Default',
                    'method_args': [],
                    'method_name': "GET",
                }
            },
            {
                'in': dict(method="GET", path="/happy"),
                'out': {
                    'module_name': "controller_info_advanced",
                    'class_name': 'Default',
                    'method_args': ["happy"],
                    'method_name': "GET",
                }
            },
            {
                'in': dict(method="GET", path="/foo/baz"),
                'out': {
                    'module_name': "controller_info_advanced.foo.baz",
                    'class_name': 'Default',
                    'method_args': [],
                    'method_name': "GET",
                }
            },
            {
                'in': dict(method="GET", path="/foo/baz/che"),
                'out': {
                    'module_name': "controller_info_advanced.foo.baz",
                    'class_name': 'Che',
                    'method_args': [],
                    'method_name': "GET",
                }
            },
            {
                'in': dict(method="GET", path="/foo/baz/happy"),
                'out': {
                    'module_name': "controller_info_advanced.foo.baz",
                    'class_name': 'Default',
                    'method_args': ["happy"],
                    'method_name': "GET",
                }
            },
            {
                'in': dict(method="GET", path="/foo/happy"),
                'out': {
                    'module_name': "controller_info_advanced.foo",
                    'class_name': 'Default',
                    'method_args': ["happy"],
                    'method_name': u"GET",
                }
            },
        ]

        for t in ts:
            req, res = self.get_http_instances(**t['in'])
#             r = Request()
#             for key, val in t['in'].items():
#                 setattr(r, key, val)

            r = Router(controller_prefix)
            d = r.find(req, res)
            for key, val in t['out'].items():
                self.assertEqual(val, d[key])



#class CallTest(TestCase):
class CallXXXX(object):


    def test_public_controller(self):
        contents = os.linesep.join([
            "from endpoints import Controller",
            "class Bar(Controller):",
            "    def get(*args, **kwargs): pass"
        ])
        testdata.create_module("controller2.foo2", contents=contents)

        r = Request()
        r.path = u"/foo2/bar"
        r.path_args = [u"foo2", u"bar"]
        r.query_kwargs = {u'foo2': u'bar', u'che': u'baz'}
        r.method = u"GET"
        c = Call("controller2")
        c.request = r

        # if it succeeds, then it passed the test :)
        with self.assertRaises(CallError):
            d = c.get_callback_info()

    def test_handle_redirect(self):
        contents = os.linesep.join([
            "from endpoints import Controller, Redirect",
            "class Testredirect(Controller):",
            "    def GET(*args, **kwargs):",
            "        raise Redirect('http://example.com')"
        ])
        testdata.create_module("controllerhr.handle", contents=contents)

        r = Request()
        r.path = u"/handle/testredirect"
        r.path_args = [u'handle', u'testredirect']
        r.query_kwargs = {}
        r.method = u"GET"
        c = Call("controllerhr")
        c.response = Response()
        c.request = r

        res = c.handle()
        self.assertEqual(302, res.code)
        self.assertEqual('http://example.com', res.headers['Location'])

    def test_handle_404_typeerror(self):
        """make sure not having a controller is correctly identified as a 404"""
        controller_prefix = "h404te"
        s = create_modules(controller_prefix)
        r = Request()
        r.method = u'GET'
        r.path = u'/foo/boom'

        c = Call(controller_prefix)
        c.response = Response()
        c.request = r

        res = c.handle()
        self.assertEqual(404, res.code)

    def test_handle_404_typeerror_2(self):
        """make sure 404 works when a path bit is missing"""
        controller_prefix = "h404te2"
        contents = os.linesep.join([
            "from endpoints import Controller, decorators",
            "class Default(Controller):",
            "    def GET(self, needed_bit, **kwargs):",
            "       return ''",
            "",
            "    def POST(self, needed_bit, **kwargs):",
            "       return ''",
            "",
            "class Htype(Controller):",
            "    def POST(self, needed_bit, **kwargs):",
            "       return ''",
            "",
            "class Hdec(Controller):",
            "    @decorators.param('foo', default='bar')",
            "    def POST(self, needed_bit, **kwargs):",
            "       return ''",
            "",
        ])
        testdata.create_module(controller_prefix, contents=contents)
        c = Call(controller_prefix)
        c.response = Response()

        r = Request()
        r.method = u'POST'
        r.path = u'/hdec'
        c.request = r
        res = c.handle()
        self.assertEqual(404, res.code)

        r = Request()
        r.method = u'POST'
        r.path = u'/htype'
        c.request = r
        res = c.handle()
        self.assertEqual(404, res.code)

        r = Request()
        r.method = u'GET'
        r.path = u'/'
        c.request = r
        res = c.handle()
        self.assertEqual(404, res.code)

        r = Request()
        r.method = u'POST'
        r.path = u'/'
        c.request = r
        res = c.handle()
        self.assertEqual(404, res.code)

    def test_handle_404_typeerror_3(self):
        """there was an error when there was only one expected argument, turns out
        the call was checking for "arguments" when the message just had "argument" """
        controller_prefix = "h404te3"
        contents = os.linesep.join([
            "from endpoints import Controller",
            "class Foo(Controller):",
            "    def GET(self): pass",
            "",
        ])
        testdata.create_module(controller_prefix, contents=contents)
        c = Call(controller_prefix)
        c.response = Response()

        r = Request()
        r.method = u'GET'
        r.path = u'/foo/bar/baz'
        r.query = 'che=1&boo=2'
        c.request = r
        res = c.handle()
        self.assertEqual(404, res.code)

    def test_handle_accessdenied(self):
        """raising an AccessDenied error should set code to 401 and the correct header"""
        controller_prefix = "haccessdenied"
        contents = os.linesep.join([
            "from endpoints import Controller, AccessDenied",
            "class Default(Controller):",
            "    def GET(*args, **kwargs):",
            "        raise AccessDenied(scheme='basic')",
            "class Bar(Controller):",
            "    def GET(*args, **kwargs):",
            "        raise AccessDenied()",
        ])
        testdata.create_module(controller_prefix, contents=contents)

        r = Request()
        r.method = u'GET'
        r.path = u'/'
        c = Call(controller_prefix)
        c.response = Response()
        c.request = r
        res = c.handle()
        res.body # we need to cause the body to be handled
        self.assertEqual(401, res.code)
        self.assertTrue('Basic' in res.headers['WWW-Authenticate'])

        r = Request()
        r.method = u'GET'
        r.path = u'/bar'
        c = Call(controller_prefix)
        c.response = Response()
        c.request = r
        res = c.handle()
        self.assertEqual(401, res.code)
        self.assertTrue('Auth' in res.headers['WWW-Authenticate'])

    def test_handle_callstop(self):
        contents = os.linesep.join([
            "from endpoints import Controller, CallStop",
            "class Testcallstop(Controller):",
            "    def GET(*args, **kwargs):",
            "        raise CallStop(205, None)",
            "",
            "class Testcallstop2(Controller):",
            "    def GET(*args, **kwargs):",
            "        raise CallStop(200, 'this is the body')",
            "",
            "class Testcallstop3(Controller):",
            "    def GET(*args, **kwargs):",
            "        raise CallStop(204, 'this is ignored')",
        ])
        testdata.create_module("handlecallstop", contents=contents)

        r = Request()
        r.path = u"/testcallstop"
        r.path_args = [u'testcallstop']
        r.query_kwargs = {}
        r.method = u"GET"
        c = Call("handlecallstop")
        c.response = Response()
        c.request = r

        res = c.handle()
        self.assertEqual('', res.body)
        self.assertEqual(None, res._body)
        self.assertEqual(205, res.code)

        r.path = u"/testcallstop2"
        r.path_args = [u'testcallstop2']
        res = c.handle()
        self.assertEqual('"this is the body"', res.body)
        self.assertEqual(200, res.code)

        r.path = u"/testcallstop3"
        r.path_args = [u'testcallstop3']
        res = c.handle()
        self.assertEqual(None, res._body)
        self.assertEqual(204, res.code)



class CallVersioningTest(TestCase):
    def test_get_version(self):
        r = Request()
        r.headers = {u'accept': u'application/json;version=v1'}

        c = Call("controller")
        c.request = r

        v = c.version
        self.assertEqual(u'v1', v)

    def test_get_version_default(self):
        """turns out, calls were failing if there was no accept header even if there were defaults set"""
        r = Request()
        r.headers = {}

        c = Call("controller")
        c.request = r
        r.headers = {}
        c.content_type = u'application/json'
        self.assertEqual(None, c.version)

        c = Call("controller")
        c.request = r
        r.headers = {u'accept': u'application/json;version=v1'}
        self.assertEqual(u'v1', c.version)

        c = Call("controller")
        c.request = r
        c.content_type = None
        with self.assertRaises(ValueError):
            v = c.version

        c = Call("controller")
        c.request = r
        r.headers = {u'accept': u'*/*'}
        c.content_type = u'application/json'
        self.assertEqual(None, c.version)

        c = Call("controller")
        c.request = r
        r.headers = {u'accept': u'*/*;version=v8'}
        c.content_type = u'application/json'
        self.assertEqual(u'v8', c.version)

    def test_normalize_method(self):
        r = Request()
        r.headers = {u'accept': u'application/json;version=v1'}
        r.method = 'POST'

        c = Call("foo.bar")
        c.content_type = u'application/json'
        c.request = r

        method = c.get_normalized_method()
        self.assertEqual(u"POST_v1", method)

