# Step 01: 环境与打包

## Python 环境

| 项目 | 值 |
|------|-----|
| Python | 3.13.14 |
| PyInstaller | 6.21.0 |
| venv 路径 | `E:\EcommerceSkills\Profit accounting-Auto.venv` |

## build_windows.bat 修改

将 `py -3 -m pip install` 和 `py -3 -m PyInstaller` 改为使用项目 `.venv`：
- `.venv` 不存在时自动创建
- PyInstaller 安装在 `.venv`
- 使用 `.venv\Scripts\python.exe -m PyInstaller`
- 失败返回非零退出码

## 打��前验证

```
.venv\Scripts\python.exe -m pytest tests -q
→ 216 passed in 3.60s

python -m compileall .
→ OK (no errors)

git diff --check
→ OK
```

## 打包命令

```bat
.venv\Scripts\python.exe -m PyInstaller ^
    --noconfirm --clean --onefile --windowed ^
    --name ProfitAccountingAuto app.py
```

## 打包结果

| 项目 | 值 |
|------|-----|
| 状态 | ✅ 成功 |
| EXE 路径 | `E:\EcommerceSkills\Profit accounting-Auto\dist\ProfitAccountingAuto.exe` |
| 文件大小 | 12,754,234 bytes (12.7 MB) |
| 退出码 | 0 |

## 警告

标准 PyInstaller 警告（非致命）：
- `grp` / `pwd` — Unix-only 模块，Windows 不适用
- `_frozen_importlib_external` — 预期缺失

无业务代码相关的隐藏导入错误。
