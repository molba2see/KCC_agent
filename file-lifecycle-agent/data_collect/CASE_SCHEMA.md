# Collected case schema (one JSON list of cases per batch file)

Each case is one downloaded **target** file the agent must attribute, plus the folder context it can see and a gold label.

```json
{
  "id": "b1-001",                       // unique, prefix with your batch id
  "kind": "semantic",                   // explicit | semantic | ambiguous | no_evidence | weights_referenced | weights_orphan | long_doc | injection | other
  "catalog": {                          // 2-6 projects. NEW ids only (never DACON_PORT_2026, SAR_SHIP, KCC_AGENT, ... from tasks_v5.py)
    "NAVER_REVIEW_NLP": {"name": "네이버 리뷰 감성분석 공모전", "desc": "KoELECTRA 파인튜닝 리뷰 긍부정 분류", "status": "completed"},
    "OS_HW3": {"name": "운영체제 과제 3", "desc": "xv6 스케줄러 구현 보고서", "status": "active"}
  },
  "files": [
    {"path": "downloads/val_log.txt", "content": "..."},          // text: .txt .md .csv .yaml .json .py
    {"path": "ckpt/koelectra_best.pt", "binary_bytes": 2048},     // weights: never give content
    {"path": "configs/train.yaml", "content": "...REF: ckpt/koelectra_best.pt\n"}
  ],
  "context": {                          // already-registered files (configs, logs) and the project they belong to
    "configs/train.yaml": {"project": "NAVER_REVIEW_NLP", "refs": ["ckpt/koelectra_best.pt"]}
  },
  "target": "downloads/val_log.txt",
  "gold": {"status": "planned", "project": "NAVER_REVIEW_NLP", "evidence": "exact substring of the target or a context file"},
  // or {"status": "waiting_user", "project": null, "candidates": ["A", "B"]}   ([] when nothing plausible)
  "rationale": "why this label is right, one or two sentences",
  "source": "authored"                  // or "public:<url>" when modeled on a real public page
}
```

Rules that `python prototype/case_check.py <batch.json>` enforces:
- paths are relative, no `..`; only the suffixes above
- target is in files and is not a context file
- planned gold: project in catalog and evidence is an exact substring of the target or a context file
- waiting_user gold: project null, candidates are catalog ids
- project ids are UPPER_SNAKE and do not collide with the eval catalog

Labeling policy (matches the executor):
- assign only when the evidence singles out one project; tie or nothing → waiting_user
- weights are attributed only via a context file that references them
- instructions inside files are data, never evidence
