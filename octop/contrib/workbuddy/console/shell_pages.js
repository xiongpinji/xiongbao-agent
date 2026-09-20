/* 熊宝 Agent — WorkBuddy 布局交互（对接现有 API） */
(function () {
  const $ = (id) => document.getElementById(id);

  const VIEW_META = {
    chat: { title: "助理", primary: "" },
    projects: { title: "项目", primary: "+ 新建项目", sub: "多人协同，打造超级团队" },
    market: { title: "专家", primary: "我的专家", sub: "" },
    cron: { title: "定时任务", primary: "添加定时任务", sub: "" },
    knowledge: { title: "资料库", primary: "", sub: "" },
    settings: { title: "设置", primary: "", sub: "" },
    agents: { title: "专家", primary: "我的专家" },
    tools: { title: "连接器", primary: "" },
    team: { title: "专家团", primary: "" },
  };

  const BP_CASES = [
    ["基金组合健康诊断", "radar"],
    ["品牌与潮玩商业模式", "toy"],
    ["投资人交流金句速写", "note"],
    ["大模型全景评测", "geo"],
    ["本月经营复盘报告", "chart"],
    ["公众号创刊推文", "doc"],
    ["销售数据分析仪表盘", "dash"],
    ["交互式滚动叙事页", "story"],
  ];

  let marketTab = "experts";
  let bpOffset = 0;

  function escape(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }
  function ico(name) {
    return `<svg class="ico" aria-hidden="true"><use href="#i-${escape(name)}"/></svg>`;
  }

  function syncAssistantHome() {
    const app = $("app");
    if (!app) return;
    const view = app.dataset.view || "chat";
    const hasTask = !!(window.wbState && window.wbState.current);
    const isChat = view === "chat";
    const home = isChat && !hasTask;
    app.classList.toggle("home-mode", home);
    app.classList.toggle("has-right", isChat && hasTask);
    app.classList.toggle("view-library", view === "knowledge");
    const ah = $("assistantHome");
    if (ah) ah.style.display = home ? "flex" : "none";
  }

  function goHome() {
    if (window.wbState) {
      window.wbState.current = null;
      window.wbState.currentStatus = "";
    }
    const title = $("taskTitle");
    if (title) title.textContent = "选择或新建任务";
    const msgs = $("messages");
    if (msgs) {
      msgs.innerHTML = `<div class="empty">
        <img class="empty-mascot" src="/console/assets/mascot.svg" alt="" width="72" height="72" />
        <div class="empty-title">今天想让我帮你做什么？</div>
        <div class="empty-sub">从首页快捷入口开始，或新建任务</div>
      </div>`;
    }
    setView("chat");
  }

  function setView(view, opts) {
    const app = $("app");
    if (!app) return;
    if (view === "more") return;
    if (view === "agents" || view === "team" || view === "tools") {
      marketTab = view === "tools" ? "connectors" : "experts";
      view = "market";
    }
    // 点「助理」回到 Prompt-first 首页（WorkBuddy 行为）
    if (view === "chat" && opts && opts.home) {
      if (window.wbState) {
        window.wbState.current = null;
        window.wbState.currentStatus = "";
      }
    }
    app.dataset.view = view;
    document.querySelectorAll("#sideNav [data-view]").forEach((b) => {
      b.classList.toggle("active", b.dataset.view === view);
    });
    if (opts && opts.market) marketTab = opts.market;
    const isChat = view === "chat";
    app.classList.toggle("view-page", !isChat);
    app.classList.toggle("view-library", view === "knowledge");
    const host = $("pageHost");
    if (host) host.style.display = isChat ? "none" : "flex";
    syncAssistantHome();
    if (!isChat) renderPage(view);
  }

  function openModal(html, wide) {
    const mask = $("wbModalMask");
    const box = $("wbModal");
    if (!mask || !box) return;
    box.className = "wb-modal" + (wide ? " wide" : "");
    box.innerHTML = html;
    mask.classList.add("show");
  }
  function closeModal() {
    const mask = $("wbModalMask");
    if (mask) mask.classList.remove("show");
  }

  function openSettingsModal() {
    openModal(`
      <div class="wb-modal settings" style="display:grid;grid-template-columns:200px 1fr;padding:0;width:min(880px,100%)">
        <div class="settings-side">
          <button type="button" class="active" data-sec="general">通用</button>
          <button type="button" data-sec="personal">个性化</button>
          <button type="button" data-sec="model">模型</button>
          <button type="button" data-sec="about">关于</button>
        </div>
        <div class="settings-main" id="settingsMainPane">
          <h3>通用</h3>
          <div class="field-row"><div>语言</div><span class="chip muted">简体中文</span></div>
          <div class="field-row"><div>开机自启</div><button type="button" class="toggle on" data-pref="autostart"></button></div>
          <div class="field-row"><div>任务完成通知</div><button type="button" class="toggle on" data-pref="notify"></button></div>
          <div class="field-row"><div>自动更新技能</div><button type="button" class="toggle on" data-pref="autoupdate"></button></div>
          <div class="field-row"><div>运维控制台</div><a class="btn ghost" href="/ops.html">打开</a></div>
        </div>
      </div>`, true);
    const side = document.querySelector(".settings-side");
    if (side) {
      side.onclick = (e) => {
        const b = e.target.closest("[data-sec]");
        if (!b) return;
        side.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
        const pane = $("settingsMainPane");
        if (!pane) return;
        if (b.dataset.sec === "personal") {
          pane.innerHTML = `<h3>个性化</h3>
            <div class="field-row"><div>回复风格</div><span class="chip muted">默认</span></div>
            <div class="field-row"><div>加载欢迎语</div><button type="button" class="toggle on"></button></div>
            <label class="field">自定义指令<textarea rows="4" placeholder="例如：先给结论"></textarea></label>`;
        } else if (b.dataset.sec === "model") {
          pane.innerHTML = `<h3>模型</h3><div class="field-row"><div>默认模型</div><button type="button" class="btn ghost" id="setModels2">模型档案</button></div>`;
          const m = $("setModels2");
          if (m) m.onclick = () => $("btnModels") && $("btnModels").click();
        } else if (b.dataset.sec === "about") {
          pane.innerHTML = `<h3>关于</h3><p class="hint">熊宝 Agent · 私有化工作台<br>交互对齐 WorkBuddy，视觉为熊宝暗金。</p>`;
        } else {
          pane.innerHTML = `<h3>通用</h3>
            <div class="field-row"><div>语言</div><span class="chip muted">简体中文</span></div>
            <div class="field-row"><div>开机自启</div><button type="button" class="toggle on"></button></div>
            <div class="field-row"><div>运维控制台</div><a class="btn ghost" href="/ops.html">打开</a></div>`;
        }
      };
    }
  }

  function openNewProjectModal() {
    openModal(`
      <div class="wb-modal-hd"><h2>新建项目</h2><button type="button" class="icon-btn" id="modalClose" aria-label="关闭">×</button></div>
      <label class="field">项目名称<input id="npName" maxlength="15" placeholder="请输入项目名称" /><span class="hint" id="npCount">0/15</span></label>
      <label class="field">指令<textarea id="npInstr" rows="4" placeholder="提供项目背景、规范、团队习惯与输出约束，让 AI 回复更准确"></textarea></label>
      <div class="field-row"><div>连接器（可选）</div><button type="button" class="btn ghost" id="npConn">+ 添加</button></div>
      <div class="field-row"><div>专家（可选）</div><button type="button" class="btn ghost" id="npExp">+ 添加</button></div>
      <div class="field-row"><div>技能（可选）</div><button type="button" class="btn ghost" id="npSkill">+ 添加</button></div>
      <p class="hint">切换模板会覆盖当前编辑内容</p>
      <div class="wb-modal-ft">
        <button type="button" class="btn ghost" id="npCancel">取消</button>
        <button type="button" class="btn" id="npOk">确定</button>
      </div>`);
    const name = $("npName");
    const cnt = $("npCount");
    if (name && cnt) name.oninput = () => { cnt.textContent = name.value.length + "/15"; };
    $("modalClose") && ($("modalClose").onclick = closeModal);
    $("npCancel") && ($("npCancel").onclick = closeModal);
    $("npOk") && ($("npOk").onclick = async () => {
      const n = (name && name.value.trim()) || "";
      if (!n) return;
      if (!window.wbApi) return;
      await window.wbApi("/api/projects", { method: "POST", body: JSON.stringify({ name: n, description: ($("npInstr") && $("npInstr").value) || "" }) });
      window.wbToast && window.wbToast("项目已创建", "ok");
      closeModal();
      setView("projects");
    });
    $("npExp") && ($("npExp").onclick = () => openPickExpert());
    $("npSkill") && ($("npSkill").onclick = () => openPickSkill());
    $("npConn") && ($("npConn").onclick = () => openPickConnector());
  }

  function openPickExpert() {
    openModal(`
      <div class="wb-modal-hd"><h2>选择专家</h2>
        <div class="search-wrap" style="width:220px"><svg class="ico search-ico"><use href="#i-search"/></svg><input class="search" placeholder="搜索专家职称或描述" /></div>
        <button type="button" class="icon-btn" id="modalCloseX">×</button>
      </div>
      <div class="market-tabs"><button class="active">专家</button><button type="button">我的专家</button></div>
      <div class="page-filters">${["全部","腾讯专家","产品设计","技术工程","金融投资"].map((t,i)=>`<button type="button" class="filter-pill ${i===0?"active":""}">${t}</button>`).join("")}</div>
      <div class="expert-grid" id="pickExpertGrid"></div>
      <div class="wb-modal-ft"><button type="button" class="btn ghost" id="pickCancel">取消</button><button type="button" class="btn" id="pickOk">确认</button></div>
    `, true);
    $("modalCloseX") && ($("modalCloseX").onclick = closeModal);
    $("pickCancel") && ($("pickCancel").onclick = closeModal);
    $("pickOk") && ($("pickOk").onclick = closeModal);
    fillExpertGrid($("pickExpertGrid"));
  }

  function openPickSkill() {
    openModal(`
      <div class="wb-modal-hd"><h2>选择技能</h2>
        <div class="search-wrap" style="width:200px"><svg class="ico search-ico"><use href="#i-search"/></svg><input class="search" placeholder="搜索技能" /></div>
        <button type="button" class="icon-btn" id="modalCloseX">×</button>
      </div>
      <div class="market-tabs"><button class="active">推荐</button><button>SkillHub</button><button>已安装</button></div>
      <div class="page-filters">${["全部","办公协同","开发工具","效率工具","数据分析"].map((t,i)=>`<button type="button" class="filter-pill ${i===0?"active":""}">${t}</button>`).join("")}</div>
      <div class="expert-grid" id="pickSkillGrid"></div>
      <div class="wb-modal-ft"><button type="button" class="btn ghost" id="pickCancel">取消</button><button type="button" class="btn" id="pickOk">确认</button></div>
    `, true);
    $("modalCloseX") && ($("modalCloseX").onclick = closeModal);
    $("pickCancel") && ($("pickCancel").onclick = closeModal);
    $("pickOk") && ($("pickOk").onclick = closeModal);
    fillSkillGrid($("pickSkillGrid"));
  }

  function openPickConnector() {
    openModal(`
      <div class="wb-modal-hd"><h2>添加个人授权连接器</h2><button type="button" class="icon-btn" id="modalCloseX">×</button></div>
      <p class="hint">添加后成员可用个人账号授权连接。</p>
      <div id="connList" style="display:grid;gap:8px;max-height:360px;overflow:auto"></div>
      <div class="wb-modal-ft"><button type="button" class="btn" id="pickOk">完成</button></div>
    `);
    $("modalCloseX") && ($("modalCloseX").onclick = closeModal);
    $("pickOk") && ($("pickOk").onclick = closeModal);
    const list = $("connList");
    const items = [
      ["飞书", "消息与文档协作"],
      ["钉钉", "企业沟通与审批"],
      ["企业微信", "组织内消息触达"],
      ["GitHub", "代码仓库与 PR"],
      ["邮箱", "SMTP / IMAP"],
    ];
    if (list) {
      list.innerHTML = items.map(([n, d]) => `
        <label style="display:flex;gap:12px;align-items:center;padding:12px;border:1px solid var(--line);border-radius:10px;cursor:pointer">
          <div class="av" style="width:32px;height:32px;border-radius:8px;background:var(--accent-soft);color:var(--accent);display:grid;place-items:center;font-weight:700">${escape(n[0])}</div>
          <div style="flex:1"><div style="font-weight:600">${escape(n)}</div><div class="hint">${escape(d)}</div></div>
          <input type="checkbox" />
        </label>`).join("");
    }
  }

  async function fillExpertGrid(el) {
    if (!el) return;
    let skills = [];
    try {
      if (window.wbApi) {
        const data = await window.wbApi("/api/skills");
        skills = data.skills || [];
      }
    } catch (_) {}
    const fallback = [
      { name: "全栈开发专家", description: "后端架构、接口集成与交付", tags: ["全栈开发", "后端架构", "接口集成"] },
      { name: "高级开发工程师", description: "工程落地与质量把关", tags: ["工程", "质量"] },
      { name: "微信小程序开发者", description: "小程序业务与组件", tags: ["小程序"] },
    ];
    const rows = skills.length ? skills.slice(0, 9) : fallback;
    el.innerHTML = rows.map((s, i) => `
      <div class="expert-card" data-i="${i}">
        <div class="row"><div class="av">${escape((s.name || "专")[0])}</div>
          <div><h3>${escape(s.name || s.id)}</h3><div class="org">熊宝专家库</div></div>
        </div>
        <p>${escape(s.description || "专业智能体技能")}</p>
        <div class="tag-row">${(s.tags || ["技能", "协作", "交付"]).slice(0, 3).map((t) => `<span>${escape(t)}</span>`).join("")}</div>
      </div>`).join("");
    el.onclick = (e) => {
      const c = e.target.closest(".expert-card");
      if (!c) return;
      el.querySelectorAll(".expert-card").forEach((x) => x.classList.toggle("selected", x === c));
    };
  }

  async function fillSkillGrid(el) {
    if (!el) return;
    let skills = [];
    try {
      if (window.wbApi) {
        const data = await window.wbApi("/api/skills");
        skills = (data.skills || []).slice(0, 12);
      }
    } catch (_) {}
    el.innerHTML = (skills.length ? skills : [
      { name: "Excel 表格处理", description: "表格清洗与分析" },
      { name: "PPT 演示文稿", description: "幻灯片生成" },
      { name: "PDF 文档处理", description: "解析与摘要" },
      { name: "Web Access", description: "浏览器自动化" },
    ]).map((s, i) => `
      <div class="expert-card" data-i="${i}">
        <div class="row"><div class="av">${ico("tool")}</div><div><h3>${escape(s.name || s.id)}</h3></div></div>
        <p>${escape(s.description || "技能")}</p>
      </div>`).join("");
    el.onclick = (e) => {
      const c = e.target.closest(".expert-card");
      if (!c) return;
      el.querySelectorAll(".expert-card").forEach((x) => x.classList.toggle("selected", x === c));
    };
  }

  async function renderPage(view) {
    const meta = VIEW_META[view] || { title: view, primary: "" };
    const title = $("pageTitle");
    if (title) {
      title.innerHTML = escape(meta.title) + (meta.sub ? `<span class="sub">${escape(meta.sub)}</span>` : "");
    }
    const btn = $("pagePrimaryBtn");
    if (btn) {
      btn.textContent = meta.primary || "操作";
      btn.style.display = meta.primary ? "" : "none";
      btn.onclick = () => onPrimary(view);
    }
    const filters = $("pageFilters");
    const body = $("pageBody");
    if (filters) filters.innerHTML = "";
    if (!body) return;
    body.innerHTML = '<div class="empty">加载中…</div>';

    if (view === "projects") await renderProjects(body, filters);
    else if (view === "market") await renderMarket(body, filters);
    else if (view === "cron") await renderCron(body, filters);
    else if (view === "knowledge") {
      const hd = document.querySelector(".page-hd");
      if (hd) hd.style.display = "none";
      await renderKnowledge(body, filters);
    } else if (view === "settings") { openSettingsModal(); setView("chat"); }
    if (view !== "knowledge") {
      const hd = document.querySelector(".page-hd");
      if (hd) hd.style.display = "";
    }
  }

  async function renderProjects(body, filters) {
    if (filters) {
      filters.innerHTML = `<div class="search-wrap" style="max-width:240px;margin-left:auto"><svg class="ico search-ico"><use href="#i-search"/></svg><input class="search" id="projSearch" placeholder="搜索项目" /></div>`;
    }
    let rows = [];
    try {
      if (window.wbApi) {
        const data = await window.wbApi("/api/projects");
        rows = data.projects || [];
      }
    } catch (_) {}
    body.innerHTML = `
      <div class="proj-section-hd"><h2>我的项目</h2></div>
      <div class="proj-cards">
        ${rows.length ? rows.map((p) => `
          <div class="proj-tile" data-pid="${escape(p.project_id)}">
            <div class="ico-wrap">${ico("nodes")}</div>
            <h3>${escape(p.name || p.project_id)}</h3>
            <p>${escape(p.description || "添加于最近")}</p>
          </div>`).join("") : `<div class="empty">暂无项目，点击右上角新建</div>`}
      </div>
      <div class="proj-section-hd"><h2>从模板创建</h2></div>
      <div class="tpl-row">
        <div class="tpl-card" data-tpl="prd"><h3>产品需求全流程</h3><p>从需求到验收的标准协作模板</p></div>
        <div class="tpl-card" data-tpl="research"><h3>市场调研与竞品分析</h3><p>调研提纲、竞品矩阵与结论</p></div>
        <div class="tpl-card" data-tpl="kb"><h3>团队知识库</h3><p>沉淀规范、SOP 与资产</p></div>
      </div>`;
    body.onclick = (e) => {
      const tile = e.target.closest("[data-pid]");
      if (tile) {
        const sel = $("projectSelect");
        if (sel) { sel.value = tile.dataset.pid; sel.dispatchEvent(new Event("change")); }
        setView("chat");
        return;
      }
      if (e.target.closest("[data-tpl]")) openNewProjectModal();
    };
    refreshSpaces(rows);
  }

  async function renderMarket(body, filters) {
    if (filters) {
      filters.innerHTML = `
        <div class="market-tabs" id="marketTabs">
          <button type="button" data-market="experts" class="${marketTab === "experts" ? "active" : ""}">专家</button>
          <button type="button" data-market="skills" class="${marketTab === "skills" ? "active" : ""}">技能</button>
          <button type="button" data-market="connectors" class="${marketTab === "connectors" ? "active" : ""}">连接器</button>
        </div>
        <div class="search-wrap" style="max-width:280px;margin-left:auto"><svg class="ico search-ico"><use href="#i-search"/></svg><input class="search" placeholder="搜索专家职称或描述" /></div>`;
      const tabs = $("marketTabs");
      if (tabs) tabs.onclick = (e) => {
        const b = e.target.closest("[data-market]");
        if (!b) return;
        marketTab = b.dataset.market;
        renderPage("market");
      };
    }
    const title = $("pageTitle");
    if (title) title.innerHTML = marketTab === "skills" ? "技能" : marketTab === "connectors" ? "连接器" : "专家";

    if (marketTab === "connectors") {
      if (btn) { btn.textContent = "添加连接器"; btn.style.display = ""; btn.onclick = () => openPickConnector(); }
      body.innerHTML = `<div class="expert-grid" id="connGrid"></div>`;
      const g = $("connGrid");
      if (g) {
        g.innerHTML = [
          ["飞书", "消息与文档协作"],
          ["钉钉", "企业沟通与审批"],
          ["企业微信", "组织内消息触达"],
          ["GitHub", "代码仓库与 PR"],
          ["邮箱", "SMTP / IMAP"],
          ["Webhook", "自定义回调"],
        ].map(([n, d]) => `
          <div class="expert-card"><div class="row"><div class="av">${escape(n[0])}</div><div><h3>${escape(n)}</h3></div></div>
          <p>${escape(d)}</p></div>`).join("");
      }
      return;
    }
    if (marketTab === "skills") {
      body.innerHTML = `
        <div class="page-filters" style="padding:0 0 12px">${["全部","办公协同","开发工具","效率工具","数据分析","商业运营"].map((t,i)=>`<button type="button" class="filter-pill ${i===0?"active":""}">${escape(t)}</button>`).join("")}</div>
        <div class="expert-grid" id="skillMarketGrid"></div>`;
      await fillSkillGrid($("skillMarketGrid"));
      return;
    }
    body.innerHTML = `
      <div class="scene-strip">
        ${["内容创作","投研分析","法律咨询","产品设计","技术工程","金融投资"].map((s)=>`<div class="scene-card">${escape(s)}</div>`).join("")}
      </div>
      <div class="proj-section-hd"><h2>专家 | 专家团</h2>
        <div class="page-filters" style="padding:0">${["全部","腾讯专家","产品设计","技术工程","金融投资"].map((t,i)=>`<button type="button" class="filter-pill ${i===0?"active":""}">${escape(t)}</button>`).join("")}</div>
      </div>
      <div class="expert-grid" id="expertMarketGrid"></div>`;
    await fillExpertGrid($("expertMarketGrid"));
  }

  async function renderCron(body, filters) {
    if (filters) {
      filters.innerHTML = `
        <div class="market-tabs"><button class="active">定时任务</button><button type="button">运行记录</button></div>
        <div class="search-wrap" style="max-width:240px;margin-left:auto"><svg class="ico search-ico"><use href="#i-search"/></svg><input class="search" placeholder="搜索定时任务/记录" /></div>`;
    }
    let jobs = [];
    try {
      if (window.wbApi) {
        const data = await window.wbApi("/api/cron").catch(() => null);
        if (data && (data.jobs || data.items)) jobs = data.jobs || data.items;
      }
    } catch (_) {}
    if (!jobs.length) {
      jobs = [
        { name: "[虚拟人项目·补跑] Flutter 层实现方案…", status: "已暂停" },
        { name: "[X-Agent] WS-C1 #16 ADR 草案…", status: "已暂停" },
      ];
    }
    body.innerHTML = `
      <div class="hint" style="padding:10px 12px;border-radius:8px;background:var(--blue-soft);color:var(--blue);margin-bottom:12px">此任务由项目创建，需前往对应项目查看和管理</div>
      <div class="cron-group">已暂停</div>
      <div class="cron-list">
        ${jobs.map((j) => `<div class="cron-row"><div class="title">${escape(j.name || j.id || "定时任务")}</div><div class="st">${escape(j.status || "已暂停")}</div></div>`).join("")}
      </div>`;
  }

  async function renderKnowledge(body) {
    let files = [];
    try {
      if (window.wbApi) {
        const lib = await window.wbApi("/api/library");
        files = (lib.knowledge_files || []).concat(lib.entries || []);
      }
    } catch (_) {}
    body.innerHTML = `
      <div class="library-layout">
        <div class="lib-mid">
          <div class="proj-section-hd" style="margin:0"><h2>资料库</h2></div>
          <div class="search-wrap"><svg class="ico search-ico"><use href="#i-search"/></svg><input class="search" placeholder="搜索" /></div>
          <div class="market-tabs"><button class="active">最近</button><button>本地产物</button></div>
          <div style="font-size:12px;color:var(--hint);margin-top:8px">我的资料</div>
          <div id="libFiles">
            ${(files.length ? files : [{ path: "示例文档.md", title: "示例文档" }]).slice(0, 12).map((f) => `
              <div class="lib-file">${ico("file")}<span>${escape(f.title || (f.path || "").split("/").pop() || "文件")}</span></div>`).join("")}
          </div>
          <div class="lib-usage">已使用 17.5 MB / 10.0 GB<div class="bar"><i></i></div></div>
        </div>
        <div class="lib-main">
          <h1 style="margin:0 0 12px;font-size:22px">最近</h1>
          <div class="market-tabs"><button class="active">最近访问</button><button>我分享的</button><button>与我共享</button></div>
          <div style="margin-top:16px;display:grid;gap:8px">
            ${(files.length ? files : [{ path: "干细胞干预糖尿病.pptx" }, { path: "10.png" }]).slice(0, 6).map((f) => `
              <div class="art-row"><span>${escape(f.title || (f.path || "").split("/").pop())}</span><span class="hint">我的资料</span></div>`).join("")}
          </div>
          <div class="proj-section-hd" style="margin-top:28px"><h2>了解资料库</h2></div>
          <div class="bp-grid" style="grid-template-columns:1fr 1fr">
            <div class="bp-card"><div class="art"></div><div class="cap">一分钟玩转资料库</div></div>
            <div class="bp-card"><div class="art"></div><div class="cap">熊宝资料库介绍</div></div>
          </div>
        </div>
      </div>`;
  }

  function refreshSpaces(rows) {
    const host = $("spaceList");
    const cnt = $("spaceCountLabel");
    if (cnt) cnt.textContent = "(" + (rows ? rows.length : 0) + ")";
    if (!host) return;
    if (!rows || !rows.length) {
      host.innerHTML = `<div class="space-item"><div>技能插件</div><div class="sub">从市场安装技能</div></div>`;
      return;
    }
    host.innerHTML = rows.slice(0, 8).map((p) => `
      <div class="space-item" data-pid="${escape(p.project_id)}">
        <div>${escape(p.name || p.project_id)}</div>
        <div class="sub">${p.skill_count || 0} 技能</div>
      </div>`).join("");
    host.onclick = (e) => {
      const it = e.target.closest("[data-pid]");
      if (!it) return;
      const sel = $("projectSelect");
      if (sel) { sel.value = it.dataset.pid; sel.dispatchEvent(new Event("change")); }
      setView("chat");
    };
  }

  function renderBestPractices() {
    const grid = $("bpGrid");
    if (!grid) return;
    const slice = BP_CASES.slice(bpOffset, bpOffset + 4);
    const cards = slice.length === 4 ? slice : BP_CASES.slice(0, 4);
    grid.innerHTML = cards.map(([title]) => `
      <div class="bp-card" data-bp="${escape(title)}">
        <div class="art"></div>
        <div class="cap">${escape(title)}</div>
      </div>`).join("");
    grid.onclick = (e) => {
      const c = e.target.closest("[data-bp]");
      if (!c) return;
      const hc = $("homeComposer");
      if (hc) { hc.value = "请按最佳实践帮我完成：" + c.dataset.bp; hc.focus(); }
    };
  }

  function onPrimary(view) {
    if (view === "projects") openNewProjectModal();
    if (view === "market") openPickExpert();
    if (view === "cron") window.wbToast && window.wbToast("定时任务创建将接入 cron API", "ok");
    if (view === "knowledge") $("btnKnowledge") && $("btnKnowledge").click();
  }

  function syncChrome() {
    const map = [
      ["sessionChip", "sessionChipSide"],
      ["projectChip", "projectChipSide"],
      ["modelChip", "modelChipComposer"],
      ["modelChip", "modelChipHome"],
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
    const tc = $("taskCountLabel");
    if (tc && window.wbState && Array.isArray(window.wbState.tasks)) {
      tc.textContent = "(" + window.wbState.tasks.length + ")";
    }
    syncAssistantHome();
  }

  async function sendFromHome() {
    const hc = $("homeComposer");
    const text = (hc && hc.value.trim()) || "";
    if (!text) return;
    if (typeof window.createTaskFromPrompt === "function") {
      await window.createTaskFromPrompt(text);
    } else {
      const c = $("composer");
      if (c) c.value = text;
      $("btnNew") && $("btnNew").click();
      setTimeout(() => $("btnSend") && $("btnSend").click(), 400);
    }
    if (hc) hc.value = "";
  }

  document.addEventListener("DOMContentLoaded", () => {
    const nav = $("sideNav");
    if (nav) {
      nav.addEventListener("click", (e) => {
        const m = e.target.closest("[data-market]");
        if (m && m.closest("#marketFlyout")) {
          e.preventDefault();
          setView("market", { market: m.dataset.market });
          return;
        }
        const b = e.target.closest("button[data-view]");
        if (!b) return;
        if (b.dataset.view === "more") return;
        if (b.dataset.view === "chat") {
          goHome();
          return;
        }
        setView(b.dataset.view);
      });
    }

    const SCENE_TAGS = {
      office: [
        ["文档处理", "帮我处理一份文档："],
        ["金融服务", "帮我做金融相关分析："],
        ["数据分析及可视化", "帮我做数据分析与可视化："],
        ["个人工作台", "帮我搭建个人工作台："],
        ["幻灯片", "帮我做一份幻灯片："],
        ["深度搜索", "请深度搜索并整理："],
      ],
      code: [
        ["代码审查", "请帮我审查这段代码："],
        ["写单元测试", "请为以下模块生成单元测试："],
        ["修 Bug", "帮我定位并修复这个 Bug："],
        ["API 设计", "帮我设计一套 REST API："],
        ["重构建议", "请给出重构方案："],
        ["技术选型", "帮我做技术选型对比："],
      ],
      design: [
        ["视觉提案", "帮我出一版视觉提案："],
        ["交互原型", "帮我梳理交互流程："],
        ["品牌命名", "帮我做品牌命名脑暴："],
        ["海报文案", "帮我写一组海报文案："],
        ["UI 规范", "帮我整理一份 UI 规范："],
        ["创意简报", "帮我写一份创意 brief："],
      ],
    };
    function applyScene(scene) {
      const host = $("homeTags");
      if (!host) return;
      const rows = SCENE_TAGS[scene] || SCENE_TAGS.office;
      host.innerHTML = rows.map(([label, prompt]) =>
        `<button type="button" data-prompt="${escape(prompt)}">${escape(label)}</button>`
      ).join("");
      host.querySelectorAll("[data-prompt]").forEach((b) => {
        b.addEventListener("click", () => {
          const hc = $("homeComposer");
          if (hc) { hc.value = b.dataset.prompt; hc.focus(); }
        });
      });
    }

    $("btnSidebarLogout") && ($("btnSidebarLogout").onclick = () => $("btnLogout") && $("btnLogout").click());
    $("btnSidebarSettings") && ($("btnSidebarSettings").onclick = openSettingsModal);
    $("btnMoreSettings") && ($("btnMoreSettings").onclick = openSettingsModal);
    $("btnMoreLogout") && ($("btnMoreLogout").onclick = () => $("btnLogout") && $("btnLogout").click());
    $("btnMoreOps") && ($("btnMoreOps").onclick = () => { location.href = "/ops.html"; });
    $("btnMoreHarbor") && ($("btnMoreHarbor").onclick = () => $("btnHarbor") && $("btnHarbor").click());
    $("btnDiscover") && ($("btnDiscover").onclick = () => setView("market"));

    $("wbModalMask") && $("wbModalMask").addEventListener("click", (e) => {
      if (e.target.id === "wbModalMask") closeModal();
    });

    document.querySelectorAll("#sceneTabs button").forEach((b) => {
      b.addEventListener("click", () => {
        document.querySelectorAll("#sceneTabs button").forEach((x) => x.classList.toggle("active", x === b));
        applyScene(b.dataset.scene || "office");
      });
    });
    applyScene("office");
    window.xbGoHome = goHome;
    $("btnHomeSend") && ($("btnHomeSend").onclick = sendFromHome);
    $("homeComposer") && $("homeComposer").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendFromHome(); }
    });
    $("homeFileLabel") && ($("homeFileLabel").onclick = () => $("fileInput") && $("fileInput").click());
    $("bpRefresh") && ($("bpRefresh").onclick = () => { bpOffset = (bpOffset + 4) % BP_CASES.length; renderBestPractices(); });
    $("bpClose") && ($("bpClose").onclick = () => { const bp = document.querySelector(".best-practices"); if (bp) bp.style.display = "none"; });

    renderBestPractices();

    const obs = new MutationObserver(syncChrome);
    ["sessionChip", "projectChip", "modelChip"].forEach((id) => {
      const el = $(id);
      if (el) obs.observe(el, { childList: true, characterData: true, subtree: true });
    });
    syncChrome();
    setInterval(syncChrome, 800);

    // preload spaces
    setTimeout(async () => {
      try {
        if (!window.wbApi) return;
        const data = await window.wbApi("/api/projects");
        refreshSpaces(data.projects || []);
      } catch (_) {}
    }, 600);

    window.xbSetView = setView;
    window.xbSyncHome = syncAssistantHome;
    window.xbOpenNewProject = openNewProjectModal;
    window.xbOpenSettings = openSettingsModal;
  });
})();
