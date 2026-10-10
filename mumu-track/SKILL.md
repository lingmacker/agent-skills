---
name: mumu-track
description: "定位 macOS ARM64 MuMuPlayer 本地用户模型、启动退出、Guest冻结与宿主点击/拖动失效。用于Swift所有权/回调ABI、重签后延迟trap或nil事件monitor、Guest内置镜像、独立新VM真实长测、正常退出确认、DMG导出与有界测试清理。提供核心流程和6个标准库分析/只读健康工具，不含补丁、App/镜像、版本payload、凭据或会员授权。后续工作收尾同步更新此skill。"
---

# MuMu Track

从当前版本的真实读取和导航链定位问题；复用方法，不复用旧地址、输入 hash、字段偏移或机器码。先建立证据，再决定修改范围。

## 约束与工具入口

- 只修改当前工作区内明确指定的工作副本；保留原输入及可核验回滚文件。不替换安装版，不操作已有 VM/userdata，不清凭据或重置缓存。
- 对正常Library配置、新建/运行独立VM、Guest镜像替换/重签、调试权限分别确认范围。静态分析不自动授权运行；不从旧轮次或其他skill继承权限。用户要求自主推进、不再询问时，仍不自行扩权；没有已授权安全通路就保留证据和阻塞。
- 不改服务器授权、通用网络鉴权、启动 token、TLS/代理或系统安全设置。保留真实在线失败、普通停止和非目标检查；本地用户不等于服务器登录或会员。
- 使用已连接 REA 的实际工具和既有证据；普通文件/脚本工作不启动逆向 provider。原生 provider 不可用时使用已有反汇编及 Xcode 工具，不盲重开 Hopper或绕过试用限制，不自动安装依赖。
- 将脚本路径解析到本 `SKILL.md` 所在目录。设置 `PYTHONDONTWRITEBYTECODE=1`；生成的源码、JSON、日志和编译缓存放任务目录，不能写进 skill。

详细方法与验收/导出/清理流程见 [diagnosis-and-verification.md](references/diagnosis-and-verification.md)，用于分流失败、恢复Swift读取/所有权、Guest镜像/宿主输入和真实长测。

随包提供六个 Python 标准库核心工具；不含任何补丁、厂商输入或版本锁机器码。静态工具不修改/执行输入；Guest工具只通过明确SHA锁定的已有ADB只读查询，不启动/停止App或VM：

| 工具 | 用途 | 边界 |
|---|---|---|
| `scripts/macho_text.py BINARY` | 整文件/主 `__text` SHA、静态地址/文件偏移/长度 | 只支持薄 little-endian ARM64 Mach-O；不证明运行或 arm64e ABI |
| `scripts/swift_fields.py BINARY` | 账号/用户相关字段名、部分符号类型/context/协议实现线索 | 不是实际字段偏移、完整 Optional 类型或所有权证明 |
| `scripts/arm64_calls.py BINARY --target UNSLID_VA` | 扫描主 `__text` 内直接 B/BL 到指定地址的调用点 | 不覆盖间接调用、数据指针、其他代码区或所有交叉引用 |
| `scripts/signed_code_diff.py BEFORE AFTER` | 排除嵌入签名和LINKEDIT大小元数据后的同布局正文差异 | 不验签名/资源/权限，新增段及布局变更另审计 |
| `scripts/inspect_ext4.py --raw RAW --path /GUEST/PATH` | 冷RAW路径/inode/extent/hash定位；可提取文件到新工作区目录 | 首MBR分区、4KiB ext4、有限布局；不挂载或写回，不能代替fsck/安全写回证明 |
| `scripts/guest_health.py --adb PATH --adb-sha256 SHA --adb-home HOME --guest-port PORT --output-dir NEW_DIR` | 私有ADB真实计时的Guest七服务/panic/uptime检查 | 默认一小时；只是健康，不代替宿主身份、loaded-memory或真实UI交互 |

运行前阅读相应脚本。六个工具均支持 `--self-test`。不得使用 `python -O` 绕过校验。

外部工具按需使用现有 `codesign`、`otool`、`dwarfdump`、LLVM objdump/nm、swiftc/clang/LLDB；本包不安装或配置工具。

## 1. 建立输入身份与读取边界

