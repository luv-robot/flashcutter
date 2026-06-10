import { expect, test } from '@playwright/test';

test('walks the operator guide flow with mocked backend data', async ({ page }) => {
  const now = new Date().toISOString();
  const state = {
    assets: [] as Array<{
      id: number;
      original_filename: string;
      stored_filename: string;
      file_path: string;
      status: string;
      created_at: string;
    }>,
    tasks: [] as Array<Record<string, unknown>>,
    outputs: [] as Array<Record<string, unknown>>
  };
  const templates = [
    template(101, '快速开场 + 证据展示'),
    template(102, '静音字幕版'),
    template(103, '产品细节特写')
  ];

  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    if (!url.pathname.startsWith('/api/')) {
      return route.continue();
    }

    if (url.pathname === '/api/auth/login' && method === 'POST') {
      return json(route, {
        access_token: 'test-token',
        token_type: 'bearer',
        user: { id: 99, phone: '+15550009999', display_name: '新手测试员' }
      });
    }
    if (url.pathname === '/api/auth/me') {
      return json(route, { id: 99, phone: '+15550009999', display_name: '新手测试员' });
    }
    if (url.pathname === '/api/assets' && method === 'GET') {
      return json(route, state.assets);
    }
    if (url.pathname === '/api/assets/upload' && method === 'POST') {
      state.assets = [
        {
          id: 501,
          original_filename: '新手测试-已授权竖版素材.mp4',
          stored_filename: 'asset-501.mp4',
          file_path: '/tmp/asset-501.mp4',
          status: 'ready',
          created_at: now
        }
      ];
      return json(route, state.assets[0]);
    }
    if (url.pathname === '/api/templates') {
      return json(route, templates);
    }
    if (url.pathname === '/api/tasks') {
      return json(route, state.tasks);
    }
    if (url.pathname === '/api/outputs/review') {
      return json(route, state.outputs);
    }
    if (url.pathname === '/api/music') {
      return json(route, [
        {
          id: 1,
          user_id: null,
          title: 'System Test Beat',
          original_filename: 'system-test.wav',
          stored_filename: 'system-test.wav',
          file_path: '/tmp/system-test.wav',
          mime_type: 'audio/wav',
          file_size_bytes: 1024,
          duration_seconds: 30,
          scope: 'system',
          artist: 'Flashcutter',
          license_name: 'Internal generated test audio',
          license_url: null,
          source_url: null,
          attribution_text: 'Generated test audio.',
          mood: 'test',
          bpm: null,
          is_active: true,
          created_at: now
        }
      ]);
    }
    if (url.pathname === '/api/ai-assets') {
      return json(route, []);
    }
    if (url.pathname.match(/^\/api\/assets\/501\/render-variants\/preflight$/)) {
      return json(route, {
        asset_id: 501,
        asset_filename: '新手测试-已授权竖版素材.mp4',
        asset_duration_seconds: 6,
        items: templates.slice(0, 2).map((item) => preflightItem(item))
      });
    }
    if (url.pathname.match(/^\/api\/assets\/501\/render-variants\/enqueue$/)) {
      state.tasks = templates.slice(0, 2).map((item, index) => ({
        id: 700 + index,
        name: `new-user-guide - ${item.name}`,
        production_run_id: 900,
        revision_number: 1,
        asset_id: 501,
        template_id: item.id,
        status: 'completed',
        progress_percent: 100,
        progress_message: '已完成，请审核',
        params_json: {}
      }));
      state.outputs = templates.slice(0, 2).map((item, index) => outputReview(item, index));
      return json(route, state.tasks);
    }
    if (url.pathname.match(/^\/api\/outputs\/80\d\/review$/) && method === 'PATCH') {
      const outputId = Number(url.pathname.split('/')[3]);
      state.outputs = state.outputs.map((output) =>
        output.output_id === outputId
          ? { ...output, review_status: 'approved', review_notes: '新手测试通过', reviewed_at: now }
          : output
      );
      return json(route, state.outputs.find((output) => output.output_id === outputId));
    }
    if (url.pathname === '/api/production-runs/900/package/estimate') {
      return json(route, {
        production_run_id: 900,
        package_name: 'flashcutter-run-900-new-user-guide',
        seed_filename: '新手测试-已授权竖版素材.mp4',
        seed_size_bytes: 1024,
        approved_output_count: state.outputs.filter((output) => output.review_status === 'approved').length,
        approved_output_size_bytes: 2048,
        total_size_bytes: 3072,
        missing_files: []
      });
    }

    return json(route, {});
  });

  await page.goto('/');
  await page.getByLabel('手机号').fill('+15550009999');
  await page.getByLabel('密码').fill('trial-secret');
  await page.getByRole('button', { name: '登录' }).click();

  await expect(page.getByText('首次试用清单')).toBeVisible();
  await page.getByRole('button', { name: '上传视频' }).click();
  await expect(page.getByText('素材导入')).toBeVisible();

  await page.setInputFiles('input[type="file"]', {
    name: '新手测试-已授权竖版素材.mp4',
    mimeType: 'video/mp4',
    buffer: Buffer.from('mock video payload')
  });
  await page.getByRole('button', { name: '上传' }).click();
  await expect(page.getByText('新手测试-已授权竖版素材.mp4')).toBeVisible();

  await page.getByRole('button', { name: '生产工作台' }).click();
  await page.getByRole('button', { name: '创建生产批次' }).click();
  await expect(page.getByRole('button', { name: '一个视频生成多版' })).toHaveClass(/selected-mode-card/);
  await page.getByRole('button', { name: '下一步' }).click();
  await expect(page.getByText('新手测试-已授权竖版素材.mp4')).toBeVisible();
  await page.getByRole('button', { name: '下一步' }).click();

  await page.getByText('快速开场 + 证据展示').click();
  await page.getByText('静音字幕版').click();
  await page.getByRole('button', { name: '下一步' }).click();
  await page.getByRole('button', { name: '下一步' }).click();
  await page.getByRole('button', { name: '运行预检' }).click();
  await expect(page.getByRole('heading', { name: '可入队' })).toBeVisible();
  await page.getByRole('button', { name: '前往入队' }).click();
  await page.getByRole('button', { name: '批量入队' }).click();
  await expect(page.getByText('去队列与失败')).toBeVisible();
  await page.getByRole('button', { name: '去队列与失败' }).click();
  await expect(page.getByText('已完成，待审核')).toBeVisible();

  await page.getByRole('button', { name: '审核' }).click();
  await expect(page.getByText('当前批次')).toBeVisible();
  await page.getByRole('button', { name: '通过' }).click();
  await expect(page.getByText('1 已通过')).toBeVisible();

  await page.getByRole('button', { name: '投放包', exact: true }).click();
  await page.getByLabel('商品 / 服务').fill('新手测试产品');
  await page.getByLabel('落地页').fill('https://example.com/landing');
  await page.getByLabel('行业').fill('食品饮料');
  await page.getByLabel('素材标题').fill('新手测试素材');
  await page.getByLabel('确认素材权利已完成').check();
  await expect(page.getByText('规格预检通过，可生成交付物。')).toBeVisible();
});

