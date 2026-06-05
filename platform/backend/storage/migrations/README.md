# migrations —— 建表 / 改表 SQL

三张共享表：统一事件表（含全部三圈字段，metadata=JSONB，在 tool_id/conversation_id/start_time/status 建索引）、工具注册表、用户账号表（密码只存哈希）。不预建价格表。

## 怎么应用（迁移执行器）

按 `NNNN_描述.sql` 编号命名，编号决定执行顺序（`0001_init.sql`、`0002_*.sql`…）。统一由**迁移执行器**幂等应用，不要手工逐条跑：

```
python tools/migrate.py            # 用环境变量 DATABASE_URL
python tools/migrate.py --database-url <url> --migrations-dir <dir>
```

执行器会建一张 `schema_migrations` 跟踪表记「哪些办过了」，每次只跑没办过的，已办的跳过（幂等）。每张迁移连同它的登记在**同一个事务**里——要么整张生效并记账，要么整张回滚，不会半生效。新机器/升级都跑这一条即可。

## 已有旧库要先「基线」

若某个库的表是**早先用别的方式建的**（如下面 docker `initdb` 首次挂载、或手工建过），表已存在，直接跑 `0001` 会因重复/属主问题报错。对这种库**先基线一次**——把已存在对应的迁移编号标记为「已办」而不真跑：

```sql
INSERT INTO schema_migrations (version, name) VALUES (1, '0001_init');
```

之后再 `python tools/migrate.py`，它就只会应用 `0002` 及以后的新迁移。**全新空库不需要这步。**

## 与 docker 的关系

`docker-compose.yml` 仍把本目录挂到 Postgres 的 `/docker-entrypoint-initdb.d`，让**全新容器首次启动**时建好表。但 `initdb` 只在首次空库生效，**之后的 `0002+` 不会自动应用**——升级一律走上面的执行器。
