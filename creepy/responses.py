from json import loads, dumps

from twisted.web.resource import Resource
from twisted.web._responses import (
    OK, 
    FORBIDDEN, 
    NOT_FOUND, 
    BAD_REQUEST,
)

class JsonResponse(Resource):

    isLeaf = True

    def __init__(self, code=200, data=None):
        Resource.__init__(self)
        self.code = code
        self.data = data or dict()


    def render(self, request):
        self.data['response_code'] = self.code
        request.setResponseCode(self.code)
        request.setHeader(b"content-type", b"application/json; charset=utf-8")
        response = dumps(self.data)

        if isinstance(response, unicode):
            return response.encode('utf-8')
        return response    

class ErrorResponse(JsonResponse):
    def __init__(self, code, reason):
        JsonResponse.__init__(self, code, data={
            'reason': reason
        })

class BadRequestResponse(ErrorResponse):
    def __init__(self, reason='Bad Request.'):
        ErrorResponse.__init__(self, BAD_REQUEST, reason)

class ForbiddenResponse(ErrorResponse):
    def __init__(self, reason='Resource is forbidden.'):
        ErrorResponse.__init__(self, FORBIDDEN, reason)

class NotFoundResponse(ErrorResponse):
    def __init__(self, reason='Resource not found.'):
        ErrorResponse.__init__(self, NOT_FOUND, reason)