1. 从 DMG/外层启动器找到实际 Player及嵌套 Emulator，不把启动器当账号实现。
2. 记录版本/build、CPU slice/subtype、UUID、整文件及代码 SHA、段/节映射、签名和原 entitlements。明确官方原始文件、实验中间文件及实际运行文件。
3. 若为 universal，先明确 slice；若为 arm64e，额外核对指针认证，不能直接套用薄 arm64 假设。
4. 保存一个工作 App及原可执行文件/资源封印；修改/恢复前确认相关进程与目标盘FD均关闭。通常走正常退出；另获明确强停授权时，先重验PID/创建时间/实际映像SHA与VM FD，再有界停止并记录信号，不能冒充正常退出。只回滚本轮修改过的 App 文件，不回滚 userdata。
5. 地址转换使用当前映像：`unslidVA = runtimePC - slide`；文件偏移按实际 segment 的 `fileoff + VA - vmaddr` 求出，要求目标范围完全 file-backed。不要默认所有映像都是 `VA - 固定基址`。

## 2. 找到首个失败，区分入口、模型、导航与在线刷新

沿 **Player启动 → 用户存储读取 → 状态枚举/发布 → 管理窗口 → 用户中心/创建 → Emulator预检/启动** 逐项检查。

| 现象 | 先定位 | 不要误判 |
|---|---|---|
| 调试器启动即退出，账号断点零命中 | Main、内联 SVC/ptrace、真实 syscall参数及退出值 | 不先归因账号/签名；libc wrapper断点可能看不到内联系统调用 |
| 首次无登录，点用户信息后失效 | 用户中心 toggle/refreshUserInfo、真实账号请求及状态清理 | 不把点击后的登录页写成启动绕过失败 |
| 默认模型已构造，冷启仍登录 | 缓存 decoder、属性包装器、返回的嵌套 Optional及发布源 | “默认值有效”不等于“读取值有效” |
| 管理窗口出现，但创建/启动失败 | 创建入口、真实 preflight/Result/callback、配置/网络阶段 | 不以隐藏登录窗口、列表项或PID证明Android启动 |
| 点击启动后 Emulator 很快消失 | 进程出生/消失时间、崩溃报告、独立 User 读取、Bool 完成及 watchdog/VM stop | 没有崩溃报告不等于没有失败；主动停止不是异常崩溃，不能先禁用停止函数 |
| 重签后延迟trap或dyld失败 | 当前UUID/slide对应的trap、签名检查或实际库解析 | 不全局禁brk/计时器，不把库存在但验证失败当丢失 |
| Guest命令/画面正常，但两宿主所有点击与拖动失效 | 实际激活、窗口命中、事件路由，再查签名失败延迟闭包及AppKit local monitor | AX响应/路由成功不是UI通过；主线程事件循环不排除应用级吞事件 |
| Guest桌面冻结/panic | init退出、七核心服务、SIGSTOP/真实故障，再查版本锁handler与镜像来源 | 不把设备连通或进程存活当Guest健康，不靠旧地址猜补丁 |

对调试失败先做只读入口观察。已跟踪进程调用 `PT_DENY_ATTACH` 可能按内核语义以 ENOTSUP退出；核对当前 SDK及真实寄存器，不硬套退出号或地址。确需诊断时只修改已确认的入口调用并保留原 helper，取得临时权限许可，结束后撤销诊断修改。

每条记录区分静态观察、组件试验、用户反馈和实际运行。没有观察到请求时，不能仅凭空token断言服务器的具体错误码。用户自行结束进程、删除/重建VM后，注销旧PID/创建时间、row/root/FD/ADB端口绑定并重新只读核验；不恢复已删除的盘，不继承代理强停/删除授权。复现先比对实际运行宿主的SHA及目标原/候选指令：重建VM不自动应用离线宿主候选，AppTranslocation也不能仅凭显示路径或App名称判断版本。未安装候选的再次失败，不是候选回归失败。

启动立即关闭时，先按明确 App 路径/hash 和唯一测试项做有界复现，记录 Emulator 出生/消失及退出类型。只读 sample 可先确认当前 UUID/slide 和停止栈；它不能提供 Optional 或回调参数。已授权 LLDB 观察只记录代码地址、目标 Optional tag、Bool/有限状态及 Swift 上下文是否非空，不读取账号内容或强制返回。串起 **独立 User 读取 → 目标 tag → 真实完成回调 → watchdog/stop**；每段分别证明，不把不同预检的整数状态回调当作 Bool 完成。

