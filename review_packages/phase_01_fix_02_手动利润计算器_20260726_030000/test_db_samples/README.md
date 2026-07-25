# test_db_samples/ 说明

## old_defaults_36_0.db

这是模拟 v0.1 旧版本的数据库文件，用于测试配置迁移。

### 特征
- **无 schema_version 表**（旧版没有迁移机制）
- **产品快照表无规则列**（无 exchange_rate, head_haul_rate, fixed_service_fee, rule_version）
- **旧默认配置**：fixed_service_fee=36.0, default_tail_haul=0.0
- **无 _config_migrated_v1 标记**

### 包含数据
- 2 条商品记录：一条完整、一条包装数据为空

### 迁移测试方法

```bash
# 1. 复制此 DB 到项目 data 目录
cp test_db_samples/old_defaults_36_0.db ../Profit accounting-Auto/data/profit_accounting.db

# 2. 启动应用（自动触发迁移）
cd ../Profit accounting-Auto
python app.py

# 3. 验证迁移结果
python -c "
from database.db_manager import DatabaseManager
db = DatabaseManager()
print('Schema version:', db.get_schema_version())  # 应为 1
print('Fixed fee:', db.get_config('fixed_service_fee'))  # 应为 6.0
print('Tail haul:', db.get_config('default_tail_haul'))  # 应为 40.0
print('Products:', len(db.list_all_products()))  # 应为 2
"
```

### 预期迁移行为
1. schema_version 表被创建，版本设为 1
2. 快照表自动补列（exchange_rate, head_haul_rate, fixed_service_fee, rule_version）
3. config 表 fixed_service_fee 36.0→6.0, default_tail_haul 0.0→40.0
4. 旧商品数据完整保留
5. _config_migrated_v1 标记设为 1，不会重复迁移
