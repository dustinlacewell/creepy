
Running The Worker
-------------------

Provided that the creepy is in the PYTHONPATH you may run these commands::

help on the twistd flags

    twistd --help

help on the plugin flags

    twistd creepy --help

start the daemon in various different configurations

    twistd -n creepy
    twistd -n creepy --strport tcp:8000 --debug
    twistd -n -r epoll creepy --strport unix:/var/tmp/creepy-unix-socket
    twistd -n creepy -s ssl:8000:privateKey=key.pem:certKey=cert.pem

change the amount of concurrent jobs with -j

    twistd -n creepy -j 3

change the amount of concurrent workers per job with -w

    twistd -n creepy -w 100


You may specify any reactor in the twistd -r argument, you may specify any
endpoint description in the strport, and it will set up a little listening
server.

Running on Boot
---------------

This is an appropriate way of running a daemon on boot, from a supervisor of 
some kind, or from an init.d script::

    /usr/bin/twistd --reactor=epoll --nodaemon \
                    --syslog --prefix=creepy \
                    --pidfile=/var/run/creepy.pid \
                    --uid=nobody --gid=nobody \
                    creepy --strport tcp:8000

Breaking down these options:
    
 * **--reactor=epoll** is a more efficient reactor implementation.
 * **--nodaemon** stops twisted from daemonising, and will run it in the foreground
   omit --nodaemon, unless you are running under a supervisor.
 * **--syslog** and --prefix provide logging to your OS syslog daemon.
 * **--pidfile** will save the pid in an appropriate place.
 * **--uid** and **--gid** will drop privs to the nobody user (uid 1)

No output will be seen on your terminal if you test this command. Look in
/var/log/syslog or /var/log/messages to see the logs.


Browsing the REST endpoints
---------------------------

* denotes required arguments

POST "/echo"
------------
CreepyAPI.echo
* args:
  * ANY

CreepyAPI.echo will simply return the provided JSON encoded arguments back to
the caller.

--

POST "/": CreepyAPI.start_job
    args:
        * "urls": list of urls to crawl
        - "depth": How many levels of recursion past the initially provided
           urls to crawl. Default 0. Max 3. Any value above 3 will be limited
           to 3.

    retval:

        {
            "job": "XnCCZiYPTfnjB6ZwZSwfxC",
            "response_code": 200
        }

CreepyAPI.start_job will initialize a job and place it into the job queue with
a status of "pending". Jobs are processed in order, one at a time.

--

GET "/status/<job id>"
    args:
        NONE

    retval:
        {
            "status": "running",
            "num_completed": 0,
            "response_code": 200,
            "start_time": 1381001340.045198,
            "num_images": 1694,
            "num_parsed_pages": 1571,
            "queued_time": 1381001340.045161,
            "job": "TNxNej3Tau85QcGKoHVCwg",
            "urls": ["http://docker.io"]
        }

        when finished

        {
            "status": "finished",
            "total_time": 70.57744407653809,
            "num_completed": 1,
            "ResponseCode": 200,
            "start_time": 1381001340.045198,
            "num_images": 6387,
            "num_parsed_pages": 1770,
            "queued_time": 1381001340.045161,
            "job": "TNxNej3Tau85QcGKoHVCwg",
            "stop_time": 1381001410.622642,
            "urls": ["http://docker.io"]
        }        

CreepyAPI.job_status will return JSON encoded data describing the state of queried job.

--

GET "/result/<job id>"
    args:
        - "result_format": one of:
            'list' : Format "results" as a simple list of all images collected.
            'by_page' : Format "results" as a mapping of pages scraped to images found on those pages.
            'by_image' : Format "results" as a mapping of images to pages those images were found on.

        - "include_empty": If true, include pages scraped that contained no images.


    retval:
        {
            "total_time": 70.57744407653809,
            "num_pages": 1770,
            "response_code": 200,
            "start_time": 1381001340.045198,
            "num_images": 6387,
            "results": [IMAGE ... URLS ... HERE],
            "job": "TNxNej3Tau85QcGKoHVCwg",
            "stop_time": 1381001410.622642,
            "urls": ["http://docker.io"]
        }

CreepyAPI.job_result will return information about completed jobs including
runtime and the results of the scraping work. If the job is not yet complete
job_result will return an error.
