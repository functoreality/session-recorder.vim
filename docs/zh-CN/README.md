# Vim 与 Neovim 会话记录器

[English](../../README.md) | 简体中文

记录每次编辑器会话中打开的文件、原始文本、保存后的修改和最后光标位置，
供工作复盘或其他本地工具读取。从第一个符合条件的文件开始记录，正常退出时完成。

## 安装

需要 Python 3，推荐 3.11 或更新版本。旧版本可能可用，但未经验证，不保证兼容。
编辑器需要 Neovim 0.9+，或具有 `+eval`、`+job`、`+channel`、
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
Windows 的 `py -3` 顺序查找，并使用找到的第一个解释器。
如需选择其他解释器，请明确配置其路径。
使用编辑器所在系统的原生 Python。修改配置后重启编辑器。
插件也支持在 `VimEnter` 后由插件管理器加载。

## 存储位置

先通过 My Big Brother 初始化共享存储。插件读取 `C/storage.json`，写入
`<data_root>/daily/<逻辑工作日>/vim/<分段>/`，共用固定日界线和持久化日期登记。
无需设置额外的 Vim 路径变量。共享配置缺失或无效时停止采集并报告错误，
不会选择其他目录。不要只手工创建 JSON 文件而不建立配套登记。

`C` 是平台配置目录：

| 系统 | C |
| --- | --- |
| Linux | `$XDG_CONFIG_HOME/my-big-brother`，默认 `~/.config/my-big-brother` |
| macOS | `~/Library/Application Support/my-big-brother/configs` |
| Windows | `%LOCALAPPDATA%/my-big-brother/configs` |

Linux XDG 变量为空或为相对路径时使用默认值。
Windows 的 `LOCALAPPDATA` 为空时采用 `~/AppData/Local`。
WSL、远程编辑器使用所在系统、用户和文件系统中的位置。

共享模式在编辑器事件发生时以及每 30 秒保存检查点。
新工作日创建有独立原始快照的新分段，不依赖之前日期的目录。
跨日观察存在空缺时会明确报告。删除已无活动写入的旧日期表示放弃，
插件不会重建它，也不会把当天事件转写到其他目录。

每个分段包含 `record.json`、有大小限制的 UTF-8 原始快照、检查点和修改 diff。
目录名带首个记录文件的文件名，便于浏览：

```text
daily/YYYY-MM-DD/vim/HH-MM-SS_工作笔记.md_<session_id>/
```

保留 Unicode 字符，将 Windows 不允许的字符替换为 `_`。
文件名片段最多 64 个 UTF-8 字节，不截断字符。
没有片段或遇到路径长度限制时，使用 `HH-MM-SS_<session_id>`。
完整随机标识用于防止碰撞。完整路径及快照文件名以 `record.json` 为准。
编写读取器前请读[格式契约](../RECORD-FORMAT.md)。

如需脱离 My Big Brother 单独使用，在加载插件前显式设置绝对路径 `record_dir`。
独立模式写入 `<record_dir>/<session>/`，退出时完成记录，
不使用共享日期登记、定期检查点和按日清理机制。

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
- `record_dir`：可选的独立输出绝对路径，使用 `<record_dir>/<session>/` 布局。
  接入 My Big Brother 的共享存储时应省略。

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

共享模式会持续发布检查点，独立模式在退出时发布。
崩溃可能留下不完整材料。源文件读取失败、比较失败会记录在元数据中。
最终写入失败会显示在编辑器消息中，并留下诊断材料。

## My Big Brother

本仓库独立提供编辑器采集器，My Big Brother 已包含对应来源适配器。
验证一次合成会话后，明确启用其 `vim` 来源。共享目录本身不代表授权分析。
接入规则见[读取契约](../RECORD-FORMAT.md)。

当前实现与测试见[开发说明](../DEVELOPMENT.md)。
早期个人需求和设计稿保留在 [docs/archive](../archive/README.md)，与现行说明分开。
仓库尚未选择许可证。
