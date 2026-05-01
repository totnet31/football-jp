const REPO = "totnet31/football-jp";
const WORKFLOW = "fetch.yml";

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(trigger(env));
  },
  async fetch(_req, env) {
    const r = await trigger(env);
    return new Response(JSON.stringify(r), { headers: { "Content-Type": "application/json" } });
  }
};

async function trigger(env) {
  const res = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.GITHUB_PAT}`,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "football-jp-cron"
      },
      body: JSON.stringify({ ref: "main" })
    }
  );
  return { triggered_at: new Date().toISOString(), status: res.status, ok: res.status === 204 };
}
