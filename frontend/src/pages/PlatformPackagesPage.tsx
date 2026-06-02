import { productionRunPackageUrl } from '../api/client';
import type { OutputReview } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

type PlatformPackagesPageProps = {
  outputs: OutputReview[];
};

const platforms = ['巨量引擎', '腾讯广告', '阿里广告平台'];

export function PlatformPackagesPage({ outputs }: PlatformPackagesPageProps) {
  const approvedOutputs = outputs.filter((output) => output.review_status === 'approved');
  const packages = groupApprovedOutputs(approvedOutputs);

  return (
    <section className="platform-package-page">
      <div className="panel package-flow-panel">
        <div>
          <div className="panel-kicker">投放包</div>
          <h2>平台投放包</h2>
          <p>选择过审视频，完成平台规格预检后导出或推送。</p>
        </div>
        <div className="package-steps" aria-label="投放包流程">
          {['选择过审视频', '选择平台', '填写投放信息', '规格预检', '生成投放包', '推送或导出'].map(
            (step, index) => (
              <span key={step} className={index === 0 ? 'current-package-step' : ''}>
                {step}
              </span>
            )
          )}
        </div>
      </div>

      <div className="workspace-grid package-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>平台</h2>
              <p>先生成交付包，API 推送在接口层接入后启用。</p>
            </div>
          </div>
          <div className="platform-list">
            {platforms.map((platform, index) => (
              <button
                key={platform}
                className={index === 0 ? 'selected-output' : ''}
                type="button"
              >
                {platform}
              </button>
            ))}
          </div>
        </section>

        <section className="panel wide">
          <div className="panel-header">
            <div>
              <h2>过审视频</h2>
              <p>{approvedOutputs.length} 条视频可进入投放包。</p>
            </div>
            <StatusBadge value={approvedOutputs.length > 0 ? 'ready' : 'draft'} />
          </div>
          <div className="package-card-list">
            {packages.length === 0 ? (
              <p className="empty-state">暂无过审视频。</p>
            ) : (
              packages.map((item) => (
                <article key={item.key} className="package-card">
                  <div>
                    <strong>{item.title}</strong>
                    <span>
                      {item.outputs.length} 条过审视频 · {item.assetFilename}
                    </span>
                  </div>
                  <div className="package-form-grid">
                    <label>
                      商品 / 服务
                      <input placeholder="例如：新品活动套装" />
                    </label>
                    <label>
                      落地页
                      <input placeholder="https://..." />
                    </label>
                    <label>
                      行业
                      <input placeholder="例如：食品饮料" />
                    </label>
                    <label>
                      素材标题
                      <input placeholder="用于平台素材管理" />
                    </label>
                  </div>
                  <div className="package-status-line">
                    <StatusBadge value="ready" />
                    <span>规格预检：可导出，推送接口待配置。</span>
                  </div>
                  <div className="button-row">
                    {item.productionRunId ? (
                      <a
                        className="button-link primary-link"
                        href={productionRunPackageUrl(item.productionRunId)}
                      >
                        生成投放包
                      </a>
                    ) : (
                      <button className="primary-action" type="button" disabled>
                        生成投放包
                      </button>
                    )}
                    <button className="secondary-action" type="button" disabled>
                      推送到平台
                    </button>
                    <button className="secondary-action" type="button" disabled>
                      导出预检报告
                    </button>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>
      </div>
    </section>
  );
}

function groupApprovedOutputs(outputs: OutputReview[]) {
  const map = new Map<
    string,
    {
      key: string;
      title: string;
      assetFilename: string;
      productionRunId: number | null;
      outputs: OutputReview[];
    }
  >();
  outputs.forEach((output) => {
    const key = output.production_run_id
      ? `run-${output.production_run_id}`
      : `asset-${output.asset_id}`;
    const current =
      map.get(key) ??
      {
        key,
        title: output.production_run_name || output.asset_filename,
        assetFilename: output.asset_filename,
        productionRunId: output.production_run_id,
        outputs: []
      };
    current.outputs.push(output);
    map.set(key, current);
  });
  return Array.from(map.values());
}
