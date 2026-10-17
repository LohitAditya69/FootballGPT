#!/usr/bin/env python3
"""Generate extractive cited briefs and RGG JSON for the frozen test questions."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.reporting import build_grounded_report
from backend.retrieval.combined_retriever import retrieve_combined
from backend.retrieval.graph_retriever import load_graph
from backend.retrieval.historical_retriever import load_historical_index
from backend.retrieval.vector_retriever import load_bm25_index


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def safe_json(value: object) -> str:
    # Prevent a source excerpt from closing the embedded JSON script element.
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_html(reports: list[dict]) -> str:
    payload = safe_json(reports)
    return f'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FootballGPT grounded evidence briefs</title>
<style>
body{{font:16px/1.55 system-ui,sans-serif;max-width:1050px;margin:2rem auto;padding:0 1rem;color:#18212b;background:#f5f7f8}}
header,section,details{{background:white;border:1px solid #d8e0e5;border-radius:10px;padding:1rem 1.2rem;margin:1rem 0}}
select{{font:inherit;max-width:100%;padding:.5rem}} .badge{{font-size:.85rem;font-weight:650;color:#164e63}}
blockquote{{border-left:4px solid #1884a3;margin:1rem 0;padding:.4rem 1rem;background:#f1f8fa}}
small,.muted{{color:#52616b}} code{{overflow-wrap:anywhere}}
</style>
<header><h1>Grounded evidence briefs</h1><p>Verbatim UEFA report passages and recorded StatsBomb events, linked through the retrieval provenance trace. This pilot does not generate recommendations or claim expert factuality review.</p>
<label for="item">Question </label><select id="item"></select></header>
<main id="view"></main>
<script type="application/json" id="reports">{payload}</script>
<script>
const reports=JSON.parse(document.getElementById('reports').textContent), menu=document.getElementById('item'), view=document.getElementById('view');
const el=(tag,text,cls)=>{{const n=document.createElement(tag); if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}};
reports.forEach((r,i)=>{{const o=document.createElement('option');o.value=i;o.textContent=r.question_id+' — '+r.question;menu.append(o);}});
function show(){{const r=reports[Number(menu.value)];view.replaceChildren();let s=document.createElement('section');s.append(el('div',r.answer_mode.replaceAll('_',' '),'badge'),el('h2',r.question),el('p',r.answer));
if(r.tactical_passages.length){{s.append(el('h3','Retrieved report passages'));r.tactical_passages.forEach(p=>{{const b=el('blockquote',p.text);b.append(el('div',p.citation,'badge'));s.append(b);}});}}else s.append(el('p','No citeable report passage was retrieved.','muted'));
view.append(s);s=document.createElement('section');s.append(el('h2','Recorded match evidence'),el('p','Match '+r.event_evidence.match_id+' · '+r.event_evidence.trigger_event_type+' · '+r.event_evidence.trigger_timestamp),el('p',r.event_evidence.window_rule,'muted'));
const d=document.createElement('details'),sum=el('summary','Show event window ('+r.event_evidence.events.length+' records)');d.append(sum);const pre=el('pre',JSON.stringify(r.event_evidence.events,null,2));d.append(pre);s.append(d);view.append(s);
s=document.createElement('section');s.append(el('h2','Reasoning Graph Generator provenance'));const prov=r.provenance;const list=document.createElement('ul');prov.edges.forEach(e=>{{const source=prov.nodes.find(n=>n.id===e.target);const li=el('li',(e.relation==='retrieved_support'?'Rank '+e.rank+': ':'')+e.relation+' → '+e.target+(source?.citation?' ('+source.citation+')':''));list.append(li);}});s.append(list);view.append(s);
s=document.createElement('section');s.append(el('h2','Limits'));const ul=document.createElement('ul');r.limitations.forEach(x=>ul.append(el('li',x)));s.append(ul);view.append(s);}}
menu.addEventListener('change',show);menu.value='0';show();
</script></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/generated")
    args = parser.parse_args()
    data = ROOT / "backend/data"
    with (ROOT / "reports/evaluation_seed_questions.csv").open(encoding="utf-8-sig", newline="") as f:
        seeds = [row for row in csv.DictReader(f) if row.get("split") == "test"]
    windows = {row["case_id"]: row for row in read_jsonl(data / "question_event_evidence.jsonl")}
    if len(seeds) != 12 or set(windows) != {row["case_id"] for row in seeds}:
        raise ValueError("Expected exactly the 12 frozen test seeds and matching StatsBomb windows")
    graph = load_graph(data / "retrieval_graph.json")
    index = load_bm25_index(data / "uefa_bm25_index.json")
    historical = load_historical_index(data / "historical_train_sample.jsonl.gz")
    reports = []
    for seed in seeds:
        case_id = seed["case_id"]
        window = windows[case_id]
        trigger = next((event for event in window["events"] if event.get("id") == window["trigger_event_id"]), None)
        if trigger is None:
            raise ValueError(f"Missing trigger event for {case_id}")
        question = seed.get("revised_question_seed") or seed["question_seed"]
        ranked = retrieve_combined(
            question, graph=graph, vector_index=index, historical_cases=historical,
            query_event=trigger, exclude_match_id=window["match_id"], top_k=20,
        )
        report = build_grounded_report(
            question=question, support_status=seed["gold_support_status"],
            ranked_evidence=ranked, event_window=window,
        )
        reports.append(report)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "grounded_reports.jsonl"
    provenance_path = args.output_dir / "rgg_provenance.jsonl"
    review_path = args.output_dir / "factuality_review.csv"
    report_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in reports), encoding="utf-8")
    provenance_path.write_text("".join(json.dumps(r["provenance"], ensure_ascii=False) + "\n" for r in reports), encoding="utf-8")
    (args.output_dir / "index.html").write_text(render_html(reports), encoding="utf-8")
    with review_path.open("w", encoding="utf-8", newline="") as f:
        fields = ["question_id", "answer_mode", "question", "evidence_id", "citation", "verbatim_passage", "review_decision", "support_type", "reviewer_notes"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for report in reports:
            passages = report["tactical_passages"] or [{"evidence_id": "", "citation": "", "text": ""}]
            for passage in passages:
                writer.writerow({
                    "question_id": report["question_id"], "answer_mode": report["answer_mode"],
                    "question": report["question"], "evidence_id": passage["evidence_id"],
                    "citation": passage["citation"], "verbatim_passage": passage["text"],
                    "review_decision": "", "support_type": "", "reviewer_notes": "",
                })
    print(f"Generated {len(reports)} evidence briefs ({sum(r['answer_mode'] == 'abstain' for r in reports)} abstentions).")
    print(f"Reports: {report_path.relative_to(ROOT)}; provenance: {provenance_path.relative_to(ROOT)}")
    print(f"Review sheet: {review_path.relative_to(ROOT)}; interface: {(args.output_dir / 'index.html').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
