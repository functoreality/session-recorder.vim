# Vim 与 Neovim 会话记录器

[English](../../README.md) | 简体中文

记录每次编辑器会话中打开的文件、原始文本、保存后的修改和最后光标位置，
供工作复盘或其他本地工具读取。从第一个符合条件的文件开始记录，正常退出时完成。

## 安装

需要 Python 3.11+，以及 Neovim 0.9+，或具有 `+eval`、`+job`、`+channel`、
JSON 和浮点数支持的 Vim 8.2+。无需安装 Python 包、编辑器 Python provider
或 Unix 命令行工具。编辑器使用 UTF-8 编码。
实现面向 Linux、macOS 和原生 Windows，实际验证范围见
[开发说明](../DEVELOPMENT.md)。

使用插件管理器安装**完整仓库**，例如 vim-plug：

```vim
Plug 'functoreality/session-recorder.vim'
```

也可克隆到编辑器 `packpath` 下的 `pack/*/start/session-recorder.vim`。
只复制 `plugin/` 不能安装完整插件。

如果编辑器的 PATH 中没有合适的 Python，请在加载插件前设置：

```vim
let g:vim_session_recorder#config = {
    \ 'python_executable': '/absolute/path/to/python3',
    \}
```

Windows 可使用 `C:/Python313/python.exe`。默认按 `python3`、`python`、
Windows 的 `py -3` 顺序查找，找到的第一个解释器必须符合版本要求。
使用编辑器所在系统的原生 Python。修改配置后重启编辑器。
插件也支持在 `VimEnter` 后由插件管理器加载。

## 存储位置

默认输出到 `D/raw-logs/YYYY-MM-DD/vim/<session>/`。
`C` 是配置目录，`D` 是默认数据目录：

| 系统 | C | D |
| --- | --- | --- |
| Linux | `$XDG_CONFIG_HOME/my-big-brother`，默认 `~/.config/my-big-brother` | `$XDG_DATA_HOME/my-big-brother`，默认 `~/.local/share/my-big-brother` |
| macOS | `~/Library/Application Support/my-big-brother/configs` | `~/Library/Application Support/my-big-brother/data` |
| Windows | `%LOCALAPPDATA%/my-big-brother/configs` | `%LOCALAPPDATA%/my-big-brother/data` |

Linux 的 XDG 变量为空或是相对路径时使用默认值。
Windows 的 `LOCALAPPDATA` 为空时采用 `~/AppData/Local`。
WSL、远程编辑器分别使用所在系统、用户与文件系统中的位置。

要与 My Big Brother 等采集器共享自定义原始日志根，在
`C/raw-logs-path.txt` 中写入一行 UTF-8 绝对路径，例如：

```text
/absolute/path/to/work-records
```

允许一个 LF 或 CRLF 行尾，保留空格和反斜杠。
不要加引号、注释、`~` 或环境变量。文件缺失时采用默认位置。
文件存在但无效时停止本次编辑器进程的采集，并报告错误。
插件在进程启动时读取一次该文件，不读取主项目的 `config.json` 或 `results_root`。

每个会话目录包含 `record.json`、小型 UTF-8 文件的原始副本，以及修改文件的
unified diff。日期取第一个记录文件时的本地自然日期。
跨午夜会话仍留在原目录。编写读取器前请读[格式契约](../RECORD-FORMAT.md)。

## 配置与验证

```vim
let g:vim_session_recorder#config = {
    \ 'enabled': 1,
    \ 'exclude_patterns': ['*.tmp', '*.log', '.git/*'],
    \ 'max_file_size': 1048576,
    \ 'helper_timeout_ms': 30000,
    \}
```

- `enabled`：在加载前设为 `0`，完全关闭采集。
- `exclude_patterns`：区分大小写的 glob，匹配路径后缀或路径组成部分，
  不是 Vim 正则表达式。例如 `private/*` 排除任意 `private` 目录及其子目录中的文件。
  三平台统一在模式中使用 `/`。自定义列表会替换默认值。
- `max_file_size`：文件字节数达到该值时只记录元数据。
  含 NUL 的二进制文件和非 UTF-8 文件也只记录元数据。
- `helper_timeout_ms`：单次 Python 调用的最长时间，包含退出时整批文件的比较。
  文件很多或磁盘较慢时可调高。超时会报告采集失败，可能留下原始副本，
  却没有最终 `record.json`。
- `record_dir`：可选的独立输出绝对路径，保留旧版
  `<record_dir>/<session>/` 平铺布局，并绕过共享路径发现。
  接入 My Big Brother 时应省略。旧 `uuid_length` 已不再使用，
  目录始终包含完整随机会话标识。

运行 `:RecorderStatus` 查看实际根目录、共享配置文件、覆盖来源、当前会话目录和最近错误。
采集错误也可通过 `:messages` 查看。

验证时打开一个可丢弃的文本文件，修改并保存一行，然后正常退出。
检查新会话目录中的 `record.json` 和 `*-modification.diff`。
关闭采集、仅打开被排除的文件、空编辑器均不会创建会话。

## 记录范围

插件保存原始全文、文件路径、已保存修改和光标行片段，片段可能包含未保存文本。
在打开私密文件前配置排除规则，或关闭插件。
Unix 上新建会话目录仅当前用户可访问，已有父目录权限与 Windows ACL 由用户管理。
插件不上传、不分析，也不自动清理记录。

Diff 比较首次记录时和退出时磁盘上的文件内容。放弃的 buffer 修改不算已保存修改。
外部程序对磁盘文件的改动也可能出现在 diff 中。
光标位置不表示注意力时长，可选的 `executed` 标记仅表示用户映射的声明，不能证明测试通过。
重命名按文件路径观察，不会自动关联成重命名事件。

目前没有定时检查点或按日轮转，长会话只有关闭后才发布记录。
崩溃可能只留下原始副本。源文件读取失败、比较失败会记录在元数据中。
最终写入失败会显示在编辑器消息中，并留下诊断材料。

## 迁移与 My Big Brother

[迁移说明](../MIGRATION.md)列出了默认位置与旧配置的变化。
已有日志不会自动移动或删除，旧读取器仍可递归发现旧 `record.json`。

本仓库独立提供编辑器采集器，公开 My Big Brother 目前尚无 Vim 来源适配器。
共享原始日志位置只完成存储接口准备，不会自动开启每日分析。
[读取契约](../RECORD-FORMAT.md)说明后续接入要求。

当前实现与测试见[开发说明](../DEVELOPMENT.md)。
早期个人需求和设计稿保留在 [docs/archive](../archive/README.md)，与现行说明分开。
仓库尚未选择许可证。
