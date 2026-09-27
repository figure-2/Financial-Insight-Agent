/** Deterministic answers over an explicitly synthetic, single-company dataset. */
const LABELS = { report: "증권 리포트", financial: "재무", legal: "법령", market: "시장 흐름" };
const EXAMPLES = [
  "가상기업 A에 대한 증권사 의견은?",
  "가상기업 A의 실적과 관련 법령을 알려줘",
  "가상기업 A의 최근 주가 흐름을 알려줘",
];
const format = value => new Intl.NumberFormat("ko-KR").format(value);

export function selectLanes(message, previous = []) {
  const text = message.normalize("NFKC").toLowerCase();
  const rules = {
    report: /증권사|증권|리포트|투자의견|목표주가|목표가|애널리스트/,
    financial: /재무|실적|매출|영업이익|이익률|공시/,
    legal: /법령|법률|규제|조문|규정/,
    market: /주가|시장|거래량|시세|종가/,
  };
  const lanes = Object.keys(rules).filter(key => rules[key].test(text));
  if (/목표주가/.test(text) && !/흐름|추이|시세|종가/.test(text)) {
    const index = lanes.indexOf("market");
    if (index >= 0) lanes.splice(index, 1);
  }
  if (/종합|기업 상태/.test(text)) return ["report", "financial", "market"];
  if (lanes.length) return lanes;
  return /근거|출처|계산|위험|이유|어떻게|왜|매일|얼마나/.test(text) ? [...previous] : [];
}

function unsupported(message) {
  return { status: "clarification", lanes: [], sections: [], message, suggestions: EXAMPLES };
}

function otherCompany(message, company) {
  if (/가상기업\s*[B-Z0-9]/i.test(message)) return true;
  const named = message.match(/^(.+?)(?:의\s*|에\s*대한\s*|\s+)(?=최근|실적|주가|증권사|매출|재무)/);
  if (!named) return false;
  const subject = named[1].trim();
  if (/^(?:최근\s*)?\d+\s*(?:거래일|일|개월|년)$/.test(subject)) return false;
  return ![company, "이 기업", "이 회사", "최근", "최신", "오늘"].includes(subject);
}

export function answerQuestion(message, previous, data) {
  if (typeof message !== "string" || !message.trim() || message.length > 600) {
    return unsupported("질문을 600자 이내로 입력해 주세요.");
  }
  if (otherCompany(message.trim(), data.company)) {
    return unsupported("이 체험에서는 가상기업 A의 예시 자료를 사용합니다. 아래 질문으로 시작해 보세요.");
  }
  const lanes = selectLanes(message, previous);
  if (!lanes.length) return unsupported("확인할 내용을 골라 주세요. 증권사 의견, 재무·법령, 주가 흐름을 살펴볼 수 있습니다.");
  const sections = [];
  if (lanes.includes("report")) {
    const r = data.report;
    const paragraphs = /위험/.test(message)
      ? [r.risk, "이는 예시 리포트가 제시한 가능성이며 실제 사건 발생을 뜻하지 않습니다."]
      : [`예시증권은 투자의견 ‘${r.opinion}’와 목표주가 ${format(r.target_price)}원을 제시했습니다.`, r.rationale, r.risk];
    sections.push({ key: "report", title: LABELS.report, paragraphs, sources: ["report"], note: "출처의 견해 · FIA의 매수 추천이 아닙니다." });
  }
  if (lanes.includes("financial")) {
    const f = data.financial;
    const margin = (f.operating_income / f.revenue * 100).toFixed(1);
    const growth = ((f.revenue - f.previous_revenue) / f.previous_revenue * 100).toFixed(1);
    sections.push({
      key: "financial", title: LABELS.financial,
      paragraphs: /계산|어떻게/.test(message)
        ? [`영업이익률은 영업이익을 같은 기간의 매출로 나눠 계산합니다. ${format(f.operating_income)} ÷ ${format(f.revenue)} × 100 = ${margin}%입니다.`, `매출 비교는 (${format(f.revenue)} − ${format(f.previous_revenue)}) ÷ ${format(f.previous_revenue)} × 100 = ${growth}%입니다.`]
        : [`${f.period} 매출은 ${format(f.revenue)}억 원, 영업이익은 ${format(f.operating_income)}억 원입니다.`, `같은 기간의 영업이익률은 ${margin}%입니다. 같은 공시의 전년 동기 매출 ${format(f.previous_revenue)}억 원과 비교하면 ${growth}% 높습니다.`],
      metrics: [ { label: "매출", value: `${format(f.revenue)}억 원` }, { label: "영업이익", value: `${format(f.operating_income)}억 원` }, { label: "영업이익률", value: `${margin}%` } ],
      sources: ["financial"], note: "합성 공시의 동일 기간·연결 기준으로 계산했습니다.",
    });
  }
  if (lanes.includes("legal")) {
    sections.push({ key: "legal", title: LABELS.legal, paragraphs: ["설명용 가상 조문 L-1 제3조는 서비스 이용조건의 사전 고지를 다룹니다.", "기업이 실제로 이 의무를 준수했는지는 이 예시 자료에 포함되지 않습니다."], sources: ["legal"], note: "가상 조문 · 실제 법률이나 적용성 판단이 아닙니다." });
  }
  if (lanes.includes("market")) {
    const first = data.market[0], last = data.market.at(-1), change = last.close - first.close;
    sections.push({
      key: "market", title: LABELS.market,
      paragraphs: /매일/.test(message)
        ? ["매 관측일마다 상승하지는 않았습니다. 9월 2일 10,200원에서 9월 3일 10,100원으로 낮아진 구간이 있습니다."]
        : [`${first.date} ${format(first.close)}원에서 ${last.date} ${format(last.close)}원으로, 두 종가 필드의 단순 차이는 ${change >= 0 ? "+" : ""}${format(change)}원입니다.`, `현재 예시는 ${data.market.length}개 관측일을 포함합니다. 20거래일 전체 흐름이나 실시간 시세를 나타내지는 않습니다.`],
      observations: data.market, sources: ["market"], note: "수정주가·기업행위 영향 미확인 · 합성 관측값",
    });
  }
  const suggestions = lanes.includes("financial")
    ? ["영업이익률은 어떻게 계산했어?", "가상기업 A의 최근 주가 흐름을 알려줘"]
    : lanes.includes("market") ? ["매일 상승한 거야?", "가상기업 A의 실적과 관련 법령을 알려줘"]
      : ["증권사가 제시한 위험은?", "가상기업 A의 실적과 관련 법령을 알려줘"];
  return { status: "example", lanes, sections, suggestions, message: `${data.company}의 예시 자료에서 질문에 필요한 근거를 모았습니다.` };
}
