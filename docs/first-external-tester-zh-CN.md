# 首位外部测试者任务卡（离线样例）

目标：让一位**不是项目作者**的测试者，在 10 分钟内从项目目录跑出第一份 Signal Digest Loop 摘要，并留下不含私人信息的验收结果。

这次只测试虚构的离线样例。**不要接入真实 X 数据，不要填写账号、Cookie、API key，不要联网配置，也不要公开分享测试包、终端截图或结果。**

## 测试前提

- 你已收到一个本地的 `signal-digest-loop` 文件夹；
- 电脑已安装 Python 3.11 或更高版本；
- 不需要安装 Python 依赖；
- 不需要账号、密钥、浏览器登录态或网络；
- 不要修改样例文件。

如果你是通过聊天或网盘收到文件夹，先把它解压到一个普通本地目录。不要把自己的真实数据放进该目录。

## 计时记录

在运行第一条命令前开始计时。

```text
测试者代号（不要写真实姓名）：
操作系统：
Python 版本：
开始时间（HH:MM:SS）：
首次看到完整摘要时间（HH:MM:SS）：
总耗时（分:秒）：
是否需要作者协助：是 / 否
协助内容（如有，不写私人路径）：
```

## 操作步骤

### 1. 打开终端并进入项目目录

下面的 `<项目目录>` 只是占位符。请在本机终端中进入你收到的 `signal-digest-loop` 文件夹，不要把实际绝对路径发给作者或截图公开。

```bash
cd "<项目目录>/signal-digest-loop"
```

### 2. 检查 Python 版本

```bash
python3 --version
```

预期：显示 `Python 3.11` 或更高版本。如果版本低于 3.11，到此停止并记录 `环境不满足`，不要为了本次测试临时安装软件。

### 3. 运行第一份摘要

```bash
python3 demo.py
```

预期输出应包含以下证明点；receipt 的具体值每次可能不同：

```text
Signal Digest Loop — offline sample
No install · no account · no key · no network
Sources healthy:     1/1
Items normalized:    3
Items deduplicated:  3
Semantic shortlist:  3
Worth knowing:       3
Formal promotions:   1
Selected:
Receipt:
This run used fictional local data and an isolated temporary state directory.
```

看到完整摘要时立即停止计时，并填写上面的计时记录。

### 4. 可选：检查机器可读输出

这一步不计入“首次摘要”耗时，也不影响通过与否。

```bash
python3 demo.py --json
```

预期：输出一段 JSON，并至少包含：

```text
"mode": "offline_fictional_sample"
"network_required": false
"account_required": false
"worth_knowing_count": 3
"formal_promotion_count": 1
```

## 通过 / 失败标准

满足以下全部条件才算 `PASS`：

1. 测试者不是项目作者；
2. 从开始计时到首次完整摘要不超过 10 分钟；
3. 只运行本页的离线样例命令；
4. 没有安装依赖、登录账号、填写密钥、访问私人 X 数据或请求网络权限；
5. `python3 demo.py` 退出时没有 traceback；
6. 输出包含 `Sources healthy: 1/1`、`Worth knowing: 3`、`Formal promotions: 1` 和 `Receipt:`；
7. 测试者能用一句话说明：3 条“值得知道”不等于 3 条正式写回，正式晋升只有 1 条。

出现以下任一情况则记为 `FAIL`：

- 超过 10 分钟；
- 必须由作者代操作；
- 需要账号、key、网络、真实 X 数据或额外依赖；
- 命令报错或缺少上述证明点；
- 测试者无法区分“值得知道”和“正式晋升”。

Python 低于 3.11 记为 `ENV_BLOCKED`，不算产品通过，也不把它伪装成代码失败。

## 失败时如何回传（隐私安全）

不要发送完整终端截图、项目绝对路径、用户名、主目录、环境变量、浏览器信息、Cookie、token、key 或任何真实来源数据。

只回传下面这张卡：

```text
结果：FAIL / ENV_BLOCKED
Python 版本：
运行到第几步：
退出码（如可见）：
错误类型或第一行错误：
已脱敏的最后 10 行输出：
是否出现本机路径：是 / 否（若是，先替换为 <LOCAL_PATH>）
是否出现账号、key、真实数据：是 / 否（若是，不要粘贴内容）
总耗时（分:秒）：
```

如需保留错误文本，先把 macOS、Linux 或 Windows 的用户主目录整体替换成 `<LOCAL_PATH>`。不确定是否敏感时，只描述错误，不粘贴原文。

## 最终回执

测试完成后，只把以下文本私下发给项目作者；**不得公开发布、转发测试包或上传终端录像。**

```text
Signal Digest Loop 首次摘要测试
结果：PASS / FAIL / ENV_BLOCKED
总耗时：
是否需要作者协助：
证明点：health 1/1；worth knowing 3；formal promotions 1；receipt 有 / 无
一句话理解：
一个最卡的地方：
一个最想改进的地方：
```
