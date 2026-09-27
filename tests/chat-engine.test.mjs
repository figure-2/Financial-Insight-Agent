import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { answerQuestion, selectLanes } from "../web/chat-engine.mjs";

const data = JSON.parse(readFileSync(new URL("../demo/chat-scenarios.json", import.meta.url), "utf8"));

test("three question types choose matching evidence", () => {
  assert.deepEqual(selectLanes("증권사 의견과 목표주가는?"), ["report"]);
  assert.deepEqual(selectLanes("실적과 관련 법령은?"), ["financial", "legal"]);
  assert.deepEqual(selectLanes("최근 주가 흐름은?"), ["market"]);
});
test("financial calculation uses consistent operands", () => {
  const result = answerQuestion("영업이익률은 어떻게 계산했어?", [], data);
  assert.match(result.sections[0].paragraphs[0], /180 ÷ 1,200 × 100 = 15.0%/);
  assert.deepEqual(result.sections[0].sources, ["financial"]);
});
test("report risk follow-up retains source role", () => {
  const result = answerQuestion("그 위험은?", ["report"], data);
  assert.deepEqual(result.lanes, ["report"]);
  assert.match(result.sections[0].paragraphs[0], /출시 일정 지연/);
  assert.deepEqual(result.sections[0].sources, ["report"]);
});
test("switching lanes replaces the previous subject type", () => {
  const result = answerQuestion("최근 주가 흐름은?", ["report"], data);
  assert.deepEqual(result.lanes, ["market"]);
  assert.equal(result.sections.length, 1);
});
test("market answer keeps five-observation limitation", () => {
  const result = answerQuestion("20거래일 주가 흐름은?", [], data);
  assert.match(result.sections[0].paragraphs[0], /\+500원/);
  assert.match(result.sections[0].paragraphs[1], /5개 관측일/);
  assert.match(result.sections[0].note, /미확인/);
});
test("market follow-up does not erase the downward observation", () => {
  const result = answerQuestion("매일 상승한 거야?", ["market"], data);
  assert.match(result.sections[0].paragraphs[0], /10,200원에서.*10,100원/);
});
test("unsupported subjects and unrelated text request clarification", () => {
  for (const message of ["가상기업 B의 실적은?", "삼성전자 주가 흐름은?", "날씨가 어때?", "", "a".repeat(601)]) {
    assert.equal(answerQuestion(message, ["report"], data).status, "clarification", message);
  }
});
test("same inputs produce the same cited answer", () => {
  const first = answerQuestion("가상기업 A의 실적과 관련 법령을 알려줘", [], data);
  assert.deepEqual(first, answerQuestion("가상기업 A의 실적과 관련 법령을 알려줘", [], data));
  for (const section of first.sections) {
    assert.ok(section.sources.every(key => data.sources[key]));
  }
});
