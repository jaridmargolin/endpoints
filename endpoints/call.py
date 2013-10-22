import importlib
import logging
import os
import fnmatch

from .utils import AcceptHeader
from .http import Response, Request


logger = logging.getLogger(__name__)

_module_cache = {}

def get_controllers(controller_prefix):
    """get all the modules in the controller_prefix"""
    global _module_cache
    if not controller_prefix:
        raise ValueError("controller prefix is empty")
    if controller_prefix in _module_cache:
        return _module_cache[controller_prefix]

    module = importlib.import_module(controller_prefix)
    basedir = os.path.dirname(module.__file__)
    modules = set()

    for root, dirs, files in os.walk(basedir, topdown=True):
        dirs[:] = [d for d in dirs if d[0] != '.' or d[0] != '_']

        module_name = root.replace(basedir, '', 1)
        module_name = [controller_prefix] + filter(None, module_name.split('/'))
        for f in fnmatch.filter(files, '*.py'):
            if f.startswith('__init__'):
                modules.add('.'.join(module_name))
            else:
                # we want to ignore any "private" modules
                if not f.startswith('_'):
                    file_name = os.path.splitext(f)[0]
                    modules.add('.'.join(module_name + [file_name]))

    _module_cache.setdefault(controller_prefix, {})
    _module_cache[controller_prefix] = modules
    return modules


class CallError(RuntimeError):
    """
    http errors can raise this with an HTTP status code and message
    """
    def __init__(self, code, msg):
        '''
        create the error

        code -- integer -- http status code
        msg -- string -- the message you want to accompany your status code
        '''
        self.code = code
        super(CallError, self).__init__(msg)


