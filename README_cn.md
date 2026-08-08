# pylcl

[English](README.md)

`pylcl` 是面向 Python 3.14+、异步优先的纯 Python 配置表达式语言。0.2.0
语言、运行时与 `.lclcfg` release candidate 已完成验证；正式发布是独立的维护者操作。
详见 [CHANGELOG.md](CHANGELOG.md)。

## 项目状态

- 目标版本：0.4.0 开发版本
- 最新完成：M072 — 配置文档与 0.2 发布门
- 下一计划：M080 — 强类型 CLI 应用契约
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
  暴露完整 runtime 工作流，并提供首选的 source-string `define_module`/`define_frame`
  shortcut、`LCL_ROOT -> LCL_BUILTINS -> LCL_RUNTIME -> LCL_IMPORTS -> user` 标准层级，
  首选的 `Frame.derive` child 构造、不触发求值的 Frame `has`/`get_definition` 检查，
  以及受控、右侧优先的 `Frame.mixin` host-value 更新、定义上下文 `lhs()`、严格的
  `YYYYMMDD` 日期内建函数，以及不触发求值、包含 Frame 路径和值终点的依赖图
  ，并支持闭包中词法化的 `lhs()`、可直接接收源码的 `evaluate_sync`、确定性的
  FrameFactory 默认 ID，以及配套依赖分析教程和经过审计的嵌套模块布局
- 测试状态：695 个测试以 99.34% 分支覆盖率通过；strict mypy、Ruff、完整
  source/docstring policy、可执行文档与 artifact 闸门均通过

`Frame` 现在可直接接收字符串 ID，省略时使用 `frame-<module name>`；
`inspect_variable()` 可在不触发求值的前提下生成包含缓存状态、定义、Frame 路径、
当前值或异常的调试树；每个父节点下的直接依赖按首次出现的变量名去重，而不同
分支仍可分别包含同一变量，并使用
`name@frame/path: [definition ](Status) typed-payload` 单行格式；外部值不显示定义，值与错误均显示类型。Frame 子系统现统一位于
`pylcl.runtime.frame` 嵌套包中。

package metadata 现报告 `0.2.0`；wheel 与 sdist 均在全新 Python 3.14 环境完成
无依赖安装与配置加载验证。正式发布是独立的维护者操作。

权威进度与验证证据保存在 [progress.md](progress.md)。计划能力不会被描述为已经实现。

## 快速开始

在已经安装开发环境的 checkout 中运行。测试套件会直接提取并执行下面的示例。

```python
import asyncio

import pylcl


async def main() -> None:
    module = pylcl.define_module(
        "quickstart",
        {"result": 'json.encode({"message": "hello pylcl"})'},
    )
    frame = pylcl.define_frame(module)
    try:
        print(await frame.get("result"))
        snapshot = frame.dependency_snapshot("result")
        print(",".join(str(edge.target) for edge in snapshot.dynamic_edges))
    finally:
        await frame.close()


asyncio.run(main())
```

新的教程结构目前仅提供英文版：从[教程索引](docs/tutorials/README.md)开始，
再阅读 [runtime 指南](docs/tutorials/runtime.md)、
[LCL 示例库](docs/tutorials/lcl_examples.md)或
[配置文件指南](docs/tutorials/config_file.md)，并可阅读英文
[依赖分析教程](docs/tutorials/dependency-analytics.md)。中文
[runtime API 指南](doc_cn/runtime-api_cn.md)继续保留。

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
- 英文教程索引：[docs/tutorials/README.md](docs/tutorials/README.md)
- 英文 runtime 教程：[docs/tutorials/runtime.md](docs/tutorials/runtime.md)
- 英文 LCL 示例库：[docs/tutorials/lcl_examples.md](docs/tutorials/lcl_examples.md)
- 英文配置文件教程：[docs/tutorials/config_file.md](docs/tutorials/config_file.md)
- 英文依赖分析教程：[docs/tutorials/dependency-analytics.md](docs/tutorials/dependency-analytics.md)
- 中文教程：`doc_cn/`

## 许可证

MIT。当前包要求 Python 3.14+，没有运行时第三方依赖。
