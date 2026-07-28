"""OCR 引擎层（可替换）。

字段提取器和 UI 不直接依赖具体引擎，只依赖 base_engine.BaseOcrEngine 接口。
未来换 RapidOCR/本地模型时只新增引擎实现，不改 extractors 和利润计算。
"""
