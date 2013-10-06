from os import environ, path
from json import loads, dumps
from uuid import uuid1
from StringIO import StringIO
from tempfile import NamedTemporaryFile

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.defer import succeed, Deferred
from twisted.web.client import getPage
from twisted.web import server
from twisted.web.test.test_web import DummyRequest
from twisted.web._responses import *
from twisted.web.static import File
from twisted.web.server import Site

class SmartDummyRequest(DummyRequest):
    def __init__(self, method, url, args=None, headers=None, body=None):
        DummyRequest.__init__(self, url.split('/'))
        self.method = method
        self.path =url
        self.headers.update(headers or {})
        self.content = StringIO()
    	self.content.write(body or '')
        self.content.seek(0)
 
        # set args                                                                                                                                                                                       
        args = args or {}
        for k, v in args.items():
            self.addArg(k, v)

    def getAllHeaders(self):
    	return self.headers
 
    def value(self):
        return "".join(self.written)
 
 
class DummySite(server.Site):
    def get(self, url, args=None, headers=None):
        return self._request("GET", url, args, headers)
 
    def post(self, url, args=None, headers=None, body=None):
        return self._request("POST", url, args, headers, body=body)
 
 
    def _request(self, method, url, args, headers, body=None):
        request = SmartDummyRequest(method, url, args, headers, body)
        resource = self.getResourceFor(request)
        result = resource.render(request)
        return self._resolveResult(request, result)
 
 
    def _resolveResult(self, request, result):
        if isinstance(result, str):
            request.write(result)
            request.finish()
            return succeed(request)
        elif result is server.NOT_DONE_YET:
            if request.finished:
                return succeed(request)
            else:
                return request.notifyFinish().addCallback(lambda _: request)
        else:
            raise ValueError("Unexpected return value: %r" % (result,))


from twisted.trial import unittest

from creepy.api import CreepyAPI

api_url = "http://localhost:8000/"
api_target = api_url + 'index.html'

