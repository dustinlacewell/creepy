from lxml import html, etree
from StringIO import StringIO
from urlparse import urljoin
from collections import defaultdict

from twisted.internet import threads
from twisted.internet.defer import Deferred, DeferredList, setDebugging
setDebugging(True)

from twisted.web.client import getPage
from twisted.python import log

import shortuuid

from txrdq.rdq import ResizableDispatchQueue

def clean(url):
    if url.endswith('/'):
        return url[:-1]
    return url

def parse_html(html):
    html_parser = etree.HTMLParser()
    tree = etree.parse(StringIO(html), html_parser)
    return tree

def _parse_html(html):
    return threads.deferToThread(parse_html, html)

class Job(object):
    """
    Represents a scraping job and its results.
    """

    def __init__(self, urls, depth=0, debug=False):
        self.urls = urls
        self.depth = depth
        self.debug = debug
        self.uuid = shortuuid.uuid()
        self.pages = defaultdict(list) # processed pages
        self.images = defaultdict(list) # found images
        self.errors = {} # pages with errors
        self.waiting = 0 # pages waiting to be processed
        self.completed = 0 # pages successfully procssed
        self.job = None # underlying RDQ job
        self.queue = None # underlying worker RDQ
        self.finished = Deferred() # final deferred

    def check_done(self, *args, **kwargs):
        """
        Called anytime a worker is done processing through success or failure.
        If all pending workers have been completed, fire the finished deferred.
        """
        self.completed += 1
        self.waiting -= 1
        if self.waiting == 0 and self.finished is not None: 
            self.finished.callback(self)
            self.finished = None

    def link_error(self, failure, url):
        """
        Record anytime a worker bails with an error.
        """
        self.errors[url] = str(failure.value)
        self.check_done()

    def add_link(self, url, depth):
        """
        Add an additional pending link for workers to process.
        """
        if url not in self.pages:
            self.waiting += 1
            self.queue.put((url, depth))

    def start_link(self, link_data):
        """
        Begin working on a new link.
        """
        url, depth = link_data
        url = clean(url)
        self.pages[url] = []
        d = self.crawlPage(str(url), depth)
        d.addCallback(self.check_done)
        d.addErrback(self.link_error, url)
        d.addErrback(self.check_done)
        return d

    def start(self, workers=1):
        """
        Start this job.
        """
        # create a worker queue just for this job
        self.queue = ResizableDispatchQueue(self.start_link, workers)
        log.msg("Starting job: %s" % self.uuid)

        # add all top-level urls to worker queue
        for url in self.urls:
            self.add_link(url, self.depth)    
        return self.finished

    def extract_images(self, tree, url):
        """
        Extracts all images from a parsed lxml tree.
        """
        if self.debug:
            print ""
            print "Extracting images from", url
        for src in tree.xpath('/html/body//img/@src'):
            src_link = urljoin(url, src)
            self.pages[url].append(src_link)
            self.images[src_link].append(url)
        return tree

    def extract_links(self, tree, url, depth):
        """
        Extracts all links from a parsed lxml tree.
        Filters out any links we've already seen.
        """
        if self.debug:
            print ""
            print "Extracting links from", url, depth
        links = [
            urljoin(url, href)
            for href in tree.xpath('/html/body//a/@href')
        ]
        links = list(set(links) - set(self.pages))
        for link in links:
            self.add_link(link, depth)

    def crawlPage(self, url, depth):
        """
        Crawl a page and extract images.
        If depth is non-zero, recurse into any found links.
        """
        if self.debug:
            print ""
            print "Crawling", url, depth
        d = getPage(url)
        d = d.addCallback(_parse_html)
        d = d.addCallback(self.extract_images, url)
        if depth:
            d = d.addCallback(self.extract_links, url, depth-1)
        return d
