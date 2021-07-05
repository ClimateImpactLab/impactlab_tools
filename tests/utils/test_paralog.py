
from __future__ import absolute_import

import shutil
from impactlab_tools.utils import paralog
import os 

def test_claiming():
    statman1 = paralog.StatusManager('test', 'Testing process', 'testing-paralog', 60*60)
    print(statman1.logpath)
    if not statman1.claim("testing-paralog"):
        raise IOError("Cannot claim directory!")

    statman2 = paralog.StatusManager('test', 'Testing process', 'testing-paralog', 60*60)
    print(statman2.logpath)
    if statman2.claim("testing-paralog"):
        raise IOError("Accidentally claimed directory!")

    statman1.update("testing-paralog", "New status.")
    statman1.release("testing-paralog", "First pass complete.")

    if not statman2.claim("testing-paralog"):
        raise IOError("Cannot claim directory afterwards!")

    statman2.release("testing-paralog", "Second pass complete.")

    logpath1 = statman1.logpath
    logpath2 = statman2.logpath

    del statman2 # need to delete in opposite order for our test
    del statman1

    print(logpath1)
    print(logpath2)

    with open(paralog.StatusManager.globalstatus_filepath("testing-paralog"), 'r') as fp:
        print(fp.read())

    shutil.rmtree('testing-paralog')

def test_extra_log():

    ''' split tests by input :
    - two different instances of Status Manager with different job names and different suffizes => two different files 
    - successive loggings => appends to file 
    '''

    statman0 = paralog.StatusManager(jobname='test', jobtitle='Testing process', logdir='testing-paralog', timeout=60*60)
    extrapath = statman0.extra_log(suffix='-extra', msg='msg in first extra log')
    assert extrapath=="testing-paralog/test-0-extra.log"

    statman1 = paralog.StatusManager(jobname='test', jobtitle='Testing process', logdir='testing-paralog', timeout=60*60)
    statman1.extra_log(suffix='-extra', msg='msg in second extra log')

    assert os.path.exists("testing-paralog/test-0-extra.log")
    assert os.path.exists("testing-paralog/test-1-extra.log")
    with open("testing-paralog/test-0-extra.log", 'r') as fp:
        assert fp.read()=="msg in first extra log"

    with open("testing-paralog/test-1-extra.log", 'r') as fp:
        assert fp.read()=="msg in second extra log"

    statman1.extra_log(suffix='-extra', msg=' and another msg in second extra log')

    with open("testing-paralog/test-1-extra.log", 'r') as fp:
        assert fp.read()=="msg in second extra log and another msg in second extra log"

    del statman1
    del statman0

    shutil.rmtree('testing-paralog')

