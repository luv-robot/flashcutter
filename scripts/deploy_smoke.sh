#!/usr/bin/env bash
set -euo pipefail

API_BASE="${FLASHCUTTER_SMOKE_API_BASE:-${1:-http://127.0.0.1:8000}}"
PHONE="${FLASHCUTTER_SMOKE_PHONE:-}"
PASSWORD="${FLASHCUTTER_SMOKE_PASSWORD:-}"
VIDEO_PATH="${FLASHCUTTER_SMOKE_VIDEO:-}"
RUN_RENDER="${FLASHCUTTER_SMOKE_RENDER:-false}"
TEMPLATE_NAME="${FLASHCUTTER_SMOKE_TEMPLATE_NAME:-}"

json_get() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)'"$1"')'
}

echo "Checking health: $API_BASE/health"
curl -fsS "$API_BASE/health" >/dev/null

TOKEN=""
if [ -n "$PHONE" ] && [ -n "$PASSWORD" ]; then
  echo "Checking trial login for $PHONE"
  REGISTER_BODY="$(PHONE="$PHONE" PASSWORD="$PASSWORD" python3 -c 'import json,os; print(json.dumps({"phone": os.environ["PHONE"], "password": os.environ["PASSWORD"], "display_name": "Deploy smoke"}))')"
  curl -fsS -X POST "$API_BASE/api/auth/register" \
    -H "Content-Type: application/json" \
    -d "$REGISTER_BODY" >/dev/null 2>&1 || true

  LOGIN_BODY="$(PHONE="$PHONE" PASSWORD="$PASSWORD" python3 -c 'import json,os; print(json.dumps({"phone": os.environ["PHONE"], "password": os.environ["PASSWORD"]}))')"
  LOGIN_RESPONSE="$(curl -fsS -X POST "$API_BASE/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "$LOGIN_BODY")"
  TOKEN="$(printf '%s' "$LOGIN_RESPONSE" | json_get '["access_token"]')"
  curl -fsS "$API_BASE/api/auth/me" -H "Authorization: Bearer $TOKEN" >/dev/null
fi

AUTH_ARGS=()
if [ -n "$TOKEN" ]; then
  AUTH_ARGS=(-H "Authorization: Bearer $TOKEN")
fi

echo "Checking templates"
TEMPLATES_RESPONSE="$(curl -fsS "$API_BASE/api/templates" "${AUTH_ARGS[@]}")"
TEMPLATE_ID="$(TEMPLATE_NAME="$TEMPLATE_NAME" python3 -c 'import json,os,sys; data=json.load(sys.stdin); name=os.environ.get("TEMPLATE_NAME", ""); match=next((item for item in data if item["name"] == name), None) if name else (data[0] if data else None); print(match["id"] if match else "")' <<< "$TEMPLATES_RESPONSE")"
if [ -z "$TEMPLATE_ID" ]; then
  echo "No matching template returned"
  exit 1
fi

if [ -n "$VIDEO_PATH" ]; then
  if [ ! -f "$VIDEO_PATH" ]; then
    echo "Smoke video not found: $VIDEO_PATH"
    exit 1
  fi

  echo "Uploading smoke video"
  ASSET_RESPONSE="$(curl -fsS -X POST "$API_BASE/api/assets/upload" \
    "${AUTH_ARGS[@]}" \
    -F "file=@$VIDEO_PATH;type=video/mp4")"
  ASSET_ID="$(printf '%s' "$ASSET_RESPONSE" | json_get '["id"]')"

  echo "Segmenting uploaded asset"
  curl -fsS -X POST "$API_BASE/api/assets/$ASSET_ID/segment?segment_seconds=3" \
    "${AUTH_ARGS[@]}" >/dev/null

  echo "Creating smoke task"
  TASK_BODY="$(ASSET_ID="$ASSET_ID" TEMPLATE_ID="$TEMPLATE_ID" python3 -c 'import json,os; print(json.dumps({"name": "deploy-smoke", "asset_id": int(os.environ["ASSET_ID"]), "template_id": int(os.environ["TEMPLATE_ID"]), "params_json": {}}))')"
  TASK_RESPONSE="$(curl -fsS -X POST "$API_BASE/api/tasks" \
    "${AUTH_ARGS[@]}" \
    -H "Content-Type: application/json" \
    -d "$TASK_BODY")"
  TASK_ID="$(printf '%s' "$TASK_RESPONSE" | json_get '["id"]')"

  echo "Building smoke render plan"
  curl -fsS -X POST "$API_BASE/api/tasks/$TASK_ID/render-plan" \
    "${AUTH_ARGS[@]}" >/dev/null

  if [ "$RUN_RENDER" = "true" ]; then
    echo "Rendering smoke output"
    OUTPUT_RESPONSE="$(curl -fsS -X POST "$API_BASE/api/tasks/$TASK_ID/render" \
      "${AUTH_ARGS[@]}")"
    OUTPUT_ID="$(printf '%s' "$OUTPUT_RESPONSE" | json_get '["id"]')"

    echo "Writing smoke review decision"
    REVIEW_BODY="$(python3 -c 'import json; print(json.dumps({"review_status": "needs_changes", "review_notes": "Deploy smoke review check.", "reviewer_name": "Deploy smoke", "change_request": "No change requested; smoke marker only.", "priority": "low", "tags": ["deploy-smoke"]}))')"
    curl -fsS -X PATCH "$API_BASE/api/outputs/$OUTPUT_ID/review" \
      "${AUTH_ARGS[@]}" \
      -H "Content-Type: application/json" \
      -d "$REVIEW_BODY" >/dev/null
  fi
fi

echo "Deploy smoke complete"