class Call(object):
    """
    Where all the routing magic happens

    we always translate an HTTP request using this pattern: METHOD /module/class/args?kwargs

    GET /foo -> controller_prefix.version.foo.Default.get
    POST /foo/bar -> controller_prefix.version.foo.Bar.post
    GET /foo/bar/che -> controller_prefix.version.foo.Bar.get(che)
    POST /foo/bar/che?baz=foo -> controller_prefix.version.foo.Bar.post(che, baz=foo)
    """

    controller_prefix = u""
    """since endpoints interprets requests as /module/class, you can use this to do: controller_prefix.module.class"""

    content_type = "application/json"
    """the content type this call is going to represent"""

    @property
    def request(self):
        '''
        Call.request, this request object is used to decide how to route the client request

        a Request instance to be used to translate the request to a controller
        '''
        if not hasattr(self, "_request"):
            self._request = Request()

        return self._request

    @request.setter
    def request(self, v):
        self._request = v

    @property
    def response(self):
        '''
        Call.response, this object is used to decide how to answer the client

        a Response instance to be returned from handle populated with info from controller
        '''
        if not hasattr(self, "_response"):
            self._response = Response()

        return self._response

    @response.setter
    def response(self, v):
        self._response = v

    def __init__(self, controller_prefix, *args, **kwargs):
        '''
        create the instance

        controller_prefix -- string -- the module path where all your controller modules live
        *args -- tuple -- convenience, in case you extend and need something in another method
        **kwargs -- dict -- convenience, in case you extend
        '''
        assert controller_prefix, "controller_prefix was empty"

        self.controller_prefix = controller_prefix
        self.args = args
        self.kwargs = kwargs

    def get_controller_info_simple(self):
        '''
        get info about finding a controller based off of the request info

        this method will use the path info as:

            module_name/class_name/args?kwargs

        return -- dict -- all the gathered info about the controller
        '''
        d = {}
        req = self.request
        path_args = list(req.path_args)
        d['module_name'] = u"default"
        d['class_name'] = u"Default"
        d['module'] = None
        d['class'] = None
        d['method'] = req.method.upper()
        d['args'] = []
        d['kwargs'] = {}

        # the first arg is the module
        if len(path_args) > 0:
            module_name = path_args.pop(0)
            if module_name.startswith(u'_'):
                raise ValueError("{} is an invalid".format(module_name))
            d['module_name'] = module_name

        controller_prefix = self.get_normalized_prefix()
        if controller_prefix:
            d['module_name'] = u".".join([controller_prefix, d['module_name']])

        # the second arg is the Class
        if len(path_args) > 0:
            class_name = path_args.pop(0)
            if class_name.startswith(u'_'):
                raise ValueError("{} is invalid".format(class_name))
            d['class_name'] = class_name.capitalize()

        d['module'] = importlib.import_module(d['module_name'])
        d['class'] = getattr(d['module'], d['class_name'])
        d['args'] = path_args
        d['kwargs'] = req.query_kwargs

        return d

    def get_controller_info_advanced(self):
        '''
        get info about finding a controller based off of the request info

        This method will use path info trying to find the longest module name it
        can and then the class name, passing anything else that isn't the module
        or the class as the args, with any query params as the kwargs

        return -- dict -- all the gathered info about the controller
        '''
        d = {}
        req = self.request
        path_args = list(req.path_args)
        d['module_name'] = u""
        d['class_name'] = u"Default"
        d['module'] = None
        d['class'] = None
        d['method'] = req.method.upper()
        d['args'] = []
        d['kwargs'] = {}

        controller_prefix = self.get_normalized_prefix()
        cset = get_controllers(controller_prefix)
        module_name = controller_prefix
        mod_name = module_name
        while path_args:
            mod_name += "." + path_args[0]
            if mod_name in cset:
                module_name = mod_name
                path_args.pop(0)
            else:
                break

        d['module_name'] = module_name
        d['module'] = importlib.import_module(d['module_name'])

        # let's get the class
        if path_args:
            class_name = path_args[0].capitalize()
            if hasattr(d['module'], class_name):
                d['class_name'] = class_name
                path_args.pop(0)

        d['class'] = getattr(d['module'], d['class_name'])
        d['args'] = path_args
        d['kwargs'] = req.query_kwargs

        return d

    def get_controller_info(self):
        return self.get_controller_info_advanced()

    def get_callback_info(self):
        '''
        get the controller callback that will be used to complete the call

        return -- tuple -- (callback, callback_args, callback_kwargs), basically, everything you need to
            call the controller: callback(*callback_args, **callback_kwargs)
        '''
        try:
            d = self.get_controller_info()

        except (ImportError, AttributeError), e:
            r = self.request
            raise CallError(404, "{} not found because of error: {}".format(r.path, e.message))

        try:
            instance = d['class'](self.request, self.response)
            instance.call = self

            callback = getattr(instance, d['method'])
            logger.debug("handling request with callback {}.{}.{}".format(d['module_name'], d['class_name'], d['method']))

        except AttributeError, e:
            r = self.request
            raise CallError(405, "{} {} not supported".format(r.method, r.path))

        return callback, d['args'], d['kwargs']

    def get_normalized_prefix(self):
        """
        do any normalization of the controller prefix and return it

        return -- string -- the full controller module prefix
        """
        return self.controller_prefix

    def handle(self):
        '''
        handle the request

        return -- Response() -- the response object, populated with info from running the controller
        '''
        try:
            callback, callback_args, callback_kwargs = self.get_callback_info()
            self.response.headers['Content-Type'] = self.content_type
            body = callback(*callback_args, **callback_kwargs)
            self.response.body = body

        except CallError, e:
            logger.exception(e)
            self.response.code = e.code
            self.response.body = e

        except Exception, e:
            logger.exception(e)
            self.response.code = 500
            self.response.body = e

        return self.response


class VersionCall(Call):
    """
    versioning is based off of this post: http://urthen.github.io/2013/05/09/ways-to-version-your-api/
    """
    default_version = None
    """set this to the default version if you want a fallback version, if this is None then version check is enforced"""

    def get_normalized_prefix(self):
        cp = u""
        if hasattr(self, "controller_prefix"):
            cp = self.controller_prefix
        v = self.get_version()
        if cp:
            cp += u".{}".format(v)
        else:
            cp = v

        return cp

    def get_version(self):
        if not self.content_type:
            raise ValueError("You are versioning a call with no content_type")

        v = None
        h = self.request.headers
        accept_header = h.get('accept', u"")
        if accept_header:
            a = AcceptHeader(accept_header)
            for mt in a.filter(self.content_type):
                v = mt[2].get(u"version", None)
                if v: break

        if not v:
            v = self.default_version
            if not v:
                raise CallError(406, "Expected accept header with {};version=N media type".format(self.content_type))

        return v
