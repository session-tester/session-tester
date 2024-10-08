# Session Tester - 面向会话的测试框架

一个 **面向会话（多轮请求、状态更新）** 的测试框架库。

## 一、简介

考虑推荐、抽奖等服务场景，每个用户会进行多轮请求，每轮请求的结果又依赖于之前的轮次。
对这类服务的功能测试，需要校验**每个请求返回**、**每个玩家的前后请求返回**、以及**所有玩家的返回分布**等是否符合预期。

本测试框架，针对以上类似场景，提供了一套解决方案:

- 为每个玩家维护一个会话信息，允许用户自定义用户信息结构、自定义请求包、根据返回更新会话状态、自定义会话终止条件。
- 自定义单请求返回、单会话、多会话的校验函数，用于逻辑正确与否的同时，还可以输出详细的报告，比如返回道具的分布概率等。

以下是 [demo/session_test_demo.py](demo/session_test_demo.py) 的一个示例。
四个测试用例包含了三类校验，并且最后一个测试用例产出了额外的详细数据：

![test_report_cn](docs%2Ftest_report_cn.png)

除此之外，框架还有其他一些特点：

- 高性能收发数据
- 解耦请求发送接收和数据验证，一次发送多次验证
- 详细的测试报告
- 将测试用例与函数相结合，通过函数注释生成测试报告
- 自动捕获`chk_`开头的测试函数，无需注册
- 多语言支持
- 多模块支持

TODO:

- 提供更多的加载用户数据的工具
- 累积更多的校验函数
- 自动生成测试用例
- UserInfo使用通用结构替换
- 流水线
- 发布到 PiPy 仓库

## 二、基本概念

![framework.png](docs%2Fframework.png)

### 2.1 TestCase/CheckResult

**TestCase(测试用例)** 针对一项独立逻辑功能进行逻辑校验。
每个测试用例最终会在测试报告中生成一条汇总信息，包括测试用例名称、预期结果、是否通过、异常信息等，*可选择*额外输出一份独立的测试报告。

TestCase 有三类，并对应不同的校验函数：

- SingleRequestCase，校验单一请求返回，校验函数输入参数为 `HttpTransaction`
- SingleSessionCase，校验单一会话，校验函数即单个用户多次请求返回，输入参数为 `Session`
- AllSessionCase，校验所有会话，即所有用户多次请求返回，校验函数输入参数为 `List[Session]`

比如，以下几项可以分别作为单独的测试用例存在：

- 一次返回中没有相同的推荐信息
- 多次的返回结果中没有相同的推荐信息
- 所有用户的返回的道具信息，符合概率分布

## 2.2 TestSuite/Tester

**TestSuite(测试套件)** 用于组织和执行测试用例，包含一个组测试用例和一个会话维持器，这一组测试用例将会对同一批请求返回进行校验。

不同的TestSuite 使用不同的请求进行校验。如果服务针对不同类型的用户，提供不同概率的道具产出，则可以使用多个的 TestSuite 加载不同类型的用户。

**Tester** 则是包含一个或多个TestSuite，来运行TestSuite 并将结果汇总，产生测试报告。

比如以下三项均为一个测试用例

一个测试用例结构，用于存储测试用例的相关信息，包括测试名称、测试函数、测试结果等。

### 2.3 UserInfo/HttpTransaction/Session

**UserInfo** 是一个用户信息结构，用于存储用户的基本信息。
`user_id`, `user_type` 等常用字段可以直接写入结构，其他属性，可以写入字典 `extra` 中。

**HttpTransaction** 是一个 HTTP 事务结构，用于存储 HTTP 请求和响应的相关信息，包括请求时间、请求、响应、状态码、耗时等，用于后续分析和验证。

**Session** 是一个会话结构，用于存储单个用户的多次请求和响应，以及用户的一些状态。
Session 是存储的单元，每个对应一个文件存放在 test_sessions 目录下。该目录可以通过 `TEST_SESSION_DIR` 环境变量配置。

### 2.4 SessionMaintainer

SessionMaintainer 是一个会话维护器，其中有一个 `user_info_queue`用于存储用户信息。
使用者需要指定URL、HTTP方法，另外须简单继承并实现其四个方法，这4个方法伴随着一个会话的生命周期：

- ``init_session`` 会话开始时调用，可以用于初始化Session，比如拉去用户附加信息、清理用户缓存状态
- ``req_wrapper`` 用于根据会话状态，封装当次请求包的内容
- ``update_session`` 用于处理请求返回，更新会话状态
- ``should_stop_session`` 判断会话是否需要停止

另外，方法 ``load_user_info()`` 用于用户信息太大时的加载，可以边运行边加载。如果数据量少，也可以直接放到 ``user_info_queue`` 中。

![session_lifecycle.png](docs%2Fsession_lifecycle.png)

### 2.6 测试报告

测试报告是一个Excel文件，包括汇总表、检测详情表。

汇总表包括测试标题、测试预期、是否通过、异常示例等信息。

每个测试用例可以输出一个检测详情表，所输出可以自定义表结构和数据。

## 三、安装

## 四、使用方法

项目中 [demo/session_test_demo.py](demo/session_test_demo.py) 中提供了一个比较详细的使用 Demo。

本节将根据该 Demo 介绍框架的使用。

### 4.0 被测服务介绍

为了使用框架，这里提供了一个简单的HTTP服务。其主要逻辑有以下几点：

- 接收 POST 请求：服务器接收包含用户 ID、回合数和已拥有数字列表
- 生成随机物品：从0-99中，提出已经推荐给用户数字，从剩余数字中随机选择 5 个物品
- 计算签名：基于用户 ID、回合数和随机选择的物品计算一个 MD5 签名

