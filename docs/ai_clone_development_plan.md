# AI Clone 开发启动计划 v0.1

## 1. 目标

上线一个你能亲自操作的 AI Clone MVP，用于生产第一批测试素材，并推动客户进入试用阶段。

第一阶段不接真实 GPU，也不做复杂 ComfyUI UI。先跑通：

```text
参考图片/视频
→ prompt 仿制任务
→ 可见队列
→ mock worker 生成结果
→ 入库为视频片段
→ 模板 slot 可复用
```

第二阶段再接国内 4090 分时平台：

```text
共绩算力 / 星宇智算
→ 启动 ComfyUI worker
→ 提交 workflow
→ 下载输出
→ 回写视频片段库
```

---

## 2. 产品入口

入口放在：

```text
视频片段库
  ├── 上传片段
  ├── 上传参考图
  └── 仿制生成
```

不恢复单独 AICF 菜单。

---

## 3. 第一阶段开发项

### PR 1：数据模型与状态机

新增：

```text
ai_clone_workflows
ai_clone_jobs
ai_clone_workers
ai_clone_job_events
```

任务状态：

```text
queued
prechecking
starting_worker
warming_models
submitting
waiting_provider
running
postprocessing
importing
succeeded
failed
cancelled
refunded
```

计时字段：

```text
queue_entered_at
started_at
provider_started_at
postprocess_started_at
finished_at
wait_seconds
elapsed_seconds
estimated_seconds
progress_percent
progress_message
queue_position
retry_count
```

### PR 2：Workflow Registry

内置两个 workflow：

```text
image_clone_video_v1
video_clone_clip_v1
```

manifest 字段：

```text
workflow_id
version
mode
provider
estimated_credits
estimated_seconds
params_schema
workflow_api_json
status
```

### PR 3：MockCloneClient

本地 mock 不调用 GPU，但模拟完整任务生命周期：

```text
queued 3s
starting_worker 5s
warming_models 5s
running 10-20s
postprocessing 3s
importing
succeeded
```

输出：

```text
本地占位 mp4
封面图
AIAsset / 视频片段记录
```

### PR 4：AI Clone API

```http
GET /api/ai-clone/workflows
POST /api/ai-clone/jobs
GET /api/ai-clone/jobs
GET /api/ai-clone/jobs/{job_id}
POST /api/ai-clone/jobs/{job_id}/cancel
POST /api/ai-clone/jobs/{job_id}/retry
```

提交任务时必须检查：

```text
参考素材存在
参考素材类型匹配 workflow
prompt 非空
duration 合规
用户有权限
```

### PR 5：可见队列前端

视频片段库增加：

```text
仿制生成按钮
仿制生成对话框
生成队列面板
任务详情抽屉
失败重试
取消任务
完成后查看片段
```

队列卡片文案：

```text
排队中：第 3 位，已等待 01:24
启动中：正在启动 GPU worker
预热中：正在加载模型
生成中：已运行 02:10
后处理中：下载、转码、生成封面
已完成：已加入视频片段库
失败：credits 已退回，可重新发起
```

---

## 4. 第二阶段开发项：真实 ComfyUI Worker

### PR 6：Worker Provider 抽象

```python
class ComfyUIWorkerProvider:
    async def start_worker(self, workflow_id: str) -> WorkerHandle:
        ...

    async def wait_until_ready(self, worker_id: str) -> None:
        ...

    async def submit_workflow(self, worker_id: str, workflow_api_json: dict, params: dict) -> str:
        ...

    async def get_status(self, worker_id: str, provider_job_id: str) -> dict:
        ...

    async def get_outputs(self, worker_id: str, provider_job_id: str) -> list[str]:
        ...

    async def stop_worker_if_idle(self, worker_id: str) -> None:
        ...
```

配置样例：

```json
{
  "provider": "gongjiyun",
  "gpu_type": "rtx4090",
  "hourly_price_cny": 1.68,
  "billing_granularity": "second",
  "idle_shutdown_seconds": 900,
  "max_concurrent_jobs": 1
}
```

### PR 7：ComfyUI Adapter

对接独立 ComfyUI API：

```text
POST /prompt
GET /queue
GET /history/{prompt_id}
GET /view
```

注意：

```text
1. endpoint 只存在后端配置。
2. workflow_api_json 只能来自 registry。
3. 输出文件必须下载到系统存储。
4. ComfyUI worker 不作为长期文件存储。
```

### PR 8：真实 GPU 试生产

目标：

```text
1. 选择 10 张参考图
2. 生成 10-30 个测试 clip
3. 每条记录 GPU 秒数、等待秒数、失败原因
4. 人工审核质量
5. 汇总客户试用素材包
```

---

## 5. 验收清单

第一阶段完成标准：

```text
1. 视频片段库能发起仿制生成。
2. 队列状态和计时可见。
3. mock 任务完成后自动入库。
4. 失败任务可以重试。
5. 完成 clip 能被模板 slot 选择。
6. 所有错误提示是运营可理解文案。
```

第二阶段完成标准：

```text
1. 能启动真实 4090 ComfyUI worker。
2. 能提交 image_clone_video_v1。
3. 能拿到真实 mp4 输出。
4. 能自动入库并展示。
5. 空闲 worker 能释放。
6. 每条任务有成本记录。
```

---

## 6. 开发顺序

```text
Day 1:
  数据模型
  mock workflow registry
  job API

Day 2:
  mock worker
  队列计时
  资产入库

Day 3:
  视频片段库前端入口
  队列面板
  手工测试

Day 4+:
  ComfyUI worker provider
  4090 平台调试
  第一批测试素材生产
```
