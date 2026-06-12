import { expect, test } from '@playwright/test';

test('keeps one custom strong-opening copy per line', async ({ page }) => {
  let preflightPayload: Record<string, unknown> | null = null;
  const now = new Date().toISOString();
  const asset = {
    id: 25,
    original_filename: '美团-神券节-zy-0415004.mp4',
    stored_filename: 'asset-25.mp4',
    file_path: '/tmp/asset-25.mp4',
    status: 'ready',
    created_at: now
  };

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
        user: { id: 99, phone: '+15550000999', display_name: '线上验收账号' }
      });
    }
    if (url.pathname === '/api/auth/me') {
      return json(route, { id: 99, phone: '+15550000999', display_name: '线上验收账号' });
    }
    if (url.pathname === '/api/assets') {
      return json(route, [asset]);
    }
    if (url.pathname === '/api/templates') {
      return json(route, [template()]);
    }
    if (url.pathname === '/api/tasks' || url.pathname === '/api/outputs/review') {
      return json(route, []);
    }
    if (url.pathname === '/api/music' || url.pathname === '/api/ai-assets') {
      return json(route, []);
    }
    if (url.pathname === '/api/expansion-plans/strong-opening/copy-suggestions') {
      return json(route, {
        provider: 'openai_compatible',
        model: 'deepseek-v4-flash',
        suggestions: [
          copySuggestion('优惠信息清楚，一眼看明白', 1),
          copySuggestion('短视频投放测试，试试这个', 2),
          copySuggestion('别划走！优惠信息清楚', 3)
        ],
        warnings: []
      });
    }
    if (url.pathname === '/api/expansion-runs/strong-opening/preflight') {
      preflightPayload = JSON.parse(request.postData() ?? '{}');
      return json(route, {
        preflight_token: 'strong-opening-token',
        summary: {
          asset_count: 1,
          template_count: 1,
          task_count: 3,
          ready_count: 3,
          warning_count: 0,
          blocked_count: 0
        },
        items: [],
        suggestions: [],
        runtime_values: {},
        output_preset_id: 'vertical_9_16_cover',
        name_prefix: 'strong-opening',
        template_id: 101,
        template_name: '强开场文字扩量',
        warnings: []
      });
    }

    return json(route, {});
  });

  await page.goto('/');
  await page.getByLabel('手机号').fill('+15550000999');
  await page.getByLabel('密码').fill('trial-secret');
  await page.getByRole('button', { name: '登录' }).click();

  await page.getByRole('button', { name: '创建生产批次' }).first().click();
  await page.getByRole('button', { name: '关闭' }).first().click();
  await page.getByRole('button', { name: '开始强开场扩量' }).click();

  await page.getByLabel('目标数量').fill('3');
  await page.getByLabel('商品 / 项目名').fill('线上验收商品');
  await page.getByLabel('卖点 / 痛点').fill('优惠信息清楚\n适合短视频投放测试');
  await page.getByRole('button', { name: '生成 AI 建议版' }).click();
  await expect(page.getByText('已生成 3 条建议。可以编辑后预检。')).toBeVisible();

  await page.getByLabel('我的文字方案').fill('先看优惠，三秒讲清\n这条素材先看结果\n别划走，重点在这里');
  await page.getByRole('button', { name: '替换 AI 建议' }).click();
  await expect(page.getByText('已替换为 3 条自定义开场文字。')).toBeVisible();
  await expect(page.locator('.opening-copy-card')).toHaveCount(3);

  await page.getByRole('button', { name: '运行预检' }).click();
  await expect(page.getByText('预检完成：3 个任务，0 个阻塞。')).toBeVisible();

  expect(preflightPayload?.opening_texts).toEqual([
    '先看优惠，三秒讲清',
    '这条素材先看结果',
    '别划走，重点在这里'
  ]);
});

function copySuggestion(text: string, index: number) {
  return {
    id: `copy-${index}`,
    text,
    angle: 'result_first',
    source: 'openai_compatible',
    risk_level: 'low',
    length_level: 'short',
    locked: false
  };
}

function template() {
  return {
    id: 101,
    name: '强开场文字扩量',
    description: '强开场测试模板',
    version: 1,
    is_builtin: true,
    json_spec: {
      schema_version: 2,
      type: 'variant_recipe',
      recipe_id: 'strong_opening.test',
      name: '强开场文字扩量',
      blueprint: {
        blueprint_id: 'strong_opening',
        name: '强开场文字扩量',
        creative_goal: { title: '强开场文字扩量' },
        production_contract: {
          use_case: '把一条已授权视频扩成多条强开场变体。',
          operator_notes: '使用已授权素材。',
          review_checklist: ['开场文字清晰。']
        },
        editing: {
          cut_style: 'fixed_interval',
          clip_duration_seconds: 2,
          target_duration_seconds: 6,
          max_clip_count: 3
        },
        slots: []
      },
      render_preset: {
        preset_id: 'vertical_9_16_cover',
        name: '9:16 竖屏',
        delivery: { aspect_ratio: '9:16', width: 1080, height: 1920, fps: 30, format: 'mp4', fit: 'cover' }
      },
      style_pack: { style_pack_id: 'clean_ad', name: 'Clean', transformations: {} },
      review_notes: '确认开场文字可读。'
    }
  };
}

async function json(
  route: { fulfill: (response: { status: number; contentType: string; body: string }) => Promise<void> },
  body: unknown
) {
  return route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body)
  });
}
