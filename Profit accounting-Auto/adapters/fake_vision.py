"""Fake AI 适配器 — ROAD-1 占位实现

模拟视觉 API 返回结果，不调用任何付费模型。
用于走通界面：AI识图 → 属性回填 → 包装规格估算 → 正常/保守档展示。
"""
import random
import time


class FakeVisionAdapter:
    """Fake 视觉识别适配器。"""

    name = "Fake Vision (ROAD-1)"
    version = "road-1-mock"

    FAKE_PRODUCTS = [
        {
            "product_type": "女士帆布手提包",
            "material": "帆布 + 棉质内衬",
            "structure": "单层无隔层，配短提手",
            "rigidity": "软",
            "foldable": "好",
            "compressible": "好",
            "shape_keep": "否",
            "note": "常规手提袋，可折叠压缩包装",
            "normal": {
                "method": "PE 袋 + 气泡膜",
                "length_cm": 30, "width_cm": 20, "height_cm": 5,
                "weight_g": 250, "note": "折叠后 PE 袋包装，加一层气泡膜保护"
            },
            "conservative": {
                "method": "PE 袋 + 气泡膜 + 纸箱",
                "length_cm": 35, "width_cm": 25, "height_cm": 8,
                "weight_g": 380, "note": "偏保守余量，加小纸箱防挤压变形"
            },
        },
        {
            "product_type": "硅胶手机壳",
            "material": "液体硅胶",
            "structure": "一体成型，四角防摔气囊",
            "rigidity": "中",
            "foldable": "差",
            "compressible": "差",
            "shape_keep": "是",
            "note": "薄型硬质保护壳，不可折叠",
            "normal": {
                "method": "气泡膜包裹 + 纸板",
                "length_cm": 18, "width_cm": 10, "height_cm": 1.5,
                "weight_g": 35, "note": "薄型，气泡膜+纸板平包装"
            },
            "conservative": {
                "method": "气泡膜 + 小纸箱",
                "length_cm": 22, "width_cm": 14, "height_cm": 4,
                "weight_g": 80, "note": "加小纸箱防止运输压碎"
            },
        },
        {
            "product_type": "女士瑜伽裤",
            "material": "尼龙 + 氨纶",
            "structure": "高腰收腹设计，四针六线",
            "rigidity": "软",
            "foldable": "好",
            "compressible": "好",
            "shape_keep": "否",
            "note": "柔软弹性面料，可折叠压缩",
            "normal": {
                "method": "OPP 自封袋",
                "length_cm": 25, "width_cm": 18, "height_cm": 3,
                "weight_g": 200, "note": "折叠后入 OPP 袋"
            },
            "conservative": {
                "method": "OPP 袋 + 气泡信封",
                "length_cm": 32, "width_cm": 24, "height_cm": 4,
                "weight_g": 260, "note": "加气泡信封防潮防脏"
            },
        },
    ]

    @classmethod
    def recognize(cls, image_paths, product_info=None):
        """模拟视觉识别，返回结构化结果。

        Args:
            image_paths: 图片路径列表（fake 模式不使用）
            product_info: 可选手动输入的额外商品信息

        Returns:
            dict: 包含 product_type, material, structure, rigidity,
                  foldable, compressible, shape_keep, note,
                  normal (包装方案), conservative (包装方案)
        """
        # 模拟 API 调用延迟
        time.sleep(0.3)
        # 随机选择一款假商品
        product = random.choice(cls.FAKE_PRODUCTS)
        return dict(product)

    @classmethod
    def reestimate_packaging(cls, product_attributes):
        """基于商品属性重新估算包装规格（不重新调视觉 API）。

        Args:
            product_attributes: dict 包含 rigidity, foldable, compressible, shape_keep

        Returns:
            dict: 更新后的 normal 和 conservative 包装方案
        """
        time.sleep(0.15)
        # 根据材质软硬简单模拟不同包装
        is_soft = product_attributes.get("rigidity") == "软"
        is_hard = product_attributes.get("rigidity") == "硬"
        fold_bonus = 0 if product_attributes.get("foldable") == "好" else 5 if product_attributes.get("foldable") == "一般" else 10

        if is_soft:
            normal_dims = [25 + fold_bonus, 18 + fold_bonus, 3 + fold_bonus // 2]
            conservative_dims = [32 + fold_bonus, 24 + fold_bonus, 5 + fold_bonus // 2]
            normal_weight = 180 + fold_bonus * 10
            conservative_weight = 250 + fold_bonus * 15
            normal_method = "OPP / PE 袋"
            conservative_method = "OPP 袋 + 气泡信封"
        elif is_hard:
            normal_dims = [22, 15, 8]
            conservative_dims = [28, 20, 12]
            normal_weight = 350
            conservative_weight = 500
            normal_method = "珍珠棉 + 纸板"
            conservative_method = "珍珠棉 + 纸箱"
        else:
            normal_dims = [22, 15, 4]
            conservative_dims = [28, 20, 7]
            normal_weight = 200
            conservative_weight = 300
            normal_method = "气泡膜"
            conservative_method = "气泡膜 + 纸板"

        return {
            "normal": {
                "method": normal_method,
                "length_cm": normal_dims[0], "width_cm": normal_dims[1], "height_cm": normal_dims[2],
                "weight_g": normal_weight,
                "note": f"基于当前属性估算（{product_attributes.get('rigidity', '未知')}质/折叠{product_attributes.get('foldable', '未知')}）"
            },
            "conservative": {
                "method": conservative_method,
                "length_cm": conservative_dims[0], "width_cm": conservative_dims[1], "height_cm": conservative_dims[2],
                "weight_g": conservative_weight,
                "note": f"偏保守余量（{product_attributes.get('rigidity', '未知')}质/折叠{product_attributes.get('foldable', '未知')}）"
            },
        }
