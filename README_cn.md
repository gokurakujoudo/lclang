# pylcl

[English](README.md)

`pylcl` 是面向 Python 3.14+、异步优先的纯 Python 配置表达式语言。0.1 language/runtime
实现已经完成，但在 artifact 与 clean-install release-candidate 门通过前仍未发布。

## 项目状态

- 目标版本：0.4.0 开发版本
- 最新完成：M050 — 0.1 双语用户文档
- 当前工作：M051 — 0.1 artifact 与 clean-install 发布门
- 已实现：基础工程、强制英文 rST API 文档、带源码位置的 lexer、不可变 AST、
  完整表达式/comprehension 解析、全部计划内 V1 表达式 form，以及确定性的
  AST 到源码渲染、semantic f-string 解析、稳定的根包 parse/print API、异步表达式求值、
  词法闭包、结构化错误、断言、try 恢复、finalization、同步/异步上下文管理与
  semantic f-string 求值、不可变 runtime module、层级 single-flight Frame 缓存与
  结构化环检测、取消隔离、不失效 dependant 的原子定向重算，以及 task-local 的
  深度、工作量和物化集合限制、确定性的 Frame 关闭与资源清理，以及作用域感知的
  eager/conditional/deferred 依赖分析、不可变 module 依赖图、按边类型过滤的查询，
  确定性的拓扑排序、有界 runtime 查找追踪、静态/动态边协调，以及具有原子重算语义、
  能路由到真正 owner 的不可变 Frame 依赖快照，以及浅层不可变 host preset 和可复用、
  每次创建独立状态的 Frame factory、由 manifest 驱动的只读标准库 namespace，以及经审查的
  async iterable、文本、不可变数据与严格 JSON helper preset，并通过聚焦的根包 API
  暴露完整 runtime 工作流
- 测试状态：578 个测试、99.12% 分支覆盖，统一质量门通过

package metadata 目前仍报告开发版本 `0.0.0`。早期 foundation wheel 已在全新 Python 3.14
环境通过无依赖安装；M051 将对 0.1 artifact 重复该验证。

权威进度与验证证据保存在 [progress.md](progress.md)。计划能力不会被描述为已经实现。

## 快速开始

在已经安装开发环境的 checkout 中运行。测试套件会直接提取并执行下面的示例。

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

继续阅读 [runtime 快速开始](doc_cn/runtime-quickstart_cn.md)和
[runtime API 指南](doc_cn/runtime-api_cn.md)。面向 Python 集成者、覆盖全部当前公共功能的
英文操作参考见 [Python user cheatsheet](docs/user-cheatsheet.md)。

## 0.4 目标能力

- 带自定义 AST 的独立版本化 Python 风格表达式语法；
- 异步优先解释器和带缓存的层级运行时 Frame；
- 区分立即、条件、延迟和动态边的依赖分析；
- 支持版本化 include 和来源诊断的 UTF-8 `.lclcfg`；
- 用于构建配置驱动命令行程序的强类型框架；
- 严格类型、分支覆盖率、差分测试、压力测试、泄漏检查和跨平台打包验证。

## 工程协议

项目采用文档先行和 TDD。每个实现 milestone 必须先形成可执行行为规范，证明测试失败，
实现最小正确行为，通过完整质量门，最后同步更新两份 README 和进度账本。生产代码与
单元测试的子模块必须按[模块布局规范](docs/architecture/module-layout.md)保持同构。

本语言面向受信的应用配置，不是处理敌意表达式的安全沙箱。

## 文档

- 长期开发规则：[AGENTS.md](AGENTS.md)
- 进度与验证证据：[progress.md](progress.md)
- 英文规范：`docs/specs/`
- 完整 LCL 语法（英文）：[docs/lcl-lang.md](docs/lcl-lang.md)
- 完整 Python 用户速查手册（英文）：[docs/user-cheatsheet.md](docs/user-cheatsheet.md)
- 英文教程：`docs/tutorials/`
- 中文教程：`doc_cn/`

## 许可证

MIT。当前包要求 Python 3.14+，没有运行时第三方依赖。
