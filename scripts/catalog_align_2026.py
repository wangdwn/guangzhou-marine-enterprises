# -*- coding: utf-8 -*-
"""按《海洋产业投融资指导目录（2026版）》对齐企业库分类。

优先级：GB/T 大类直映 > 广海汇产业标签 > 名称/主营关键词预标 > 未归口。
关键词预标标 level=auto，全部写入复核 CSV；不改动 sector / chain / identity 原值，不编造财务。
"""
import json, os, csv, re, shutil, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
CAT_PATH = os.path.join(DATA, 'catalog2026.json')

CATALOG = {
    "standard": "海洋产业投融资指导目录（2026版）",
    "issuer": "自然资源部、国家发展改革委、中国人民银行、金融监管总局、中国证监会",
    "issued_at": "2026-10-19",
    "published_at": "2026-11-20",
    "source_url": "http://app.m.mnr.gov.cn/gk/tzgg/202611/t20261120_2942962.html",
    "source_pdf": "P020261120484342055192.pdf",
    "basis": "《产业结构调整指导目录（2024年本）》及国家产业政策、海洋开发利用保护政策",
    "categories": [
        {"code": "01", "name": "海洋渔业与海洋水产品加工"},
        {"code": "02", "name": "海洋油气"},
        {"code": "03", "name": "海洋工程建筑"},
        {"code": "04", "name": "海洋船舶与海洋工程装备"},
        {"code": "05", "name": "海洋电力"},
        {"code": "06", "name": "海洋药物和生物制品"},
        {"code": "07", "name": "海水淡化与综合利用"},
        {"code": "08", "name": "涉海材料制造"},
        {"code": "09", "name": "海洋交通运输"},
        {"code": "10", "name": "海洋文化和旅游"},
        {"code": "11", "name": "海洋公共管理服务"},
    ],
    "gbt_mapping": {
        "01": {"catalog": "01", "level": "direct", "note": ""},
        "02": {"catalog": "01", "level": "direct", "note": ""},
        "03": {"catalog": "02", "level": "direct", "note": ""},
        "04": {"catalog": "", "level": "unlisted", "note": "目录未单列海洋矿产开采；采矿装备归04，勘察服务归11"},
        "05": {"catalog": "07", "level": "proxy", "note": "按海水综合利用归口"},
        "06": {"catalog": "08", "level": "proxy", "note": "海洋化工按涉海材料制造归口"},
        "07": {"catalog": "06", "level": "direct", "note": ""},
        "08": {"catalog": "05", "level": "direct", "note": ""},
        "09": {"catalog": "07", "level": "direct", "note": ""},
        "10": {"catalog": "04", "level": "direct", "note": ""},
        "11": {"catalog": "04", "level": "direct", "note": ""},
        "12": {"catalog": "08", "level": "proxy", "note": "历史重复项，按涉海材料制造归口"},
        "13": {"catalog": "03", "level": "direct", "note": ""},
        "14": {"catalog": "09", "level": "direct", "note": ""},
        "15": {"catalog": "10", "level": "direct", "note": ""},
        "16": {"catalog": "11", "level": "proxy", "note": "科研服务按公共管理服务归口"},
        "17": {"catalog": "11", "level": "proxy", "note": "海洋教育按公共管理服务归口"},
        "18": {"catalog": "11", "level": "direct", "note": ""},
        "19": {"catalog": "11", "level": "direct", "note": ""},
        "20": {"catalog": "11", "level": "direct", "note": ""},
        "21": {"catalog": "11", "level": "proxy", "note": "按工程勘察设计等服务归口"},
        "22": {"catalog": "11", "level": "direct", "note": ""},
        "23": {"catalog": "04", "level": "proxy", "note": "涉海设备按海洋装备归口"},
        "24": {"catalog": "08", "level": "direct", "note": ""},
        "25": {"catalog": "01", "level": "proxy", "note": "按水产品加工归口"},
        "26": {"catalog": "11", "level": "proxy", "note": "涉海经营服务按公共管理服务归口"},
        "27": {"catalog": "", "level": "unlisted", "note": "目录未单列海洋产品批发零售"},
        "28": {"catalog": "11", "level": "proxy", "note": "社会组织按公共管理服务归口"},
    },
    "sector_mapping": {
        "海洋交通运输业": "09", "海洋生物医药业": "06", "海洋工程装备制造业": "04",
        "海洋旅游业": "10", "海洋电力业": "05", "海洋船舶工业": "04",
        "海洋工程建筑业": "03", "海洋渔业": "01",
    },
    # 顺序即优先级：先具体后泛化
    "keyword_rules": [
        {"code": "07", "re": r"海水淡化|苦咸水淡化|海水综合利用|海水直接利用"},
        {"code": "06", "re": r"海洋生物医药|海洋药物|海洋生物制品|海洋生物技术|甲壳素|鱼油|海藻多糖|海洋中药"},
        {"code": "05", "re": r"海上风电|海洋能|潮流能|波浪能|潮汐能|温差能|海上光伏|海洋电力"},
        {"code": "04", "re": r"港口机械|造船|船厂|修船|船舶制造|船舶修理|船舶改装|船舶设计|船用设备|船用机电|锚链|螺旋桨|海工装备|海洋工程装备|钻井平台|海洋平台|船舶配套|无人船|水下机器人"},
        {"code": "02", "re": r"海洋油气|海洋石油|海洋天然气|LNG|FPSO|FLNG|油气开采|油气勘探|钻井服务"},
        {"code": "08", "re": r"海洋新材料|海工材料|防腐材料|海洋生物材料|膜材料|钛合金|海洋化工"},
        {"code": "03", "re": r"航道工程|疏浚|吹填|围海|海洋工程建筑|防波堤|码头建设|港口建设|海上施工"},
        {"code": "01", "re": r"远洋捕捞|海洋捕捞|海水养殖|海洋渔业|渔港|海洋牧场|水产种苗|水产品加工|水产加工|渔业"},
        {"code": "09", "re": r"港口|码头|航运|海运|远洋运输|船务代理|船舶代理|无船承运|船舶管理|拖轮|轮驳|集装箱运输|物流"},
        {"code": "10", "re": r"邮轮|游艇|滨海旅游|海上旅游|海岛旅游|海洋文旅|海洋公园|潜水"},
        {"code": "11", "re": r"海洋监测|海洋测绘|海洋预报|海洋环评|海事检验|检测认证|勘察设计|海洋信息|海洋大数据|海洋碳汇|生态修复|海洋科研|海洋研究|海洋大学|海事大学|海洋协会|海洋学会"},
    ],
    "sector_raw_mapping": {
        "交通运输、仓储和邮政业": "09",
        "科学研究和技术服务业": "11",
        "信息传输、软件和信息技术服务业": "11",
        "水利、环境和公共设施管理业": "11",
        "电力、热力、燃气及水生产和供应业": "05",
        "农、林、牧、渔业": "01",
        "建筑业": "03",
        "文化、体育和娱乐业": "10",
    },
    "sector_raw_note": "国民经济行业门类只作粗归口；制造业、住宿餐饮、批发零售、租赁商务等门类跨度过大，不硬挂目录。",
    "unlisted_note": "目录未单列海洋矿产开采、海洋产品批发零售等；企业层保留 unlisted，不硬挂门类。",
}

