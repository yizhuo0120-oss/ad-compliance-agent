# ad-compliance-agent · 海报合规审核 Agent

广告宣传 Agent 项目第一期：**粘贴海报文案 或 上传海报图片 → 输出带法条引用的合规审核报告**。

法律语料：《广告法》全文 +《民法典》人格权编/侵权责任编，按条切块建 RAG 知识库，审核判定引用到具体条号。

## 目录结构

```
engine/            审核引擎
  keyword_layer.py    关键词层：违禁词/正则 + 变体归一化（D5）
  rag_layer.py        语义层：法条检索 + LLM 判断（D6）
  image_channel.py    图片通道：VL 转写 + 视觉合规判定（D7）
  pipeline.py         双通道合并出报告（D7）
  report_schema.json  审核报告 JSON Schema（定稿 v1.0）
data/
  laws/               法律语料（法名/条号/条文/适用场景备注，D2 下午）
  banned_words.txt    违禁词库（D3）
  eval_cases.jsonl    文案评测集 30~50 条，带标注（D3）
  eval_images/        海报评测图 15~20 张 + 标注（D4）
eval/run_eval.py    评估脚本：一条命令跑分（D8）
app/app.py          Streamlit 双入口 Demo（D10）
tests/              单测
docs/report_schema.md   报告 schema 定稿文档（卡1 产出）
```

## 排期与进度

总排期见《第一期计划手册.md》（上一级目录）。当前进度：

- [x] 卡1 立项定界：报告 schema 定稿 v1.0（docs/report_schema.md）
- [x] 卡2 环境与模型跑通：deepseek-flash 文本+视觉双链路 ✅（海报 6 行文字全部转写成功）
- [x] 卡3 法律语料 + 双形态标注评测集 ✅
  - 法律语料：广告法 74 条 + 民法典人格权/侵权责任两编 145 条（`eval/build_laws.py`）
  - 违禁词库 206 词；文案评测集 40 条（16 违规 / 8 疑似 / 16 合规）
  - 海报评测集 22 张（17 采集 + 5 合成违规），标注 `data/eval_images/annotations.jsonl`
- [x] 卡4 双通道审核引擎 ✅
  - `keyword_layer.py`（归一化+语境白名单）/ `rag_layer.py`（混合检索+LLM判断+标签归一）/ `image_channel.py`（VL转写+视觉判定）/ `pipeline.py`（合并+schema校验），单测 5/5
- [x] 卡5 评估出数据 ✅（D8 全指标 + D9 调优达标）
  - 最终指标（`eval/run_eval.py`，判分口径见文件头）：

    | 指标 | 文案·有RAG | 文案·无RAG | 图片侧 |
    |---|---|---|---|
    | 违规拦截率 | 100% (16/16) | 100% | 100% (5/5) |
    | 合规误报率 | **0%** (0/16) | 12.5% | **0%** (0/12) |
    | 法条引用准确率 | 76.92% | 45.65% | 80.0% |
    | 向量检索命中率 | 41.67% | — | — |
    | 转写完整率（合成真值） | — | — | 100% (23/23) |

  - 消融结论：撤掉 RAG 后误报 0%→12.5%、引用准确率 76.92%→45.65% 且无法溯源——法条知识库真实有效
  - 混合检索必要性：纯向量命中率仅 41.67%，关键词层「预期法条」并入候选是拦截率的关键
  - D9 调优三件套：视觉判定 prompt 收紧（模特出镜/正常促销不构成违规）、判断指引补常见合法表达、关键词语境白名单（第一人称/第一波）
- [x] 卡6 Streamlit Demo ✅（`app/app.py`）
  - 双入口：文案粘贴 / 海报图上传（含内置示例）；模式切换：双层 vs 仅关键词层
  - 报告页：风险等级、违规高亮、法条引用卡片、改写建议、画面转写核对区
  - 浏览器实测：文案审核（违规示例→violation+法条引用）与海报审核（转写+双层判定）全流程通过
  - 启动：`python -m streamlit run app/app.py` → http://localhost:8501

**🎉 一期（P0）全部完成。** 二期（多平台文案 + 宣传图 + 审核闭环）待启动。

## 演示截图

实测截图见 `docs/demo/`：

| 截图 | 内容 |
|---|---|
| `01-文案审核-结论违规.png` | 极限词示例 → 红色「违规」结论 + 2 条 findings |
| `02-文案审核-法条引用与改写建议.png` | 广告法·第九条原文引用、判定理由、改写建议卡片 |
| `03-海报图审核-入口.png` | 海报图上传 / 内置示例入口 |
| `04-海报审核-小字与引用.png` | 海报审核结果：转写文字命中的极限词与底部「最终解释权」小字均被引用法条标出 |

## 环境准备

```bash
python -m venv .venv && .venv/Scripts/activate    # Windows
pip install -r requirements.txt
# .env 已就位（LLM_PROVIDER 控制供应商切换：deepseek | zhipu | dashscope，换模型零改码）

python hello_text.py            # 违禁词最小链路（本地，零成本）
python hello_image.py           # 视觉转写最小链路（调 API，默认转写 data/test_poster.png）
python -m engine.llm_client     # 查看当前供应商与模型配置
```
