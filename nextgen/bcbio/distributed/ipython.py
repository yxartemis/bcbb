"""Distributed execution using an IPython cluster.

Uses IPython parallel to setup a cluster and manage execution:

http://ipython.org/ipython-doc/stable/parallel/index.html

Borrowed from Rory Kirchner's Bipy cluster implementation:

https://github.com/roryk/bipy/blob/master/bipy/cluster/__init__.py
"""
import copy
import time
import uuid
import subprocess
import contextlib

from IPython.parallel import Client

from bcbio.pipeline.main import run_main

def _start(workers_needed, profile, cluster_id, delay):
    """Starts cluster from commandline.
    """
    subprocess.check_call(["ipcluster", "start",
                           "--daemonize=True",
                           "--delay=%s" % delay, 
                           "--log-level=%s" % 30,
                           #"--cluster-id=%s" % cluster_id,
                           "--n=%s" % workers_needed,
                           "--profile=%s" % profile])

def _stop(profile, cluster_id):
    subprocess.check_call(["ipcluster", "stop", "--profile=%s" % profile,
                           #"--cluster-id=%s" % cluster_id
                           ])

def _is_up(profile, cluster_id, n):
    try:
        client = Client(profile=profile, cluster_id=cluster_id)
        up = len(client.ids)
    except IOError, msg:
        return False
    else:
        not_up = n - up
        if not_up > 0:
            return False
        else:
            return True

@contextlib.contextmanager
def cluster_view(parallel):
    """Provide a view on an ipython cluster for processing.

    parallel is a dictionary with:
      - profile: The name of the ipython profile to use
      - cores: The number of cores to start for processing.
      - queue_type: Optionally, the type of parallel queue
        to start. Defaults to a standard parallel queue, can
        also specify 'multicore' for a multiple core machine
        and 'io' for an I/O intensive queue.
    """
    delay = 10
    max_delay = 300
    profile = parallel["profile"]
    if parallel.get("queue_type", None):
        profile = "%s_%s" % (profile, parallel["queue_type"])
    cluster_id = str(uuid.uuid1())
    # need at least two processes to run main and workers
    _start(parallel["cores"], profile, cluster_id, delay)
    try:
        slept = 0
        while not _is_up(profile, cluster_id, parallel["cores"]):
            time.sleep(delay)
            slept += delay
            if slept > max_delay:
                raise IOError("Cluster startup timed out.")
        client = Client(profile=profile, cluster_id=cluster_id)
        yield client.load_balanced_view()
    finally:
        _stop(profile, cluster_id)

def idict(orig, k, v):
    """Imitates immutability by adding a key/value to a new dictionary.
    """
    new = copy.deepcopy(orig)
    new[k] = v
    return new

def run_and_monitor(config, config_file, run_info, parallel):
    """Run a distributed analysis after starting an Ipython parallel environment.
    """
    with cluster_view(parallel) as view:
        parallel["view"] = view
        run_main(config, config_file, run_info["work_dir"],
                 parallel, run_info["fc_dir"], run_info["run_info_yaml"])