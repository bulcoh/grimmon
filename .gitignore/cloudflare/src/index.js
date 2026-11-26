const json = (o, status = 200) =>
  new Response(JSON.stringify(o), { status, headers: { "Content-Type": "application/json" } });

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (req.headers.get("X-Key") !== env.KEY) return json({}, 403);

    if (req.method === "GET" && url.pathname === "/board") {
      const day = url.searchParams.get("day") || "";
      const q = url.searchParams.get("tab") === "today"
        ? env.DB.prepare("select uid,name,cm,grid,day,today from b where day=? order by today desc limit 50").bind(day)
        : env.DB.prepare("select uid,name,cm,grid,day,today from b order by cm desc limit 50");
      const { results } = await q.all();
      return json(results);
    }
    if (req.method === "POST" && url.pathname === "/submit") {
      let d; try { d = await req.json(); } catch { return json({}, 400); }
      const uid = String(d.uid ?? "").slice(0, 64), name = String(d.name ?? "").slice(0, 20);
      const cm = Number(d.cm), grid = String(d.grid ?? ""), day = String(d.day ?? "").slice(0, 10), today = Number(d.today) || 0;
      if (!uid || grid.length !== 1024 || !(cm >= 0 && cm < 1e9)) return json({}, 400);
      if (await env.DB.prepare("select 1 from banned where uid=?").bind(uid).first()) return json({ ok: 1 });  // 차단된 uid는 조용히 무시
      await env.DB.prepare(
        "insert into b(uid,name,cm,grid,day,today) values(?,?,?,?,?,?) on conflict(uid) do update set " +
        "name=excluded.name, cm=max(cm, excluded.cm), grid=excluded.grid, day=excluded.day, today=excluded.today")
        .bind(uid, name, cm, grid, day, today).run();
      return json({ ok: 1 });
    }
    return json({}, 404);
  },
};