def main():
    json.dump(CATALOG, open(CAT_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    names = {c['code']: c['name'] for c in CATALOG['categories']}
    rules = [(r['code'], re.compile(r['re'])) for r in CATALOG['keyword_rules']]

    ep = os.path.join(DATA, 'enterprises.json')
    d = json.load(open(ep, encoding='utf-8'))
    es = d['enterprises']

    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bak = os.path.join(DATA, 'backups', f'enterprises-pre-catalog2026-{stamp}.json')
    shutil.copy2(ep, bak)

    stats, by_source, unlisted_breakdown, review = {}, {'gbt': 0, 'sector': 0, 'sector_raw': 0, 'keyword': 0, 'none': 0}, {}, []
    for e in es:
        ident = e.get('identity') or {}
        code = str(ident.get('gbt_code') or '').strip()
        entry, source, hit = CATALOG['gbt_mapping'].get(code), 'gbt', ''

        if not entry:
            c = CATALOG['sector_mapping'].get((e.get('sector') or '').strip())
            if c:
                entry, source = {"catalog": c, "level": "proxy", "note": "按广海汇产业标签归口"}, 'sector'

        if not entry:
            sr = (e.get('sector_raw') or '').strip()
            c2 = CATALOG['sector_raw_mapping'].get(sr)
            if c2:
                entry, source = {"catalog": c2, "level": "proxy", "note": "按国民经济行业门类粗归口，待细分"}, 'sector_raw'

        if not entry:
            text = (e.get('name') or '') + ' ' + (e.get('main_biz') or '')
            for ccode, rx in rules:
                m = rx.search(text)
                if m:
                    entry = {"catalog": ccode, "level": "auto", "note": "名称/主营关键词预标，待复核"}
                    source, hit = 'keyword', m.group(0)
                    break

        if not entry:
            entry, source = {"catalog": "", "level": "unlisted", "note": "无可用分类依据"}, 'none'

        cc = entry['catalog']
        e['catalog'] = {"code": cc, "name": names.get(cc, "未归口"), "level": entry['level'],
                        "by": source, "note": entry.get('note', ''), "match": hit}
        by_source[source] += 1
        k = cc or 'unlisted'
        stats[k] = stats.get(k, 0) + 1
        if not cc:
            mn = ident.get('major_name') or '未分类'
            unlisted_breakdown[mn] = unlisted_breakdown.get(mn, 0) + 1
        if source == 'keyword':
            review.append([e.get('id', ''), e.get('name', ''), cc, names.get(cc, ''), hit])

    meta = d['meta']
    meta['schema'] = '1.4'
    meta['catalog_aligned_at'] = datetime.datetime.now().strftime('%Y-%m-%d')
    meta['catalog_standard'] = CATALOG['standard']
    meta['catalog_source_url'] = CATALOG['source_url']
    meta['catalog_distribution'] = stats
    meta['catalog_coverage'] = round((len(es) - stats.get('unlisted', 0)) / len(es) * 100, 1)
    meta['catalog_align_note'] = ('按五部门《海洋产业投融资指导目录（2026版）》十一门类对齐：'
                                  'direct 直接对应／proxy 按业务实质归口／auto 关键词预标待复核／unlisted 目录未单列。'
                                  '未改动原 sector、chain、identity 字段，未编造财务数据。')
    json.dump(d, open(ep, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    csv_path = os.path.join(DATA, 'reports', 'catalog_align_2026_review.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(['id', 'name', 'catalog_code', 'catalog_name', 'matched_keyword']); w.writerows(review)

    report = {
        "generated_at": datetime.datetime.now().isoformat(timespec='seconds'),
        "backup": os.path.relpath(bak, ROOT),
        "total": len(es),
        "distribution": dict(sorted(stats.items(), key=lambda x: (-x[1], x[0]))),
        "by_source": by_source,
        "coverage_pct": meta['catalog_coverage'],
        "unlisted_breakdown": dict(sorted(unlisted_breakdown.items(), key=lambda x: -x[1])),
        "review_csv": os.path.relpath(csv_path, ROOT),
        "review_rows": len(review),
    }
    json.dump(report, open(os.path.join(DATA, 'reports', 'catalog_align_2026.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
