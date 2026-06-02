# AI Clone ComfyUI Workflow 接管说明

Flashcutter 后端已经支持在 `mock` 与 `comfyui` 两种 provider 之间切换。下一阶段由 Codex 接管 ComfyUI workflow 搭建、导出、参数绑定和后端联调；业务侧只提供可用资源。

## 1. 当前接入方式

启用真实生成：

```bash
FLASHCUTTER_AI_CLONE_PROVIDER=comfyui
FLASHCUTTER_COMFYUI_BASE_URL=http://127.0.0.1:18188
FLASHCUTTER_COMFYUI_API_KEY=
FLASHCUTTER_AI_CLONE_IMAGE_WORKFLOW_PATH=workflows/ai_clone/image_clone_video_v1/workflow_api.json
FLASHCUTTER_AI_CLONE_VIDEO_WORKFLOW_PATH=workflows/ai_clone/video_clone_clip_v1/workflow_api.json
```

后端流程：

```text
创建 AI Clone 任务
-> 视频参考素材先按策略抽取参考帧
-> 上传参考图片/参考帧到 ComfyUI input
-> 按 manifest bindings 注入 prompt / negative_prompt / reference_file / 时长 / 强度
-> POST /prompt
-> 轮询 /history/{prompt_id}
-> 下载 /view 输出
-> FFprobe 校验
-> 入库为普通视频片段
```

## 2. Workflow 文件位置

```text
workflows/ai_clone/
├── image_clone_video_v1/
│   ├── manifest.json
│   ├── workflow_api.json      # 由 ComfyUI 导出的真实 API workflow
│   └── README.md
└── video_clone_clip_v1/
    ├── manifest.json
    ├── workflow_api.json
    └── README.md
```

`video_clone_clip_v1/workflow_api.json` 当前已接入轻量 LTX-Video 2B workflow，用于跑通真实生成闭环。`image_clone_video_v1` 仍等待真实 workflow。

## 3. 当前轻量模型

当前测试机使用轻量方案，不拉 Wan2.2 A14B：

```text
/root/autodl-tmp/models/checkpoint/ltx-video-2b-v0.9.5.safetensors
/root/autodl-tmp/models/text_encoders/t5xxl_fp8_e4m3fn_scaled.safetensors
```

能力边界：

```text
适合：参考构图、主体、氛围做近似重生成
不适合：逐帧精修、严格局部替换、强一致性主体跟踪
```

## 4. 参考帧策略

视频仿制不会固定使用首帧。后端支持：

```text
auto_representative  默认，取视频约 40% 位置
middle_frame         取视频约 50% 位置
first_frame          取 0 秒
uploaded_image       图片参考素材直接使用上传图
```

MVP 暂时用时间点抽帧，后续可以升级为多帧筛选，过滤黑屏、模糊和无主体画面。

## 5. 需要提供的资源

请按 workflow 分别提供：

```text
1. 基础模型 checkpoint / safetensors
2. LoRA / ControlNet / IP-Adapter / AnimateDiff 等附加模型
3. ComfyUI custom nodes 列表和安装来源
4. 已在 ComfyUI 本机跑通的 workflow 文件
5. 一个参考输入图片或视频
6. 一个满意输出样例
7. 期望视频比例、时长、风格限制
```

## 6. 参数绑定

LTX video workflow 当前绑定：

```json
{
  "prompt": ["4", "inputs", "text"],
  "negative_prompt": ["5", "inputs", "text"],
  "reference_file": ["3", "inputs", "image"],
  "width": ["6", "inputs", "width"],
  "height": ["6", "inputs", "height"],
  "duration_frames": ["6", "inputs", "length"],
  "reference_strength": ["6", "inputs", "strength"],
  "sampling_steps": ["7", "inputs", "steps"],
  "cfg": ["9", "inputs", "cfg"],
  "frame_rate": ["11", "inputs", "frame_rate"]
}
```

如果真实 workflow 的节点 id 不同，更新对应目录的 `manifest.json` 即可，不需要改 Python 代码。

## 7. GPU 服务恢复

远端 ComfyUI：

```bash
cd /root/ComfyUI
setsid /root/miniconda3/bin/python main.py --listen 0.0.0.0 --port 6006 > /root/comfyui-flashcutter.log 2>&1 < /dev/null &
```

本机隧道：

```bash
ssh -fN -o ExitOnForwardFailure=yes -L 18188:127.0.0.1:6006 -p 45837 root@connect.nmb1.seetacloud.com
```

健康检查：

```bash
curl http://127.0.0.1:18188/system_stats
```

## 8. 验收标准

第一版真实生成能力通过以下条件即可进入人工测试：

```text
1. 本地或云端 ComfyUI /system_stats 可访问
2. image_clone_video_v1 可生成 mp4 并入库
3. video_clone_clip_v1 可生成 mp4 并入库
4. 失败时任务状态变 failed，错误信息可见
5. 成功素材在“视频片段/用户资产”中与上传视频一视同仁
```
