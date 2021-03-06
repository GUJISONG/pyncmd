'''
@Author: greats3an
@Date: 2020-01-20 19:26:37
@LastEditors  : greats3an
@LastEditTime : 2020-02-11 16:47:48
@Site: mos9527.tooo.top
@Description: Pool-like downloader
'''
import os,sys,time
from threading import Thread
from queue import Queue
from requests import Session
from .progressbar import ProgressBar
from .clisheet import CLISheet


class PoolWorker(Thread):
    '''
            Basic worker model.
    '''
    def __init__(self,queue,id=0):
        self.id = id
        self.task_queue = queue
        super().__init__()
        # This is needed for daemon flag to be set.
        self.daemon = True
        # Once set,the main thread won't stay to wait for its sub-threads to end

    def run(self):
        while True:
            task,args = self.task_queue.get()
            task(args) if args else task()
            self.task_queue.task_done()

class DownloadWorker(PoolWorker):
    '''
        Workers for downloading:

            Needed the task_queue,which contains the url needed to fetch a download
                session     :       which is the request.session used to download files
                    id      :       to identify the downloader it self
    '''

    def init_status(self):
        self.status = {'id': self.id, 'status': None, 'url': None,
                       'path': None, 'length': None, 'finished': 0}

    def __init__(self, session: Session,task_queue: Queue, id=0,  timeout=5,buffer_size=256):
        super().__init__(task_queue,id)
        self.session = session
        self.timeout = timeout
        self.buffer_size = buffer_size
        # Buffer size.Note it's in KB
        self.init_status()


    def __call__(self):
        '''
        Reports the status once called
        '''
        return self.status

    def run(self):
        while True:
            url,path = self.task_queue.get()
            # This will block the thread if no queue object is available,work start        
            self.init_status()
            # Reinitalize status
            self.status = {**self.status, 'url':url,'path':path}
            try:
                r = self.session.get(url, stream=True, timeout=self.timeout)
                self.status['status'] = r.status_code
                # Send GET request and send stream flag to download data in a streamed fashion
            except Exception:
                self.status['status'] = 0x198
                # Time-out：failed to get the requested resource (code 408)
            if not self.status['status'] == 0xC8:
                self.task_queue.task_done()
                continue
            # Stops this iteration if server doesn't response 200 (0xC8)
            length = int(r.headers['content-length'])
            if (length):
                self.status['length'] = length
            # Sets content-length if the server ever sends one
            p = os.path.split(path)
            if p[0]:
                if not os.path.exists(p[0]):os.makedirs(p[0])
            # Creates directory tree if dosen't exsist
            try:
                with open(path, 'wb') as f:
                    chunk_size = self.buffer_size * 1024
                    # Buffer of 128 KB
                    for chunk in r.iter_content(chunk_size):
                        # Iterate content with buffer size of which
                        f.write(chunk)
                        self.status['finished'] += len(chunk)
                        # Writes to file and updates infomation
                self.status['status'] = 0xFF
                # sets flag to 0xFF since 255 isnt in the HTTP Standard
            except Exception as e:
                # Uncaught excpetion
                print(e)
            self.task_queue.task_done()
            # Marks that one task is completed.Note that it doesn't specifiy which task,work end
class Downloader():
    '''
        Threadpool a-like downloader
            session   :   request.Session()
            pool_size :   downloader count,specifies how many cocurrent tasks can be processed at once
            timeout   :   the time before raising TimeoutException
            append    :   append a new download task
            wait      :   wait util all tasks are finished
            report    :   geneartes a pretty report
    '''

    def __init__(self,session: Session = None, worker=DownloadWorker, pool_size=1, timeout=5,buffer_size=256):
        if not session:session = Session()
        self.sheet = CLISheet(('ID', 3), ('PROGRESS', 60), ('STATUS', 6))
        self.pool_size = pool_size
        self.task_queue = Queue()
        def get_worker(i):
            if worker == DownloadWorker:
                return worker(session,self.task_queue,id=i, timeout=timeout,buffer_size=buffer_size) 
            elif worker == PoolWorker:
                return worker(self.task_queue,id=i) 
            else:
                raise NotImplementedError
        self.workers = [get_worker(i) for i in range(0, pool_size) ]
        # Generate workers
        for worker in self.workers:
            worker.start()
            self.sheet.add_line()
        # and start them

    def report(self, format='{}\n IN QUEUE:{},DOWNLOADING:{}'):
        '''
            Generates report.
        '''
        for worker in self.workers:
            if not type(worker) in [DownloadWorker]:
                raise NotImplementedError(type(worker))
            progress = ProgressBar(worker()['length'])
            self.sheet.modify_line(
                ('ID', worker()['id']),
                ('PROGRESS', progress(worker()['finished'])),
                ('STATUS', worker()['status']),
                pos=worker()['id']
            )
        return format.format(self.sheet.get_output(), self.task_queue.qsize(), self.task_queue.unfinished_tasks)

        
    def wait(self, *args, func=None, do_when_done=True):
        '''
            Equvilant to .task_queue.join(),but tasks during wait time is possible.
                do_when_done    :   Specifies whether exec the fucntion when loop ends or not
            Waits for all tasks are finished
        '''
        def do_func():
            if args and func:
                func(*args)
            elif func:
                func()

        while self.task_queue.unfinished_tasks != 0:
            do_func()
        if do_when_done:
            do_func()

    def append(self, url, path):
        '''        
            Appends a new download task into queue

                url     : the file url
                path    : the path of the destination file
        '''
        self.task_queue.put((url,path))
