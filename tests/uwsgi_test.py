# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import codecs
import hashlib

import testdata

from endpoints.interface.uwsgi.client import UWSGIServer, WebsocketClient

from .wsgi_test import TestCase, WSGIServerTest, WSGIServer, WSGITest, WSGIClient, ClientTestCase


class UWSGIClient(WSGIClient):
    server_class = UWSGIServer


class UWSGITest(WSGITest):

    client_class = UWSGIClient

    def create_client(self, *args, **kwargs):
        kwargs.setdefault("config_module_body", [])
        config_module_body = [
            "from endpoints.interface.uwsgi import Application",
        ]
        config_module_body.extend(kwargs.get("config_module_body", []))
        kwargs["config_module_body"] = config_module_body
        return super(UWSGITest, self).create_client(*args, **kwargs)

    def test_chunked(self):
        filepath = testdata.create_file("filename.txt", testdata.get_words(500))
        controller_prefix = 'wsgi.post_chunked'

        c = self.create_client(controller_prefix, [
            "import hashlib",
            "from endpoints import Controller",
            "class Bodykwargs(Controller):",
            "    def POST(self, **kwargs):",
            "        return hashlib.md5(kwargs['file'].file.read()).hexdigest()",
            "",
            "class Bodyraw(Controller):",
            "    def POST(self, **kwargs):",
            "        return len(self.request.body)",
            "",
        ])

        size = c.post_chunked('/bodyraw', {"foo": "bar", "baz": "che"}, filepath=filepath)
        self.assertGreater(int(size), 0)

        with codecs.open(filepath, "rb", encoding="UTF-8") as fp:
            h1 = hashlib.md5(fp.read().encode("UTF-8")).hexdigest()
            h2 = c.post_chunked('/bodykwargs', {"foo": "bar", "baz": "che"}, filepath=filepath)
            self.assertEqual(h1, h2.strip('"'))


class WebsocketTestClient(UWSGIClient):
    client_class = WebsocketClient


class WebsocketTest(TestCase):

    client_class = WebsocketTestClient

    def create_client(self, *args, **kwargs):
        kwargs.setdefault("config_module_body", [])
        kwargs["config_module_body"].extend([
            "from endpoints.interface.uwsgi.gevent import WebsocketApplication as Application",
            "import gevent",
            "import gevent.monkey",
            "if not gevent.monkey.saved:",
            "    gevent.monkey.patch_all()",
        ])
        return super(WebsocketTest, self).create_client(*args, **kwargs)

    def test_connect(self):
        c = self.create_client('ws.connect', [
            "from endpoints import Controller",
            "class Default(Controller):",
            "    def CONNECT(self, *args, **kwargs):",
            "        pass",
            "    def DISCONNECT(self, *args, **kwargs):",
            "        pass",
        ])

        c.connect(trace=True)
        self.assertTrue(c.connected)

        c.close()
        self.assertFalse(c.connected)

    def test_request(self):
        c = self.create_client('ws.request', [
            "from endpoints import Controller",
            "",
            "class Default(Controller):",
            "    def CONNECT(self, *args, **kwargs):",
            "        #pout.v(args, kwargs, self.request)",
            "        pout.b('CONNECT')",
            "        pass",
            "    def DISCONNECT(self, *args, **kwargs):",
            "        pout.b('DISCONNECT')",
            "        pass",
            "",
            "    def SOCKET(self, *args, **kwargs):",
            "        #pout.v(args, kwargs)",
            "        pout.b('SOCKET')",
            "        return {",
            "            'args': args,",
            "            'kwargs': kwargs,",
            "        }",
        ])

        c.send("/foo/bar", {"val1": 1, "val2": 2})

        path, body = c.recv()
        self.assertEqual({"val1": 1, "val2": 2}, body["kwargs"])


class UWSGIServerTest(WSGIServerTest):
    server_class = UWSGIServer

