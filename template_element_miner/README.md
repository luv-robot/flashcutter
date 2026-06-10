# Template Element Miner

CPU-only CLI pipeline for mining reusable FlashCutter template elements from
rights-cleared ad videos and images.

The MVP uses deterministic OpenCV heuristics. It does not use SAM,
GroundingDINO, CLIP, OCR, GPU inference, or automatic copyright judgment.

## Install

Install the optional offline-tool dependencies into your local Python
environment:

```bash
./backend/.venv/bin/pip install -r template_element_miner/requirements.txt
```

## Input Layout

Place source media under:

```text
data/template_element_miner/input/
  videos/
  images/
```

Supported inputs are `mp4`, `mov`, `jpg`, `jpeg`, `png`, and `webp`.

## Run Pipeline

```bash
python -m template_element_miner extract-frames \
  --input data/template_element_miner/input \
  --output data/template_element_miner/output \
  --fps 1

python -m template_element_miner detect-candidates \
  --frames data/template_element_miner/output/frames \
  --output data/template_element_miner/output

python -m template_element_miner cluster \
  --candidates data/template_element_miner/output/candidates.jsonl \
  --output data/template_element_miner/output/clusters

python -m template_element_miner build-review \
  --candidates data/template_element_miner/output/candidates.jsonl \
  --clusters data/template_element_miner/output/clusters.json \
  --output data/template_element_miner/output/review
```

Or run the extraction, detection, clustering, and review page generation in one
step:

```bash
python -m template_element_miner run-all \
  --input data/template_element_miner/input \
  --output data/template_element_miner/output \
  --assets data/template_element_miner/assets \
  --fps 1
```

Open `data/template_element_miner/output/review/index.html`, copy approved JSON
snippets into `approved_assets.jsonl`, and then import:

```bash
python -m template_element_miner import-approved \
  --approved data/template_element_miner/output/review/approved_assets.jsonl \
  --assets data/template_element_miner/assets
```

## Output

The pipeline writes:

- `frames.jsonl` with normalized frame metadata.
- `candidates.jsonl` with crop paths, bboxes, detector hints, pHash, and cluster
  IDs.
- `clusters.json` and contact-sheet images.
- Static review files under `output/review`.
- Approved asset folders under `data/template_element_miner/assets`.

Generated input, output, and asset folders are ignored by Git.
