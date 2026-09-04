# 广州涉海企业名录 · 数据说明

本仓库是海洋系列 **A 家底盘** 的企业登记数据。看板页面：<https://wangdwn.github.io/guangzhou-marine-enterprises/>

## 存储位置

| 文件 | 作用 |
| --- | --- |
| `data/enterprises.json` | 主库：`meta` + `enterprises[]`（schema 1.3） |
| `data/taxonomy.json` | GB/T 20794-2021 大类口径（项目用 28 类） |
| `data/index_constituents.json` | 中证海洋经济指数 932056 **精简样本**（非完整 211 只） |
| `data/facilities.json` | 深水试验设施台账 |
| `data/nodes.json` | 节点发现（政府采购中标） |
| `data/verified_listings.json` | 本次公开核验的 A 股代码/信用代码叠加层 |
| `data/content_refresh_changelog.json` | 最近一次内容刷新计数 |
| `data.json` | **旧** 672 家官方清单快照（2026-07），看板不再读取 |
| `activity.json` | 情报采集日志，不是企业名录 |

企业记录为 JSON 对象，不使用 CSV 作为主存储；页面可导出 CSV。

## 记录字段（schema 1.3）

**身份**

- `id`, `name`, `credit_code`, `credit_code_source`
- `district`, `registered_address`, `founded_at`, `legal_rep`, `registered_capital`
- `sector` / `sector_raw`：广海汇产业标签 / 国民经济行业
- `identity.gbt_code`：两位大类代码；`major_name`；`layer` ∈ core/support/peripheral
- `identity.confidence`：`ghh` 广海汇原值 · `auto` 名称关键词预标 · `verified` 公开资料核对

**身价（不编造财务）**

- `capital.grade`：A=932056 在列 · B=已上市未入指 · C=辅导/股改 · D=专精特新/规上 · E=其他
- `capital.listed`, `ticker`, `in_932056`, `listing_source`
- `revenue`：仅保留底库已有值；空值表示未知，**禁止估算填入**

**身家**

- `facility.needs_deepwater`, `depth_required_m`, `test_types`（多为待访谈预标）

## 数据来源与缺口

1. **底库快照 2026-08-25**：广海汇（ghh.gzlpc.gov.cn）在穗企业去重合并，约 7045 家。平台无公开可下载全量名录，本次**未做大规模抓取**。
2. **内容刷新 2026-09-04**：从已有 `main_biz` 文本抽取统一社会信用代码/成立日期/法人/注册资本/地址；用沪深交易所与巨潮公告核对 36 家 A 股代码；修正错挂 ticker 与 3 条明显错分产业；对名称可判涉海的待打标记录做自动预标（需人工复核）。
3. **仍空的字段**：约 90% 企业无信用代码；几乎全部无营收；5835 家重点企业中多数仍为「待打标」。官方海洋经济活动单位名录核实结果依法不公开。
4. **932056**：完整 211 只成分股未在中证指数官网以可引用结构化文件发布；A 级只覆盖本库样本文件 + 底库已标 `in_932056=true` 的记录。

可重复执行：`python3 scripts/refresh_content.py`

## 海洋系列

页面通过 `https://wangdwn.github.io/design-system/` 加载 `tokens.css` / `nav.css`，顶部为共享「海洋系列」导航（A 家底为当前页）。内容刷新不得拆除该导航或改写设计系统 URL。
