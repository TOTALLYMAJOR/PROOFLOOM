const state = {
  token: null,
  workflows: [],
  active: null,
  repository: null,
  events: [],
};

const elements = {
  workflowList: document.querySelector("#workflow-list"),
  form: document.querySelector("#operator-form"),
  task: document.querySelector("#task-input"),
  surface: document.querySelector("#surface-input"),
  profile: document.querySelector("#profile-input"),
  reformatField: document.querySelector("#reformat-field"),
  reformatScope: document.querySelector("#reformat-scope"),
  taskRequirement: document.querySelector("#task-requirement"),
  eyebrow: document.querySelector("#operation-eyebrow"),
  title: document.querySelector("#operation-title"),
  description: document.querySelector("#operation-description"),
  actionClass: document.querySelector("#action-class"),
  authority: document.querySelector("#authority-label"),
  proofBoundary: document.querySelector("#proof-boundary"),
  runButton: document.querySelector("#run-button"),
  resultPanel: document.querySelector("#result-panel"),
  resultTitle: document.querySelector("#result-title"),
  resultStatus: document.querySelector("#result-status"),
  resultHighlights: document.querySelector("#result-highlights"),
  resultJson: document.querySelector("#result-json"),
  nextAction: document.querySelector("#next-action"),
  eventList: document.querySelector("#event-list"),
  toast: document.querySelector("#toast"),
};

elements.form.addEventListener("submit", runActiveWorkflow);
elements.form.addEventListener("reset", () => {
  window.setTimeout(() => {
    elements.resultPanel.hidden = true;
    addEvent("Inputs cleared", "Ready for a new bounded operation.", "current");
  }, 0);
});

initialize();

