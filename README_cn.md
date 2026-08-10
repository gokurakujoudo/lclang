# lclang

`lclang` 是面向 Python 应用的小型、异步优先配置语言。你可以用表达式描述一组
相互关联的值，从 Python 提供当前环境所需的输入，并且只计算本次运行真正请求的
结果。

当配置不再只是静态数据，但仍应当保持明确、可检查，并与应用代码分离时，可以使用
`lclang`。典型场景包括派生服务设置、部署策略、命令默认值以及请求级计算。

`lclang` 使用纯 Python 实现，要求 Python 3.14 或更高版本，没有第三方运行时依赖，
采用 MIT License。

> LCL 用于受信任的应用配置，不是执行攻击者表达式的安全沙箱。宿主应用提供的值和
> callable 仍然拥有普通 Python 对象原本具备的能力。

## 安装

```console
python -m pip install lclang
```

## 心智模型

大多数应用只需要理解两个概念：

- `Module` 是一组不可变、尚未求值的命名定义。它回答：**可以计算什么？**
- `Frame` 把 Module、宿主输入、名称查找层级、惰性结果快照以及它所拥有的异步工作
  组合起来。它回答：**这些定义在本次运行中代表什么？**

```text
            只解析一次                              每次运行创建

  表达式源码 ──> Module                Module + 宿主输入 ──> Frame
                  │                                         │
             可复用的定义                              惰性结果快照
```

Module 不包含求值状态，因此可以安全地在不同请求、租户、命令和测试之间复用。Frame
则有意保留状态，并且属于一个 event loop。每次独立运行都应创建新的 Frame，并在该次
运行结束时将其关闭。

这是 lclang 最核心的使用方式：**定义一次，在短生命周期的上下文中求值**。

## 推荐的应用模式

在应用启动时定义 Module。创建 Frame 时只提供必要的 Python 值，按需请求输出，并在
`finally` 中关闭 Frame。

```python
import asyncio

import lclang


INVOICE = lclang.define_module(
    "invoice",
    {
        "subtotal": "unit_price * quantity",
        "total": "subtotal + tax",
        "label": 'f"Total: {total:.2f}"',
    },
)


async def price_invoice(*, unit_price: float, quantity: int, tax: float) -> str:
    frame = lclang.define_frame(
        INVOICE,
        preset={
            "unit_price": unit_price,
            "quantity": quantity,
            "tax": tax,
        },
    )
    try:
        return await frame.get("label")
    finally:
        await frame.close()


async def main() -> None:
    label = await price_invoice(unit_price=6.5, quantity=4, tax=2.0)
    assert label == "Total: 28.00"


asyncio.run(main())
```

定义的书写顺序不是求值顺序。无论 `total` 和 `subtotal` 在 mapping 中如何排列，
`total` 都可以引用 `subtotal`。解析阶段会预先验证全部表达式；只有调用
`frame.get()` 请求某个值时，Frame 才会沿着名称依赖执行计算。

`define_module()` 和 `define_frame()` 是首选的高层 API。通过这种方式创建的 Frame
也可以使用 lclang 提供的、经过审查的纯函数 builtin，以及 `iter`、`text`、`data`
和 `json` namespace。

## 选择最小且合适的入口

| 需求 | 首选 API | 所有权模型 |
| --- | --- | --- |
| 在同步代码中计算一个表达式 | `evaluate_sync(source, values)` | 临时 event loop 由 lclang 管理 |
| 计算一组相互关联的命名定义 | `define_module()` + `define_frame()` | 复用 Module；关闭每个 Frame |
| 加载 `.lclcfg` 并读取一个值 | `load_config()` + `evaluate_config()` | `evaluate_config()` 自动关闭临时 Frame |
| 异步计算一个已经解析的表达式 | `parse_expression()` + `await evaluate()` | 调用者提供 resolver values |
| 只解析、打印或分析语法 | `parse_expression()` + `to_source()` 或 runtime 分析 API | 不创建求值状态 |
| 使用同一策略执行多次独立计算 | `FrameFactory` 或 `Config.frame_factory()` | 关闭每个创建出来的 Frame |

对于小型同步脚本，直接使用 `evaluate_sync()`：

```python
import lclang

total = lclang.evaluate_sync(
    "unit_price * quantity",
    {"unit_price": 6, "quantity": 4},
)
assert total == 24
```

