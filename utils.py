from client import Session


def stop_till_n_repeat(n):
    def session_stop_func(s: Session):
        return len(s.transactions) >= n

    return session_stop_func
