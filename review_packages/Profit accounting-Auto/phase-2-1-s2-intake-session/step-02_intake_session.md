# Phase 2.1 / S2 OCR 图片录入会话与文件管理 — 步骤说明

## 目标

实现图片副本管理、OCR 会话目录、session.json 读写和清理函数。继续使用 PlaceholderOcrEngine，不开发字段提取、GUI 或真实 OCR。

## 分支与完整 HEAD

| 项 | 值 |
|---|---|
| 仓库根 | `E:/EcommerceSkills` |
| 当前分支 | `codex/feature/phase-02-01-s2-intake-session` |
| 当前 HEAD（S2 提交前） | `15a9c6a3c2cab8f6f43c346d627f17d8975abbd5`（S1 提交） |
| 是否合并 master | 否 |
| 工作区其他项目修改 | 原样保留未触碰（logistics-cost-skill-2.0 等） |

## S1 提交文件数量差异核对

用户指出：S1 报告称提交 10 个文件，但正文"新增文件"列表只列 9 个源码/配置文件。

核对 `git show --stat 15a9c6a3` 实际提交的 10 个文件：

1. `Profit accounting-Auto/.gitignore`
2. `Profit accounting-Auto/image_intake/__init__.py`
3. `Profit accounting-Auto/image_intake/image_types.py`
4. `Profit accounting-Auto/image_intake/result_models.py`
5. `Profit accounting-Auto/ocr/__init__.py`
6. `Profit accounting-Auto/ocr/base_engine.py`
7. `Profit accounting-Auto/requirements-ocr.txt`
8. `Profit accounting-Auto/tests/test_base_engine.py`
9. `Profit accounting-Auto/tests/test_result_models.py`
10. `review_packages/Profit accounting-Auto/phase-2-1-s1-foundation/step-01_foundation_skeleton.md`

**差异原因**：第 10 个是 S1 步骤报告本身。S1 报告正文"新增文件"列表只列源码和配置文件，未把报告自己列入（报告是交付物，不是源码）。数量无实际缺失，无需修改 S1 代码。

## 新增和修改文件

### 新增

| 文件 | 作用 |
|---|---|
| `image_intake/intake_service.py` | IntakeService：会话创建、图片副本管理、session.json 原子读写、占位引擎调用、旧会话清理、路径穿越防护 |
| `tests/test_intake_service.py` | 20 个测试用例，覆盖会话目录、图片添加、JSON 读写、清理、路径安全 |

### 修改

无。本步骤未修改 S1 的任何文件（result_models.py、image_types.py、base_engine.py、__init__.py 均保持不变）。序列化逻辑全部放在 intake_service.py 服务层，未污染数据结构层。

## 默认目录与注入目录方案

### 默认目录

`resolve_default_session_root()`：
1. 优先读环境变量 `LOCALAPPDATA`
2. 存在时返回 `Path(LOCALAPPDATA) / "ProfitAccountingAuto" / "ocr_sessions"`
3. 缺失时回退 `Path.home() / "AppData" / "Local" / "ProfitAccountingAuto" / "ocr_sessions"`
4. 只返回路径，不创建目录

### 注入目录

```python
IntakeService(session_root=tmp_path, engine=placeholder_engine)
```

- `session_root` 为 `None` 时用默认目录
- 测试全部用 `tmp_path` 注入，不写真实 LOCALAPPDATA
- 构造时 `mkdir(parents=True, exist_ok=True)` 确保根目录存在

## session.json 示例结构

```json
{
  "format_version": 1,
  "session_id": "20260727_040322_f6f84b17",
  "created_at": "2026-07-27T04:03:22",
  "engine_name": "placeholder",
  "images": [
    {
      "image_id": "a3f2e1c8...",
      "original_filename": "商品核价图.png",
      "stored_filename": "a3f2e1c8....png",
      "stored_path": "C:/.../ocr_sessions/20260727_040322_f6f84b17/original/a3f2e1c8....png",
      "image_type": "shein_pricing",
      "added_at": "2026-07-27T04:03:22"
    }
  ],
  "field_candidates": {
    "weight_g": {
      "field_name": "weight_g",
      "candidates": [
        {
          "candidate_id": "...",
          "field_name": "weight_g",
          "parsed_value": 0.5,
          "normalized_value": 500.0,
          "unit_original": "kg",
          "unit_normalized": "g",
          "selectable": true,
          "source_image": "a3f2e1c8...",
          "raw_text": "0.5kg",
          "confidence": 0.92,
          "measurement_group_id": "grp1"
        }
      ],
      "selected_candidate_id": "..."
    }
  },
  "selections": {
    "weight_g": {
      "field_name": "weight_g",
      "source_candidate_id": "...",
      "confirmed_value": 500.0,
      "confirmed_unit": "g",
      "measurement_scope": "bare",
      "user_modified": false
    }
  }
}
```

