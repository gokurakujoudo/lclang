# Runtime 快速开始

本指南使用已经实现的 0.1 表达式与 runtime API。代码已经完成并通过测试，但在
0.1 release-candidate 门通过前，distribution metadata 仍报告开发版本 `0.0.0`。

## 构建 Module 与 Frame

LCL `Module` 是 definition 名称到已解析 custom AST 表达式的不可变映射。
`FrameFactory` 每次创建具有独立状态的惰性 runtime Frame。经审查的
`STANDARD_PRESET` 提供 `iter`、`text`、`data` 与 `json` namespace，不提供隐式的
文件、网络、环境变量或动态 import 能力。

```python
import asyncio

import pylcl


async def main() -> None:
    module = pylcl.Module(
        pylcl.ModuleName("quickstart"),
        {
            "result": pylcl.parse_expression(
                'json.encode({"message": "hello pylcl"})'
            )
        },
    )
    frame = pylcl.FrameFactory(module, pylcl.STANDARD_PRESET).create(
        pylcl.FrameId("quickstart:1"),
    )
    try:
        print(await frame.get("result"))
        snapshot = frame.dependency_snapshot("result")
        print(",".join(str(edge.target) for edge in snapshot.dynamic_edges))
    finally:
        await frame.close()


asyncio.run(main())
```

第一次 `get` 会求值并缓存 `result`，之后返回同一快照。dependency snapshot 会记录
本次求值实际解析的 `json` namespace，并保留 source occurrence 作为诊断证据。

## 缓存、重算与依赖检查

`await frame.recalculate("result")` 只原子替换 `result`，永远不会使已缓存 dependant
失效。refresh 运行期间，普通读取和 `dependency_snapshot` 继续看到旧值与旧 trace；
成功或普通失败一起发布新 outcome/trace，取消则保留二者。

快照包含 `static_edges`、实际 `dynamic_edges`，以及分为 `confirmed`、`inactive`、
`unexpected` 的 reconciliation。父 Frame 拥有的 definition 始终由 owner 执行、缓存、
检查依赖、重算和关闭。

## 限制与清理

向 factory 或 Frame 传入 `EvaluationLimits`，可限制 AST 深度、工作步数和物化集合大小。
始终在 `finally` 中 await `close()`：它取消 owner work，再按反向顺序一次性清理缓存的
同步/异步资源。取消某个 close waiter 不会取消真正的 owner cleanup task。

完整 surface 与错误模型见 [runtime API 指南](runtime-api_cn.md)。
