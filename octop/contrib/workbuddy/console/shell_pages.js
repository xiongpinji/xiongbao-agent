/* 熊宝 Agent — full-page views: agents / projects / knowledge / settings */
(function () {
  const $ = (id) => document.getElementById(id);

  const VIEW_META = {
    chat: { title: "对话", primary: "" },
    agents: { title: "智能体", primary: "浏览技能市场" },
    projects: { title: "项目", primary: "新建项目" },
    knowledge: { title: "知识库", primary: "录入笔记" },
    tools: { title: "工具箱", primary: "打开运维" },
    team: { title: "团队协作", primary: "专家团" },
    settings: { title: "设置", primary: "运维控制台" },
  };

  const AGENT_FILTERS = ["全部", "办公", "开发", "分析", "创作", "研究"];
  const PROJ_FILTERS = ["全部", "进行中", "已完成", "已归档"];
  const ICON_CYCLE = ["chart", "code", "write", "star", "search", "settings", "rocket", "bot"];

  function escape(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  function ico(name) {
    return `<svg class="ico" aria-hidden="true"><use href="#i-${escape(name)}"/></svg>`;
  }

  function iconBox(name) {
    return `<div class="icon">${ico(name)}</div>`;
  }

  function setView(view) {
    const app = $("app");
    if (!app) return;
    app.dataset.view = view;
    document.querySelectorAll("#sideNav button").forEach((b) => {
      b.classList.toggle("active", b.dataset.view === view);
    });
    const isChat = view === "chat";
    app.classList.toggle("view-page", !isChat);
    app.classList.toggle("has-right", isChat);
    const host = $("pageHost");
    if (host) host.style.display = isChat ? "none" : "flex";
    if (!isChat) renderPage(view);
  }

  async function renderPage(view) {
    const meta = VIEW_META[view] || { title: view, primary: "" };
    $("pageTitle").textContent = meta.title;
    const btn = $("pagePrimaryBtn");
    btn.textContent = meta.primary || "操作";
    btn.style.display = meta.primary ? "" : "none";
    btn.onclick = () => onPrimary(view);
    const filters = $("pageFilters");
    const body = $("pageBody");
    filters.innerHTML = "";
    body.innerHTML = '<div class="empty">加载中…</div>';

    if (view === "agents") {
      filters.innerHTML = AGENT_FILTERS.map((f, i) =>
        `<button type="button" class="filter-pill ${i === 0 ? "active" : ""}" data-f="${escape(f)}">${escape(f)}</button>`
      ).join("");
      await renderAgents(body, "全部");
      filters.onclick = (e) => {
        const b = e.target.closest("[data-f]");
        if (!b) return;
        filters.querySelectorAll(".filter-pill").forEach((x) => x.classList.toggle("active", x === b));
        renderAgents(body, b.dataset.f);
      };
    } else if (view === "projects") {
      filters.innerHTML = PROJ_FILTERS.map((f, i) =>
        `<button type="button" class="filter-pill ${i === 0 ? "active" : ""}" data-f="${escape(f)}">${escape(f)}</button>`
      ).join("");
      await renderProjects(body);
    } else if (view === "knowledge") {
      await renderKnowledge(body);
    } else if (view === "tools") {
      body.innerHTML = `
        <div class="card-grid">
          <div class="agent-card" data-go="parity-models">${iconBox("brain")}<h3>模型档案</h3><p>切换本地 / 远程模型</p></div>
          <div class="agent-card" data-go="parity-channels">${iconBox("radio")}<h3>通道向导</h3><p>飞书 / 钉钉 / 企微配置</p></div>
          <div class="agent-card" data-go="parity-worktree">${iconBox("leaf")}<h3>仓库 Worktree</h3><p>并行任务目录</p></div>
          <div class="agent-card" data-go="ops">${iconBox("tool")}<h3>运维控制台</h3><p>Harbor / Runtime / 连接器</p></div>
        </div>`;
      body.onclick = (e) => {
        const c = e.target.closest("[data-go]");
        if (!c) return;
        if (c.dataset.go === "ops") location.href = "/ops.html";
        if (c.dataset.go === "parity-models") $("btnModels") && $("btnModels").click();
        if (c.dataset.go === "parity-channels") $("btnChannels") && $("btnChannels").click();
        if (c.dataset.go === "parity-worktree") $("btnWorktree") && $("btnWorktree").click();
      };
    } else if (view === "team") {
      body.innerHTML = `
        <div class="settings-panel" style="max-width:640px">
          <h2>专家团协作</h2>
          <p class="hint">多席专家编排可在壳内演练或实跑。也可从顶栏「专家团」打开。</p>
          <button type="button" class="btn" id="openTeamParity">打开专家团面板</button>
        </div>`;
      const t = $("openTeamParity");
      if (t) t.onclick = () => $("btnTeam") && $("btnTeam").click();
    } else if (view === "settings") {
      renderSettings(body);
    }
  }

  async function renderAgents(body, filter) {
    if (!window.wbApi) {
      body.innerHTML = '<div class="empty">请先登录</div>';
      return;
    }
    const data = await window.wbApi("/api/skills");
    const installed = new Set(data.installed || []);
    let skills = data.skills || [];
    if (filter && filter !== "全部") {
      const map = { 办公: /办公|office|ppt|doc|写/i, 开发: /code|dev|工程|开发|git/i, 分析: /数据|分析|analy/i, 创作: /创作|创意|内容|写/i, 研究: /研究|research|知识/i };
      const re = map[filter];
      if (re) skills = skills.filter((s) => re.test((s.name || "") + (s.description || "")));
    }
    body.innerHTML = skills.length
      ? `<div class="card-grid">${skills.map((s, i) => `
          <div class="agent-card" data-skill="${escape(s.id)}">
            ${iconBox(ICON_CYCLE[i % ICON_CYCLE.length])}
            <h3>${escape(s.name || s.id)}</h3>
            <p>${escape(s.description || "专业智能体技能")}</p>
            <p class="proj-meta" style="margin-top:8px">${installed.has(s.id) ? "已安装" : "可安装"}</p>
          </div>`).join("")}</div>`
      : `<div class="empty"><div class="empty-art"></div>暂无匹配的智能体</div>`;
    body.onclick = async (e) => {
      const card = e.target.closest("[data-skill]");
      if (!card) return;
      const id = card.dataset.skill;
      if (!installed.has(id)) {
        await window.wbApi("/api/skills/install", { method: "POST", body: JSON.stringify({ skill_id: id }) });
        window.wbToast && window.wbToast("已安装技能", "ok");
      }
      if (window.wbState && window.wbState.projectId) {
        await window.wbApi("/api/projects/" + encodeURIComponent(window.wbState.projectId) + "/skills/deposit", {
          method: "POST", body: JSON.stringify({ skill_id: id }),
        });
        window.wbToast && window.wbToast("已存入当前项目", "ok");
      } else {
        $("btnSkills") && $("btnSkills").click();
      }
      renderAgents(body, filter);
    };
    const prev = $("rightAgentPreview");
    if (prev) {
      prev.innerHTML = (data.skills || []).slice(0, 4).map((s, i) => `
        <div class="agent-card">
          ${iconBox(ICON_CYCLE[i % ICON_CYCLE.length])}
          <h3>${escape(s.name || s.id)}</h3>
        </div>`).join("");
    }
  }

  async function renderProjects(body) {
    if (!window.wbApi) return;
    const data = await window.wbApi("/api/projects");
    const rows = data.projects || [];
    body.innerHTML = rows.length
      ? `<div class="proj-list">${rows.map((p) => `
          <div class="proj-card" data-pid="${escape(p.project_id)}">
            ${iconBox("folder")}
            <div>
              <h3>${escape(p.name || p.project_id)}</h3>
              <p>${escape(p.description || "项目空间")}</p>
              <div class="proj-meta">${p.skill_count || 0} 个技能 · ${escape(p.project_id)}</div>
            </div>
            <span class="chip muted">打开</span>
          </div>`).join("")}</div>`
      : `<div class="empty"><div class="empty-art"></div>暂无项目，点击右上角新建</div>`;
    body.onclick = (e) => {
      const c = e.target.closest("[data-pid]");
      if (!c) return;
      const sel = $("projectSelect");
      if (sel) {
        sel.value = c.dataset.pid;
        sel.dispatchEvent(new Event("change"));
      }
      setView("chat");
      $("btnProjects") && $("btnProjects").click();
    };
  }

  async function renderKnowledge(body) {
    if (!window.wbApi) return;
    let lib = { entries: [], tree: [], knowledge_files: [] };
    try { lib = await window.wbApi("/api/library"); } catch (_) {}
    const entries = lib.entries || [];
    const files = lib.knowledge_files || [];
    body.innerHTML = `
      <div class="card-grid">
        ${entries.map((e) => `
          <div class="kb-card">
            ${iconBox("folder")}
            <h3>${escape(e.title || e.entry_id)}</h3>
            <p>${escape(e.path || "")}</p>
            <div class="proj-meta" style="margin-top:8px">${e.size || 0} B · ${escape((e.indexed_at || "").slice(0, 10))}</div>
          </div>`).join("")}
        ${files.map((f) => `
          <div class="kb-card">
            ${iconBox("file")}
            <h3>${escape(f.path.split("/").pop())}</h3>
            <p>${escape(f.path)}</p>
            <div class="proj-meta" style="margin-top:8px">${f.bytes || 0} B</div>
          </div>`).join("")}
      </div>
      ${!(entries.length || files.length) ? '<div class="empty"><div class="empty-art"></div>知识库为空，点击「录入笔记」开始</div>' : ""}`;
  }

  function renderSettings(body) {
    const prefs = {
      autostart: localStorage.getItem("xb_pref_autostart") === "1",
      notify: localStorage.getItem("xb_pref_notify") !== "0",
      voice: localStorage.getItem("xb_pref_voice") === "1",
    };
    body.innerHTML = `
      <div class="settings-layout">
        <div class="settings-nav">
          <button type="button" class="active" data-sec="profile">个人资料</button>
          <button type="button" data-sec="account">账号管理</button>
          <button type="button" data-sec="appear">外观</button>
          <button type="button" data-sec="about">关于</button>
        </div>
        <div class="settings-panel" id="settingsPanel">
          <h2>个人资料</h2>
          <div class="setting-row">
            <div><div class="label" id="setUser">—</div><div class="desc">当前登录用户</div></div>
            <button type="button" class="btn ghost" id="setEditUser">刷新</button>
          </div>
          <div class="setting-row">
            <div><div class="label">开机自启</div><div class="desc">桌面端可选；Web 壳仅本地记忆</div></div>
            <button type="button" class="toggle ${prefs.autostart ? "on" : ""}" data-pref="autostart" aria-label="开机自启"></button>
          </div>
          <div class="setting-row">
            <div><div class="label">任务完成通知</div><div class="desc">完成后弹出提示</div></div>
            <button type="button" class="toggle ${prefs.notify ? "on" : ""}" data-pref="notify" aria-label="通知"></button>
          </div>
          <div class="setting-row">
            <div><div class="label">语音提醒</div><div class="desc">实验性</div></div>
            <button type="button" class="toggle ${prefs.voice ? "on" : ""}" data-pref="voice" aria-label="语音"></button>
          </div>
          <div class="setting-row">
            <div><div class="label">默认模型</div><div class="desc">在模型档案中切换</div></div>
            <button type="button" class="btn ghost" id="setModels">模型档案</button>
          </div>
          <div class="setting-row">
            <div><div class="label">运维控制台</div><div class="desc">Harbor / Runtime / 连接器</div></div>
            <a class="btn ghost" href="/ops.html">打开</a>
          </div>
        </div>
      </div>`;
    const u = $("userNameLabel");
    const su = $("setUser");
    if (su && u) su.textContent = u.textContent || "—";
    body.querySelectorAll(".toggle").forEach((t) => {
      t.onclick = () => {
        t.classList.toggle("on");
        const key = t.dataset.pref;
        const on = t.classList.contains("on");
        localStorage.setItem("xb_pref_" + key, on ? "1" : "0");
      };
    });
    const m = $("setModels");
    if (m) m.onclick = () => $("btnModels") && $("btnModels").click();
  }

  function onPrimary(view) {
    if (view === "agents") $("btnSkills") && $("btnSkills").click();
    if (view === "projects") $("btnNewProject") && $("btnNewProject").click();
    if (view === "knowledge") $("btnKnowledge") && $("btnKnowledge").click();
    if (view === "tools" || view === "settings") location.href = "/ops.html";
    if (view === "team") $("btnTeam") && $("btnTeam").click();
  }

  function syncChrome() {
    const map = [
      ["sessionChip", "sessionChipSide"],
      ["projectChip", "projectChipSide"],
      ["modelChip", "modelChipComposer"],
    ];
    map.forEach(([a, b]) => {
      const src = $(a);
      const dst = $(b);
      if (src && dst) dst.textContent = src.textContent;
    });
    const session = $("sessionChip");
    const name = $("userNameLabel");
    if (session && name) {
      const t = session.textContent || "";
      name.textContent = t.includes("·") ? t.split("·").pop().trim() : (t || "未登录");
      const av = $("userAvatar");
      if (av) av.textContent = (name.textContent || "宝").slice(0, 1);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const nav = $("sideNav");
    if (nav) {
      nav.addEventListener("click", (e) => {
        const b = e.target.closest("button[data-view]");
        if (b) setView(b.dataset.view);
      });
    }
    const logout = $("btnSidebarLogout");
    if (logout) logout.onclick = () => $("btnLogout") && $("btnLogout").click();

    document.querySelectorAll(".quick-actions [data-qa]").forEach((b) => {
      b.addEventListener("click", () => {
        if (b.dataset.qa === "chat") {
          setView("chat");
          $("composer") && $("composer").focus();
        } else if (b.dataset.qa === "file") {
          $("fileInput") && $("fileInput").click();
        } else if (b.dataset.qa === "write") {
          setView("chat");
          const c = $("composer");
          if (c) { c.value = "请帮我写一份："; c.focus(); }
        }
      });
    });

    ["toolWeb", "toolThink", "toolKb"].forEach((id) => {
      const el = $(id);
      if (!el) return;
      el.addEventListener("click", () => {
        const c = $("composer");
        if (!c) return;
        const tips = {
          toolWeb: "【网页搜索】请结合公开资料：",
          toolThink: "【深度思考】请分步推理后再给结论：",
          toolKb: "【知识库】请优先引用本地资料：",
        };
        c.value = (tips[id] || "") + c.value;
        c.focus();
      });
    });

    const obs = new MutationObserver(syncChrome);
    ["sessionChip", "projectChip", "modelChip"].forEach((id) => {
      const el = $(id);
      if (el) obs.observe(el, { childList: true, characterData: true, subtree: true });
    });
    syncChrome();
    setInterval(syncChrome, 1500);

    setTimeout(async () => {
      if (!window.wbApi) return;
      try {
        const data = await window.wbApi("/api/skills");
        const prev = $("rightAgentPreview");
        if (!prev) return;
        prev.innerHTML = (data.skills || []).slice(0, 4).map((s, i) => `
          <div class="agent-card">
            ${iconBox(ICON_CYCLE[i % ICON_CYCLE.length])}
            <h3>${escape(s.name || s.id)}</h3>
          </div>`).join("");
      } catch (_) { /* ignore */ }
    }, 800);

    const pcs = $("projectChipSide");
    if (pcs) pcs.addEventListener("click", () => $("btnProjects") && $("btnProjects").click());

    window.xbSetView = setView;
  });
})();
