#!/usr/bin/env python3
"""Evaluate the frozen retrieval prototype against locked page-level qrels."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.retrieval.combined_retriever import load_ranking_config, normalize_channel
from backend.retrieval.graph_retriever import load_graph, retrieve_graph
from backend.retrieval.historical_retriever import load_historical_index, retrieve_historical
from backend.retrieval.vector_retriever import build_bm25_index, load_index, retrieve_bm25, retrieve_vector

SEEDS = ROOT / "reports/evaluation_seed_questions.csv"
EVENTS = ROOT / "backend/data/question_event_evidence.jsonl"
VECTOR_INDEX = ROOT / "backend/data/uefa_tfidf_index.json"
CHUNKS = ROOT / "backend/data/uefa_evidence_chunks.jsonl"
GRAPH_PATH = ROOT / "backend/data/retrieval_graph.json"
HISTORY = ROOT / "backend/data/historical_train_sample.jsonl.gz"
V1_CONFIG = ROOT / "backend/retrieval/ranking_config_v1.json"
CSV_OUT = ROOT / "reports/retrieval_evaluation_per_question.csv"
MD_OUT = ROOT / "reports/retrieval_evaluation.md"
K = 5
RETRIEVAL_POOL = max(4 * K, 20)

SOURCE_MENTION = re.compile(r"Women[’']s\s+EURO|UWCL|UCL", re.I)
SOURCE_IDS = {
    "uwcl": "uefa-uwcl-2024-25",
    "ucl": "uefa-ucl-2024-25",
    "women's euro": "uefa-weuro-2025",
    "women’s euro": "uefa-weuro-2025",
}
PAGE_REF = re.compile(r"\bpp?\.?\s*(\d+)\s*(?:[-–]\s*(\d+))?", re.I)


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def parse_qrels(raw: str) -> set[tuple[str, int]]:
    mentions = []
    for match in SOURCE_MENTION.finditer(raw):
        label = match.group(0).casefold()
        mentions.append((match.start(), match.end(), SOURCE_IDS[label]))
    relevant: set[tuple[str, int]] = set()
    for i, (_, end, source_id) in enumerate(mentions):
        segment_end = mentions[i + 1][0] if i + 1 < len(mentions) else len(raw)
        for ref in PAGE_REF.finditer(raw[end:segment_end]):
            first = int(ref.group(1))
            last = int(ref.group(2) or first)
            relevant.update((source_id, page) for page in range(first, last + 1))
    return relevant


def page_rank(rows: list[dict], score_field: str) -> list[tuple[str, int, float]]:
    scores: dict[tuple[str, int], float] = {}
    for row in rows:
        page = (row["source_id"], int(row["page"]))
        scores[page] = max(scores.get(page, -1.0), float(row[score_field]))
    return sorted(((source, page, score) for (source, page), score in scores.items()), key=lambda x: (-x[2], x[0], x[1]))


def fused_page_rank(v_rows: list[dict], g_rows: list[dict], alpha: float, beta: float) -> list[tuple[str, int, float]]:
    v_scores = normalize_channel(v_rows, "vector_score")
    g_scores = normalize_channel(g_rows, "graph_score")
    all_ids = set(v_scores) | set(g_scores)
    doc_by_id = {row["evidence_id"]: row for row in v_rows + g_rows}
    page_scores: dict[tuple[str, int], float] = {}
    for evidence_id in all_ids:
        doc = doc_by_id[evidence_id]
        score = alpha * v_scores.get(evidence_id, 0.0) + beta * g_scores.get(evidence_id, 0.0)
        page = (doc["source_id"], int(doc["page"]))
        page_scores[page] = max(page_scores.get(page, -1.0), score)
    return sorted(((source, page, score) for (source, page), score in page_scores.items()), key=lambda x: (-x[2], x[0], x[1]))


def metrics(ranked: list[tuple[str, int, float]], qrels: set[tuple[str, int]]) -> dict[str, float]:
    top = [(source, page) for source, page, _ in ranked[:K]]
    hits = sum(page in qrels for page in top)
    first_rank = next((i for i, page in enumerate(top, 1) if page in qrels), None)
    return {
        "P@5": hits / K,
        "Recall@5": hits / len(qrels) if qrels else 0.0,
        "MRR": 1 / first_rank if first_rank else 0.0,
    }


def display_pages(ranked: list[tuple[str, int, float]], count: int = K) -> str:
    return "; ".join(f"{source} p.{page}" for source, page, _ in ranked[:count])


def main() -> int:
    try:
        graph = load_graph(GRAPH_PATH)
        vector_index = load_index(VECTOR_INDEX)
        bm25_index = build_bm25_index(CHUNKS, k1=1.5, b=0.75)
        v1_config = json.loads(V1_CONFIG.read_text(encoding="utf-8"))
        selected_bm25_index = build_bm25_index(CHUNKS, k1=v1_config["bm25"]["k1"], b=v1_config["bm25"]["b"])
        history = load_historical_index(HISTORY)
        events = {row["case_id"]: row for row in read_jsonl(EVENTS)}
        with SEEDS.open(encoding="utf-8-sig", newline="") as f:
            questions = list(csv.DictReader(f))
        if len(questions) != 12 or len(events) != 12:
            raise ValueError("The locked pilot must have exactly 12 questions and event windows")

        config = load_ranking_config(V1_CONFIG)
        alpha, beta, gamma = (config["weights"][key] for key in ("alpha", "beta", "gamma"))
        report_rows = []
        covered = []
        h_safety = []
        for q in questions:
            case_id = q["case_id"]
            event_window = events[case_id]
            trigger = next((e for e in event_window["events"] if e["id"] == event_window["trigger_event_id"]), None)
            if trigger is None:
                raise ValueError(f"Missing locked trigger event for {case_id}")
            query = q.get("revised_question_seed") or q["question_seed"]
            # Match the configured pool size for a requested top-five result.
            v_rows = retrieve_vector(query, vector_index, RETRIEVAL_POOL)
            bm_rows = retrieve_bm25(query, bm25_index, RETRIEVAL_POOL)
            selected_rows = retrieve_bm25(query, selected_bm25_index, RETRIEVAL_POOL)
            g_rows = retrieve_graph(query, graph, RETRIEVAL_POOL)
            v_rank = page_rank(v_rows, "vector_score")
            bm_rank = page_rank(bm_rows, "vector_score")
            vg_rank = fused_page_rank(v_rows, g_rows, 0.5, 0.5)
            bmg_rank = fused_page_rank(bm_rows, g_rows, 0.5, 0.5)
            selected_rank = fused_page_rank(selected_rows, g_rows, alpha / (alpha + beta), beta / (alpha + beta))
            # H provides historical cases, not UEFA pages. On the UEFA page-only
            # candidate pool its score is absent; retain fixed 1/3 coefficients.
            # H contributes historical cases, not UEFA pages. The page-only
            # projection of the frozen full config is the selected BM25+G rank.
            full_page_rank = selected_rank
            h_rows = retrieve_historical(trigger, history, exclude_match_id=event_window["match_id"], top_k=5)
            leakage = any(str(row["match_id"]) == str(event_window["match_id"]) for row in h_rows)
            h_safety.append((case_id, leakage))
            qrels = parse_qrels(q["gold_qrel_pages"])
            row = {
                "case_id": case_id,
                "support_status": q["gold_support_status"],
                "relevant_page_count": len(qrels),
                "V_P@5": "", "V_Recall@5": "", "V_MRR": "",
                "BM25_P@5": "", "BM25_Recall@5": "", "BM25_MRR": "",
                "VG_P@5": "", "VG_Recall@5": "", "VG_MRR": "",
                "BM25G_P@5": "", "BM25G_Recall@5": "", "BM25G_MRR": "",
                "Selected_P@5": "", "Selected_Recall@5": "", "Selected_MRR": "",
                "GGTR_page_P@5": "", "GGTR_page_Recall@5": "", "GGTR_page_MRR": "",
                "V_top5_pages": display_pages(v_rank),
                "BM25_top5_pages": display_pages(bm_rank),
                "VG_top5_pages": display_pages(vg_rank),
                "BM25G_top5_pages": display_pages(bmg_rank),
                "Selected_top5_pages": display_pages(selected_rank),
                "GGTR_page_top5": display_pages(full_page_rank),
                "H_top1_case_id": h_rows[0]["case_id"] if h_rows else "",
                "H_top1_match_id": h_rows[0]["match_id"] if h_rows else "",
                "H_same_match_returned": leakage,
                "no_UEFA_match_returned": not bool(v_rank or bm_rank or vg_rank or bmg_rank or selected_rank),
            }
            if q["gold_support_status"] == "conditional":
                if not qrels:
                    raise ValueError(f"Covered question lacks page qrels: {case_id}")
                vm, bm, vgm, bgm, sm, fm = (metrics(rank, qrels) for rank in (v_rank, bm_rank, vg_rank, bmg_rank, selected_rank, full_page_rank))
                for prefix, result in (("V", vm), ("BM25", bm), ("VG", vgm), ("BM25G", bgm), ("Selected", sm), ("GGTR_page", fm)):
                    row[f"{prefix}_P@5"] = result["P@5"]
                    row[f"{prefix}_Recall@5"] = result["Recall@5"]
                    row[f"{prefix}_MRR"] = result["MRR"]
                covered.append(row)
            elif q["gold_support_status"] != "not_covered":
                raise ValueError(f"Unknown support status {q['gold_support_status']} for {case_id}")
            report_rows.append(row)

        CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
        with CSV_OUT.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(report_rows[0]))
            writer.writeheader()
            writer.writerows(report_rows)

        aggregate = {}
        for prefix in ("V", "BM25", "VG", "BM25G", "Selected", "GGTR_page"):
            aggregate[prefix] = {metric: mean(float(row[f"{prefix}_{metric}"]) for row in covered) for metric in ("P@5", "Recall@5", "MRR")}
        no_cover = [r for r in report_rows if r["support_status"] == "not_covered"]
        all_passed = len(h_safety) == 12 and not any(leaked for _, leaked in h_safety)
        md = [
            "# Locked retrieval evaluation",
            "",
            "Evaluated the 12 frozen prompts against the locked report-page qrels. No retrieval parameters were tuned on these questions.",
            "",
            "## Macro results on the 10 UEFA-covered questions",
            "",
            "| Page-ranking mode | P@5 | Recall@5 | MRR |",
            "|---|---:|---:|---:|",
        ]
        for prefix, label in (("V", "V (TF-IDF baseline)"), ("BM25", "V (BM25 baseline, k1=1.5, b=0.75)"), ("VG", "TF-IDF+G (equal weights)"), ("BM25G", "BM25+G (equal weights)"), ("Selected", "Selected BM25+G (dev-tuned relative weight)"), ("GGTR_page", "Full configuration, UEFA-page candidate pool")):
            values = aggregate[prefix]
            md.append(f"| {label} | {values['P@5']:.3f} | {values['Recall@5']:.3f} | {values['MRR']:.3f} |")
        md += [
            "",
            "Metrics use distinct report pages, ranked by the best chunk score on each page. `P@5` divides by 5; `Recall@5` uses all locked relevant pages for that question; MRR uses the first relevant page. Macro means cover the ten questions with conditional UEFA support.",
            "",
            "## Interpretation and limits",
            "",
            "- BM25 is a sparse lexical ranking method, not dense embedding semantics. The selected k1/b and V:G relative weight were tuned only on the separate 22-question development set, then frozen before this locked evaluation.",
            "- For UEFA-page metrics, H has no page-level relevance labels and returns a different item type (historical match cases). The full-configuration page row therefore projects the frozen αV+βG weights onto UEFA chunks; γH is absent for each page. This does not measure H relevance or the quality of a mixed-source top-five list.",
            f"- H same-match exclusion: {'passed for all 12 queries' if all_passed else 'FAILED; inspect per-question CSV'}. Historical relevance is unjudged because the locked qrels contain no similar-match labels.",
            f"- Two not-covered questions are reported separately; lexical and graph retrieval returned no UEFA pages for {sum(bool(r['no_UEFA_match_returned']) for r in no_cover)} of 2. The system has no explicit calibrated abstention threshold, so this is a no-result check, not a validated abstention score.",
            "- The selected development setting performs below fixed BM25 on all three locked metrics. This indicates poor development-to-test transfer; the locked set was not used to retune or choose a replacement.",
            "- This is a 12-question pilot. Report results descriptively; do not infer broad generalization.",
            "",
            "## Per-question results",
            "",
            "See `reports/retrieval_evaluation_per_question.csv` for every question’s metrics, top-five pages, H top match, and same-match exclusion result.",
            "",
            "No answer generation or factuality scoring was run in this step.",
            "",
        ]
        MD_OUT.write_text("\n".join(md), encoding="utf-8")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Retrieval evaluation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Evaluated {len(covered)} covered and {len(no_cover)} not-covered questions.")
    print(f"H same-match exclusion: {'passed' if all_passed else 'FAILED'}.")
    print(f"Results: {MD_OUT.relative_to(ROOT)} and {CSV_OUT.relative_to(ROOT)}")
    for key, vals in aggregate.items():
        print(key, " ".join(f"{m}={vals[m]:.3f}" for m in ("P@5", "Recall@5", "MRR")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
