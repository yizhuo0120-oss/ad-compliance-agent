# 审核报告 Schema 定稿 · v1.0

> 卡1 产出 ｜ 定稿日期：2026-09-19 ｜ 状态：**已定稿**
> 机器可校验版本：`engine/report_schema.json`（JSON Schema draft 2020-12，D6 起供 pipeline 输出自检、D8 供评测脚本校验）

## 一、定稿变更记录（相对《第一期计划手册.md》第二节草案）

| # | 变更 | 理由 |
|---|---|---|
| 1 | `transcript` 从字符串升级为结构化对象：`{ texts[], visual_elements[] }` | 转写文字逐条列出，D7 时可逐条送文案通道并逐条回填判定；画面元素单独列出供视觉判定引用 |
| 2 | `meta` 增补为：`schema_version / model / latency_ms / timestamp / cost_cny` | D8 评测要按模型与耗时分组统计；成本数据为简历素材预留（允许 null） |
| 3 | 其余字段（`input_type / risk_level / findings[] / summary`）与草案一致 | 评审通过，无增删 |

## 二、字段定义

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `input_type` | string | 是 | `text`（海报文案）｜ `image`（海报图片） |
| `transcript` | object/null | 图片版必填 | `texts[]`：画面文字逐字转写；`visual_elements[]`：画面元素描述（人物/产品/场景/标识）。文本版为 `null` |
| `risk_level` | string | 是 | `violation`（违规）｜ `suspicious`（疑似，转人工）｜ `compliant`（合规） |
| `findings[]` | array | 是 | 命中明细，可为空数组（合规时） |
| `findings[].type` | string | 是 | 八类之一：`极限词 / 虚假误导 / 医疗功效 / 保健食品 / 肖像权 / 名誉权 / 隐私 / 低俗` |
| `findings[].fragment` | string | 是 | 命中的原文或画面片段 |
| `findings[].law` | object | 是 | `name`（法名）+ `article`（条号）+ `quote`（条文原文），可溯源 |
| `findings[].reason` | string | 是 | 判定理由 |
| `findings[].suggestion` | string | 是 | 改写建议 |
| `findings[].source` | string | 是 | 产出通道：`keyword`（关键词层）｜ `rag`（语义层/法条检索）｜ `visual`（视觉判定） |
| `summary` | string | 是 | 一句话总结 |
| `meta` | object | 是 | `schema_version="1.0"`、`model`、`latency_ms`、`timestamp`（ISO 8601）、`cost_cny`（可 null） |

**三级判定口径**（评测标注与引擎输出共用）：`violation` = 明确命中法条禁止情形；`suspicious` = 语义接近但需人工确认（边缘表达一律归此级，宁可多进人工）；`compliant` = 关键词层与语义层均无发现。

## 三、示例一：文本输入

```json
{
  "input_type": "text",
  "transcript": null,
  "risk_level": "violation",
  "findings": [
    {
      "type": "极限词",
      "fragment": "全网最低价，行业第一品牌",
      "law": { "name": "广告法", "article": "第九条", "quote": "广告不得使用「国家级」「最高级」「最佳」等用语" },
      "reason": "「最低」「第一」属于绝对化用语",
      "suggestion": "改为「高性价比之选」「深耕行业多年」",
      "source": "keyword"
    }
  ],
  "summary": "检出 1 处极限词违规，建议改写后复检",
  "meta": { "schema_version": "1.0", "model": "deepseek-chat", "latency_ms": 2300, "timestamp": "2026-09-21T10:00:00+08:00", "cost_cny": 0.002 }
}
```

## 四、示例二：图片输入

```json
{
  "input_type": "image",
  "transcript": {
    "texts": ["全场最低价", "买一送一", "*活动最终解释权归本店所有"],
    "visual_elements": ["一名女性模特手持产品", "红底黄字促销标签"]
  },
  "risk_level": "violation",
  "findings": [
    {
      "type": "极限词",
      "fragment": "全场最低价",
      "law": { "name": "广告法", "article": "第九条", "quote": "广告不得使用「国家级」「最高级」「最佳」等用语" },
      "reason": "「最低价」属于绝对化用语（来自画面转写）",
      "suggestion": "改为「全场特惠」",
      "source": "rag"
    }
  ],
  "summary": "画面文字检出 1 处极限词，转写完整率详见 meta",
  "meta": { "schema_version": "1.0", "model": "qwen-vl-max + deepseek-chat", "latency_ms": 5100, "timestamp": "2026-09-21T10:05:00+08:00", "cost_cny": 0.012 }
}
```

## 五、验收关联

- D6 产出报告须通过 `engine/report_schema.json` 校验后才算跑通
- D8 评测脚本以本 schema 解析报告，统计四指标
- 字段再变更须升 `schema_version` 并回写本文件变更记录
