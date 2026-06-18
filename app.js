const UNITS = [
  { id: 1, name: "Unit 1" },
  { id: 2, name: "Unit 2" },
  { id: 3, name: "Unit 3" },
  { id: 4, name: "Unit 4" },
  { id: 5, name: "Unit 5" },
  { id: 6, name: "Unit 6" },
  { id: 7, name: "Unit 7" }
];

const STORAGE_KEYS = {
  history: "ukgk_score_history_v1",
  imports: "ukgk_imported_questions_v1"
};

const state = {
  questions: [],
  currentSet: [],
  submitted: false,
  answers: new Map()
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function readJson(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function textFor(value, language) {
  if (!value) return "";
  if (language === "en") return value.en || value.hi || "";
  if (language === "hi") return value.hi || value.en || "";
  return `${value.en || ""}${value.hi ? `<br><span lang="hi">${value.hi}</span>` : ""}`;
}

function shuffle(items) {
  return [...items].sort(() => Math.random() - 0.5);
}

function sample(items, count) {
  return shuffle(items).slice(0, Math.min(count, items.length));
}

function loadQuestionBank() {
  const imported = readJson(STORAGE_KEYS.imports, []);
  const generated = window.GENERATED_QUESTIONS || [];
  const base = generated.length ? generated : window.DEFAULT_QUESTIONS;
  state.questions = [...base, ...imported];
}

function initUnitSelect() {
  const unitSelect = $("#unitSelect");
  unitSelect.innerHTML = UNITS.map((unit) => `<option value="${unit.id}">${unit.name}</option>`).join("");
}

function makePracticeSet() {
  state.submitted = false;
  state.answers = new Map();
  const mode = $("#modeSelect").value;
  const selectedUnit = Number($("#unitSelect").value);

  if (mode === "all") {
    state.currentSet = UNITS.flatMap((unit) => sample(state.questions.filter((q) => q.unit === unit.id), 10));
  } else {
    state.currentSet = sample(state.questions.filter((q) => q.unit === selectedUnit), 10);
  }

  renderQuiz();
}

function renderQuiz() {
  const language = $("#languageSelect").value;
  const quizForm = $("#quizForm");
  const mode = $("#modeSelect").value;
  const unitsLabel = mode === "all" ? "All units" : `Unit ${$("#unitSelect").value}`;

  $("#quizMeta").innerHTML = `
    <span>${unitsLabel}</span>
    <span>${state.currentSet.length} questions</span>
    <span>Correct +1 | Wrong -0.25 | Unattempted 0</span>
  `;

  quizForm.innerHTML = state.currentSet
    .map((question, index) => renderQuestion(question, index, language))
    .join("");

  $("#scorePreview").textContent = state.submitted ? currentScoreText().summary : "";
  updateSubmitButton();
}

function renderQuestion(question, index, language) {
  const selected = state.answers.get(question.id);
  const optionHtml = question.options
    .map((option, optionIndex) => {
      const checked = selected === optionIndex ? "checked" : "";
      const resultClass = state.submitted
        ? optionIndex === question.answerIndex
          ? " correct"
          : selected === optionIndex
            ? " incorrect"
            : ""
        : "";
      return `
        <label class="option${resultClass}">
          <input type="radio" name="${question.id}" value="${optionIndex}" ${checked} ${state.submitted ? "disabled" : ""}>
          <span>${String.fromCharCode(65 + optionIndex)}. ${textFor(option, language)}</span>
        </label>
      `;
    })
    .join("");

  const explanation = state.submitted
    ? `<div class="explanation">${textFor(question.explanation, language)}</div>`
    : "";

  return `
    <article class="question-card" data-question-id="${question.id}">
      <div class="question-head">
        <div class="question-text">
          <strong>Q${index + 1}. ${textFor(question.question, language)}</strong>
          <small class="muted">${question.source}</small>
        </div>
        <span class="tag">Unit ${question.unit}</span>
      </div>
      <div class="options">${optionHtml}</div>
      ${explanation}
    </article>
  `;
}

function updateSubmitButton() {
  $("#submitButton").disabled = state.submitted || state.currentSet.length === 0;
}

function currentScoreText() {
  let correct = 0;
  let wrong = 0;
  let unattempted = 0;

  for (const question of state.currentSet) {
    const selected = state.answers.get(question.id);
    if (selected === undefined) unattempted += 1;
    else if (selected === question.answerIndex) correct += 1;
    else wrong += 1;
  }

  const score = correct - wrong * 0.25;
  const maxScore = state.currentSet.length;
  const accuracy = correct + wrong === 0 ? 0 : Math.round((correct / (correct + wrong)) * 100);
  return {
    correct,
    wrong,
    unattempted,
    score,
    maxScore,
    accuracy,
    summary: `Score ${score.toFixed(2)} / ${maxScore} | ${correct} correct, ${wrong} wrong, ${unattempted} skipped`
  };
}

function submitSet() {
  state.submitted = true;
  const result = currentScoreText();
  const attempt = {
    id: crypto.randomUUID(),
    date: new Date().toISOString(),
    mode: $("#modeSelect").value,
    unit: $("#modeSelect").value === "all" ? "All" : Number($("#unitSelect").value),
    language: $("#languageSelect").value,
    questionIds: state.currentSet.map((q) => q.id),
    units: state.currentSet.reduce((acc, question) => {
      const selected = state.answers.get(question.id);
      const unit = String(question.unit);
      acc[unit] ??= { total: 0, correct: 0, wrong: 0, unattempted: 0 };
      acc[unit].total += 1;
      if (selected === undefined) acc[unit].unattempted += 1;
      else if (selected === question.answerIndex) acc[unit].correct += 1;
      else acc[unit].wrong += 1;
      return acc;
    }, {}),
    ...result
  };

  const history = readJson(STORAGE_KEYS.history, []);
  writeJson(STORAGE_KEYS.history, [attempt, ...history]);
  renderQuiz();
  renderAnalytics();
  renderHistory();
}

function renderAnalytics() {
  const history = readJson(STORAGE_KEYS.history, []);
  const attempts = history.length;
  const totalScore = history.reduce((sum, item) => sum + item.score, 0);
  const totalCorrect = history.reduce((sum, item) => sum + item.correct, 0);
  const totalWrong = history.reduce((sum, item) => sum + item.wrong, 0);
  const best = history.reduce((max, item) => Math.max(max, item.score), 0);
  const accuracy = totalCorrect + totalWrong === 0 ? 0 : Math.round((totalCorrect / (totalCorrect + totalWrong)) * 100);

  $("#analyticsCards").innerHTML = [
    ["Attempts", attempts],
    ["Average Score", attempts ? (totalScore / attempts).toFixed(2) : "0.00"],
    ["Best Score", best.toFixed(2)],
    ["Accuracy", `${accuracy}%`]
  ]
    .map(([label, value]) => `<div class="metric-card"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");

  const byUnit = {};
  for (const item of history) {
    for (const [unit, stats] of Object.entries(item.units || {})) {
      byUnit[unit] ??= { total: 0, correct: 0, wrong: 0, unattempted: 0 };
      byUnit[unit].total += stats.total;
      byUnit[unit].correct += stats.correct;
      byUnit[unit].wrong += stats.wrong;
      byUnit[unit].unattempted += stats.unattempted;
    }
  }

  $("#unitAnalytics").innerHTML = UNITS.map((unit) => {
    const stats = byUnit[String(unit.id)] || { total: 0, correct: 0, wrong: 0 };
    const attempted = stats.correct + stats.wrong;
    const unitAccuracy = attempted === 0 ? 0 : Math.round((stats.correct / attempted) * 100);
    return `
      <div class="unit-row">
        <strong>Unit ${unit.id}</strong>
        <div class="bar-track"><div class="bar-fill" style="width:${unitAccuracy}%"></div></div>
        <span>${unitAccuracy}%</span>
      </div>
    `;
  }).join("");
}

function renderHistory() {
  const history = readJson(STORAGE_KEYS.history, []);
  $("#historyList").innerHTML = history.length
    ? history
      .map((item) => {
        const date = new Date(item.date).toLocaleString();
        return `
          <article class="history-item">
            <strong>${item.score.toFixed(2)} / ${item.maxScore} - ${item.mode === "all" ? "All Units" : `Unit ${item.unit}`}</strong>
            <span>${date}</span>
            <span>${item.correct} correct, ${item.wrong} wrong, ${item.unattempted} skipped, ${item.accuracy}% accuracy</span>
          </article>
        `;
      })
      .join("")
    : `<div class="panel muted">No attempts yet.</div>`;
}

function renderBank() {
  const byUnit = UNITS.map((unit) => ({
    unit,
    count: state.questions.filter((q) => q.unit === unit.id).length
  }));

  $("#bankList").innerHTML = `
    <div class="panel">
      <h3>Loaded Questions</h3>
      ${byUnit.map((row) => `<div class="unit-row"><strong>${row.unit.name}</strong><div>${row.count} questions</div><span></span></div>`).join("")}
      <div class="bank-question">
        <strong>Total:</strong> ${state.questions.length} questions
      </div>
    </div>
  `;
}

function importQuestions() {
  const raw = $("#importBox").value.trim();
  if (!raw) return;
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    alert("JSON is not valid.");
    return;
  }
  if (!Array.isArray(parsed)) {
    alert("Import must be an array of questions.");
    return;
  }
  const imported = readJson(STORAGE_KEYS.imports, []);
  writeJson(STORAGE_KEYS.imports, [...imported, ...parsed]);
  $("#importBox").value = "";
  loadQuestionBank();
  makePracticeSet();
  renderBank();
  alert(`${parsed.length} questions imported.`);
}

function bindEvents() {
  $$(".tab-button").forEach((button) => {
    button.addEventListener("click", () => {
      $$(".tab-button").forEach((tab) => tab.classList.remove("active"));
      $$(".view").forEach((view) => view.classList.remove("active"));
      button.classList.add("active");
      $(`#${button.dataset.view}View`).classList.add("active");
      renderAnalytics();
      renderHistory();
      renderBank();
    });
  });

  $("#newSetButton").addEventListener("click", makePracticeSet);
  $("#submitButton").addEventListener("click", submitSet);
  $("#unitSelect").addEventListener("change", makePracticeSet);
  $("#modeSelect").addEventListener("change", makePracticeSet);
  $("#languageSelect").addEventListener("change", renderQuiz);
  $("#importButton").addEventListener("click", importQuestions);
  $("#resetBankButton").addEventListener("click", () => {
    localStorage.removeItem(STORAGE_KEYS.imports);
    loadQuestionBank();
    makePracticeSet();
    renderBank();
  });
  $("#clearHistoryButton").addEventListener("click", () => {
    if (confirm("Clear all score history?")) {
      localStorage.removeItem(STORAGE_KEYS.history);
      renderAnalytics();
      renderHistory();
    }
  });

  $("#quizForm").addEventListener("change", (event) => {
    if (event.target.matches("input[type='radio']")) {
      state.answers.set(event.target.name, Number(event.target.value));
    }
  });
}

loadQuestionBank();
initUnitSelect();
bindEvents();
makePracticeSet();
renderAnalytics();
renderHistory();
renderBank();
