# Vim 与 Neovim 会话记录器

[English](../../README.md) | 简体中文

记录每次编辑器会话中打开的文件、原始文本、保存后的修改和最后光标位置，
供工作复盘或其他本地工具读取。以具名缓冲区启动 Vim 时开始记录，正常退出时完成。

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

插件仅在启动时按以下优先级确定记录根目录：

1. Vim 配置中的绝对路径 `record_dir`。
2. `C/raw-logs-path.txt` 中的绝对路径。
   文件使用 UTF-8，只存一条路径，可带一个 LF 或 CRLF 行尾。
3. 平台默认数据目录下的 `daily`。

`C` 是平台配置目录：

| 系统 | C | 默认数据目录 |
| --- | --- | --- |
| Linux | `$XDG_CONFIG_HOME/my-big-brother` | `$XDG_DATA_HOME/my-big-brother` |
| macOS | `~/Library/Application Support/my-big-brother/configs` | `~/Library/Application Support/my-big-brother/data` |
| Windows | `%LOCALAPPDATA%/my-big-brother/configs` | `%LOCALAPPDATA%/my-big-brother/data` |

Linux 的 XDG 值为空或相对路径时，分别采用 `~/.config` 和 `~/.local/share`。
Windows 在 `LOCALAPPDATA` 为空时采用 `~/AppData/Local`。
WSL 和远程编辑器使用各自系统、账户和文件系统的位置。
已有 TXT 配置无效时报告错误，不静默选用其他根目录。
指定 `record_dir` 时直接使用它，不读取 TXT。

三种配置统一写入 `<根目录>/YYYY-MM-DD/vim/<会话>/`。
日期取会话启动时的本机自然日期。即使跨午夜、TXT 或 Vim 配置发生变化，
也始终使用启动时创建的会话目录和原始副本。
插件不读取 `storage.json`、不登记日期、不判断逻辑日，不轮转或定时生成检查点。
它无需 My Big Brother 的运行时。
会话目录若被删除，退出时报告写入失败，不重建，也不改存其他位置。

每个会话在打开文件时保存原始快照，在正常退出时生成 `record.json` 和修改 diff。
目录名带启动时具名缓冲区的文件名，便于浏览：

```text
daily/YYYY-MM-DD/vim/HH-MM-SS_工作笔记.md_<short-id>/
```

保留 Unicode 字符，将 Windows 不允许的字符替换为 `_`。
主文件名超过 20 个字符时，保留前 18 个字符、`..` 和扩展名，
没有扩展名则保留末尾 8 个字符。
文件名片段最多 64 个 UTF-8 字节，超出时保留两端，不截断字符。
`<short-id>` 使用随机会话标识的前 8 位十六进制字符，完整标识仍保存在 `record.json`。
若目录已存在，则重新生成标识，不覆盖已有记录。
没有片段或遇到路径长度限制时，使用 `HH-MM-SS_<short-id>`。
完整路径及快照文件名以 `record.json` 为准。
编写读取器前请读[格式契约](../RECORD-FORMAT.md)。

## 配置与验证

```vim
let g:vim_session_recorder#config = {
    \ 'enabled': 1,
    \ 'exclude_patterns': ['\.tmp$', '\.log$', '/\.git/'],
    \ 'max_file_size': 1048576,
    \}
```

- `enabled`：在加载前设为 `0`，完全关闭采集。
- `exclude_patterns`：区分大小写的 Vim 正则表达式，匹配进入编辑器的绝对路径。
  自定义列表替换默认值。示例排除 `.tmp`、`.log` 和采用 `/` 分隔的 `.git` 路径。
  Windows 请匹配编辑器实际使用的路径分隔符。保留了历史默认字符串，
  这些字符串仍按 Vim 正则表达式解释。
- `max_file_size`：现有文件字节数达到该值时只记录元数据。
  仅限制打开时的副本，文件后来增大不会取消退出时的比较。
  含 NUL 的二进制文件只记录元数据。非 UTF-8 文本和带 BOM 的 UTF-16 文本
  均按原始字节保存快照。
- `helper_timeout_ms`：可选的单次 Python 调用等待上限，须为正整数。
  默认等待调用完成，与原行为一致。
  显式设置此项也会限制整次退出比较，超时会报告失败，
  可能留下原始副本，却没有最终 `record.json`。
- `record_dir`：可选的记录根目录绝对路径，覆盖 TXT 配置。
  使用 `<record_dir>/YYYY-MM-DD/vim/<session>/` 布局。

运行 `:RecorderStatus` 查看实际根目录、配置来源、当前会话目录和最近错误。
采集错误也可通过 `:messages` 查看。

验证时打开一个可丢弃的文本文件，修改并保存一行，然后正常退出。
检查新会话目录中的 `record.json` 和 `*-modification.diff`。
关闭采集或以空的无名缓冲区启动 Vim 时不会创建会话。
具名启动会话中的排除文件不进入文件记录。磁盘上尚不存在的新路径没有原始快照。

## 记录范围

插件保存原始全文、文件路径、已保存修改和光标行片段，片段可能包含未保存文本。
在打开私密文件前配置排除规则，或关闭插件。
Unix 上新建会话目录仅当前用户可访问，已有父目录权限与 Windows ACL 由用户管理。
插件不上传、不分析，也不自动清理记录。

Diff 比较首次记录时和退出时磁盘上的文件内容。放弃的 buffer 修改不算已保存修改。
外部程序对磁盘文件的改动也可能出现在 diff 中。
光标位置不表示注意力时长，可选的 `executed` 标记仅表示用户映射的声明，不能证明测试通过。
重命名按文件路径观察，不会自动关联成重命名事件。

最终记录只在退出时发布，跨午夜仍写入启动日期目录。
崩溃可能留下不完整材料。源文件读取失败、比较失败会记录在元数据中。
最终写入失败会显示在编辑器消息中，并留下诊断材料。

## My Big Brother

本仓库独立提供编辑器采集器，My Big Brother 已包含对应来源适配器。
如需使用自定义根目录，将其 `daily` 的绝对路径写入 `C/raw-logs-path.txt`，
或设置 `record_dir`。读取器使用同一根目录，其中应包含 `YYYY-MM-DD/vim/`。
验证一次合成会话后，明确启用其 `vim` 来源。共享目录本身不代表授权分析。
接入规则见[读取契约](../RECORD-FORMAT.md)。

系统存在 `diff -u` 时优先使用其比较算法，否则使用 Python 标准库，
不增加强制依赖。启动后打开文件、切换缓冲区和保存时不启动 Python，
也不重新生成 diff。

当前实现与测试见[开发说明](../DEVELOPMENT.md)。
早期个人需求和设计稿保留在 [docs/archive](../archive/README.md)，与现行说明分开。
仓库尚未选择许可证。
