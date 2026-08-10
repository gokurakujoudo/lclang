# 在 Python 脚本中构建 CLI

`lclang.cli` 用于构建由默认值、`.lclcfg` 配置和命令行覆盖共同驱动的强类型
Python 脚本 CLI。它没有第三方运行时依赖。LCL 是可信的应用配置语言，不是恶意
表达式的安全沙箱。

## 一个可直接运行的脚本

根 `CommandGroup` 描述整个应用，但它本身不属于命令路径。装饰后的异步处理函数只接收
一个 `CliContext`，并返回一个 `CliResult`。

<!-- lclang-cli-exec -->
```python
import asyncio

from lclang.cli import (
    CliContext,
    CliEntrance,
    CliResult,
    CommandGroup,
    ParameterDoc,
    cli,
)


@cli.command(
    parameter_docs=[
        ParameterDoc("message", str, True, "Message to display", "Hello from lclang")
    ]
)
async def greet_command(context: CliContext) -> CliResult:
    """Display the configured greeting.

    :param context: Current CLI invocation.
    :returns: Successful command result.
    """
    message = await context.frame.get("message")
    return CliResult.success(f"{message} (as of {context.as_of_date.isoformat()})")


root = CommandGroup("root", "Greeting tools", [greet_command])
application = CliEntrance(root, version="1.0.0")
status = asyncio.run(
    application.run(
        ["python", "greeting.py", "greet", "--as-of", "20260809"]
    )
)
assert status == 0
```

输出：

```text
Hello from lclang (as of 2026-08-09)
```

真实脚本把显式 token 数组替换为 `asyncio.run(application.run())`。环境适配器会构造
`[sys.executable, *sys.argv]` 形式的完整 argv。

## 命令行模型

每次调用都拆分为：

```text
<Python 可执行文件> <script.py> [<command_group> ...] <command> [options]
```

命令和命令组使用小写 `snake_case` 并精确匹配；根组名称只用于描述。公共选项如下：

- `-c, --config <file>`：加载一个 `.lclcfg` 文件。
- `-o, --override <key> [<value>]`：可以重复，同一键以最后一个值为准。
  省略值时保存布尔值 `True`；后续 `-o` 或 `--override` 始终开始新覆盖，
  不会成为前一键的值。
- `-a, --as-of <YYYYMMDD>`：覆盖严格日历日期，默认是执行当天。
- `-wif, --dryrun`：通知处理函数避免其负责的副作用。
- `-h, --help`：显示根、组或命令级帮助。
- `-v, --version`：在根级显示版本。

显式帮助和版本不会加载配置、创建 Frame 或日志目录，也不会调用处理函数。缺失命令、
未知命令和无效选项返回状态 `2`，并把最近作用域的帮助写到 stderr。

## 参数方法与优先级

`ParameterDoc` 描述一个 Frame 绑定。`required=True` 只检查最终绑定是否存在，不会提前
求值或转换类型；`value_type` 只用于帮助文本。处理函数在
`await context.frame.get("name")` 时取得惰性值，并负责业务类型验证。

每次调用独占并在结束时关闭以下层级，右侧优先级更高：

```text
LCL_IMPORTS(preset)
  -> 命令参数和日志默认值
  -> 配置文件
  -> CLI 覆盖
  -> cli-runtime
```

## 静态配置与惰性覆盖

`common.lclcfg`：

```lcl
prefix: "Hello "
target: "world"
```

`application.lclcfg`：

```lcl
using "common.lclcfg"
message: prefix + target
```

普通覆盖始终是原样的外部提供字符串：

```console
python greeting.py greet -c application.lclcfg -o message "literal message"
```

不提供值时，该键会成为外部提供的布尔 `True`：

```console
python greeting.py greet -o enabled
```

因此 `-o first -o second value` 表示 `first=True` 与 `second="value"`。
只有 `-o` 和 `--override` 不能作为覆盖值；其他类似选项的 token 仍可作为原样字符串值。

只有完整且成功解析的 `LCL[...]` token 才会保存为惰性 LCL 表达式：

```console
python greeting.py greet -c application.lclcfg -o message "LCL[prefix + 'team']"
```

空标记或语法错误的标记仍是外部提供字符串；Frame 静态检查将其显示为
`ExternalProvided`，只有有效的 `LCL[...]` 才是未求值定义。`as_of_date`、`dryrun` 和
`cli_params` 是不可覆盖的运行时绑定。

## dryrun、副作用和测试

