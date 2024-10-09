# Session Tester - A Framework for Session-Based Testing

<p align="center">
    <a>English</a> •
    <a href="README.md">中文</a> 
</p>

A **session-based (multi-round requests, state updates)** testing framework library.

The testing process, expected checks, and reports are all reflected in the code, embodying the concept of **Test as Code
**.

## 1. Introduction

Consider scenarios such as recommendation systems or lottery services, where each user makes multiple requests, and the result of each request depends on the previous rounds. Functional testing for such services requires verifying whether
**each request's response**, **each player's consecutive request responses**, and **the distribution of responses across
all players** meet expectations.

This testing framework provides a solution for the above scenarios:

- Maintains session information for each player, allowing users to customize user information structures, request packets, update session states based on responses, and define session termination conditions.
- Customizable validation functions for single request responses, single sessions, and multiple sessions, which can output detailed reports, such as the distribution probabilities of returned items.

Install directly using pip:

```shell
pip install session-tester
```

Import the module:

```python
import session_tester
```

Below is an example from [demo/session_test_demo.py](demo/session_test_demo.py). The four test cases include three types of validations, and the last test case produces additional detailed data:

![test_report_cn](https://raw.githubusercontent.com/session-tester/session-tester/main/docs%2Ftest_report_cn.png)

Additionally, the framework has other features:

- High-performance data transmission
- Decouples request sending/receiving and data validation, allowing multiple validations for a single send
- Combines test cases with functions, generating test reports from function annotations, with the report order following the code definition order
- Automatically captures test functions starting with `chk_`, no registration needed
- Single test cases can produce additional test reports
- Multi-language support
- Multi-module support

This framework is designed to focus on testing the special scenarios of **single stateful services
**, where the tested service has only a single HTTP URL. Comprehensive testing frameworks cover a wide range but come with higher usage costs.

## 2. Basic Concepts

![framework.png](https://raw.githubusercontent.com/session-tester/session-tester/main/docs%2Fframework.png)

### 2.1 TestCase/CheckResult

**TestCase
** is used to validate an independent logical function. Each test case will generate a summary in the test report, including the test case name, expected result, pass/fail status, exception information, and optionally, an additional independent test report.

There are three types of TestCase, each corresponding to different validation functions:

- SingleRequestCase: Validates a single request response, with the validation function taking `HttpTransaction` as input.
- SingleSessionCase: Validates a single session, with the validation function taking `Session` as input.
- AllSessionCase: Validates all sessions, with the validation function taking `List[Session]` as input.

For example, the following can be separate test cases:

- No duplicate recommendation information in a single response
- No duplicate recommendation information in multiple responses
- The distribution of item information returned by all users meets the expected probability distribution

`CheckResult` contains three elements: pass/fail status, failure message, and test report information. If the test fails, the reason for failure can be provided. If an additional test report is needed, the test information field should be filled.

### 2.2 TestSuite/Tester

**TestSuite
** is used to organize and execute test cases, containing a group of test cases and a session maintainer. This group of test cases will validate the same batch of request responses.

Different TestSuites use different requests for validation. If the service provides different probabilities of item output for different types of users, multiple TestSuites can be used to load different types of users.

**Tester** contains one or more TestSuites, runs the TestSuites, and aggregates the results to produce a test report.

For example, the following are test cases:

A test case structure stores information related to the test case, including the test name, test function, test result, etc.

### 2.3 UserInfo/HttpTransaction/Session

**UserInfo
** is a user information structure used to store basic user information. Common fields like `user_id` and `user_type` can be directly written into the structure, while other attributes can be written into the `extra` dictionary.

**HttpTransaction
** is an HTTP transaction structure used to store information related to HTTP requests and responses, including request time, request, response, status code, duration, etc., for subsequent analysis and validation.

**Session
** is a session structure used to store multiple requests and responses of a single user, as well as some user states. Sessions are stored as units, each corresponding to a file in the `test_sessions` directory. This directory can be configured via the `TEST_SESSION_DIR` environment variable.

### 2.4 SessionMaintainer

SessionMaintainer is a session maintainer that includes a `user_info_queue` for storing user information. Users need to specify the URL and HTTP method, and simply extend and implement its four methods, which accompany the lifecycle of a session:

- `init_session`: Called at the start of a session, can be used to initialize the session, such as fetching additional user information or clearing user cache states.
- `req_wrapper`: Used to wrap the request packet content based on the session state.
- `update_session`: Used to process the request response and update the session state.
- `should_stop_session`: Determines whether the session needs to stop.

Additionally, the method `load_user_info()` is used for loading user information when the data is too large, allowing for loading while running. If the data volume is small, it can be directly placed into the `user_info_queue`.

### 2.5 Test Report

The test report is an Excel file that includes a summary sheet and a detailed check sheet.

The summary sheet includes the test title, test expectations, pass/fail status, and exception examples.

Each test case can output a detailed check sheet, with customizable table structure and data.

## 3. Usage - Demo

The project [demo/session_test_demo.py](demo/session_test_demo.py) provides a detailed usage demo.

This section will introduce the usage of the framework based on that demo. The main process includes:

- Creating one or more TestSuites
    - Each TestSuite contains a SessionMaintainer
    - Each TestSuite contains one or more TestCases
- Running the tests

### 3.1 Introduction to the Tested Service

To use the framework, a simple HTTP service is provided here. Its main logic includes:

- Receiving POST requests: The server receives a request containing the user ID, round number, and a list of already owned numbers.
- Generating random items: From 0-99, excluding numbers already recommended to the user, randomly selecting 5 items from the remaining numbers.
- Calculating a signature: Based on the user ID, round number, and randomly selected items, calculating an MD5 signature.

We can perform the following tests:

- Test whether the signature returned by each request is correct.
- Test that there are no duplicate numbers in each response.
- Test that there are no duplicate numbers in multiple responses for each user.
- Count the returns of all users and check the overall distribution of numbers.

Next, we will test the above logic. Since the logic is simple, **the demo test will only involve one TestSuite**.

### 3.2 Defining SessionMaintainer

To maintain sessions, we need to define a `SessionMaintainer` class. SessionMaintainer is divided into two parts: a member method for loading user information, and four static methods for handling session process information.

The method `load_user_info()` for loading the user queue is used to load user information. Here, we simply put user IDs into the queue. Alternatively, this function can be omitted, and the `user_info_queue` can be directly populated during initialization.

```python
def load_user_info(self):
    for i in range(10):
        self.user_info_queue.put(UserInfo(userid=uuid.uuid4().hex, extra={"index": i}))
```

**The session initialization function `init_session()` is used to initialize each session and is called when the session
is created
**. Many user state cleanup or initialization operations can be done here, such as clearing user Redis cache, without the need for additional tools.

In the example, initialization creates a list to maintain the numbers obtained by the user and creates a round to maintain the round number.

```python
@staticmethod
def init_session(s: Session):
    s.ext_state.update({"items": [], "round": 0})
```

**The session initialization function `init_session()` is used to initialize each session and is called when the session
is created
**. Many user state cleanup or initialization operations can be done here, such as clearing user Redis cache, without the need for additional tools.

In the example, initialization creates a list to maintain the numbers obtained by the user and creates a round to maintain the round number.

```python
@staticmethod
def init_session(s: Session):
    s.ext_state.update({"items": [], "round": 0})
```

**The termination judgment function `should_stop_session()` allows the user to actively determine when to stop the
session
**. For example: determining if a certain item is in the response, how many rounds the session has accumulated, whether the user's balance is zero, etc.

In this example, since there are only 100 numbers in total, we only send 20 rounds of requests:

```python
@staticmethod
def should_stop_session(s: Session) -> bool:
    return len(s.transactions) >= 20
```

**The session update function `update_session()` can simulate the state maintenance and update of the caller, and is
called each time a request response is received**.

In this example, after receiving the response, the round number is incremented by 1, and the returned numbers are recorded:

```python
@staticmethod
def update_session(s: Session):
    o = s.transactions[-1].rsp_json()
    s.ext_state["items"] += o["items"]
    s.ext_state["round"] = o["next_round"]
```

**The request wrapping function `wrap_req()` generates the request packet based on user information and session state
**. It can be a dictionary, which will be converted to JSON, or it can be text directly used as the message body.

In this example, the request wrapping function constructs the request using the user ID, round number, and the list of owned numbers:

```python
@staticmethod
def wrap_req(s: Session):
    ui = s.user_info
    items_owned = s.ext_state.get("items", [])
    round_ = s.ext_state.get("round", 0)
    return {"user_id": ui.userid, "round": round_, "items_owned": items_owned}
```

### 3.3 Defining Test Suites

A test includes one or more TestSuites.

Each TestSuite contains multiple TestCases and a SessionMaintainer, which can be passed in during initialization.

TestSuites have a name, and TestCases have a name and an expectation to generate test reports. To keep it concise and follow the Test as Code principle, we directly extract these test case functions from the comments.

![test_comment_report.png](https://raw.githubusercontent.com/session-tester/session-tester/main/docs%2Ftest_comment_report.png)

All functions in the TestSuite that start with `chk_` will be automatically recognized as test cases. There are three types of test cases, each accepting different parameters: `HttpTransaction`, `Session`, and `List[Session]`. These functions need to return a `TestResult`.

Single request return validation:

```python
@staticmethod
def chk_rsp_sig(s: HttpTransaction) -> CheckResult:
    """Single Request - Signature Validation:
    1. The interface returns the sig field
    2. The sig field matches the calculated result of user_id, round, and items
    """
    req = s.req_json()
    rsp = s.rsp_json()
    sig = calc_sig(rsp.get("user_id", ""), req.get("round", 0), rsp.get("items", []))
    if sig == rsp.get("signature"):
        return CheckResult(True, "sig check pass")
    return CheckResult(False, f"sig check failed, {s.response}")
```

Single session validation:

```python
@staticmethod
def chk_no_repeat_item_in_all_sessions(s: Session) -> CheckResult:
    """
    Single User - Return Item Non-repetition Validation:
    1. The items field in all request responses does not repeat
    """
    item_set = set()
    for t in s.transactions:
        items = t.rsp_json().get("items", [])
        for item in items:
            if item in item_set:
                return CheckResult(False, f"item[{item}] repeat, {t}")
            item_set.add(item)
    return CheckResult(True)
```

**All session validations can be applied to the return statistics, and whether the statistical information of each item
deviates too much can be used as a condition for passing.**
**These statistics can be produced as additional reports.**

In the example, it simply outputs the count statistics without performing any probability-related calculations:

```python
@staticmethod
def chk_items_dist_in_all_sessions(ss: List[Session]) -> CheckResult:
    """
    Returns item distribution check:
    1. The distribution of the items field in the results of all requests is uniform.
    """
    item_dist = {}
    for s in ss:
        for t in s.transactions:
            items = t.rsp_json().get("items", [])
            for item in items:
                item_dist[item] = item_dist.get(item, 0) + 1

    dist_detail = [{"item": k, "count": v} for k, v in sorted(item_dist.items())]

    return CheckResult(True, "", dist_detail)
```

Here is the result generated on a faulty demo:

![test_report_dist_detail](https://raw.githubusercontent.com/session-tester/session-tester/main/docs%2Ftest_report_dist_detail_cn.png)

### 3.4 Execute Tests

After preparing the above work, you can run the tests and verify the results.

We create a test object and set some basic information into it.

```python
t = Tester(
    name=f"release_12345",
    test_suites=[T(session_maintainer=SessionMaintainer())]
)
```

Finally, we run the test cases to generate a report.

```python
t.run(
    # session_cnt_to_check=1000,  # Number of checks, if the user queue data is greater than this value, the actual user queue size is used
    # only_check=True,  # Only check, do not send requests
    clear_session=True
)
```

The process logs will be printed in the terminal during execution:

![process_logging_cn.png](https://raw.githubusercontent.com/session-tester/session-tester/main/docs%2Fprocess_logging_cn.png)

And a report will be generated in the `test_reports` directory:

![report_location_cn.png](https://raw.githubusercontent.com/session-tester/session-tester/main/docs%2Freport_location_cn.png)

## 4. Auxiliary Tools

### Auxiliary Decorators for SessionMaintainer

There are several decorators starting with `sm_` to simplify the implementation of `SessionMaintainer`.

- `sm_n_rounds(n)` Simple judgment to resend requests for n rounds
- `sm_no_update` No need to update the state
- `sm_no_init` No initial state update

# FAQ

## Why separate load_user_info and session maintenance?

If user information loading is placed in init_session(), it may seem simpler, but often user data loading needs to be fetched in bulk separately, placing it in init_session would disrupt this loading process.

## Why is load_user_info a member method while the other four are static methods?

Because load_user_info needs to insert data into a queue, it needs to be attached to a specific object. The latter methods are unrelated to specific instances and only related to the passed Session parameters.

# TODO

- Provide more tools for loading user data
- Accumulate more validation functions
- Automatically generate test cases
- Replace UserInfo with a general structure
- Pipeline
- Link additional test reports
- Publish to the PyPi repository