/**
 * Cloudflare Worker：football-jp の毎朝データ更新ジョブを起動
 *
 * GitHub Actions の `schedule` トリガーは遅延・スキップが多いため、
 * Cloudflare Cron で正確な時刻に workflow_dispatch を叩く構成。
 *
 * 環境変数（Secret）:
 *  - GITHUB_PAT: fine-grained personal access token (Actions: write)
 *
 * Cron: 0 22 * * * UTC = 7:00 JST 毎日
 */

interface Env {
  GITHUB_PAT: string;
}

const REPO_OWNER = "totnet31";
const REPO_NAME = "football-jp";
const WORKFLOW_FILE = "fetch.yml";
const REF = "main";

export default {
  async scheduled(_event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(triggerWorkflow(env));
  },

  // 動作確認用 HTTP エンドポイント
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/trigger") {
      const result = await triggerWorkflow(env);
      return new Response(JSON.stringify(result, null, 2), {
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(
      "football-jp cron trigger\n\nNext run: 7:00 JST every morning\nManual trigger: GET /trigger\n",
      { headers: { "Content-Type": "text/plain; charset=utf-8" } }
    );
  },
};

async function triggerWorkflow(env: Env) {
  const apiUrl = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW_FILE}/dispatches`;
  const body = JSON.stringify({ ref: REF });
  const res = await fetch(apiUrl, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_PAT}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": "football-jp-cron-trigger",
    },
    body,
  });
  const ok = res.status === 204;
  const text = ok ? "" : await res.text();
  console.log(`workflow_dispatch: status=${res.status}, ok=${ok}, body=${text.slice(0, 300)}`);
  return {
    triggered_at: new Date().toISOString(),
    status: res.status,
    ok,
    error: ok ? null : text.slice(0, 500),
  };
}
