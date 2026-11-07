import test from "node:test";
import assert from "node:assert/strict";
import { copy, Draft } from "../src/model.js";

test("HTTP browsers without structuredClone can construct and edit card drafts", () => {
  const nativeClone = globalThis.structuredClone;
  try {
    globalThis.structuredClone = undefined;
    const original = {
      enabled: false,
      items: [{ name: "world" }],
      empty: null,
    };
    const cloned = copy(original);
    assert.deepEqual(cloned, original);
    cloned.items[0].name = "changed";
    assert.equal(original.items[0].name, "world");
    assert.equal(copy(undefined), undefined);
    const draft = new Draft();
    draft.update(original);
    draft.set("items", [{ name: "edited" }]);
    assert.equal(draft.dirty, true);
    assert.deepEqual(draft.conflicts, []);
    assert.equal(draft.live.items[0].name, "world");
    draft.reset(draft.value);
    assert.equal(draft.dirty, false);
  } finally {
    globalThis.structuredClone = nativeClone;
  }
});
