# 核心定位、修改与验收方法

## 导航

1. [首个失败分流](#首个失败分流)
2. [Swift读取与所有权](#swift读取与所有权)
3. [Guest镜像与宿主输入](#guest镜像与宿主输入)
4. [真实计时与关闭](#真实计时与关闭)
5. [导出与清理](#导出与清理)
6. [工具入口](#工具入口)

只复用方法；重新恢复当前输入的布局、地址、原字节与调用契约。本文件不提供补丁、版本地址、原厂文件或会员授权。

## 首个失败分流

按时间串起Player→Emulator→Guest，先识别首个偏离预期的阶段：

| 证据 | 最小下一步 | 不要做 |
|---|---|---|
| 调试器启动立即退出、账号断点未命中 | Main内联系统调用、真实syscall参数、退出码及SDK定义 | 把调试条件诱发的退出当正常运行故障 |
| 初始管理界面正常、用户中心后回登录 | toggle→线上refresh→状态清理，与初始读取分开 | 全局伪造网络成功或清账号缓存 |
| 默认值有效但冷启仍失败 | 读取优先级、缓存decoder、嵌套Optional与发布源 | 只强改默认值或共享tag函数 |
| Emulator几秒内普通停止 | 独立typed getter→tag→真正Bool/Result完成→stop/watchdog | 禁用stop、只看崩溃报告是否存在 |
| 重签后库拒载 | 实际库路径/hash、Team ID与Library Validation | 把重签干扰当原启动故障，批量重签库 |
| Guest panic或核心服务停止 | init退出、service状态及当前版本的dispatch表/全部副本 | 修改图形锁或把ADB device当健康 |
| Guest刷新但两宿主点击、拖动失效 | 激活/窗口命中/事件路由→延迟闭包→local monitor | 把AX响应或主线程事件循环当可交互 |
| quit被接受但进程未退出 | 标准确认sheet、未完成的stop/Promise、FD与退出时间 | 重复quit、直接强停、宣称关闭成功 |

临时诊断与最终生产状态分开；结束诊断后恢复反调试入口、撤销get-task-allow，再无调试器验收。未知SIGXCPU、trap或资源限制保留，不屏蔽未知信号。

## Swift读取与所有权

1. 建立UserData→User→AccountResponse及设备值的实际层次，核对字段类型/偏移、size/stride/alignment、metadata、Optional/Result tag和值见证。
2. 区分整个外层none、some但内层User.none、已有真实User；缓存成功解码的缺失内层值可能覆盖默认值。
3. 搜索全部直接调用、数据引用及可确认的间接入口。共享泛型reader可能服务于布局兼容但语义不同的模型。
4. 原读取恰好一次；已有User和非目标类型保持。替换some旧值时先调用对应destroy；nil分支不释放不存在的对象。
5. initializeWithTake转移所有权，不等于initializeWithCopy或memcpy。测试必须让源先销毁，再检查目标与原destroy。
6. 原shipped witness组件、合成stub、参考Codable、App现场分别记证据，不能合成“完整ABI通过”。
7. 回调核对参数类型、Swift上下文、输出缓冲、闭包寿命及恰好一次完成；字符串锚点的整数状态回调不能当Bool。
8. Player与Emulator独立读取；仅启动专用fallback不等于更新共享存储/通知或所有消费者。
9. 本地空token不是凭据，paid/member保持false；不改变真实用户、服务器订购、TLS或通用鉴权。

需要新增代码时使用经审查的独立可执行空间。核对栈/寄存器、B/BL范围、ADRP/ADD/LDR与GOT、LINKEDIT所有载入命令/表偏移；未链接object text不能直接粘贴。分别报告原正文、新代码区、头部/重定位和签名差异，不称“全文件只改几字节”。

## Guest镜像与宿主输入

### Guest

- 从文件系统路径/inode/extent找ELF，不能在RAW直接套旧物理块；核对ELF架构、PT_LOAD及虚拟地址到文件偏移。
- 对每个handler完整恢复message范围、表编码、原拒绝/epilogue与所有相关副本。只处理已证实的破坏性响应，保留普通检查/错误/停止及其他消息。
- read-only extent工具用于定位与提取，不证明安全写回。写回另查hole/跨extent、重复物理块、xattr、shared-data、加密、verity和布局歧义；不支持则拒绝。
- 验证完整逻辑RAW差异、inode/extent/xattr、原/候选只读fsck、qcow2 check/compare；组件不执行危险原响应或真实init线程。
- 替换App内置system后由内向外重签；不改旧userdata。旧VM不自动消费factory模板，创建授权独立新VM并重绑row/root/FD。
- 磁盘文件hash、loaded-memory、Guest健康、显示刷新、鼠标输入是独立门禁。权限不足记录未验，不提权。

### 宿主

- 恢复签名失败分支、随机延迟、block/thin-closure捕获、event mask及返回值。AppKit local monitor返回nil会阻止sendEvent递送；不要与只读global monitor混淆。
- 仅处理经版本锁和契约审查的专用破坏性注册入口，保留签名predicate/日志、定时任务、共享leaf、普通monitor、账号/stop/watchdog。
- 强证据分层：静态机制→API fixture组件→冷启红/绿输入恢复；没有直接读取活进程注册记录时如实标注。
- Foundation可把/private/var规范化为/var；接受AppTranslocation须完整后缀、当前运行与指定工作文件SHA相同，不能删quarantine/关闭Gatekeeper。
- 校准拖动点：同PID不足，确认空白AXWindow而非标题栏按钮。首个dragged事件可能仅进入tracking，使用渐进事件并核验实际坐标变化。
- 关闭菜单也可能常驻AX列表；项数不变不代表失败。用可见popup或真实menu-tracking栈，Escape后有界等待异步退出。
- Popup不一定在应用AX children中；从目标PID专属可见popup几何定位SystemWide AX hit，核对owner/role/精确菜单标签，不盲选首项或套旧版本菜单。
- tooltip可遮住按钮，移开指针再命中核验；不能把允许区域放宽到任意AXGroup。

## 真实计时与关闭

1. 新run重新核对PID创建时间、实际映像SHA、唯一测试root/磁盘FD、实际ADB监听端口。UI增行不证明VM启动，目录名不证明模板消费。
2. 在早期故障窗口前开始，使用monotonic计时和uptime双证据；进程/端口变化或重启不拼接成同一长测。
3. 每隔约20秒采样七服务、panic及uptime；拒绝核心PID变化、停止/阻塞态、异常stop/trap及超限缺口。dmesg无法读取不是panic=false。
4. 一小时须真实覆盖至少3600秒，并在开始、延迟窗口、多个中间点和终点重复原生菜单、两窗拖动、Date/Home与Guest画面/前台变化。
5. ADB可准备无破坏场景和只读分类；不能用ADB Home/keyevent替代原生点击。选定控件通过不代表全部Guest触摸、每款游戏或网络。
6. 普通quit接受不等于退出。如果出现标准退出确认sheet，先核对目标PID/SHA、退出语义、唯一确认按钮、无删除/重置/强制提示，再确认正常退出；不能把待确认误判成必然死锁。
7. 最终核对Player/Emulator及相关进程与盘FD消失。强停须另行明确授权，核对身份后执行；绝不算正常关闭，不能回滚userdata。
8. 只存标量、有限代码符号、分类与已校准中央Guest crop。采样stdout/stderr在RAM分类后丢弃，不保存完整账号、请求、错误userInfo或原profile。

## 导出与清理

- 先满足本次明确运行验收，再冷态导出。保留原DMG、一个工作App及可验证回滚；不把VM/userdata、调试helper或凭据放进分发包。
- 临时staging仅用于打包，保留资源/xattr/权限，App inventory和deep/strict需与源一致；不因打包再次修改签名。
- 用hdiutil创建压缩DMG、verify、只读挂载到工作区，并核对挂载App完整inventory/签名/身份；拆卸后删临时stage。新电脑/安装后双击仍是独立验收，不自动替换安装版。
- 明示ad-hoc非官方签名/公证，Library Validation放宽风险、本地权限不是服务器会员，以及未验项目。
- 用户授权清理工作区外测试残留后，按精确路径、所有者、PID/UUID/历史证据、无FD核对，记录hash/大小后删除。不要只凭名称删整棵临时目录。
- Docker仅移除本轮专属资源；--rm容器已删除就记无残留。复用的镜像、已有volume、用户容器和Colima profile保留，不全局prune或停止其他服务。默认ADB不动，只关闭本轮私有server。

## 工具入口

所有工具仅依赖Python标准库；设PYTHONDONTWRITEBYTECODE=1，禁止-O。相对路径从Skill根目录解析，输出写调用者工作区。

| 工具 | 核心用途 | 明确限制 |
|---|---|---|
| scripts/macho_text.py | 主text映射及hash | 薄ARM64，不证明运行 |
| scripts/swift_fields.py | Swift语义字段/符号线索 | 不是布局/所有权证明 |
| scripts/arm64_calls.py | 主text直接B/BL调用者 | 不覆盖间接引用 |
| scripts/signed_code_diff.py | 同布局重签前后正文差异 | 排除嵌入签名及LINKEDIT大小元数据；不验签名/资源/entitlements，新RX/布局变化另审计 |
| scripts/inspect_ext4.py | 冷RAW路径/inode/extent/hash，可提取文件到新工作区目录 | 仅首MBR Linux分区、4KiB ext4；拒绝未知布局/加密/verity/shared blocks，不挂载/写回 |
| scripts/guest_health.py | 私有ADB有限健康采样 | 要显式ADB SHA/端口/私有home；不启动/停止VM，不验宿主/loaded-memory/原生UI |

先运行各脚本--self-test并阅读源码，再针对当前已授权输入做只读对照；不要复制任何调查目录的patch脚本进入Skill。
