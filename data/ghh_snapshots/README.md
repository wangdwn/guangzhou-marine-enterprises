# 广海汇公开快照目录

本目录用于离线回填。云主机出口访问 `ghh.gzlpc.gov.cn` 常被空响应断开时，请在可访问网络的本机执行：

```bash
curl -sS -X POST 'https://ghh.gzlpc.gov.cn/hyjj_backend/listEnterprise' \
  -H 'Content-Type: application/json' \
  -d '{"pageNum":1,"pageSize":100}' -o listEnterprise_p1.json
```

将分页结果合并为 `{"total":N,"list":[...]}` 后：

```bash
python3 scripts/backfill_from_ghh.py --from-snapshot data/ghh_snapshots/your_dump.json
```

`selftest_from_local.json` 仅用于匹配器自测，不是广海汇实时拉取。
