# minecraft-mod-fliter

NeoForge Mod 服务端筛选工具。

读取指定文件夹中的所有 NeoForge Mod（`.jar`），根据 `neoforge.mods.toml` 中的 `side=` 字段筛选出需要在服务端运行的 Mod，移动到输出文件夹。

## 系统要求

- Python 3.10+
- Windows / macOS / Linux

## 安装

```bash
# Python 3.10 需要安装 tomli
pip install tomli

# Python 3.11+ 无需额外依赖
```

## 运行

```bash
python main.py
```

## 打包为 EXE（Windows）

```bash
pip install pyinstaller
python -m PyInstaller --onefile --windowed --name "Mod筛选器" main.py
```

生成的文件在 `dist/` 目录下。

## 使用方法

1. 点击 **浏览...** 选择输入文件夹（存放所有 Mod 的目录）
2. 点击 **浏览...** 选择输出文件夹（筛选后的 Mod 将移动至此）
3. 点击 **开始筛选**

## 筛选规则

读取每个 `.jar` 文件内 `META-INF/neoforge.mods.toml` 的 `side=` 字段：

| side 值 | 行为 |
|---------|------|
| `SERVER` | 移动到输出文件夹 |
| `BOTH` | 移动到输出文件夹 |
| 未指定 | 移动到输出文件夹（默认 BOTH） |
| `CLIENT` | 跳过，不移动 |
| 无 toml 文件 | 跳过（非 NeoForge Mod） |

## 项目结构

```
minecraft-mod-fliter/
├── main.py                 # 入口
├── requirements.txt        # Python 依赖
├── src/
│   ├── __init__.py
│   ├── filter.py           # 核心筛选逻辑
│   └── gui.py              # GUI 界面 (tkinter)
├── package.json            # Node.js 开发工具
├── commitlint.config.js    # commitlint 配置
├── cliff.toml              # git-cliff 配置
├── CHANGELOG.md            # 变更日志
└── README.md
```

## 开发

使用 git cz 进行规范化提交，git cliff 生成变更日志：

```bash
npm install        # 安装 git cz 和 git-cliff
npm run commit     # 交互式提交
npm run changelog  # 生成 CHANGELOG.md
```