class WebTest(unittest.TestCase):
    def setUp(self):
        self.api = CreepyAPI(1, 1)
        self.web = DummySite(self.api)
        staticfiles = path.join(path.dirname(path.abspath(__file__)), 'static')
        files = DummySite(File(staticfiles))
        factory = Site(files)
        self.static = reactor.listenTCP(8000, factory)

    def tearDown(self):
        self.static.stopListening()
        return self.api.queue.queue.stop()

    def assertJson(self, response, data):
    	resp = loads(response.value())
    	for key, val in data.items():
    		self.assertTrue(key in resp)
    		self.assertEqual(resp[key], val)

    def assertCode(self, response, code, data={}):
    	data['response_code'] = code
    	self.assertJson(response, data)

    @inlineCallbacks
    def test_bad_request(self):
        response = yield self.web.post(
        	"/echo", body="{'foo': 1, 'bar': 2",
        )
        self.assertCode(response, BAD_REQUEST)

    @inlineCallbacks
    def test_echo(self):
        struct = {'foo': 1, 'bar': 2}
        response = yield self.web.post(
            "/echo", body=dumps(struct),
        )
        self.assertCode(response, 200, struct)

    def test_static(self):
        return getPage(api_target)

    def job_setup(self, urls=[api_target], depth=0):
        struct = {
            'urls': urls,
            'depth': depth,
        }
        d = self.web.post(
            "/", body=dumps(struct),
        )

        def handle_job_response(response):
            self.assertCode(response, 200)
            params = loads(response.value())
            jobid = params.get('job')
            self.assertIsNotNone(jobid)
            self.assertTrue(len(jobid) == 22)

            checker = Deferred()

            def check_status():
                d = self.web.get(
                    "/status/" + jobid
                )

                def _check_status(response):
                    self.assertCode(response, 200)
                    params = loads(response.value())
                    status = params.get('status')
                    if status in ('pending', 'running'):
                        reactor.callLater(1.0, check_status)
                    else:
                        checker.callback(response)
                d.addCallback(_check_status)
            reactor.callLater(1.0, check_status)

            def handle_status_response(response):
                self.assertCode(response, 200)
                params = loads(response.value())
                jobid = params.get('job')
                self.assertIsNotNone(jobid)
                status = params.get('status')
                self.assertTrue(status == 'finished')
                _urls = params.get('urls')
                self.assertTrue(_urls == urls)
                return response

            checker.addCallback(handle_status_response)
            return checker

        d.addCallback(handle_job_response)

        # def fail(*args):
        #     import pdb; pdb.set_trace()
        # d.addErrback(fail)
        return d

    def test_empty_urls(self):
        struct = {
            'urls': [],
        }
        d = self.web.post(
            "/", body=dumps(struct),
        )

        def handle_job_response(response):
            self.assertCode(response, 400)

        d.addCallback(handle_job_response)
        return d

    def test_depth_0(self):
        d = self.job_setup()

        def handle_setup_response(response):
            params = loads(response.value())
            images = params.get('num_images')
            self.assertTrue(images == 1, "Images was %s" % images)

        d.addCallback(handle_setup_response)
        return d

    def test_depth_1(self):
        d = self.job_setup(depth=1)

        def handle_setup_response(response):
            params = loads(response.value())
            images = params.get('num_images')
            self.assertTrue(images == 4, "Images was %s" % images)

        d.addCallback(handle_setup_response)
        return d

    def test_depth_2(self):
        d = self.job_setup(depth=2)

        def handle_setup_response(response):
            params = loads(response.value())
            images = params.get('num_images')
            self.assertTrue(images == 5)

        d.addCallback(handle_setup_response)
        return d

    def results_test(self, handler, handler_args=None, urls=[api_target], depth=0):
        d = self.job_setup(urls, depth=depth)

        def handle_setup_response(response):
            params = loads(response.value())
            jobid = params.get('job')
            self.assertIsNotNone(jobid)

            d = self.web.get(
                "/result/" + jobid,
                args=handler_args,
            )

            d.addCallback(handler)

        d.addCallback(handle_setup_response)
        return d


    # def test_broken(self):
    #     url = 'http://.com'
    #     def check_result(response):
    #         self.assertCode(response,200)
    #         params = loads(response.value())
    #         images = params.get('num_images')
    #         self.assertTrue(images == 0, "Images was %s" % images)
    #         self.assertTrue(url in params.get('errors', {}))

    #     return self.results_test(check_result, urls=[url])

    def test_default_results(self):
        def check_result(response):
            self.assertCode(response, 200)
            params = loads(response.value())
            urls = params.get('urls')
            self.assertEqual(urls, [api_target])
            num_images = params.get('num_images')
            self.assertEqual(num_images, 5)
            results = params.get('results')
            for image in (
                'index.png',
                'a.png', 'a2.png',
                'b.png', 'c.png'
            ):
                self.assertTrue(api_url+image in results)
        return self.results_test(check_result, depth=2)

    def test_by_image_results(self):
        def check_result(response):
            self.assertCode(response, 200)
            params = loads(response.value())
            urls = params.get('urls')
            self.assertEqual(urls, [api_target])
            num_images = params.get('num_images')
            self.assertEqual(num_images, 5)
            results = params.get('results')
            self.assertEqual(results, {
                api_url + 'index.png': [api_url + 'index.html'],
                api_url + 'a.png': [api_url + 'a.html'],
                api_url + 'a2.png': [api_url + 'a2.html'],
                api_url + 'b.png': [api_url + 'b.html'],
                api_url + 'c.png': [api_url + 'c.html'],
            })
        return self.results_test(check_result, handler_args={
            'result_format': 'by_image',
        }, depth=2)

    def test_by_page_results(self):
        def check_result(response):
            self.assertCode(response, 200)
            params = loads(response.value())
            urls = params.get('urls')
            self.assertEqual(urls, [api_target])
            num_images = params.get('num_images')
            self.assertEqual(num_images, 5)
            results = params.get('results')
            self.assertEqual(results, {
                api_url + 'index.html': [api_url + 'index.png'],
                api_url + 'a.html': [api_url + 'a.png'],
                api_url + 'a2.html': [api_url + 'a2.png'],
                api_url + 'b.html': [api_url + 'b.png'],
                api_url + 'c.html': [api_url + 'c.png'],
            })
        return self.results_test(check_result, handler_args={
            'result_format': 'by_page',
        }, depth=2)

    def test_by_page_with_empty_results(self):
        def check_result(response):
            self.assertCode(response, 200)
            params = loads(response.value())
            urls = params.get('urls')
            self.assertEqual(urls, [api_target])
            num_images = params.get('num_images')
            self.assertEqual(num_images, 5)
            results = params.get('results')
            self.assertEqual(results, {
                api_url + 'index.html': [api_url + 'index.png'],
                api_url + 'a.html': [api_url + 'a.png'],
                api_url + 'a2.html': [api_url + 'a2.png'],
                api_url + 'b.html': [api_url + 'b.png'],
                api_url + 'c.html': [api_url + 'c.png'],
                api_url + 'd.html': [],
            })
            parsed = params.get('num_parsed_pages')
            completed = params.get('num_completed')
            self.assertTrue(completed == parsed)

        return self.results_test(check_result, handler_args={
            'result_format': 'by_page',
            'include_empty': True,
        }, depth=2)


    def test_double(self):
        def check_result(response):
            self.assertCode(response, 200)
            params = loads(response.value())
            urls = params.get('urls')
            self.assertEqual(urls, [api_target, api_target])
            num_images = params.get('num_images')
            self.assertEqual(num_images, 5)
            num_pages = params.get('num_pages')
            self.assertTrue(num_pages == 6)
        return self.results_test(check_result, urls=[api_target, api_target], depth=2)


