# 数据模型

```
Room 房间
 └── Container 容器（parent_id 自关联，支持无限层级）
      └── Item 物品 ── Category 大类（1 个）
                   ├── Tag 标签（N 个，多对多）
                   └── Photo 照片（N 张，含 AI 识图结果）

Admin        唯一管理员（密码哈希）
AiMessage    AI 会话历史
OperationLog 操作审计日志
```

删除策略：
- 房间 / 容器下仍有子容器或物品时，服务层会拒绝删除（HTTP 409），避免误删。
- 删除分类时，物品的 `category_id` 置空。
- 删除物品时，级联删除照片记录，并清理磁盘文件。