不要在正在运行的 event loop 中调用 `evaluate_sync()`。异步应用应使用 Frame，或者
直接 `await evaluate()`。

## 值是快照，不是响应式单元

第一次执行 `await frame.get("name")` 时，Frame 会计算选中的定义，并缓存它的值或
普通失败。处于同一 event loop 的并发调用者会共享这次计算，后续读取返回相同快照。

修改宿主输入不会自动让已经缓存的定义或其依赖者失效。这是有意设计的行为：重算是
明确且局部的操作。

```python
frame.mixin({"unit_price": 10})
await frame.recalculate("subtotal")
await frame.recalculate("total")
```

应当把 Frame 理解为一次可复现的计算，而不是电子表格。如果许多输入需要同时变化，
创建新 Frame 通常比逐个刷新现有快照更清晰。只有在确实希望保留本次运行中的其他
快照时，才使用 `mixin()` 和 `recalculate()`。

## 配置文件是带来源信息的 Module

当定义应当位于 Python 代码之外、需要由多个文件组合，或者诊断信息必须保留文件和
行号时，使用 `.lclcfg`。

```lclcfg
__LCL_VERSION__: 1

scheme: "https"
host: f"api.{environment}.example.com"
endpoint: f"{scheme}://{host}"
```

配置文件应异步加载。如果只需要一个结果，并且不需要保留 Frame，可以使用
`evaluate_config()`：

```python
from pathlib import Path

from lclang.config import evaluate_config, load_config


async def endpoint_for(environment: str) -> str:
    config = await load_config(Path("settings.lclcfg"))
    result = await evaluate_config(
        config,
        "endpoint",
        values={"environment": environment},
    )
    assert isinstance(result, str)
    return result
```

如果多个值需要共享同一份缓存，可以把加载结果转换成 Module，或者使用
`config.frame_factory()`，然后按普通方式创建并关闭 Frame。`using` 声明按源码顺序
展开其他配置源；后出现的定义获胜，同时来源和历史记录仍可用于诊断。

## 保持清晰且收敛的 Python 边界

名称依次通过用户 Module、应用提供的值、runtime values、经过审查的 builtin 和
标准 namespace 进行查找。优先传入普通值或职责明确的 callable，不要直接暴露能力
过于宽泛的 service object。

宿主 callable 可以是同步或异步的。当 resolver value、调用结果、迭代器操作或
context-manager protocol 返回 awaitable 时，lclang 会自动等待。应用仍需对其提供的
任何对象所具有的行为和权限负责。

LCL 是 expression-only 语言，并且有意采用熟悉的表达方式：

```lcl
profile?.display_name ?? "anonymous"
[item * 2 for item in values if item > 0]
f"{service}: {port}"
value -> value * 2
(left, right=10) -> left + right
try primary() except ServiceError: fallback()
```

箭头函数使用 `() -> expression`、`name -> expression` 或
`(parameters) -> expression`。定义是不可变语法；词法闭包会保留它创建时所在的
定义上下文。

## 诊断与检查

预期的库错误均派生自 `lclang.LclError`。语法错误、名称错误、求值失败、循环依赖、
已关闭 Frame 以及配置错误都有对应的具体子类，并在可用时保留源码位置。

当检查名称查找但不能触发求值时，使用 `frame.has()` 和
`frame.get_definition()`。调试某个值的 owner、缓存状态、依赖树或失败路径时，使用
`frame.inspect_variable()`。当应用确实需要排序或变更影响分析时，还可以使用依赖图
和 dependency snapshot；正常求值不依赖这些高级接口。

## 实用规则

1. 只解析定义一次，并复用得到的 Module。
2. 每次独立运行或请求都创建一个 Frame。
3. 只传入配置实际需要的宿主值。
4. 把缓存结果视为快照；需要更新时明确重算。
5. 关闭自己创建的每个 Frame，通常在 `finally` 中完成。
6. 只读取一个配置值时，优先使用 `evaluate_config()`。
7. 在应用边界捕获 `LclError`，并保留其中带源码位置的诊断文本。

## 项目资源

- [文档](https://jihulab.com/midnightprotocol/lclang/-/tree/main/docs)
- [源码](https://jihulab.com/midnightprotocol/lclang)
- [问题跟踪](https://jihulab.com/midnightprotocol/lclang/-/work_items)

## 要求与许可证

- Python 3.14 或更高版本
- 无第三方运行时依赖
- MIT License
