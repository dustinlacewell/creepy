from uuid import uuid1
from json import loads, dumps
from StringIO import StringIO

from txrestapi.resource import APIResource
from txrestapi.methods import GET, POST, PUT, ALL

from creepy.queue import RDQueue
from creepy.job import Job
from creepy.responses import *

result_formats = ('list', 'by_page', 'by_image')

class CreepyAPI(APIResource):
    def __init__(self, jobs, workers, debug=False, *args, **kwargs):
        APIResource.__init__(self, *args, **kwargs)
        self.queue = RDQueue(jobs, workers)
        self.debug = debug

    def getChild(self, name, request):
        # deserialize post json data
        if request.method.lower() in ('post', 'put'):
            content = request.content.read()
            try:
                decoded = loads(content)
                request.params = decoded
            except ValueError:
                return BadRequestResponse('Could not decode JSON encoded parameters.')
        else:
            request.params = dict((k,v[0]) for (k,v) in request.args.iteritems())

        try:
            resc = APIResource.getChild(self, name, request)
            if resc is None:
                return NotFoundResponse()
            return resc
        # catch bubbled error responses
        except JsonResponse, e:
            # and return them
            return e

    def require(self, request, param):
        """
        Require a parameter of the incomming request, otherwise return BadRequestResponse.
        """
        if param not in request.params:
            raise BadRequestResponse('Missing required `%s` parameter.' % param)
        return request.params.get(param)

    @POST('^/echo$')
    def echo(self, request):
        """
        Testing endpoint.
        """
        return JsonResponse(data=request.params).render(request)

    @POST('^/$')
    def start_job(self, request):
        """
        Start a new job.

        params:
            urls : list of urls to scrape
            depth : levels of recursion
        """
        urls = self.require(request, 'urls')
        depth = min(request.params.get('depth', 0), 3)
        job = Job(urls, depth, debug=self.debug)
        self.queue.put(job)
        return JsonResponse(
            data={
                'job': job.uuid,
            }
        ).render(request)

    @GET('^/status/(?P<uuid>[a-zA-Z0-9]{22})$')
    def job_status(self, request, uuid):
        """
        Query job status.

        params: None
        """
        job = self.queue.jobs.get(uuid)
        if job is None:
            return BadRequestResponse("Job %s not found." % uuid)

        data={
            'job': job.uuid,
            'depth': job.depth,
            'urls': job.urls,
            'queued_time': job.job.queuedTime,
            'num_completed': job.completed,
            'num_waiting': job.waiting,
            'num_images': len(job.images),
            'num_pages': len(job.pages)
        }


        if job.uuid in self.queue.pending:
            data['status'] = 'pending'
        elif job.uuid in self.queue.running:
            data['status'] = 'running'
            data['start_time'] = job.job.startTime
        else:
            data['status'] = 'finished'
            data['start_time'] = job.job.startTime
            data['stop_time'] = job.job.stopTime
            data['total_time'] = job.job.stopTime - job.job.startTime

        return JsonResponse(data=data).render(request)

    @GET('^/result/(?P<uuid>[a-zA-Z0-9]{22})$')
    def job_result(self, request, uuid):
        """
        Query result of a job.

        params:
            result_format: one of the following
                - list : results as a list of images
                - by_page: results as a mapping of pages to images on that page
                - by_image: results as a mapping of images to pages where that image was found

            include_empty: when using "by_page", include pages with no images
        """
        include_empty = request.params.get('include_empty', False)
        result_format = request.params.get('result_format', 'list')
        if result_format not in result_formats:
            return BadRequestResponse("`result_format` param (%s) must be one of %s." % (result_format, str(result_formats)))

        job = self.queue.jobs.get(uuid)
        if job is None:
            return BadRequestResponse("Job %s not found." % uuid)

        if job.uuid not in self.queue.finished:
            return BadRequestResponse("Job %s is not finished." % uuid)

        data = {
            'job': job.uuid,
            'urls': job.urls,
            'num_images': len(job.images),
            'num_pages': len(job.pages),
            'start_time': job.job.startTime,
            'stop_time': job.job.stopTime,
            'total_time': job.job.stopTime - job.job.startTime,
        }

        if result_format == 'list':
            data['results'] = job.images.keys()
        elif result_format == 'by_page':
            if not include_empty:
                for key in job.pages.keys():
                    if not job.pages[key]:
                        del job.pages[key]
            data['results'] = job.pages
        elif result_format == 'by_image':
            data['results'] = job.images

        if job.errors:
            data['errors'] = job.errors
        return JsonResponse(data=data).render(request)

    @ALL('^/')
    def default_view(self, request):
        return NotFoundResponse().render(request)

