from twisted.application import service, internet
from twisted.internet import endpoints, protocol
from twisted.python import log
from twisted.python import usage

from twisted.web.server import Site

from creepy.api import CreepyAPI

DEFAULT_STRPORT = 'tcp:8000'

DEFAULT_JOBS = 1

DEFAULT_WORKERS = 1

class Options(usage.Options):
    """
    Provide a --debug option for starting the server in debug mode, and the
    ability to define what to listen on by using a string endpoint description.

    Documentation on how to configure a usage.Options object is provided here:
    http://twistedmatrix.com/documents/current/core/howto/options.html

    Endpoints are documented here in the API documentation:
    http://twistedmatrix.com/documents/current/api/twisted.internet.endpoints.html
    """
    optFlags = [['debug', 'd', 'Emit debug messages']]
    optParameters = [
        ["endpoint", "s", DEFAULT_STRPORT,
        "string endpoint descriptiont to listen on"],
        ["jobs", "j", DEFAULT_JOBS,
        "how many concurrent jobs should run"],
        ["workers", "w", DEFAULT_WORKERS,
        "howmany concurrent workers should run per job"],
    ]

class SetupService(service.Service):
    name = 'Setup Service'

    def __init__(self, reactor):
        self.reactor = reactor

    def startService(self):
        """
        Custom initialisation code goes here.
        """
        log.msg("Reticulating Splines")

        self.reactor.callLater(3, self.done)

    def done(self):
        log.msg("Finished reticulating splines")

def makeService(options):
    """
    Generate and return a definition for all the services that this package
    needs to run. Will return a 'MultiService' object with two children.
    One is a ExampleFactory listening on the configured endpoint, and the
    other is an example custom Service that will do some set-up.

    The method name and signature is the same as
    twisted.application.service.IServiceMaker.makeService, and is used
    automatically by ServiceMaker as in the example plugin found in the
    twisted/plugin/example_plugin.py file.
    """
    from twisted.internet import reactor

    debug = options['debug']

    api = CreepyAPI(options['jobs'], options['workers'], debug=True)
    f = Site(api, timeout=None)
    endpoint = endpoints.serverFromString(reactor, options['endpoint'])
    server_service = internet.StreamServerEndpointService(endpoint, f)
    server_service.setName('Creepy Daemon')

    setup_service = SetupService(reactor)

    ms = service.MultiService()
    server_service.setServiceParent(ms)
    setup_service.setServiceParent(ms)

    return ms
