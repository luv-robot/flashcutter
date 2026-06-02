# Template Component Library：广告组件参考库 v0.1

## 1. 定位

组件参考库用于把广告、电商海报、投放素材页里的典型结构沉淀成可理解、可复用的模板组件灵感。

默认规则：

```text
外部素材站页面 = 参考与拆解
已授权 / 自有 / 开放许可素材 = 可进入生产
```

系统不默认下载花瓣网等素材站图片，也不把它们当成可直接用于广告生产的素材。导入 URL 时只保存来源、标题、远程预览 URL、标签、组件类型和操作备注。

## 2. 组件类型

第一批典型组件：

```text
poster_layout       整张电商海报版式
product_card        商品卡片 / 产品主视觉区
headline_block      大标题 / 卖点标题
price_tag           价格标签 / 到手价
coupon_strip        优惠券条 / 满减条
cta_panel           行动按钮区 / 立即购买
benefit_points      卖点列表
review_card         用户评价卡片
frame_overlay       视频图片框 / 包装边框
logo_watermark      品牌标识 / 角标
bottom_caption_zone 底部字幕安全区
```

## 3. 权利状态

```text
reference_only  仅参考，不可生产使用
needs_review    需要人工确认权利
licensed        已取得授权
owned           自有素材
public_domain   公有领域
cc_by           CC BY，可按署名要求使用
```

运营导入花瓣、站酷、Pinterest、淘宝详情页截图等来源时，默认使用 `reference_only`。

## 4. 导入流程

1. 进入“组件参考”。
2. 粘贴素材页 URL，例如 `https://huaban.com/pins/7094417768`。
3. 选择组件类型、行业和标签。
4. 系统尝试读取 Open Graph 元信息。
5. 成功时展示远程预览图；失败时保留 URL 和备注，等待人工补全。
6. 设计人员把参考项拆成模板 v3 操作，如前贴片、后贴片、图片框、标题块、价格标签和 CTA 区。

## 5. 与模板 v3 的关系

组件参考库不替代模板。它的作用是帮助设计/运营把外部创意语言翻译成可复用结构：

```text
参考海报
→ 拆成组件：标题块 + 商品区 + 利益点 + CTA
→ 写入模板 v3：intro_card / outro_card / image_frame / text_placeholder
→ 在变体生产中批量套用到一批视频
```

## 6. 工程入口

API：

```http
GET /api/creative-references
POST /api/creative-references
POST /api/creative-references/import-url
```

脚本：

```bash
cd backend
./.venv/bin/python scripts/import_creative_references.py \
  https://huaban.com/pins/7094417768 \
  --component-type poster_layout \
  --tag 电商 \
  --tag 海报
```