function template(id: number, title: string) {
  return {
    id,
    name: title,
    description: '新手测试模板',
    version: 1,
    is_builtin: true,
    json_spec: {
      schema_version: 2,
      type: 'variant_recipe',
      recipe_id: `test.${id}`,
      name: title,
      blueprint: {
        blueprint_id: `guide_${id}`,
        name: title,
        creative_goal: { title, audience: '冷启动人群', selling_points: ['真人实拍'], tone: '直接' },
        production_contract: {
          use_case: '用于上传前已完成授权确认的真人实拍素材第一轮试生产广告变体。',
          operator_notes: '新手测试模板。',
          review_checklist: ['前三秒清晰。', '主体没有被遮挡。']
        },
        editing: {
          cut_style: 'fixed_interval',
          clip_duration_seconds: 2,
          target_duration_seconds: 6,
          max_clip_count: 3,
          pacing: 'fast',
          keep_original_order: true
        },
        slots: [{ slot: 'hook', role: 'source_segment' }]
      },
      render_preset: {
        preset_id: 'vertical_9_16_cover',
        name: '9:16 竖屏',
        delivery: { aspect_ratio: '9:16', width: 1080, height: 1920, fps: 30, format: 'mp4', fit: 'cover' }
      },
      style_pack: { style_pack_id: 'clean_ad', name: 'Clean', transformations: {} },
      review_notes: '确认画面清晰且素材已授权。'
    }
  };
}

function preflightItem(templateItem: ReturnType<typeof template>) {
  return {
    asset_id: 501,
    asset_filename: '新手测试-已授权竖版素材.mp4',
    template_id: templateItem.id,
    template_name: templateItem.name,
    status: 'ready',
    title: templateItem.name,
    estimated_clip_count: 3,
    estimated_duration_seconds: 6,
    output_width: 1080,
    output_height: 1920,
    output_fps: 30,
    fit: 'cover',
    cover_region_count: 0,
    text_overlay_count: 0,
    ai_asset_slot_count: 0,
    selected_ai_asset_count: 0,
    ai_asset_slots: [],
    playback_speed: null,
    mute_audio: false,
    music_track_id: null,
    music_title: null,
    music_mode: null,
    music_volume: null,
    music_loop: false,
    warnings: [],
    missing_fields: []
  };
}

function outputReview(templateItem: ReturnType<typeof template>, index: number) {
  return {
    output_id: 800 + index,
    asset_id: 501,
    asset_filename: '新手测试-已授权竖版素材.mp4',
    production_run_id: 900,
    production_run_name: 'new-user-guide',
    production_run_status: 'in_review',
    revision_number: 1,
    task_id: 700 + index,
    task_name: `new-user-guide - ${templateItem.name}`,
    template_id: templateItem.id,
    template_name: templateItem.name,
    template_version: 1,
    render_plan_id: 600 + index,
    creative_goal: templateItem.json_spec.blueprint.creative_goal,
    production_contract: templateItem.json_spec.blueprint.production_contract,
    render_plan: {
      clips: [{ start: 0, end: 2 }],
      output: { width: 1080, height: 1920, fps: 30 },
      layout: { fit: 'cover' }
    },
    file_path: `/tmp/output-${index}.mp4`,
    duration_seconds: 6,
    file_size_bytes: 2048,
    status: 'ready',
    review_status: 'pending_review',
    review_notes: null,
    review_feedback: {},
    reviewed_at: null,
    created_at: new Date().toISOString()
  };
}

async function json(route: { fulfill: (response: { status: number; contentType: string; body: string }) => Promise<void> }, body: unknown) {
  return route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body)
  });
}
