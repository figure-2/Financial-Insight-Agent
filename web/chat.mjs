import { answerQuestion } from "/assets/chat-engine.mjs";

const $ = id => document.getElementById(id);
const messages = $("messages"), question = $("question"), status = $("app-status");
const topics = {
  report: "가상기업 A에 대한 증권사 의견은?",
  financial: "가상기업 A의 실적과 관련 법령을 알려줘",
  market: "가상기업 A의 최근 주가 흐름을 알려줘",
};
let dataset = null, previous = [], turn = 0;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function showSource(key) {
  const source = dataset.sources[key];
  $("source-title").textContent = source.title;
  $("source-meta").textContent = `${source.publisher} · ${source.date} · ${source.locator}`;
  $("source-excerpt").textContent = source.excerpt;
  $("source-dialog").showModal();
}

function marketChart(observations) {
  const box = element("figure", undefined, "market-figure");
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 500 90");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "가상기업 A의 합성 종가 5개 관측. 축은 관측값 범위로 축소했습니다.");
  const values = observations.map(row => row.close), minimum = Math.min(...values), range = Math.max(...values) - minimum || 1;
  const points = values.map((value, index) => [12 + index * 476 / (values.length - 1), 77 - (value - minimum) / range * 64]);
  const line = document.createElementNS(svg.namespaceURI, "polyline");
  line.setAttribute("points", points.map(point => point.join(",")).join(" "));
  line.setAttribute("class", "chart-line");
  svg.append(line);
  for (const [x, y] of points) {
    const dot = document.createElementNS(svg.namespaceURI, "circle");
    dot.setAttribute("cx", String(x)); dot.setAttribute("cy", String(y)); dot.setAttribute("r", "4"); dot.setAttribute("class", "chart-dot"); svg.append(dot);
  }
  const caption = element("figcaption", undefined, "chart-caption");
  caption.append(element("span", observations[0].date), element("span", "합성 종가 · 관측값 범위 축"), element("span", observations.at(-1).date));
  box.append(svg, caption);
  return box;
}

function renderAnswer(result) {
  const row = element("div", undefined, "assistant-message");
  const avatar = element("span", "F", "avatar"); avatar.setAttribute("aria-hidden", "true");
  const body = element("div", undefined, "answer-body");
  const heading = element("div", undefined, "answer-heading");
  heading.append(element("strong", "FIA"), element("span", "가상기업 A · 예시 자료"));
  body.append(heading, element("p", result.message, "answer-intro"));
  for (const section of result.sections) {
    const block = element("section", undefined, "answer-section");
    block.append(element("h3", section.title));
    if (section.metrics) {
      const metrics = element("div", undefined, "metrics");
      for (const metric of section.metrics) {
        const card = element("div", undefined, "metric"); card.append(element("span", metric.label), element("strong", metric.value)); metrics.append(card);
      }
      block.append(metrics);
    }
    section.paragraphs.forEach(text => block.append(element("p", text)));
    if (section.observations) {
      block.append(marketChart(section.observations));
      const details = element("details", undefined, "observations"), list = element("ul");
      details.append(element("summary", "날짜별 관측값 보기"));
      section.observations.forEach(item => list.append(element("li", `${item.date} · ${item.close.toLocaleString("ko-KR")}원`)));
      details.append(list); block.append(details);
    }
    const sources = element("div", undefined, "sources");
    section.sources.forEach(key => {
      const button = element("button", `${dataset.sources[key].title} ↗`, "source-button");
      button.type = "button"; button.addEventListener("click", () => showSource(key)); sources.append(button);
    });
    block.append(sources, element("p", section.note, "answer-note")); body.append(block);
  }
  const next = element("div", undefined, "next-questions");
  result.suggestions.forEach(text => {
    const button = element("button", text); button.type = "button"; button.addEventListener("click", () => submit(text)); next.append(button);
  });
  body.append(next); row.append(avatar, body);
  return row;
}

function submit(text) {
  if (!dataset) return;
  text = text.trim();
  if (!text) return;
  if (turn >= 20) { status.textContent = "이 대화는 20개 질문까지 지원합니다. 새 대화로 이어가세요."; return; }
  const result = answerQuestion(text, previous, dataset);
  if (result.lanes.length) previous = result.lanes;
  turn += 1;
  $("welcome").hidden = true;
  const article = element("article", undefined, "turn"); article.id = `turn-${turn}`;
  const user = element("div", undefined, "user-message"); user.append(element("p", text));
  article.append(user, renderAnswer(result)); messages.append(article);
  if (turn === 1) $("history").replaceChildren();
  const item = element("li"), link = element("button", text);
  link.type = "button"; link.addEventListener("click", () => article.scrollIntoView({ block: "start" })); item.append(link); $("history").append(item);
  question.value = "";
  status.textContent = `${turn}번째 질문 · 예시 출처를 눌러 근거를 확인하세요.`;
  article.scrollIntoView({ block: "start" });
}

$("chat-form").addEventListener("submit", event => { event.preventDefault(); submit(question.value); });
question.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); $("chat-form").requestSubmit(); }
});
document.querySelectorAll("[data-topic]").forEach(button => button.addEventListener("click", () => submit(topics[button.dataset.topic])));
$("close-source").addEventListener("click", () => $("source-dialog").close());
function newConversation() {
  previous = []; turn = 0; messages.replaceChildren(); $("history").replaceChildren(element("li", "질문하면 대화가 여기에 표시됩니다.", "history-empty")); $("welcome").hidden = false;
  question.value = ""; status.textContent = dataset ? "새 대화 · 예시 질문을 선택하거나 직접 입력하세요." : "예시 자료를 준비하지 못했습니다. 페이지를 새로고침해 주세요."; question.focus();
}
$("new-chat").addEventListener("click", newConversation);
$("mobile-new-chat").addEventListener("click", newConversation);

try {
  const response = await fetch("/assets/scenarios.json", { cache: "no-store" });
  if (!response.ok) throw new Error("scenario_unavailable");
  dataset = await response.json();
  if (dataset.mode !== "synthetic" || dataset.company !== "가상기업 A") throw new Error("scenario_invalid");
  $("send").disabled = false;
  status.textContent = "예시 질문을 선택하거나 직접 입력하세요.";
  const topic = new URLSearchParams(location.search).get("topic");
  if (Object.hasOwn(topics, topic)) submit(topics[topic]);
} catch {
  dataset = null; status.textContent = "예시 자료를 준비하지 못했습니다. 페이지를 새로고침해 주세요.";
}
