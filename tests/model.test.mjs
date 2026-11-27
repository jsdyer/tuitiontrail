import test from "node:test";
import assert from "node:assert/strict";
import {diffText, numberOf, show, slug, yearsFor} from "../web/model.mjs";

test("display distinguishes withheld amounts from zero and respects quality flags", () => {
  assert.equal(show(0), "$0");
  assert.equal(show([9000, "E"]), "$9,000 (E)");
  assert.equal(show("x"), "Suppressed");
  assert.equal(show(".."), "Unavailable");
  assert.equal(numberOf(undefined), null);
});

test("comparison uses observed values and preserves direction and missingness", () => {
  assert.equal(diffText("Nova Scotia","British Columbia",9803,5717), "Nova Scotia is $4,086 higher for the year.");
  assert.equal(diffText("A","B",[0, "E"],1000), "B is $1,000 higher for the year.");
  assert.match(diffText("A","B",0,"x"), /requires published figures/);
  assert.match(diffText("A","B",500,500), /same published average/);
});

test("academic year menu takes union across selected series including new observations", () => {
  assert.deepEqual(yearsFor({"2025/2026":100},{"2024/2025":200,"2027/2028":300}),["2027/2028","2025/2026","2024/2025"]);
  assert.equal(slug("Québec, Arts and Design"), "quebec-arts-and-design");
});