async function initialize() {
  try {
    const response = await fetch("/api/bootstrap", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Bootstrap returned ${response.status}`);
    const payload = await response.json();
    state.token = payload.sessionToken;
    state.workflows = payload.workflows;
    state.repository = payload.repository;
    hydrateRepository(payload);
    renderWorkflowList();
    selectWorkflow(state.workflows[0]?.id);
    state.events = [];
    addEvent("Repository bound", `${payload.repository.name} · ${shortSha(payload.repository.commit)}`, "complete");
    addEvent("Workflow ready", "Choose an operation and run its safe next step.", "current");
    document.body.dataset.qaReady = "true";
  } catch (error) {
    showToast(`Operator service unavailable: ${error.message}`);
    addEvent("Connection blocked", "Start the shell with design-intelligence shell.", "current");
  }
}

function hydrateRepository(payload) {
  const repository = payload.repository;
  text("#repo-name", repository.name);
  text("#repo-branch", `${repository.branch} · ${shortSha(repository.commit)}`);
  const dirty = document.querySelector("#repo-dirty");
  dirty.textContent = repository.dirty ? `${repository.changedPaths} changed` : "Clean";
  dirty.classList.toggle("is-dirty", repository.dirty);
  const gate = document.querySelector("#repo-gate");
  gate.textContent = `Gate ${repository.governanceGate}`;
  gate.className = `gate-pill ${statusClass(repository.governanceGate)}`;
  text("#truth-root", repository.name);
  document.querySelector("#truth-root").title = repository.root;
  text("#truth-commit", shortSha(repository.commit));
  text("#global-boundary", payload.executionBoundary);
  text("#shell-version", `Design Intelligence ${payload.version}`);
}

function renderWorkflowList() {
  elements.workflowList.replaceChildren();
  state.workflows.forEach((workflow, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "workflow-option";
    button.dataset.workflow = workflow.id;
    button.setAttribute("aria-current", "false");

    const number = document.createElement("span");
    number.className = "workflow-index";
    number.textContent = String(index + 1).padStart(2, "0");
    const copy = document.createElement("span");
    copy.className = "workflow-copy";
    const label = document.createElement("strong");
    label.textContent = workflow.label;
    const action = document.createElement("small");
    action.textContent = workflow.actionClass;
    copy.append(label, action);
    button.append(number, copy);
    button.addEventListener("click", () => selectWorkflow(workflow.id));
    elements.workflowList.append(button);
  });
}

function selectWorkflow(id) {
  const workflow = state.workflows.find((item) => item.id === id);
  if (!workflow) return;
  state.active = workflow;
  document.querySelectorAll(".workflow-option").forEach((button) => {
    button.setAttribute("aria-current", String(button.dataset.workflow === id));
  });
  elements.eyebrow.textContent = workflow.eyebrow;
  elements.title.textContent = workflow.label;
  elements.description.textContent = workflow.description;
  elements.actionClass.textContent = workflow.actionClass;
  elements.authority.textContent = workflow.authority;
  elements.proofBoundary.textContent = workflow.proofBoundary;
  elements.taskRequirement.textContent = workflow.requiresTask ? "required" : "optional";
  elements.reformatField.hidden = workflow.id !== "reformat";
  elements.runButton.querySelector("span:first-child").textContent = workflow.buttonLabel;
  text("#truth-writes", workflow.writes ? "Declared output" : "None");
  text("#truth-authority", workflow.authority);
  elements.resultPanel.hidden = true;
  addEvent("Workflow selected", workflow.label, "current");
}

async function runActiveWorkflow(event) {
  event.preventDefault();
  if (!state.active) return;
  if (state.active.requiresTask && !elements.task.value.trim()) {
    elements.task.focus();
    showToast("Add a task or focus statement before running this workflow.");
    return;
  }

  const workflow = state.active;
  const taskPrefix = workflow.id === "reformat" ? `${elements.reformatScope.value}: ` : "";
  const inputs = {
    task: `${taskPrefix}${elements.task.value.trim()}`.trim(),
    surface: elements.surface.value.trim(),
    profile: elements.profile.value,
  };
  setRunning(true);
  addEvent("Preflight running", `Checking ${workflow.authority.toLowerCase()}.`, "current");

  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Proofloom-Token": state.token,
      },
      body: JSON.stringify({ workflowId: workflow.id, inputs }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `Operation returned ${response.status}`);
    renderResult(payload);
    addEvent("Evidence returned", `${workflow.label} · ${payload.status}`, "complete");
    addEvent("Review required", payload.nextAction, "current");
  } catch (error) {
    showToast(error.message);
    addEvent("Operation blocked", error.message, "current");
  } finally {
    setRunning(false);
  }
}

function renderResult(payload) {
  elements.resultPanel.hidden = false;
  elements.resultTitle.textContent = resultTitle(payload.status);
  elements.resultStatus.textContent = payload.status.replaceAll("_", " ");
  elements.resultStatus.className = `result-status ${statusClass(payload.status)}`;
  elements.nextAction.textContent = payload.nextAction;
  elements.resultJson.textContent = JSON.stringify(payload, null, 2);
  elements.resultHighlights.replaceChildren();
  highlights(payload).forEach(([label, value]) => {
    const item = document.createElement("div");
    item.className = "highlight";
    const key = document.createElement("span");
    key.textContent = label;
    const content = document.createElement("strong");
    content.textContent = String(value ?? "—");
    content.title = String(value ?? "—");
    item.append(key, content);
    elements.resultHighlights.append(item);
  });
  elements.resultPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function highlights(payload) {
  const report = payload.report || {};
  if (payload.workflow.id === "backlog-health") {
    return [["Status", report.completion], ["Open", report.openCount], ["Terminal", report.terminalCount]];
  }
  if (payload.workflow.id === "reformat") {
    return [["Status", report.status], ["Recommendation", report.recommendedDirection], ["Authorized", report.implementationReady ? "Yes" : "No"]];
  }
  if (payload.workflow.id === "ux-audit") {
    const model = report.actorTaskModel || {};
    return [["Actor", model.actor], ["Decision", model.decision], ["Next action", model.next_action || model.nextAction]];
  }
  if (payload.workflow.id === "design-audit") {
    return [["Status", report.status], ["Lint", report.lint_report?.status], ["Runtime", report.assessment?.runtime_strategy]];
  }
  if (payload.workflow.id === "governance-audit") {
    return [["Status", report.status], ["Design gate", report.designGate?.status], ["Findings", report.findings?.length ?? 0]];
  }
  if (payload.workflow.id === "build-backlog") {
    return [["Status", report.status], ["Stages", report.proposalStages?.length], ["Execution", "Not performed"]];
  }
  return [["Status", report.status], ["Browsers", report.browsers?.length], ["Viewports", report.viewports?.length]];
}

function addEvent(title, detail, stateName) {
  state.events = state.events.map((item) => ({ ...item, state: item.state === "current" ? "complete" : item.state }));
  state.events.push({ title, detail, state: stateName });
  state.events = state.events.slice(-5);
  elements.eventList.replaceChildren();
  state.events.forEach((event) => {
    const item = document.createElement("li");
    item.className = event.state === "complete" ? "is-complete" : "is-current";
    const marker = document.createElement("span");
    marker.setAttribute("aria-hidden", "true");
    const copy = document.createElement("p");
    const titleNode = document.createElement("strong");
    titleNode.textContent = event.title;
    const detailNode = document.createElement("small");
    detailNode.textContent = event.detail;
    copy.append(titleNode, detailNode);
    item.append(marker, copy);
    elements.eventList.append(item);
  });
}

function setRunning(running) {
  elements.runButton.disabled = running;
  elements.runButton.querySelector("span:first-child").textContent = running ? "Running preflight…" : state.active.buttonLabel;
  elements.form.setAttribute("aria-busy", String(running));
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    elements.toast.hidden = true;
  }, 5000);
}

function resultTitle(status) {
  if (["BLOCKED", "FAIL", "GOVERNANCE_REQUIRED"].includes(status)) return "Boundary reached";
  if (["REVIEW_REQUIRED", "DIRECTION_REVIEW_REQUIRED"].includes(status)) return "Decision required";
  return "Evidence ready";
}

function statusClass(status) {
  const normalized = String(status).toUpperCase();
  if (["PASS", "READY", "ALLOW", "COMPLETE", "READY_TO_PLAN"].includes(normalized)) return "is-ready";
  if (["BLOCKED", "FAIL", "GOVERNANCE_REQUIRED"].includes(normalized)) return "is-blocked";
  return "is-review";
}

function shortSha(value) {
  return value && value !== "unavailable" ? value.slice(0, 8) : "unavailable";
}

function text(selector, value) {
  const node = document.querySelector(selector);
  if (node) node.textContent = value;
}