ad-hoc 重签后，仍保留厂商签名的 dylib 可能因 Team ID 不匹配被 Library Validation 拒载。核对加载错误、库存在/hash和实际进程身份；这是诊断/重签引入的独立问题，不能倒推为原始启动失败。不得默认关闭库验证或重签所有库；只在另获授权后对指定嵌套 Emulator 增加进程级 entitlement，并核对外层未新增该项。若最终候选必须保留，明确其可加载非同 Team 库的风险。

LLDB 的 signal stop 要记录具体信号名；运行库信号、SIGSTOP、trap及资源限制不能混为一类。只有证实正常信号用途后才允许保持原信号交付继续观察，不屏蔽未知信号或压掉崩溃。观察提前结束的栈不能代表后续运行结果；另做撤销诊断后的无调试器验证。

宿主输入分支先用仅目标PID、有限时长的只读事件观察与已校准原生点击/拖动建立红信号。核对`addLocalMonitorForEventsMatchingMask:handler:`的mask、block捕获、Swift薄闭包和真实返回值；返回nil会在`sendEvent:`前吞事件，不同于只读global monitor。嵌套菜单/窗口tracking通常不经过local monitor，但启动tracking的mouse down可能先被吞掉。签名失败可能延迟安装这种处理器，不一定trap。只在版本锁与调用契约确认后抑制专用破坏性响应；保留签名判定/日志/普通输入monitor、共享nil leaf、账号与停止，不全局禁事件。静态链、API fixture和当前进程已注册/修复成功分别记录；未知间接引用要保留扫描边界。

原生探针必须先校准：标题栏命中同PID不够，避开AXButton并确认空白窗口区域；首个dragged事件可能仅进入tracking，需后续渐进事件驱动真实位移。闭合菜单的AX项也可能常驻，项数不变不能判定点击失败；用可见菜单窗口或主线程真实menu tracking验证，Escape后有界等待异步退出。Home hover tooltip可能以AXGroup遮住按钮，先移开指针再复核命中，不能放宽到任意遮挡。修复后冷启，在300–600秒及用户报告的5–15分钟窗口后重复原生菜单、两窗口位移、原生Home与Guest前台/原生crop变化；ADB只用于非破坏场景准备和只读结果，不用ADB keyevent充当鼠标成功。记录启动时间、uptime和覆盖时长；选定控件通过不等于所有Guest触摸、正常退出或长时通过。

## 3. 从语义锚点恢复用户数据链

1. 搜索 `UserData`、`User`、`AccountResponse`、`BaseDeviceResponse`、AccountManager、用户中心/登录导航类、属性包装器和 refreshUserInfo等字符串/字段线索。
2. 用字符串引用、函数边界、直接调用扫描、Swift metadata/VWT/协议和间接分派核对实际入口；字符串名和伪代码不能单独确认调用契约。
3. 画清以下三层，逐一确认值的来源和寿命：
   - **默认构造**：一次性初始化、默认 nil factory、包装器默认区域。
   - **实际读取**：缓存反序列化优先级、解码成功/失败及fallback、泛型 getter的结果缓冲区。
   - **发布/消费**：订阅初始化、状态变化、导航枚举、窗口/通知及创建/启动消费者。
4. 搜索被修改函数的全部相关调用者和别名。通用reader/tag leaf可能复用于其他布局兼容类型；泛化tag计数不是存在已登录User的证据。
5. 如改通用代码，验证**类型及属性身份**，保留其他模型/已有用户。相同泛型类型可能有多个存储key，类型比较不能自动证明属性唯一。

默认值和缓存值不同：`UserData?` 为 some但 `UserData.user` 为 none，可以合法解码并覆盖本地默认值。不要清缓存制造成功；在已审查的用户读取/发布接缝处理缺失模型，并单独检查冷启和状态变化。

Player 与 Emulator 是独立映像/存储消费者；Player 的本地值不自动传给 Emulator。若已证实启动专用读取返回 `User.none` 并触发 false/stop，先审查该 typed getter 的全部直接及间接调用者，再选择专用启动调用点。原 getter 恰好执行一次；只在目标 Optional 真为 none 时原位构造完整 User，已有值及其他调用者保持原样。只得到一份临时返回值不等于更新了共享存储或通知状态，其他消费者和正常关闭仍需独立验证；不能因桌面出现扩大到通用 tag leaf 或全局账号检查。

