const state = {
  token: null,
  workflows: [],
  active: null,
  repository: null,
  events: [],
  backlog: {
    prompt: "",
    validatedDraft: null,
    saved: false,
  },
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
  backlogWorkspace: document.querySelector("#backlog-workspace"),
  backlogState: document.querySelector("#backlog-state"),
  aiBrief: document.querySelector("#ai-brief-output"),
  copyBrief: document.querySelector("#copy-brief"),
  downloadBrief: document.querySelector("#download-brief"),
  proposalDraft: document.querySelector("#proposal-draft"),
  validateProposal: document.querySelector("#validate-proposal"),
  validationMessage: document.querySelector("#validation-message"),
  proposalOutputPath: document.querySelector("#proposal-output-path"),
  confirmProposalSave: document.querySelector("#confirm-proposal-save"),
  saveProposal: document.querySelector("#save-proposal"),
};

elements.form.addEventListener("submit", runActiveWorkflow);
elements.form.addEventListener("reset", () => {
  window.setTimeout(() => {
    elements.resultPanel.hidden = true;
    resetBacklogWorkspace();
    addEvent("Inputs cleared", "Ready for a new bounded operation.", "current");
  }, 0);
});
elements.copyBrief.addEventListener("click", copyAiBrief);
elements.downloadBrief.addEventListener("click", downloadAiBrief);
elements.validateProposal.addEventListener("click", validateProposal);
elements.saveProposal.addEventListener("click", saveProposal);
elements.proposalDraft.addEventListener("input", invalidateProposalValidation);
elements.proposalOutputPath.addEventListener("input", updateSaveAvailability);
elements.confirmProposalSave.addEventListener("change", updateSaveAvailability);

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
  elements.backlogWorkspace.hidden = workflow.id !== "build-backlog";
  elements.runButton.querySelector("span:first-child").textContent = workflow.buttonLabel;
  text("#truth-writes", workflow.writes ? "Declared output" : "None");
  text("#truth-authority", workflow.authority);
  elements.resultPanel.hidden = true;
  if (workflow.id === "build-backlog") resetBacklogWorkspace();
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
  if (workflow.id === "build-backlog") inputs.phase = "assemble";
  setRunning(true);
  addEvent("Preflight running", `Checking ${workflow.authority.toLowerCase()}.`, "current");

  try {
    const payload = await requestWorkflow(workflow.id, inputs);
    renderResult(payload);
    if (workflow.id === "build-backlog") receiveBacklogResult(payload);
    addEvent("Evidence returned", `${workflow.label} · ${payload.status}`, "complete");
    addEvent("Review required", payload.nextAction, "current");
  } catch (error) {
    showToast(error.message);
    addEvent("Operation blocked", error.message, "current");
  } finally {
    setRunning(false);
  }
}

