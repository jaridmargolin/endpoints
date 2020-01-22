# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import logging
import inspect
import re

from ..exception import CallError, RouteError, VersionError
from ..http import Url
from .base import ControllerDecorator


logger = logging.getLogger(__name__)


class route(ControllerDecorator):
    """Used to decide if the Controller's method should be used to satisfy the request

    :example:
        class Default(Controller):
            # this GET will handle /:uid/:title requests
            @route(lambda req: len(req.path_args) == 2)
            def GET_1(self, uid, title):
                pass

            # this GET will handle /:username requests
            @route(lambda req: len(req.path_args) == 1)
            def GET_2(self, username):
                pass

    If this decorator is used then all GET methods in the controller have to have
    a unique name (ie, there can be no just GET method, they have to be GET_1, etc.)
    """

    def handle_definition(self, callback, *args, **kwargs):
        self.callback = callback

    def handle(self, request):
        return self.callback(request)

    def decorate(self, func, callback, *args, **kwargs):
        return super(route, self).decorate(func, target=callback)

    def normalize_target_params(self, request, controller_args, controller_kwargs):
        return [request], {}

    def handle_error(self, e):
        raise RouteError(instance=self)

    def handle_failure(self, controller):
        """This is called if all routes fail, it's purpose is to completely
        fail the request

        This is not a great solution because it uses the assumption that all the
        route decorators for a given set of methods on the controller (ie all the
        GET_* methods) will be the same, so it the first failing instance of this
        decorator will have its failure method set as the global failure method
        and it will be called if all the potential routes fail

        :param controller: Controller, the controller that was trying to find a 
            method to route to
        """
        req = controller.request

        # https://www.w3.org/Protocols/rfc2616/rfc2616-sec5.html#sec5.1
        # An origin server SHOULD return the status code 405 (Method Not Allowed)
        # if the method is known by the origin server but not allowed for the
        # requested resource
        raise CallError(405, "Could not find a method to satisfy {}".format(
            req.path
        ))


class path_route(route):
    """easier route decorator that will check the sub paths to make sure they are part 
    of the full endpoint path

    :Example:

        class Foo(Controller):
            @path_route("bar", "che")
            def GET(self, bar, che):
                # you can only get here by requesting /foo/bar/che where /foo is
                # the controller path and /bar/che is the path_route
    """
    def decorate(self, func, *paths, **kwargs):
        self.paths = paths
        return super(route, self).decorate(func, target=self.target)

    def target(self, request):
        ret = True
        pas = Url.normalize_paths(self.paths)
        method_args = request.controller_info["method_args"]
        for i, p in enumerate(pas):
            try:
                if method_args[i] != p:
                    ret = False
                    break

            except IndexError:
                ret = False
                break

        return ret


class param_route(route):
    """easier route decorator that will check the sub paths to make sure they are part 
    of the full endpoint path

    :Example:

        class Foo(Controller):
            @path_route("bar", "che")
            def GET(self, bar, che):
                # you can only get here by requesting /foo/bar/che where /foo is
                # the controller path and /bar/che is the path_route
    """

    def decorate(self, func, *keys, **matches):
        self.keys = keys
        self.matches = matches
        return super(route, self).decorate(func, target=self.target)

    def target(self, request):
        ret = True
        method_kwargs = request.controller_info["method_kwargs"]
        for k in self.keys:
            if k not in method_kwargs:
                ret = False
                break

        if ret:
            for k, v in self.matches.items():
                try:
                    if type(v)(method_kwargs[k]) != v:
                        ret = False
                        break

                except KeyError:
                    ret = False
                    break

        return ret

    def handle_failure(self, controller):
        # we throw a 400 here to match @param failures
        raise CallError(400, "Could not find a method to satisfy {}".format(
            controller.request.path
        ))


class version(route):
    """Used to provide versioning support to a Controller

    :example:
        class Default(Controller):
            # this GET will handle no version and version v1 requests
            @version("", "v1")
            def GET_1(self):
                pass

            # this GET will handle version v2 request
            @version("v2")
            def GET_2(self):
                pass

    If this decorator is used then all GET methods in the controller have to have
    a unique name (ie, there can be no just GET method, they have to be GET_1, etc.)
    """

    def decorate(self, func, *versions):
        self.versions = set(versions)
        return super(route, self).decorate(func, target=self.target)

    def target(self, request):
        req_version = req.version(self.content_type)
        if req_version not in versions:
            raise VersionError(slf, req_version, versions)



        ret = True
        pas = Url.normalize_paths(self.paths)
        method_args = request.controller_info["method_args"]
        for i, p in enumerate(pas):
            try:
                if method_args[i] != p:
                    ret = False
                    break

            except IndexError:
                ret = False
                break

        return ret






    def decorate(slf, func, *versions):
        versions = set(versions)
        def decorated(self, *args, **kwargs):
            req = self.request
            req_version = req.version(self.content_type)
            if req_version not in versions:
                raise VersionError(slf, req_version, versions)

            return func(self, *args, **kwargs)

        return decorated