## 4. 恢复 Swift ABI并构造真实本地值

先核对当前版本的类型种类、字段偏移、size/stride/alignment、metadata/VWT、extra inhabitants、Optional/Result tag和值见证。字段名相同、本机参考Swift布局相同，均不能单独证明目标ABI。

模型层次通常为：

```text
UserData? → UserData(user: User?, extra: UserExtraInfo?)
User → userId?, token?, userInfo?, runningTimeCount, userScence
AccountResponse → 当前设备、状态、显示信息及成员字段
BaseDeviceResponse → 设备标识/别名、状态、平台、数组及机型
```

逐项遵守：

- 构造有效的嵌套 `.some` 值；分清整个UserData缺失、其中User缺失及User.userInfo缺失，不只强改Bool/tag。
- 使用真实Swift String、Array及runtime singleton。通过编译参考fixture/原值见证确认内联字符串编码和数组ABI；不把零指针或任意数字当Swift堆对象。
- 给本地模型可辨识的标识/显示值；若调用契约需要token Optional存在，存在但为空仍**不是凭据**，不能用它证明在线授权。
- 保持 paid/member权限为false/0；其他scene/device/trial枚举只按原状态计算及消费者语义选择，不把“某值使界面出现”当成员资格。
- 保留runningTime计数/阈值及计时语义。未知单位或长时含义需继续定位，不能顺带禁用检查。
- 依据原函数确认 initializeWithCopy/Take、assign、destroy。Take搬运所有权，不是带retain的复制；不能将这些操作一概替换为memcpy。
- 原读取完成后若保留已有非nilUser，保持值/所有权原样；若替换some且User缺失，先通过正确原destroy释放整个旧值（包括extra），再初始化新值；整个nil分支不释放不存在的对象。对非目标类型走原路径。
- 核对回调的参数寄存器、输出缓冲、错误对象释放、Swift上下文及恰好一次完成。`completion`字符串锚点可能实际传整数状态/集合，不代表Bool回调；不能直接ret使Promise悬空。

## 5. 让本地模式避开专属在线用户中心路径

先核对用户中心是否先展示本地值，再单独调用线上刷新。优先处理这个专用调用点，不禁用全局账号服务。

只对已确认的本地标识+空token组合避开在线刷新；已登录真实用户、其他token及非目标动作保留原行为和真实失败。保持原用户中心的本地展示，不伪造远端成功响应或隐藏全部错误。

若利用调用者栈里的标记，核对固定调用点、分支、栈尺寸、初始化和生命周期，只比较合法内联字，不解引用已释放对象。布局/调用者变动时重新恢复契约，不能照搬偏移。点击用户中心后仍管理可见，不能代替创建/Emulator启动验证。

## 6. 规划最小二进制修改，而非提供跨版本补丁

1. 对实际输入锁定版本/hash/原字节、函数范围、可修改区域和全部依赖；未知、重复、截断输入或输出覆盖必须拒绝。
2. 优先改专用调用或窄化的读取接缝；保留原函数、错误/停止路径及非目标消费者。不随意覆盖邻接函数当code cave。
3. 如需新增代码，确认可执行映射与独立空间。新增Mach-O RX段/节时检查header padding、段/节顺序及索引、文件与VM对齐、保护和所有引用。
4. 若移动LINKEDIT，同步调整相关load-command偏移及需要的索引；检查dyld rebase/bind、符号/导出、function starts和签名范围，不只移动原字节。
5. hook使用原指令thunk时证明复制指令可重定位，再准确接回原函数；避免递归、栈不平衡或多次原读取。
6. 对所有 B/BL、ADRP/ADD/LDR、literal及object relocation逐项解析。保持4字节指令对齐、16字节栈对齐、callee-saved寄存器和非空Swift上下文；B/BL要求 `delta % 4 == 0` 且 `-2^27 ≤ delta < 2^27`。未链接object text不可直接粘贴。
7. 比较整个候选，分别列出原正文允许差异、新代码区、Mach-O头/重定位及签名差异。不能将正文少量字节变化描述成整个文件仅这些变化。
8. 从原entitlements派生最小权限；只重签实际变更bundle及其受影响外层。必要能力不丢失，不默认放宽库验证。deep/strict不是厂商身份、公证或运行成功。

