import queue
import threading

from .client import Client
from .session import Session


# 获得大量的用户信息，创建Session，创建Client，发送消息，保存Session
# 加载最近session

class Worker(threading.Thread):
    def __init__(self, label, url, user_info_queue, session_maintainer_cls):
        threading.Thread.__init__(self)
        self.label = label
        self.url = url
        self.user_info_queue = user_info_queue
        self.session_maintainer_cls = session_maintainer_cls

    def run(self):
        while True:
            try:
                user_info = self.user_info_queue.get_nowait()
                session = Session(label=self.label)
                session.create(user_info=user_info, transactions=[])
                client = Client(session=session, url=self.url)
                client.run(self.session_maintainer_cls.wrap_data_func, self.session_maintainer_cls.start_func,
                           self.session_maintainer_cls.session_update_func, self.session_maintainer_cls.stop_func)
                session.dump()
            except queue.Empty:
                return


class BatchSender(object):
    def __init__(self, label, url, thread_cnt):
        self.thread_cnt = thread_cnt
        self.url = url
        self.label = label

    def run(self, user_info_queue, session_maintainer_cls):
        t_list = []

        for i in range(min(self.thread_cnt, user_info_queue.qsize())):
            t = Worker(self.label, self.url, user_info_queue, session_maintainer_cls)
            t_list.append(t)

        for t in t_list:
            t.start()

        for t in t_list:
            t.join()
