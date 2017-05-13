"""System for handling the parallel processing on the file system.

The use case is when we design a job to be able to be run multiple
times on the same server, where the jobs each work on distinct
directories.  Each job "claims" a directory when it begins working on
it and releases the directory when it is done.

We do this for the forecast generation, aggregation, result checking,
and cleanup jobs.

The system should handle situations where the process crashes before
it has released a directory; where we want to kill all processes early
and release their directories; where we want to track down logs for
each output; and where jobs of one kind either can or cannot be run
while jobs of another kind are active.

Usage:

 - Each process instantiates StatusManager, which begins a new log file.

 - When the process begins work in a directory, it calls "claim",
   which attempts to lock the directory and creates a job-specific
   status file, while represents that lock.

 - When the process complete it's work, it calls "release", which
   deletes the job-specific status file, but addes a new status line
   to the cross-job status file.
"""

import sys, os, glob, itertools, time, signal

class StatusManager(object):
    def __init__(self, jobname, jobtitle, logdir, timeout, exclusive_jobnames=[]):
        """
        Create a log file to capture all output, and set up to claim directories.

        Args:
            jobname: A short name for the job, used in the claim filename (e.g., aggregate)
            jobtitle: A short descriptive title for the job (e.g., "generate.aggregate configs/mortality-montecarlo.yml")
            logdir: The directory for log files.
            timeout: Seconds after which a job has started on a directory that we assume it has crashed and allow the directory to be re-claimed.
            exclusive_jobnames: Other job names which cannot be running in the same directory.  Note that `timeout` should be at least as long as the timeouts associated with these.
        """

        self.jobname = jobname
        self.jobtitle = jobtitle
        self.timeout = timeout
        self.exclusive_jobnames = exclusive_jobnames

        # Decide on the name of the log file
        if not os.path.exists(logdir):
            os.makedirs(logdir)
        for ii in itertools.count():
            logpath = os.path.join(logdir, "%s-%d.log" % (jobname, ii))
            if not os.path.exists(logpath):
                self.logpath = logpath
                break

        # Grab all std out
        self.sys_stdout = sys.stdout
        sys.stdout = DoubleLogger(self.logpath)

    def __del__(self):
        """Usually not used; allow std output to go back to its previous stream."""
        sys.stdout.close()
        sys.stdout = self.sys_stdout

    def claim(self, dirpath):
        """Claim a directory."""
        if not os.path.exists(dirpath):
            os.makedirs(os.path.abspath(dirpath))
        elif self.is_claimed(dirpath):
            return False

        status_path = StatusManager.claiming_filepath(dirpath, self.jobname)
        with open(status_path, 'w') as fp:
            fp.write("%d %s: %s\n" % (os.getpid(), self.jobtitle, self.logpath))

        return True

    def update(self, dirpath, status):
        """Provide additional status information."""
        status_path = StatusManager.claiming_filepath(dirpath, self.jobname)
        with open(status_path, 'a') as fp:
            fp.write(status + '\n')

    def release(self, dirpath, status):
        """Release the claim on this directory."""
        os.remove(StatusManager.claiming_filepath(dirpath, self.jobname))

        with open(StatusManager.globalstatus_filepath(dirpath), 'a') as fp:
            fp.write("%s %s: %s\n" % (time.asctime(), self.jobtitle, status))

    def is_claimed(self, dirname):
        """Check if a directory has claims from any of our jobs."""
        if not os.path.exists(dirname):
            return False

        for jobname in [self.jobname] + self.exclusive_jobnames:
            filepath = StatusManager.claiming_filepath(dirname, jobname)
            if os.path.exists(filepath):
                if time.time() - os.path.getmtime(filepath) < self.timeout:
                    return True
                # If after the timeout, leave it there but ignore it.

        return False

    @staticmethod
    def globalstatus_filepath(dirpath):
        """The path to the global status for the directory."""
        return StatusManager.claiming_filepath(dirpath, 'global')

    @staticmethod
    def claiming_filepath(dirpath, jobname):
        """Return the path to the status file used for claiming a directory."""
        return os.path.join(dirpath, "status-%s.txt" % jobname)

    @staticmethod
    def kill_active(dirpath, jobname):
        """Kill any job claiming this directory."""
        filepath = StatusManager.claiming_filepath(dirpath, jobname)

        if not os.path.exists(filepath):
            return

        with open(filepath, 'r') as fp:
            status = fp.read()
            pid = int(status.split()[0])
            os.kill(pid, signal.SIGTERM)

        os.remove(filepath)

class DoubleLogger(object):
    """From http://stackoverflow.com/questions/14906764/how-to-redirect-stdout-to-both-file-and-console-with-scripting"""
    def __init__(self, logpath):
        self.terminal = sys.stdout
        self.log = open(logpath, "a")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def close(self):
        self.log.close()

    def flush(self):
        #this flush method is needed for python 3 compatibility.
        #this handles the flush command by doing nothing.
        #you might want to specify some extra behavior here.
        pass