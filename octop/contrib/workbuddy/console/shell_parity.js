/* WorkBuddy shell parity extras — SSE / panels / models / channels */
(function () {
  const $ = (id) => document.getElementById(id);

  function ensureParityUI() {
    if ($("parityBar")) return;
    const top = document.querySelector(".topbar-nav");
    if (!top) return;
    const bar = document.createElement("div");
    bar.id = "parityBar";
    bar.className = "parity-bar";
    bar.innerHTML = `
      <button type="button" class="linkish hide-sm" id="btnKnowledge">资料</button>
      <button type="button" class="linkish hide-sm" id="btnCowrite">共写</button>
      <button type="button" class="linkish hide-sm" id="btnMemory">记忆</button>
      <button type="button" class="linkish hide-sm" id="btnModels">模型</button>
      <button type="button" class="linkish hide-sm" id="btnChannels">通道</button>
      <button type="button" class="linkish hide-sm" id="btnTeam">专家团</button>`;
    const skills = $("btnSkills");
    if (skills) top.insertBefore(bar, skills);
    else top.prepend(bar);

    const drawer = document.createElement("aside");
    drawer.className = "skills-drawer";
    drawer.id = "parityDrawer";
    drawer.innerHTML = `
      <div class="col-hd"><h2 id="parityDrawerTitle">面板</h2>
        <button type="button" class="btn ghost" id="btnCloseParity">关闭</button></div>
      <div class="skills-list" id="parityBody"></div>`;
    document.body.appendChild(drawer);

    const progress = document.createElement("div");
    progress.id = "runProgress";
    progress.className = "run-progress";
    progress.hidden = true;
    progress.innerHTML = `<div class="run-progress-inner"><strong id="runProgressTitle">执行中</strong>
      <ol id="runProgressSteps"></ol></div>`;
    const center = document.querySelector(".col.center");
    if (center) {
      const composer = center.querySelector(".composer");
      if (composer) center.insertBefore(progress, composer);
      else center.appendChild(progress);
    }
  }

  function openParity(title, html) {
    ensureParityUI();
    $("parityDrawerTitle").textContent = title;
    $("parityBody").innerHTML = html;
    $("parityDrawer").classList.add("open");
    const sk = $("skillsDrawer");
    const pj = $("projectDrawer");
    if (sk) sk.classList.remove("open");
    if (pj) pj.classList.remove("open");
  }

  function closeParity() {
    const d = $("parityDrawer");
    if (d) d.classList.remove("open");
  }

  async function showKnowledge() {
    const data = await window.wbApi("/api/knowledge");
    const sources = (data.sources || []).map((s) => `<li>${escape(s)}</li>`).join("") || "<li>暂无</li>";
    openParity("资料库", `
      <p class="hint">本地知识库检索与录入</p>
      <div class="composer-row"><input id="kbQ" placeholder="搜索…" style="flex:1"/><button class="btn" id="kbSearch">搜索</button></div>
      <div id="kbHits"></div>
      <h3 style="font-size:0.9rem;margin:1rem 0 0.4rem">录入笔记</h3>
      <textarea id="kbText" rows="4" style="width:100%"></textarea>
      <button class="btn" id="kbIngest" style="margin-top:0.5rem">写入知识库</button>
      <h3 style="font-size:0.9rem;margin:1rem 0 0.4rem">来源</h3><ul>${sources}</ul>`);
    $("kbSearch").onclick = async () => {
      const q = $("kbQ").value.trim();
      if (!q) return;
      const r = await window.wbApi("/api/knowledge?q=" + encodeURIComponent(q));
      $("kbHits").innerHTML = (r.hits || []).map((h) =>
        `<div class="skill-row"><p>${escape((h.text || "").slice(0, 200))}</p><small>${escape(h.source || "")}</small></div>`
      ).join("") || "<div class='empty'>无结果</div>";
    };
    $("kbIngest").onclick = async () => {
      const text = $("kbText").value.trim();
      if (!text) return;
      await window.wbApi("/api/knowledge/ingest", { method: "POST", body: JSON.stringify({ text, title: "note-" + Date.now() + ".md" }) });
      window.wbToast("已写入知识库", "ok");
      showKnowledge();
    };
  }

  async function showCowrite() {
    const data = await window.wbApi("/api/cowrite");
    openParity("共写", `
      <button class="btn" id="cwNew">新建共写会话</button>
      <div id="cwList" style="margin-top:0.75rem"></div>
      <div id="cwDetail"></div>`);
    const renderList = () => {
      $("cwList").innerHTML = (data.sessions || []).map((s) =>
        `<button type="button" class="task-item" data-cw="${escape(s.session_id)}">
          <div class="t">${escape(s.title)}</div>
          <div class="m"><span>${s.turns} 轮</span><span>${escape(s.updated_at || "")}</span></div>
        </button>`
      ).join("") || "<div class='empty'>暂无共写</div>";
    };
    renderList();
    $("cwNew").onclick = async () => {
      const title = prompt("共写标题", "共写文档");
      if (!title) return;
      const r = await window.wbApi("/api/cowrite", { method: "POST", body: JSON.stringify({ title }) });
      openCw(r.session.session_id);
    };
    $("cwList").onclick = (e) => {
      const b = e.target.closest("[data-cw]");
      if (b) openCw(b.dataset.cw);
    };
  }

  async function openCw(id) {
    const r = await window.wbApi("/api/cowrite/" + encodeURIComponent(id));
    const s = r.session;
    $("cwDetail").innerHTML = `
      <h3 style="font-size:0.95rem">${escape(s.title)}</h3>
      <textarea id="cwDoc" rows="8" style="width:100%">${escape(s.document || "")}</textarea>
      <textarea id="cwTurn" rows="2" style="width:100%;margin-top:0.4rem" placeholder="追加一条人类批注…"></textarea>
      <button class="btn" id="cwAppend" style="margin-top:0.4rem">追加到共写</button>
      <div style="margin-top:0.6rem;font-size:0.8rem;color:var(--muted)">
        ${(s.turns || []).slice(-6).map((t) => `<div>[${escape(t.author)}] ${escape((t.text || "").slice(0, 120))}</div>`).join("")}
      </div>`;
    $("cwAppend").onclick = async () => {
      const text = $("cwTurn").value.trim();
      if (!text) return;
      await window.wbApi("/api/cowrite/" + encodeURIComponent(id) + "/append", {
        method: "POST", body: JSON.stringify({ author: "human", text }),
      });
      window.wbToast("已追加", "ok");
      openCw(id);
    };
  }

  async function showMemory() {
    const pid = (window.wbState && window.wbState.projectId) || "";
    const q = pid ? ("?project_id=" + encodeURIComponent(pid)) : "";
    const data = await window.wbApi("/api/memory" + q);
    openParity("记忆", `
      <p class="hint">范围：${escape(data.scope)}${pid ? (" / " + escape(pid)) : "（工作区）"}</p>
      <textarea id="memText" rows="14" style="width:100%">${escape(data.text || "")}</textarea>
      <button class="btn" id="memSave" style="margin-top:0.5rem">保存记忆</button>`);
    $("memSave").onclick = async () => {
      const body = { text: $("memText").value };
      if (pid) body.project_id = pid;
      await window.wbApi("/api/memory", { method: "POST", body: JSON.stringify(body) });
      window.wbToast("记忆已保存", "ok");
    };
  }

  async function showModels() {
    const data = await window.wbApi("/api/models");
    openParity("模型档案", `
      <p class="hint">当前激活：<strong>${escape(data.active || "无")}</strong> · 环境 ${escape(data.env_model || "—")}</p>
      ${(data.profiles || []).map((p) => `
        <div class="skill-row">
          <h3>${escape(p.profile_id)}</h3>
          <p>${escape(p.model)} @ ${escape(p.base_url)}</p>
          <button class="btn ${data.active === p.profile_id ? "ghost" : ""}" data-act="${escape(p.profile_id)}"
            ${data.active === p.profile_id ? "disabled" : ""}>${data.active === p.profile_id ? "使用中" : "切换"}</button>
        </div>`).join("") || "<div class='empty'>暂无档案，可下方新建</div>"}
      <h3 style="font-size:0.9rem;margin:1rem 0 0.4rem">新建档案</h3>
      <input id="mpId" placeholder="profile_id" style="width:100%;margin-bottom:0.35rem"/>
      <input id="mpModel" placeholder="model" value="qwen2.5:3b" style="width:100%;margin-bottom:0.35rem"/>
      <input id="mpUrl" placeholder="base_url" value="http://host.docker.internal:11434/v1" style="width:100%;margin-bottom:0.35rem"/>
      <button class="btn" id="mpCreate">创建并激活</button>`);
    $("parityBody").onclick = async (e) => {
      const b = e.target.closest("[data-act]");
      if (!b || b.disabled) return;
      await window.wbApi("/api/models/activate", { method: "POST", body: JSON.stringify({ profile_id: b.dataset.act }) });
      window.wbToast("已切换模型", "ok");
      const chip = $("modelChip");
      if (chip) {
        const prof = (data.profiles || []).find((p) => p.profile_id === b.dataset.act);
        chip.textContent = "模型 · " + ((prof && prof.model) || b.dataset.act);
      }
      showModels();
    };
    $("mpCreate").onclick = async () => {
      const profile_id = $("mpId").value.trim();
      if (!profile_id) return;
      await window.wbApi("/api/models", {
        method: "POST",
        body: JSON.stringify({ profile_id, model: $("mpModel").value.trim(), base_url: $("mpUrl").value.trim(), activate: true }),
      });
      window.wbToast("档案已创建", "ok");
      showModels();
    };
  }

  async function showChannels() {
    const data = await window.wbApi("/api/channels");
    openParity("通道", `<pre class="preview">${escape(JSON.stringify(data, null, 2))}</pre>
      <p class="hint">凭据通过环境变量配置（飞书/钉钉/企微 webhook）。完整运维见「设置」。</p>
      <a class="btn" href="/ops.html">打开运维页</a>`);
  }

  async function showTeam() {
    const data = await window.wbApi("/api/team");
    openParity("专家团", `
      <p>${escape(data.shell_note || "")}</p>
      <p class="hint">${escape(data.hint || "")}</p>
      <p>模式：${(data.modes || []).map(escape).join(" / ")}</p>`);
  }

  function escape(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function showProgress(show) {
    ensureParityUI();
    const el = $("runProgress");
    if (!el) return;
    el.hidden = !show;
    if (show) $("runProgressSteps").innerHTML = "";
  }

  function pushProgress(ev) {
    ensureParityUI();
    const ol = $("runProgressSteps");
    const title = $("runProgressTitle");
    if (!ol) return;
    showProgress(true);
    const msg = ev.message || ev.kind || "";
    if (title && msg) title.textContent = msg;
    if (ev.kind === "step_start" || ev.kind === "step_end" || ev.kind === "plan" || ev.kind === "skills") {
      const li = document.createElement("li");
      li.textContent = msg || ev.kind;
      if (ev.kind === "step_end" && ev.ok === false) li.style.color = "var(--danger)";
      ol.appendChild(li);
    }
    if (ev.terminal) {
      setTimeout(() => showProgress(false), 1800);
    }
  }

  async function consumeEvents(taskId) {
    const token = localStorage.getItem("wb_shell_jwt") || "";
    const url = "/api/tasks/" + encodeURIComponent(taskId) + "/events?access_token=" + encodeURIComponent(token);
    const r = await fetch(url, { headers: token ? { Authorization: "Bearer " + token } : {} });
    if (!r.ok || !r.body) throw new Error("SSE 连接失败");
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    showProgress(true);
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() || "";
      for (const block of parts) {
        const dataLine = block.split("\n").find((l) => l.startsWith("data: "));
        if (!dataLine) continue;
        try {
          const ev = JSON.parse(dataLine.slice(6));
          pushProgress(ev);
          if (ev.terminal || ["done", "completed", "failed", "error", "accepted", "timeout"].includes(ev.kind)) {
            if (window.wbRefreshTask) await window.wbRefreshTask(taskId);
            return;
          }
        } catch (_) { /* ignore */ }
      }
    }
    if (window.wbRefreshTask) await window.wbRefreshTask(taskId);
  }

  window.wbParity = {
    ensureParityUI,
    consumeEvents,
    showProgress,
    pushProgress,
  };

  document.addEventListener("DOMContentLoaded", () => {
    ensureParityUI();
    document.body.addEventListener("click", (e) => {
      if (e.target.id === "btnCloseParity") closeParity();
      if (e.target.id === "btnKnowledge") showKnowledge();
      if (e.target.id === "btnCowrite") showCowrite();
      if (e.target.id === "btnMemory") showMemory();
      if (e.target.id === "btnModels") showModels();
      if (e.target.id === "btnChannels") showChannels();
      if (e.target.id === "btnTeam") showTeam();
    });
  });
})();
