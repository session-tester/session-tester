from client import BatchTester, BatchSender, load_sessions


class Tester(object):
    def __init__(self, env, cred_id,
                 user_info_queue,
                 url: str,
                 req_wrapper: callable,
                 title: str,
                 thread_cnt: int = 50,
                 ):
        self.env = env
        self.cred_id = cred_id
        self.user_info_queue = user_info_queue
        self.url = url
        self.req_wrapper = req_wrapper
        self.thread_cnt = thread_cnt
        self.title = title
        self.session_cnt_to_check = self.user_info_queue.qsize()

        # 内部的变量
        self.batch_sender = BatchSender(
            env=self.env,
            cred_id=self.cred_id,
            url=self.url,
            thread_cnt=self.thread_cnt
        )

        self.bt = None

    def run(self, test_cases, only_check=False, session_cnt_to_check: int = 0):
        if not only_check:
            self.batch_sender.run(self.user_info_queue, self.req_wrapper)

        if session_cnt_to_check:
            self.session_cnt_to_check = session_cnt_to_check

        # 加载会话结果
        session_list = load_sessions(env=self.env, cred_id=self.cred_id, n=self.session_cnt_to_check)

        # 设置测试用例
        self.bt = BatchTester(self.title, session_list)

        # 进行校验
        self.bt.check(test_cases)

        # 产生报告
        print([str(x) for x in self.bt.report()])
        return session_list
