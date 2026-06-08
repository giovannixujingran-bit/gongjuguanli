"""从 SSOT 文档生成「接入资料」分发包。

接入方若无仓库访问权，需要一个可直接发出去的文件夹。本脚本把分散在 docs/ 的接入相关
SSOT 文档汇集到 integrations/handoff-kit/，给接入方阅读用的中文文件名 + 一张说明。

**单一信息源**：本脚本不重写任何内容，只复制 SSOT 文档（.md 顶部加「自动生成」横幅
指回源文件）。改了接入文档后重跑本脚本即可让分发包同步——绝不要手改 handoff-kit/ 里的文件。
版本号取自 shared/schema_version.py。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from shared.schema_version import CURRENT_SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "integrations" / "handoff-kit"

# (源文件, 分发包内文件名)；.md 会加「自动生成」横幅，.json 原样复制（JSON 不能带注释）。
SOURCES: list[tuple[Path, str]] = [
    (ROOT / "docs" / "integration-guide-接入指南.md", "接入指南.md"),
    (ROOT / "docs" / "contract-接入契约.md", "接入契约.md"),
    (ROOT / "docs" / "schema-数据契约.md", "字段文档.md"),
    (ROOT / "docs" / "metadata-conventions-metadata约定与字段治理.md", "metadata约定.md"),
    (ROOT / "docs" / "ai-intake-guide-AI接入向导.md", "AI接入向导.md"),
    (ROOT / "shared" / "schema" / "event.schema.json", "event.schema.json"),
]


def banner(source_rel: str) -> str:
    return (
        f"<!-- 自动生成 by platform/tools/export_integration_kit.py —— 勿手改。"
        f"源文件：platform/{source_rel}。改源后重跑脚本重生成本包。 -->\n\n"
    )


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    for source, out_name in SOURCES:
        source_rel = source.relative_to(ROOT).as_posix()
        if source.suffix == ".md":
            text = banner(source_rel) + source.read_text(encoding="utf-8")
            (OUT_DIR / out_name).write_text(text, encoding="utf-8", newline="\n")
        else:
            shutil.copyfile(source, OUT_DIR / out_name)

    (OUT_DIR / "说明.txt").write_text(render_readme(), encoding="utf-8", newline="\n")
    (OUT_DIR / "README.md").write_text(render_repo_readme(), encoding="utf-8", newline="\n")
    out_rel = OUT_DIR.relative_to(ROOT.parent).as_posix()
    print(f"接入资料分发包已生成：{out_rel}（契约 {CURRENT_SCHEMA_VERSION}）")


def render_readme() -> str:
    """给接入方看的说明（随包发出）。"""
    return f"""接入资料（发给接入方）
=======================

给你的工具接入「内部工具汇总与分析平台」用。先读《接入指南》，照着做即可。
（契约版本：{CURRENT_SCHEMA_VERSION}）

阅读顺序
--------
1. 接入指南.md       —— 先读这份。五步流程 + 最小示例 + 怎么改代码 + 边界。
2. event.schema.json —— 机器校验文件。你拼好的事件 JSON 拿它自校（合不合格式）。
3. 接入契约.md       —— 义务细则（失败/流式/异步怎么处理、必填选填）。
4. 字段文档.md       —— 每个字段的含义、类型、必填/选填全表。
5. metadata约定.md   —— 要记主表没预置的东西（报告类型/分段耗时/图片产出…）时看这份的统一记法。
6. AI接入向导.md     —— 用 AI 帮你接入时，把它喂给 AI；它会自助判定字段、
                        只在必要时反问你，并产出接入配置 + 方案。

两件最容易忽略的事
------------------
- tool_id 要找平台方领（平台统一分配，命名 <team>-<tool>）。别自己编。
- 原文（input_content / output_content）已放开，可按需上报；写入侧不设门禁。
  仅读取侧（多用户上看板后谁能看原文）的可见范围待定，详见字段文档.md 敏感内容策略。

说明
----
- 本包是导出快照（契约 {CURRENT_SCHEMA_VERSION}）。平台契约更新后，问平台方要新版本。
- 《接入指南.md》正文里的链接写的是平台仓库内路径；对应文件就在本文件夹里：
    contract-接入契约.md                        → 本文件夹的「接入契约.md」
    schema-数据契约.md                          → 本文件夹的「字段文档.md」
    metadata-conventions-metadata约定与字段治理.md            → 本文件夹的「metadata约定.md」
    ../shared/schema/event.schema.json → 本文件夹的「event.schema.json」
  参考 SDK 和试点模板是代码，未放进本包；需要的话找平台方要仓库 platform/ 访问权。
- 有疑问直接找平台对接人。
"""


def render_repo_readme() -> str:
    """给仓库维护者看的说明（标明本目录是生成物）。"""
    return """# handoff-kit —— 接入资料分发包（自动生成，勿手改）

本目录由 `platform/tools/export_integration_kit.py` 从 SSOT 文档生成，供没有仓库访问权的
接入方直接获取（整个文件夹发给对方即可）。

- **不要手改本目录任何文件**：改 `docs/integration-guide-接入指南.md` /
  `docs/contract-接入契约.md` / `docs/schema-数据契约.md` /
  `shared/schema/event.schema.json` 等源文件后，重跑生成脚本：
  `python tools/export_integration_kit.py`（详见 CLAUDE.md §3 改动传播规则）。
- 本目录不是 SSOT，只是上述文档的分发副本。
"""


if __name__ == "__main__":
    main()
