---
name: macos-app-structure
description: 创建或重构标准原生 macOS SwiftUI App，使用 Xcode 工程按 Groups 组织源码，并整理资源与测试目录。
---

# macOS App 目录结构

使用原生 `.xcodeproj` 管理 macOS SwiftUI App。修改已有项目时，先检查 `project.pbxproj`、Scheme、Build Phases、资源和测试配置，再移动或增删文件引用。

## 目标结构

```text
MyMacApp/
├── .gitignore
├── MyMacApp.xcodeproj
├── MyMacApp/
│   ├── MyMacAppApp.swift
│   ├── Core/
│   ├── Models/
│   ├── Views/
│   ├── Resources/
│   │   └── Assets.xcassets
│   └── ...
└── MyMacAppTests/
```

## Xcode 组织规则

- 源码直接加入 App target，测试加入 `MyMacAppTests` target。
- 在 Xcode Project Navigator 中用 **Group** 按 `Core`、`Models`、`Views`、`Resources` 等目录组织源码。Group 是逻辑分组，不要把整个源码目录作为单个 folder reference。
- Group 路径与磁盘目录保持一致。新增、移动或删除文件后，确保 `project.pbxproj` 中的文件引用、Build Phases 和 target membership 一致，避免漏编译或重复编译。
- `Assets.xcassets` 放在 App target 的 Resources 中；其他资源按需加入对应 target。资源默认由 App 主 Bundle 提供。
- 测试放在 `MyMacAppTests/` 并归属测试 target；仅在已有测试或明确需要测试时添加测试代码。
- `.gitignore` 忽略 `.DS_Store`、`DerivedData/`、`build/`、`*.xcuserstate` 和 `xcuserdata/`，不要忽略共享 Scheme。

## 操作与验证

1. 检查现有文件布局、工程引用、target membership 和共享 Scheme。
2. 按目标结构整理文件；保留 App 入口 `MyMacAppApp.swift`，不要无故重写生命周期或业务代码。
3. 更新 Xcode Groups、文件引用和 Build Phases；删除过期引用。
4. 用项目现有 Scheme 构建，存在测试时一并运行：

```sh
xcodebuild -project MyMacApp.xcodeproj -scheme MyMacApp \
  -derivedDataPath /tmp/mymacapp-build build
xcodebuild -project MyMacApp.xcodeproj -scheme MyMacApp \
  -derivedDataPath /tmp/mymacapp-build test
```

5. 若工程名或 Scheme 不同，使用实际名称替换命令参数。检查构建产物中的资源是否进入 `MyMacApp.app/Contents/Resources`。
