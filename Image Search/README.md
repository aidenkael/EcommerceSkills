# 1688 以图搜图 v6.0

拖入图片 → 自动在 Edge 浏览器打开 1688 搜图同款结果。

## 文件

| 文件 | 用途 |
|------|------|
| `1688搜图.exe` | 已打包，双击运行 |
| `app.py` | 源代码，可修改后重新打包 |
| `requirements.txt` | Python 依赖 |

## 使用

1. 双击 `1688搜图.exe`
2. 拖入图片（或 Ctrl+V 粘贴）
3. 点击搜索
4. 自动在 Edge 打开 1688 搜图结果

## 打包

```bash
pip install -r requirements.txt
pyinstaller --onefile --windowed --name "1688搜图" app.py
```
