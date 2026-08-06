# Runtime API 指南

## Import 分层

根包提供日常工作流：`Module`、`Frame`、`FrameFactory`、`Preset`、
`EvaluationLimits`、`DependencySnapshot` 与 `STANDARD_PRESET`，以及 parser、
evaluator、identifier/source value 和错误类型。

高级静态图、topological order、动态 tracing、reconciliation 与 runtime 类型位于
`pylcl.runtime`。manifest、namespace 装配、独立 helper、`STANDARD_MANIFESTS` 和
`STANDARD_PRESET` 位于 `pylcl.stdlib`。

## Module、Preset 与 FrameFactory

`Module` 把 name-to-AST mapping 复制为只读快照。`Preset` 对 host binding 做同样处理，
`overlay` 是浅层、右侧优先。`FrameFactory` 保存 Module、可选 Preset 与默认
`EvaluationLimits`。每次 `create` 都拥有全新的 cache、task、dependency trace 与 lifecycle
状态；调用级 values/limits 覆盖 factory policy。parent Frame 只借用、不归 child 所有。

## Frame cache 与并发

`await frame.get(name)` 惰性执行本地 definition 一次，并缓存结果或普通失败。同一 event
loop 的并发调用共享 owner task，waiter 取消相互隔离。结构化环路径会在 owner deadlock
前抛出错误。parent definition 始终在其 defining Frame 中运行。

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

`await frame.close()` 拒绝新 work、取消并等待 owner task，然后按反向顺序一次性清理缓存
资源，识别同步 `close` 与异步 `aclose`。parent 资源仍由 parent 所有。cleanup 错误稳定，
取消某个 waiter 不会取消共享 close work。

## 标准 preset、错误与安全边界

`STANDARD_PRESET` 提供纯数据 `iter`、`text`、`data`、`json` namespace，不提供文件、
环境、网络、subprocess、reflection 或动态 import helper。helper 协议错误会在解释器边界
成为带 source 的结构化 evaluation failure。

LCL 面向可信应用配置，不是处理敌意表达式的安全 sandbox。host 提供的 value/callable
可以执行普通 Python 行为，包括阻塞与副作用，因此应用必须审查自己的 Preset。
