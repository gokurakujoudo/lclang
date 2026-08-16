# Runtime API 指南

## Import 分层

根包提供首选的 `define_module`/`define_frame` 工作流、标准 Frame
`LCL_ROOT`、`LCL_BUILTINS`、`LCL_RUNTIME`、`LCL_IMPORTS`，以及底层的
`Module`、`Frame`、`FrameFactory`、`Preset`、`EvaluationLimits`、
`DependencySnapshot` 与 `STANDARD_PRESET` API。

高级静态图、topological order、动态 tracing、reconciliation 与 runtime 类型位于
`lclang.runtime`。manifest、namespace 装配、独立 helper、`STANDARD_MANIFESTS` 和
`STANDARD_PRESET` 位于 `lclang.stdlib`。

## 首选 definition shortcut 与标准层级

`define_module(name, exprs)` 把 string-to-string dictionary 解析成不可变 `Module`。
`define_frame(module=None, base=LCL_RUNTIME, preset=None)` 创建新的 user Frame。
查找从最近一层依次回退：

`user module -> LCL_IMPORTS -> LCL_RUNTIME -> LCL_BUILTINS -> LCL_ROOT`。

`LCL_ROOT` 保存经审查的 LCL namespace；`LCL_BUILTINS` 保存不带 ambient I/O 的
Python type/function，包括 Python 实现的 Z 组合子 `recursive`；`LCL_RUNTIME` 是空的 package default，也可替换为每次 run 独立的
CLI-aware base；`LCL_IMPORTS` 是 detached preset 层。因此 user definition 覆盖 preset，
preset 覆盖 runtime value。标准 ancestor 只被借用，关闭 user Frame 不会关闭它们。

固定 builtin inventory 为：value type `bool`、`bytes`、`dict`、`float`、
`frozenset`、`int`、`list`、`set`、`str`、`tuple`；function `abs`、`all`、
`any`、`bin`、`chr`、`divmod`、`enumerate`、`filter`、`format`、`hex`、
`isinstance`、`len`、`map`、`max`、`min`、`oct`、`ord`、`pow`、`range`、
`recursive`、`repr`、`reversed`、`round`、`slice`、`sorted`、`sum`、`zip`。文件/进程输入、
动态 import/code、reflection 与 mutation helper 均不提供。

`recursive(builder)` 返回可调用的不动点值，表示为
`Recursive Function: <original source>`。LCL builder 使用标准 LCL 源码，Python
builder 使用函数名；Frame 检查不会输出 Python 对象地址。

匿名 LCL 函数使用 `() -> expression`、`name -> expression` 或完整的
`(parameters) -> expression`。裸 name 形式仅表示一个必需的位置参数。标准源码始终保留
参数括号。

同步或异步 iterable 产生的每个 item 都会在 comprehension、星号展开或
`iter.collect`/`iter.first` 消费前递归 await。因此
`[*map((x) -> x.lower(), ["A", "B"])]` 会得到 `["a", "b"]`，不会保留
coroutine 对象。

## 显式 Module、Preset 与 FrameFactory

`Module` 把 name-to-AST mapping 复制为只读快照。`Preset` 对 host binding 做同样处理，
`overlay` 是浅层、右侧优先。`FrameFactory` 保存 Module、可选 Preset 与默认
`EvaluationLimits`。每次 `create` 都拥有全新的 cache、task、dependency trace 与 lifecycle
状态；调用级 values/limits 覆盖 factory policy。parent Frame 只借用、不归 child 所有。

普通 owned child Frame 首选
`async with parent.derive(module, values={}) as child:`。它复制本地 host value，以 module
name 作为 child ID，拥有新的 cache/task/dependency/lifecycle state，并借用 `parent`。
离开 child block 只关闭 child，parent 保持 open。需要显式 ID 或 child-specific limit
时再直接构造 `Frame`。

## Frame cache 与并发

`await frame.get(name, fallback=NO_FALLBACK)` 惰性执行选中的 definition 一次，并缓存
结果或普通失败。如果 name 在完整 Frame 层级中不存在，显式 fallback 会被原样返回且
不会缓存；`None` 是有效 fallback。导出的 `NO_FALLBACK` sentinel 是默认值，保持原有
`LclNameError`。已有 definition 的求值失败不会被 fallback 替换。

同一 event loop 的并发调用共享 owner task，waiter 取消相互隔离。结构化环路径会在
owner deadlock 前抛出错误。parent definition 始终在其 defining Frame 中运行。

`frame.has(name)` 使用同一递归查找规则检查 definition 或 host value 是否存在。
`frame.get_definition(name)` 不求值地返回选中的 custom AST；name 不存在，或更近的 host
value 遮蔽 ancestor definition 时返回 `None`。两者都不修改 cache、dependency、task 或
lifecycle state。

`frame.inspect_variable(name)` 的当前值如果是受支持的 `LclAstNode`，表示会保留
具体节点类型，并把 Python dataclass repr 替换为标准 LCL 表达式。例如：

```text
expression@frame-app: (ExternalProvided) LclBinary: base + 2
```

原 AST 对象仍保存在 `current_value` 中；该转换只影响显示，不会求值。已经求值的
LCL 闭包同样显示为 `LclFunctionValue: (...) -> ...`，不会泄漏已绑定参数、
resolver、evaluator 或源码位置等内部状态。

`frame.mixin(values)` 把右侧优先的 dictionary 原子复制到 open Frame 的 host binding。
现有 `frame.values` view 保持只读，但会反映更新。直接查找和未缓存 definition 可看到 mixed
value；已缓存的成功/失败仍是快照。definition 需要观察新输入时应显式调用 `recalculate`。
Module definition 仍遮蔽同名 host value。

`await frame.recalculate(name)` 只原子替换该 definition 的快照，永远不会使 dependant
失效。refresh 时旧值仍可读；普通成功/失败同时替换 value/failure 和 dependency trace，
owner 取消则保留旧快照。

## Dependency snapshot

`frame.dependency_snapshot(name)` 是同步的时间点检查，返回 static edges、实际 dynamic
edges 与 confirmed/inactive/unexpected reconciliation。求值前全部 static edge 都 inactive；
cache hit 不新增观察；延迟 function/generator lookup 扩展 defining source 的 trace；parent
查询路由到 owner。

## 限制与 close

`EvaluationLimits` 限制 semantic AST 深度、node visit 数和单个物化 collection 大小。
一次 root 求值链共享 task-local budget；cache hit 不消耗预算，recalculate 使用新预算。

Frame 实现 async context-manager protocol。首选
`async with lclang.define_frame(...) as frame:`，离开 block 时会等待 owned cleanup，
并且不会抑制 block 抛出的异常。

`await frame.close()` 是底层的显式等价操作：它拒绝新 work、取消并等待 owner task，
然后按反向顺序一次性清理缓存资源，识别同步 `close` 与异步 `aclose`。parent 资源仍由
parent 所有。cleanup 错误稳定，取消某个 waiter 不会取消共享 close work。

## 标准 preset、错误与安全边界

`STANDARD_PRESET` 提供纯数据 `iter`、`text`、`data`、`json` namespace，不提供文件、
环境、网络、subprocess、reflection 或动态 import helper。helper 协议错误会在解释器边界
成为带 source 的结构化 evaluation failure。

LCL 面向可信应用配置，不是处理敌意表达式的安全 sandbox。host 提供的 value/callable
可以执行普通 Python 行为，包括阻塞与副作用，因此应用必须审查自己的 Preset。
