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

## 投融资目录对齐（2026-11-21）

依据：自然资源部、国家发展改革委、中国人民银行、金融监管总局、中国证监会《海洋产业投融资指导目录（2026版）》（2026-10-19 印发，2026-11-20 公开）。
原文：<http://app.m.mnr.gov.cn/gk/tzgg/202611/t20261120_2942962.html>；本地结构化口径见 data/catalog2026.json。

企业记录新增 catalog 字段：

- catalog.code：目录门类代码 01–11；空值表示未归口
- catalog.name：门类名称
- catalog.level：direct 直接对应 ／ proxy 按业务实质归口 ／ auto 关键词预标待复核 ／ unlisted 目录未单列
- catalog.by：判定依据（gbt ／ sector ／ sector_raw ／ keyword ／ none）
- catalog.match：命中的关键词（仅 auto）
- catalog.note：归口说明

当前分布（覆盖 42.3%）：

| 代码 | 门类 | 企业数 |
| --- | --- | --- |
| unlisted | 未归口 | 4062 |
| 09 | 海洋交通运输 | 980 |
| 11 | 海洋公共管理服务 | 812 |
| 06 | 海洋药物和生物制品 | 416 |
| 04 | 海洋船舶与海洋工程装备 | 261 |
| 10 | 海洋文化和旅游 | 219 |
| 03 | 海洋工程建筑 | 193 |
| 05 | 海洋电力 | 64 |
| 01 | 海洋渔业与海洋水产品加工 | 23 |
| 08 | 涉海材料制造 | 15 |

映射规则与未归口说明写在 data/catalog2026.json；关键词预标复核清单见 data/reports/catalog_align_2026_review.csv，统计报告见 data/reports/catalog_align_2026.json。

重跑：python3 scripts/catalog_align_2026.py

约束：只做分类映射，不改动 sector、chain、identity 原值，不编造营收与财务；未归口记录不硬挂门类。

## 数据来源与缺口

1. **底库快照 2026-08-25**：广海汇（ghh.gzlpc.gov.cn）在穗企业去重合并，约 7045 家。平台无公开可下载全量名录；公开接口 `POST /hyjj_backend/listEnterprise` 可作回填源（见下）。
2. **内容刷新 2026-09-04**：从已有 `main_biz` 文本抽取统一社会信用代码/成立日期/法人/注册资本/地址；用沪深交易所与巨潮公告核对 36 家 A 股代码；修正错挂 ticker 与 3 条明显错分产业；对名称可判涉海的待打标记录做自动预标（需人工复核）。
3. **W1 回填/打标 2026-09-19**：
   - `scripts/backfill_from_ghh.py`：按企业名/信用代码匹配回填 `credit_code`、坐标、`main_biz`、chain；报告见 `data/reports/backfill_ghh_*.json`。接口截至日以报告 `generated_at` 为准；云出口不可达时用 `data/ghh_snapshots/` 离线快照。
   - `scripts/tag_sector_rules_v1.py`：名称+主营关键词 → 国标大类预标（规则版本 `tag_sector_rules_v1`）；低置信度复核清单 `data/reports/tag_sector_rules_v1_review.csv`。
4. **仍空的字段**：约 90% 企业无信用代码；几乎全部无营收；「待打标」仍占多数（以 `meta.sector_pending_count` 为准）。官方海洋经济活动单位名录核实结果依法不公开。**禁止编造营收/财务/未核坐标。**
5. **932056**：完整 211 只成分股未在中证指数官网以可引用结构化文件发布；A 级只覆盖本库样本文件 + 底库已标 `in_932056=true` 的记录。

可重复执行：

```bash
python3 scripts/refresh_content.py
python3 scripts/backfill_from_ghh.py            # 或 --from-snapshot ...
python3 scripts/tag_sector_rules_v1.py
python3 scripts/drift_check_ghh.py              # W4：与广海汇 total 对账
```

## 海洋系列

页面通过 `https://wangdwn.github.io/design-system/` 加载 `tokens.css` / `nav.css`，顶部为共享「海洋系列」导航（A 家底为当前页）。内容刷新不得拆除该导航或改写设计系统 URL。

## 更新机制（2026-11-26 修订）

改动起因：原 `scraper.py` 用 `merged[:5000]` 硬截断，新情报挤掉旧情报（11 月一次提交是 +182/−336 行，净减）；同时 360/博查 回来的大量是企业信息聚合站与招聘站的页面标题，不构成情报。

现行规则：

| 环节 | 规则 | 实现 |
| --- | --- | --- |
| 采集节奏 | 由每日一次改为每月 1、15 日（北京时间 09:00）；可 `workflow_dispatch` 手动跑全量或单企业 | `.github/workflows/update.yml` |
| 保留策略 | 噪音剔除（爱企查/水滴信用/天眼查/BOSS直聘/就业信息网等 + "XX-招标信息"空壳标题 + 搜索来源的招聘类）→ 近 18 个月 → content 去重 → 硬顶 5000 仅兜底 | `scripts/prune_activity.py` |
| 派生数据 | `data/updates.json`（更新日志，取自 git 历史）、`data/catalog_stats.json`（归口统计，20KB，供页面秒开） | `scripts/build_updates.py`、`scripts/build_catalog_stats.py` |
| 页面可见性 | 首页顶部「最近更新」显示最近 5 次提交；`catalog.html` 显示全部门类分布、代表企业、未归口构成与 20 条日志 | `index.html`、`catalog.html` |

手工执行：

```bash
python3 scripts/prune_activity.py            # 干跑看统计
python3 scripts/prune_activity.py --apply    # 写回 activity.json
python3 scripts/build_updates.py             # 重算更新日志
python3 scripts/build_catalog_stats.py       # 重算归口统计
```

口径说明：2026-11-26 清理后 activity.json 由 5000 条降至 1880 条（剔除噪音 2871、重复 249），来源以 360 搜索为主，属"线索级"情报，引用前须回查原始公告。