async function requestWorkflow(workflowId, inputs) {
  const response = await fetch("/api/run", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Proofloom-Token": state.token,
    },
    body: JSON.stringify({ workflowId, inputs }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Operation returned ${response.status}`);
  return payload;
}

function backlogInputs(phase) {
  return {
    task: elements.task.value.trim(),
    surface: elements.surface.value.trim(),
    profile: elements.profile.value,
    phase,
    proposal: elements.proposalDraft.value,
  };
}

function receiveBacklogResult(payload) {
  const phase = payload.report?.phase;
  if (phase === "assemble") {
    state.backlog.prompt = payload.report.brief?.aiInstruction || "";
    elements.aiBrief.value = state.backlog.prompt;
    elements.copyBrief.disabled = !state.backlog.prompt;
    elements.downloadBrief.disabled = !state.backlog.prompt;
    elements.backlogState.textContent = "Brief ready";
    setBacklogStep("draft");
    elements.aiBrief.scrollIntoView({ behavior: "smooth", block: "center" });
  } else if (phase === "validate") {
    const validation = payload.report.validation;
    const valid = validation?.status === "VALID";
    state.backlog.validatedDraft = valid ? elements.proposalDraft.value : null;
    elements.validationMessage.textContent = valid
      ? `${validation.taskCount} proposed task${validation.taskCount === 1 ? "" : "s"} passed deterministic checks.`
      : `${validation.errors?.length || 1} validation finding${validation.errors?.length === 1 ? "" : "s"}; inspect the result and revise the draft.`;
    elements.validationMessage.className = valid ? "is-valid" : "is-invalid";
    elements.backlogState.textContent = valid ? "Draft valid" : "Revision required";
    setBacklogStep(valid ? "save" : "validate");
    updateSaveAvailability();
  } else if (phase === "save") {
    state.backlog.saved = true;
    elements.backlogState.textContent = "Saved for review";
    elements.validationMessage.textContent = `Saved ${payload.report.savedProposal.path}.`;
    elements.validationMessage.className = "is-valid";
    setBacklogStep("complete");
    updateSaveAvailability();
  }
}

async function copyAiBrief() {
  if (!state.backlog.prompt) return;
  try {
    await navigator.clipboard.writeText(state.backlog.prompt);
    showToast("AI instruction copied.");
  } catch (_error) {
    elements.aiBrief.focus();
    elements.aiBrief.select();
    showToast("Select and copy the highlighted instruction.");
  }
}

function downloadAiBrief() {
  if (!state.backlog.prompt) return;
  const blob = new Blob([state.backlog.prompt], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "proofloom-backlog-assembly-brief.txt";
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  showToast("AI instruction downloaded.");
}

async function validateProposal() {
  if (!elements.task.value.trim()) {
    elements.task.focus();
    showToast("Keep the backlog objective in the task field.");
    return;
  }
  if (!elements.proposalDraft.value.trim()) {
    elements.proposalDraft.focus();
    showToast("Paste the AI proposal JSON before validation.");
    return;
  }
  elements.validateProposal.disabled = true;
  elements.validationMessage.textContent = "Checking structure, dependencies, ownership, commands, and evidence…";
  try {
    const payload = await requestWorkflow("build-backlog", backlogInputs("validate"));
    renderResult(payload);
    receiveBacklogResult(payload);
    addEvent("Proposal checked", payload.nextAction, payload.status === "VALID" ? "complete" : "current");
  } catch (error) {
    showToast(error.message);
    addEvent("Validation blocked", error.message, "current");
  } finally {
    elements.validateProposal.disabled = false;
  }
}

async function saveProposal() {
  if (!canSaveProposal()) return;
  elements.saveProposal.disabled = true;
  try {
    const inputs = {
      ...backlogInputs("save"),
      outputPath: elements.proposalOutputPath.value.trim(),
      confirmSave: true,
    };
    const payload = await requestWorkflow("build-backlog", inputs);
    renderResult(payload);
    receiveBacklogResult(payload);
    text("#truth-writes", "Proposal saved");
    addEvent("Proposal saved", payload.report.savedProposal.path, "complete");
    addEvent("Human adoption required", payload.nextAction, "current");
  } catch (error) {
    showToast(error.message);
    addEvent("Save blocked", error.message, "current");
    updateSaveAvailability();
  }
}

function invalidateProposalValidation() {
  if (state.backlog.validatedDraft !== null) {
    state.backlog.validatedDraft = null;
    state.backlog.saved = false;
    elements.validationMessage.textContent = "Draft changed; validate it again before saving.";
    elements.validationMessage.className = "";
    elements.backlogState.textContent = "Validation required";
    setBacklogStep("validate");
  } else if (elements.proposalDraft.value.trim()) {
    setBacklogStep("validate");
  }
  updateSaveAvailability();
}

function canSaveProposal() {
  return Boolean(
    !state.backlog.saved &&
      state.backlog.validatedDraft === elements.proposalDraft.value &&
      elements.proposalOutputPath.value.trim() &&
      elements.confirmProposalSave.checked,
  );
}

function updateSaveAvailability() {
  elements.saveProposal.disabled = !canSaveProposal();
}

function resetBacklogWorkspace() {
  state.backlog = { prompt: "", validatedDraft: null, saved: false };
  elements.aiBrief.value = "";
  elements.proposalDraft.value = "";
  elements.copyBrief.disabled = true;
  elements.downloadBrief.disabled = true;
  elements.confirmProposalSave.checked = false;
  elements.validationMessage.textContent = "No draft has been validated.";
  elements.validationMessage.className = "";
  elements.backlogState.textContent = "Awaiting brief";
  text("#truth-writes", "None");
  setBacklogStep("brief");
  updateSaveAvailability();
}

function setBacklogStep(activeStep) {
  const order = ["brief", "draft", "validate", "save"];
  const activeIndex = activeStep === "complete" ? order.length : order.indexOf(activeStep);
  document.querySelectorAll("[data-backlog-step]").forEach((item) => {
    const index = order.indexOf(item.dataset.backlogStep);
    item.classList.toggle("is-complete", index < activeIndex);
    item.classList.toggle("is-current", index === activeIndex);
  });
}

function renderResult(payload) {
  elements.resultPanel.hidden = false;
  elements.resultTitle.textContent = resultTitle(payload.status);
  elements.resultStatus.textContent = payload.status.replaceAll("_", " ");
  elements.resultStatus.className = `result-status ${statusClass(payload.status)}`;
  elements.nextAction.textContent = payload.nextAction;
  text("#truth-writes", payload.execution?.writes ? "Proposal saved" : "None");
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
    if (report.phase === "assemble") {
      return [["Status", report.status], ["Sources", report.brief?.authoritySources?.length], ["Execution", "Not performed"]];
    }
    if (report.phase === "validate") {
      return [["Status", report.status], ["Tasks", report.validation?.taskCount], ["Findings", report.validation?.errors?.length]];
    }
    return [["Status", report.status], ["Tasks", report.savedProposal?.taskCount], ["Canonical", "No"]];
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
  if (["PASS", "READY", "ALLOW", "COMPLETE", "READY_TO_PLAN", "AI_BRIEF_READY", "VALID", "SAVED_FOR_REVIEW"].includes(normalized)) return "is-ready";
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
