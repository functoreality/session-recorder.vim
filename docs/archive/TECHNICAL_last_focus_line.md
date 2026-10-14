# last_focus_line 技术方案

## 目标
在文件记录中新增 `last_focus_line` 字段，记录用户在 Vim 中最后聚焦/光标所在行。

**输出格式**：
```yaml
# 行长度 < 120
last_focus_line:
  location: 10
  contents: "这是该行的完整内容"

# 行长度 >= 120
last_focus_line:
  location: 10
  head: "前40个字符前40个字符前40个字符前40个字符"
  tail: "后40个字符后40个字符后40个字符后40个字符"
```

---

## 方案对比

### 方案 A：BufLeave 钩子 + 内存状态（推荐）

**核心思路**：在用户离开 buffer 时记录标位置，存储在内存字典中。

**实现步骤**：
1. 在 `plugin/vim_session_recorder.vim` 添加 `autocmd BufLeave`
2. 在 `recorder.vim` 或新建状态管理模块，维护 `s:focus_lines` 字典：
   ```vim
   let s:focus_lines = {}  " { filepath: { line: 行号, col: 列号 } }
   ```
3. `BufLeave` 触发时调用记录函数：
   ```vim
   function! s:RecordFocusPosition()
       let l:bufnr = bufnr('%')
       let l:filepath = expand('%:p')
       let l:line = line('.')
       let s:focus_lines[l:filepath] = l:line
   endfunction
   ```
4. 在 `ProcessFileOnExit` 中读取并添加字段

**优点**：
- 性能开销小（只在切换 buffer 时触发）
- 实现相对简单
- 能记录每个文件的最后焦点位置

**缺点**：
- 如果 Vim 崩溃，未保存的状态会丢失
- 需要新增全局/模块级状态管理

---

### 方案 B：实时追踪 + 持久化写入

**核心思路**：使用 `CursorMoved` 实时追踪光标，频繁写入。

**实现步骤**：
1. 添加 `autocmd CursorMoved *` 触发记录
2. 每次移动光标都更新内存状态
3. 可选：定期写入临时文件（持久化）

**优点**：
- 记录最精确的光标位置

**缺点**：
- 性能开销大（每次光标移动都触发）
- 实现复杂

---

### 方案 C：VimLeavePre 时统一获取

**核心思路**：不实时追踪，只在 Vim 退出时获取当前焦点文件。

**实现步骤**：
1. 在 `VimLeavePre` 之前遍历所有窗口
2. 获取每个窗口当前 buffer 的光标位置
3. 填充到对应 file_record

**优点**：
- 最小改动
- 无需维护状态

**缺点**：
- 只能记录**当前打开在窗口中的文件**的焦点
- 已经关闭（但被记录过）的文件无法获取
- 多个窗口时需要遍历

---

## 推荐方案

**方案 A（BufLeave 钩子）** 是最佳平衡：
- 性能合理（只在切换 buffer 时触发）
- 能记录每个文件的最后焦点
- 实现复杂度可接受

---

## 改动范围

| 文件 | 改动 |
|------|------|
| `plugin/vim_session_recorder.vim` | 添加 `autocmd BufLeave` |
| `autoload/vim_session_recorder/recorder.vim` | 添加状态管理和记录函数 |
| `autoload/vim_session_recorder/recorder.vim` | 修改 `ProcessFileOnExit` 添加字段 |

---

## 待确认问题

1. **是否需要持久化？** 如果 Vim 崩溃，是否需要从文件恢复最后焦点位置？
2. **是否需要记录列位置？** 当前只记录行号，是否还需要列号？
3. **是否追踪所有文件？** 还是只追踪当前会话中打开过的文件？