本 skill 不包含补丁生成器、固定机器码、模型汇编或裸候选；具体修改应在独立任务目录实现并自测。

### Guest镜像分支

参考其他版本只复用方法，不复用ELF/RAW地址或hash。逐文件核对ELF64/AArch64/PT_LOAD、dispatch表、普通epilogue和全部消息；只处理有证据的破坏性响应，保留非目标消息、检查、拒绝、日志和普通停止。内置system修改另需明确授权：确认App与盘冷态，备份本轮文件；逻辑RAW全差异白名单、inode/extent/xattr、只读原/候选fsck、qcow2 check/compare后再替换，内Emulator→外Player重签，核对宿主非签名正文、原entitlements与资源封印。

旧VM不会自动消费新factory镜像；只新建/启动授权独立项，以row/root身份hash及FD绑定，原两项和userdata不动。分别核验Guest磁盘五份文件hash、loaded-memory、uptime/服务/panic、原生画面、真实鼠标交互；权限不足记录未完成，不提权。镜像回滚只恢复本轮App/template文件或另获授权的冷态system，不回滚userdata、不删除VM。隔离组件与有限健康不等于长时/交互通过。

## 7. 先组件，再真实验证及清理

- 测布局、所有Optional分支、真实字符串/数组、边界guard、原copy/destroy、源销毁后目标可读及原模型字段值。使用参考Codable时标注它不是目标原decoder。
- 对新reader测试原读取一次、保留已有User、其他类型/属性不变、some缺失User释放一次及nil不释放。合成stub控制流测试与原值见证测试分开记。
- 对本地刷新guard测试精确标记和相近非本地值；对branch/重定位测试边界、未知输入、重复应用及输出覆盖。
- 在授权工作App上实际确认：冷启管理窗口 → 用户中心操作不回登录 → 仅一个独立测试VM创建。每步分别记用户反馈与代理证据；列表增行只证明创建/管理状态。
- 若要求打开模拟器，另闭环Emulator Result/预检、实际进程/唯一VM路径和Android桌面操作；PID/ADB ready不等于可操作桌面。长时稳定、联网、安装版/新电脑分别验证。
- 实际退出检查可分别使用普通application quit与标准AX窗口close；成功返回只代表请求接受，不能证明退出。若有标准退出确认sheet，先核对唯一目标/确认按钮、退出语义及无删除/重置/强制提示，确认后再观察实际退出；不可把待确认误判成死锁。超时后保留现场，不重复请求、热改或重签；没有另行明确授权不强停。获授权强停仅用于解除冷态门禁，先核对身份/盘FD并保留数据，绝不算正常关闭。离线候选可制作/组件验证，安装仍须真实冷态门禁。最终撤销临时get-task-allow及入口诊断改动，在正常冷态重签并从原生入口冷启，再正常退出核验进程。不能以quit请求返回替代进程退出，不强杀冒充正常关闭。应用能进入桌面、打开应用及返回桌面，也不证明退出路径正常；若用户要求延期关闭故障，记录失败与仍存活 PID，不强杀、不重签运行中的 App、不把未进行的再次冷启记为通过。
- 若LaunchServices触发AppTranslocation，先按实际执行程序hash、来源和路径形态验证它是指定工作副本（Foundation可能将`/private/var`规范化为`/var`，两种前缀都需保持完整后缀及运行/工作文件SHA匹配），再进行已授权UI观察；不能因路径不同就删除quarantine或关闭Gatekeeper。
- 通过本次运行门禁后再导出DMG，校验checksum、只读挂载App完整inventory/签名，移除临时stage。分发包不带VM/userdata或诊断helper；安装版/新机器另验，不自动覆盖。
- 获得工作区外清理授权后，仅按精确路径、所有者、PID/UUID/历史证据及无FD删除本轮测试残留。Docker只清本轮专属资源，不全局prune、删复用镜像/旧volume或停止其他用户服务；仅关本轮私有ADB。
- 只保存有限地址/信号、域码/阶段、计数及UI分类。原始账号文本/请求/错误内容和调试stdout/stderr在RAM处理后丢弃，不保存原始RAM或账号全屏截图。