我们可以做以下测试：

- 测试每个请求的返回的签名是否正确
- 测试每个返回中没有重复的数字
- 测试每个用户的多轮返回中，数字没有重复
- 统计所有用户的返回，检查数字的总的分布情况

接下来，我们针对上述逻辑进行测试

### 4.1 定义 SessionMaintainer

为了维护会话，我们需要定义一个 SessionMaintainer 类。

**很多用户初始化的操作可以放到这里来做，比如用户 Redis 缓存的清理，而无需使用别的工具进行清理。**

示例的初始化函数，会在创建爱你会话时，创建列表维护用户获得的数字列表，创建一个 round 来维护轮次。

```python
@staticmethod
def init_session(s: Session):
    s.ext_state.update({"items": [], "round": 0})
```

**终止函数可以是判断返回中的有了某个道具、会话累计了多少轮次、用户的余额是否为0等等。**

本示例中，因为一共只有100个数字，因此我们只发送20轮请求：

```python
@staticmethod
def should_stop_session(s: Session) -> bool:
    return len(s.transactions) >= 20
```

**会话状态的维护让我们能模拟调用的状态维护，当有请求返回后，相关状态应该得到更新。**

本示例中，在收到返回后，会更新轮次+1，并将返回的数字进行记录：

```python
@staticmethod
def update_session(s: Session):
    o = s.transactions[-1].rsp_json()
    s.ext_state["items"] += o["items"]
    s.ext_state["round"] = o["next_round"]
```

**请求包装函数，根据用户信息和会话状态，生成请求包**

本示例中，请求包装函数会将用户ID、轮次、已有数字列表构造出请求：

```python
@staticmethod
def wrap_req(s: Session):
    ui = s.user_info
    items_owned = s.ext_state.get("items", [])
    round_ = s.ext_state.get("round", 0)
    return {"user_id": ui.userid, "round": round_, "items_owned": items_owned}
```

### 4.2 定义测试用例

三类测试用例，接收的参数不同，分别是 `HttpTransaction`、`Session`、`List[Session]`。

但是他们的返回都是三个元素的元组，分别是`是否通过`、`未通过的提示信息`、`测试报告信息`。(如果不输出，可以只返回前两个参数，框架已做兼容)

单请求返回校验：

```python
def chk_no_repeat_item(s: HttpTransaction):
    """单请求-返回道具重复性校验:
    1. 返回结果中items字段不重复
    """
    items = s.rsp_json().get("items")
    if len(set(items)) == len(items):
        return True, ""
    return False, f"items repeat, {s.response}"
```

单会话校验：

```python
def chk_no_repeat_item_in_all_sessions(s: Session):
    """
    单用户-返回道具重复性校验:
    1. 所有请求返回结果中items字段不重复
    """
    item_set = set()
    for t in s.transactions:
        for item in t.rsp_json().get("items"):
            if item in item_set:
                return False, f"item[{item}] repeat, {t}"
            item_set.add(item)
    return True, ""
```

**所有会话校验可以应用在返回的统计，每个项的统计信息是否偏差过大可以作为判断是否通过的条件。这些统计信息可以作为额外的报告产出。
**

示例中，只是简单地输出了数量统计，并没有做概率相关的计算：

```python
def chk_items_dist_in_all_sessions(ss: List[Session]):
    """
    返回道具分布校验:
    1. 所有请求返回结果中items字段分布均匀
    """
    item_dist = {}
    for s in ss:
        for t in s.transactions:
            for item in t.rsp_json().get("items"):
                item_dist[item] = item_dist.get(item, 0) + 1
    dist_detail = []
    for k in sorted(item_dist.keys()):
        v = item_dist[k]
        dist_detail.append({"item": k, "count": v})

    return True, "", dist_detail
```

这里在有错的 Demo 上其产生的结果如下：

![test_report_dist_detail](docs%2Ftest_report_dist_detail_cn.png)

### 4.3 执行测试

上述工作都准备好之后，就可以运行测试并校验结果了。

首先，我们需要创建一些用户，并塞到队列中。

```python
    # 1. 加载用户信息
user_info_queue = queue.Queue()
for i in range(10):
    user_info_queue.put(UserInfo(
        userid=uuid.uuid4().hex,
        extra={"index": i},
    ))
```

然后，我们创建一个测试对象，将一些基础信息设置到其中。

```python
env = "release"  # 环境
t = Tester(
    label=f"{env}_{cred_id}",
    user_info_queue=user_info_queue,  # 用户信息队列
    url="http://localhost:8000",  # 服务地址
    session_maintainer_cls=SessionMaintainer,
    title="Demo Test",  # 活动名称，用于生成报告
    thread_cnt=80
)
```

最后，我们运行测试用例产生报告。

```python
t.run(
    test_cases=auto_gen_cases_from_chk_func(),
    # session_cnt_to_check=1000,  # 检查的数量，如果用户队列数据大于该数值，实际使用用户队列大小
    # only_check=True,  # 只检查，不发送请求
    clear_session=True
)
```

运行时终端会打印过程日志：

![process_logging_cn.png](docs%2Fprocess_logging_cn.png)

并且会在 ``test_reports`` 目录下生成报告：

![report_location_cn.png](docs%2Freport_location_cn.png)

# FAQ

## 为什么要将load_user_info和 session的维护分开？

如果将用户信息的加载放在 init_session() 中看上去会简单一些，但是往往用户数据的加载是需要单独去批量拉取，放在init_session中会打乱这个加载过程。

## 为什么 load_user_info 是成员方法，而其他四个是静态方法？

因为 load_user_info 需要往一个队列里塞数据，需依附于一个具体的对象。后者于具体的示例无关，仅与传递的参数Session有关。