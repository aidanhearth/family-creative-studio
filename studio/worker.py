"""One process owns the queue; OS file locking makes crash recovery unambiguous."""
import argparse
import fcntl
import time
import signal

class Shutdown(BaseException):
    pass

def stop(signum, frame):
    raise Shutdown()
from .store import Store
from .pipeline import build, EngineChanged
from .provenance import engine_fingerprint
from .runner import Cancelled

def worker_alive(root):
    with (root/'worker.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return True
        return False

def work(once=False):
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    store=Store()
    with (store.root/'worker.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        store.recover()
        loaded_engine=engine_fingerprint()
        while True:
            job=store.claim()
            if job:
                try: build(store,job,loaded_engine)
                except Shutdown:
                    store.update(job['id'],state='interrupted',error='Worker stopped; retry the saved snapshot.')
                    return
                except EngineChanged as error:
                    store.update(job['id'],state='failed',error=str(error));return
                except Cancelled as error:store.update(job['id'],state='cancelled',error=str(error))
                except Exception as error:store.update(job['id'],state='failed',error=f'{type(error).__name__}: {error}')
            elif once:return
            else:
                try:time.sleep(.5)
                except Shutdown:return

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args();work(args.once)
