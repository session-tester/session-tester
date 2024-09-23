import queue
import threading

from .client import Client
from .session import Session


# 获得大量的用户信息，创建Session，创建Client，发送消息，保存Session
# 加载最近session

class Worker(threading.Thread):
    def __init__(self, label, url, user_info_queue, wrap_data_func, start_func, session_update_func, stop_func):
        threading.Thread.__init__(self)
        self.label = label
        self.url = url
        self.user_info_queue = user_info_queue
        self.wrap_data_func = wrap_data_func
        self.start_func = start_func
        self.session_update_func = session_update_func
        self.stop_func = stop_func

    def run(self):
        while True:
            try:
                user_info = self.user_info_queue.get_nowait()
                session = Session(label=self.label)
                session.create(user_info=user_info, transactions=[])
                client = Client(session=session, url=self.url)
                client.run(self.wrap_data_func, self.start_func, self.session_update_func, self.stop_func)
                session.dump()
            except queue.Empty:
                return


def load_sessions(env, cred_id, n=100) -> list:
    label = f"{env}_{cred_id}"
    return Session.load_sessions(label, n)


class BatchSender(object):
    def __init__(self, env, cred_id, url, thread_cnt):
        self.env = env
        self.cred_id = cred_id
        self.thread_cnt = thread_cnt
        self.url = url
        self.label = f"{env}_{cred_id}"

    def run(self, user_info_queue, wrap_data_func, start_func=None, session_update_func=None, stop_func=None):
        t_list = []

        for i in range(min(self.thread_cnt, user_info_queue.qsize())):
            t = Worker(self.label, self.url, user_info_queue, wrap_data_func, start_func, session_update_func,
                       stop_func)
            t_list.append(t)

        for t in t_list:
            t.start()

        for t in t_list:
            t.join()
