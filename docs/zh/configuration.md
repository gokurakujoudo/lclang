# `.lclcfg` 配置文件

已经实现的配置 API 位于 `lclang.config`。它把可信的 UTF-8 配置解析为 lclang
自定义 AST，在不求值普通定义的前提下展开其他文件，并把最终定义转换为现有
Module 与 Frame。实现不会使用 Python `eval`、`exec` 或 Python AST 编译。

## 文件语法

第一个有效声明可以是版本元数据；省略时默认为版本 1。

```lclcfg
__LCL_VERSION__: 1

# 定义使用冒号。
base: 2
total: (base + \ # 下一物理行继续表达式
  3)

using "parts/common.lclcfg"
```

空行、纯注释行会被忽略。版本、定义、续行符和 `using` 后均可写 `#` 注释。
字符串外的行尾反斜杠是唯一续行方式；未闭合的圆括号、方括号或花括号不会
隐式续行。续行链中不能插入空行或纯注释行。

配置定义和 LCL 表达式中的所有绑定名都不能以 `__` 开头；位于文件开头的
`__LCL_VERSION__` 元数据是唯一顶层例外。

## 文件魔法值与路径

在有物理路径的配置中，`__file__` 和 `__dir__` 会在解析时立即变成字符串
常量，分别表示定义所在文件的规范绝对路径及其目录。它们不会进入 runtime
Module，也不会形成依赖边。由子文件展开的定义始终使用该子文件的路径。
没有 `source_path` 的内存文本在使用这些值时会得到结构化错误。

根文件和 `using` 目标都必须严格以 `.lclcfg` 结尾。绝对路径直接使用；相对
路径以当前导入文件的目录为基准。目标开头的 `__dir__/` 可显式表示该目录，
后面允许任意数量的 `..`。可选的 `allowed_root` 会在路径规范化后执行边界检查。

文件严格按 UTF-8 解码，并允许只出现在文件开头的 BOM。加载过程不会执行
glob、环境变量展开、网络访问或表达式求值。

## 展开与覆盖

`using` 使用类似 C 的源代码顺序展开：子文件递归展开后的定义会插入当前
声明位置。即使读取和解析结果已缓存，每个 `using` 位置仍会再次贡献定义；
直接或间接循环会报错。

同一文件或不同文件都允许重名。按时间顺序最后出现的定义获胜，但遍历顺序
仍采用该名字第一次出现的位置。`Config.history` 保留全部来源。完整展开后才
创建 runtime Module，因此前向引用和后续覆盖不受声明先后约束。

## Python API 与生命周期

`parse_config(text, source_name="<memory>", source_path=None)` 同步解析单个、
尚未展开的文档，不执行 I/O；提供 `source_path` 只会启用文件魔法值。

`await load_config(path, resolver=None, limits=None)` 默认使用
`FileConfigResolver`。嵌入方可以提供异步 `ConfigSourceResolver`，但返回的
source 仍须带规范物理路径，以保证相对路径和魔法值确定。

```python
from pathlib import Path

from lclang.config import evaluate_config, load_config


async def read_result() -> object:
    config = await load_config(Path("settings.lclcfg"))
    return await evaluate_config(config, "result")
```

`Config.definitions` 提供最终定义，`Config.history` 提供完整来源，
`Config.to_module()` 创建不可变 Module，`Config.frame_factory()` 创建可复用且
相互独立的 Frame 构造策略。调用方负责关闭自己创建的 Frame；
`evaluate_config` 始终关闭它临时拥有的 Frame。

`ConfigLoadLimits` 限制 source 数量、递归深度、解码字符数和声明数。
`ConfigLoader` 可供同一事件循环内的并发任务安全使用，提供 single-flight、
等待者取消隔离和失败重试，并拒绝跨事件循环复用。

本语言面向可信应用配置，而不是敌对代码沙箱。求值时，宿主提供的值与函数仍
具有普通 Python 能力。