dryrun 仍会加载配置、构建 Frame、配置日志并调用处理函数。必须在真正的外部操作前检查：

```python
if context.dryrun:
    return CliResult.success("would send the greeting")
await send_greeting(await context.frame.get("message"))
return CliResult.success("greeting sent")
```

单元测试应 mock `send_greeting` 等外部连接；运行时配置使用和用例一起声明的静态字符串；
启用的日志只写入可自动清理的临时目录。把完整 token 数组直接传给 `Command.run` 或
`CliEntrance.run`，不要在测试中重建 shell 引号规则。

## 日志与结果

文件日志默认关闭。可通过配置或覆盖提供 `log_dir`、`log_file_name`、`log_level` 和
`log_format`。logger 与根 logger 隔离，使用 UTF-8 追加，并在调用结束后关闭。格式必须
保留时间、文件、行、函数、消息和原始日志参数；捕获异常时追加 traceback。

`SUCCESS` 返回 `0` 并写 stdout；`FAILURE` 返回 `1` 并写 stderr；`EXCEPTION` 和捕获的
普通异常返回 `2` 并写 stderr。取消、`KeyboardInterrupt` 和 `SystemExit` 会在尽力清理后
继续传播。处理函数使用 `CliResult.success(message)` 和
`CliResult.fail(message)` 简洁地构造对应结果：

```python
if not await context.frame.get("message"):
    return CliResult.fail("message cannot be empty")
return CliResult.success("message accepted")
```

## lclang 内置模块命令

包自身提供三个命令。`builtins` 输出全部标准 LCL 内建值及稳定说明：

```console
python -m lclang.cli builtins
```

普通函数和值占一层；namespace 方法紧随其 namespace，并缩进两个空格：

```text
- recursive: Build a variadic eager fixed point.
- text: Unicode text helpers.
  - join: Join sync or async string items.
  - lines: Split text at Unicode line boundaries.
```

顶层名称按名称排序，namespace 方法保持 manifest 声明顺序。该命令不执行 LCL
求值，也不要求 `RESULT`。

`parse_lcl` 默认输出现有的只读变量检查树，不求值 `RESULT`：

```console
python -m lclang.cli parse_lcl -o a 100 -o b 200 -o RESULT "LCL[a+b]"
```

输出的根节点包含 `RESULT` 的 `a + b (NotEvaluated)`，两个子节点分别显示外部提供的
字符串值 `'100'` 和 `'200'`。直接提供字面量结果时：

```console
python -m lclang.cli parse_lcl -o RESULT 100
```

输出为：

```text
- RESULT@cli_runtime/cli_overrides: (ExternalProvided) str: '100'
```

来自 lclang 标准层的依赖使用 `NativeProvided`。所有内置函数和 namespace
使用统一的简洁格式；CLI 字面量仍是外部值：

```text
len@.../LCL_BUILTINS: (NativeProvided) Builtin Function: len
iter@.../LCL_ROOT: (NativeProvided) Builtin Namespace: iter
```

加上无值覆盖 `-o EVAL` 后，会先求值 `RESULT` 再输出缓存树：

```console
python -m lclang.cli parse_lcl -o RESULT "LCL[1 + 2]" -o EVAL
```

```text
- RESULT@cli_runtime/cli_overrides: 1 + 2 (Cached) int: 3
```

如果求值失败，`parse_lcl -o EVAL` 仍会输出包含结构化错误与变量求值栈的
缓存检查树；不带 `EVAL` 时仍完全不求值。

`eval_lcl` 对相同绑定只求值一次：

```console
python -m lclang.cli eval_lcl -o a 100 -o b 200 -o RESULT "LCL[a+b]"
```

输出为 `100200`。三个命令都支持普通的配置、覆盖、日期、dryrun、帮助、版本和日志选项。
`parse_lcl` 与 `eval_lcl` 要求 `RESULT`；其他依赖名称可以直接来自配置文件或
`-o`，无需 ParameterDoc 声明。

求值错误会追加从直接请求变量到失败变量的路径，例如
`[variable evaluation stack: RESULT -> quicksort]`。不完整或无法解析的
`LCL[...]` 会按兼容性规则保留为外部字符串；如果 `RESULT` 调用该字符串，
错误会显示 `TypeError: 'str' object is not callable` 和
`[variable evaluation stack: RESULT]`。复杂表达式意外失败时，可先用 `parse_lcl`
确认该覆盖是惰性定义还是 `ExternalProvided` 字符串。
完整的英文说明见[英文 CLI 教程](../tutorials/cli.md)。
