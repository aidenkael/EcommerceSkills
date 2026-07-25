# 物流头程核算工具（可直接交给 Agent）

这是一个已经整理成项目根目录的物流核算工具，内置你上传表格中的 **79 条历史校准记录和 79 张商品图片**。

## 当前计费规则
- 深圳货代：`80 元/kg + 10 元固定服务费`
- 义乌货代：`100 元/kg + 6 元固定服务费`
- 体积重：`长 × 宽 × 高(cm) ÷ 8000`
- 计费重：实重与体积重取较高值

旧的“包类/非包类不同单价”已经停用，只保留为历史相似商品标签。

## 最省事的用法：直接交给 Agent
1. 把商品图片放进 `input_images/`。
2. 在 Codex、WorkBuddy 或其他能看图和运行代码的 Agent 中打开本目录。
3. 对 Agent 说：

> 读取 AGENTS.md，分析 input_images 中的图片并完成物流核算。

Agent 会看图并调用代码，结果输出到：
- `output/estimates.csv`
- `output/estimates.jsonl`

这种模式不需要额外视觉 API，因为 Agent 本身负责看图。

## 一键检查
Windows 双击：`开始使用.bat`

它会创建 Python 虚拟环境、安装 Pillow、运行自检，并检查 `input_images/`。若没有配置视觉 API，会自动生成 Agent 分析模板，而不是报废项目。

## 脱离 Agent 独立识图
复制 `.env.example` 为 `.env`，二选一配置：
- OpenAI 兼容视觉接口
- 本地 Ollama 视觉模型

然后运行：

```bash
python run.py estimate-images --input input_images --provider auto
```

## 为什么结果包含区间
历史数据中存在同一商品不同批次实际运费不同的情况。工具不会把单条实际费用当成绝对真值，而是：
1. 用图片和文字找相似校准记录；
2. 修正视觉估重偏差；
3. 按当前两家货代规则重新计算；
4. 输出建议值、上下区间和需复核原因。

## 真实反馈越用越准
```bash
python run.py add-feedback --image input_images/商品.png --actual-cost 12 --estimated-cost 10.5 --actual-weight 0.09 --dimensions 12,8,3 --product-name "商品名"
```

反馈会追加到 `data/feedback.jsonl`，不会破坏原始校准库。

## API 预留
启动本地 API：

```bash
python run.py serve --port 8765
```

接口：
- `GET /health`
- `POST /v1/estimate`：传入结构化商品分析
- `POST /v1/estimate-image`：使用已配置的视觉接口分析本地图片
- `POST /v1/feedback`：追加真实反馈

详见 `docs/API说明.md`。

## 重要说明
纯代码无法在没有视觉模型的情况下“凭空看懂图片”。本项目已经解决的是：项目结构、校准数据、图片匹配、重量/体积重、两家货代计价、区间与复核、反馈积累、CLI 和 API。直接交给能看图的 Agent 时即可使用；脱离 Agent 时需要配置视觉 API 或本地视觉模型。
