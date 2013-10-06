from twisted.python import log

from txrdq.job import Job
from txrdq.rdq import ResizableDispatchQueue

class AttributingQueue(ResizableDispatchQueue):
    """
    RDQ that tries to attach the underlying job to the 
    job argument.
    """

    def put(self, jobarg, priority=0):
        if self.stopped:
            raise QueueStopped()
        else:
            job = Job(jobarg, priority)
            jobarg.job = job
            d = job.watch().addBoth(self._jobDone, job)
            self._queue.put(job, priority)
            return d    

class RDQueue(object):
    def __init__(self, max_jobs=1, max_workers=1):
        self.queue = AttributingQueue(self.start, max_jobs)
        self.max_workers = max_workers
        self.jobs = {}
        self.pending = {}
        self.running = {}
        self.finished = {}

    def put(self, job):
        """
        Track a new job and add it to the queue.
        """
        self.jobs[job.uuid] = job
        self.pending[job.uuid] = job
        self.queue.put(job)

    def start(self, job):
        """
        Start the job.
        """
        uuid = job.uuid
        if uuid in self.pending:
            del self.pending[uuid]
            self.running[uuid] = job
            d = job.start(self.max_workers)
            d.addCallback(self.finish, job)
            return d

    def finish(self, results, job):
        """
        Move the job into the finished map.
        """
        uuid = job.uuid
        if uuid in self.running:
            del self.running[uuid]
            self.finished[uuid] = (job, results)