写入规则：UTF-8、`ensure_ascii=False`（中文不转义）、`indent=2`、原子写入（临时文件 + `os.replace` + `fsync`）。

## 路径安全措施

1. **session_id 校验**（`_validate_session_id`）：
   - 拒绝空值、含 `..`、含路径分隔符（`/`、`\`、`os.sep`）
   - 二次验证：`(root/session_id).resolve()` 必须 `relative_to(root.resolve())`
2. **路径校验**（`_validate_path_in_root`）：
   - `load_session` 传入路径时，`resolve()` 后必须 `relative_to(root)`
3. **清理安全**（`cleanup_sessions_older_than`）：
   - 跳过符号链接（`is_symlink()`）
   - 只遍历 `session_root` 直属目录
   - 每个目录 `resolve()` 后验证在 root 内，防止符号链接逃逸
4. **源文件保护**：`add_image` 用 `shutil.copy2`，不移动/覆盖/删除源文件
5. **days 校验**：必须是非负整数（排除 bool）

## 新增测试数量

| 测试文件 | 用例数 |
|---|---|
| `tests/test_intake_service.py` | 20 |

覆盖用户要求的全部 20 项：会话目录创建、session_id 唯一性、默认目录解析、LOCALAPPDATA 回退、源文件不变、同名不冲突、扩展名小写、不支持扩展名拒绝、源不存在拒绝、非法 image_type 拒绝、UTF-8 中文、保存读取完整、候选与选择 roundtrip、format_version 不支持、损坏 JSON、占位引擎空结果、清理超期会话、负数 days 拒绝、路径穿越拒绝、不写真实 LOCALAPPDATA。

## 全部测试结果

| 类别 | 数量 | 结果 |
|---|---|---|
| S1 原有 + S1 新增 | 232 | 全部通过 |
| S2 新增 | 20 | 全部通过 |
| **合计** | **252** | **252 passed in 3.01s** |

执行命令：
```
.venv-311\Scripts\python.exe -m pytest tests -q
```

测试中修正 1 处：`test_save_then_load_complete` 在 `add_image` 后补 `save_session`（add_image 只改内存，save_session 是独立职责），未修改任何现有测试或业务代码。

## 未完成事项（本步骤明确不做）

- 三个字段提取器（shein_price / cost_shipping / dimension）
- 正则价格、重量、尺寸提取
- OCR 录入对话框（GUI）
- ui/product_page.py 接入
- 真实 PaddleOCR（paddle_engine.py）
- OpenCV 预处理（preprocessing.py）
- 正式字段回填
- requirements-ocr.txt 依赖锁定（S6）
- EXE 打包
- Phase 2.2

## S3 前置条件

1. S2 全部测试通过（已满足，252 passed）
2. 用户确认进入 S3
3. S3 计划实现 3 个字段提取器（`image_intake/extractors/`）：
   - 输入 OCR 文本行列表，输出 OcrCandidate
   - 含单位归一化（g/kg/mm/cm → g/cm）、无单位 selectable=False、measurement_group_id 关联
   - measurement_scope 默认 unknown，不自动认定裸件/包装
   - 不依赖真实 OCR，用合成文本测试

## 审查重点

- session.json 原子写入是否真正用 os.replace（避免半截 JSON）
- 路径穿越是否被多层防护（session_id 校验 + resolve 校验 + 清理时跳过符号链接）
- 源文件是否只复制不移动不删除
- cleanup 是否只删 root 直属目录、不跟随符号链接、不删 root 外路径
- 测试是否全程用 tmp_path 不写真实 LOCALAPPDATA
- 是否误改了 S1 文件或现有测试（应为否）
- 是否引入 PaddleOCR/OpenCV/联网（应为否）
