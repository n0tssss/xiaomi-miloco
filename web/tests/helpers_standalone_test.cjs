// Standalone Node test runner for PerceptionDeviceTable.helpers.
// Mirrors tests/PerceptionDeviceTable.helpers.test.ts (vitest) so we have
// at least one path that runs in node 16 (vitest 4 needs node 18+ because
// of vite 7 crypto internals — broken on the current Windows env).
//
// Run: node --test tests/helpers_standalone_test.cjs
// Keep this file in sync with tests/PerceptionDeviceTable.helpers.test.ts.

const test = require("node:test");
const assert = require("node:assert/strict");

// ---- Mirror of web/src/components/PerceptionDeviceTable.helpers.ts ----
function sortCamerasByDid(cameras) {
  return [...cameras].sort((a, b) =>
    a.did < b.did ? -1 : a.did > b.did ? 1 : 0,
  );
}
function onlineCameras(cameras) {
  return cameras.filter((c) => c.isOnline);
}
function bulkEnableDisabled(cameras, modality) {
  const online = onlineCameras(cameras);
  if (online.length === 0) return true;
  return online.every((c) =>
    modality === "video" ? c.videoEnabled : c.audioEnabled,
  );
}
function bulkDisableDisabled(cameras, modality) {
  const online = onlineCameras(cameras);
  if (online.length === 0) return true;
  return online.every((c) =>
    modality === "video" ? !c.videoEnabled : !c.audioEnabled,
  );
}
function rowToggleDisabled(camera) {
  return !camera.isOnline;
}

function cam(did, over = {}) {
  return {
    did,
    name: did,
    isOnline: true,
    inUse: false,
    connected: false,
    videoEnabled: false,
    audioEnabled: false,
    ...over,
  };
}

// ---- Mirror of tests/PerceptionDeviceTable.helpers.test.ts assertions ----

test("sortCamerasByDid: 升序排序", () => {
  const r = sortCamerasByDid([cam("c3"), cam("c1"), cam("c2")]);
  assert.deepEqual(r.map((c) => c.did), ["c1", "c2", "c3"]);
});

test("sortCamerasByDid: 不修改原数组", () => {
  const input = [cam("c3"), cam("c1")];
  const r = sortCamerasByDid(input);
  assert.deepEqual(input.map((c) => c.did), ["c3", "c1"]);
  assert.deepEqual(r.map((c) => c.did), ["c1", "c3"]);
});

test("sortCamerasByDid: 空数组", () => {
  assert.deepEqual(sortCamerasByDid([]), []);
});

test("bulkEnableDisabled: 全开 → disabled", () => {
  assert.equal(
    bulkEnableDisabled(
      [
        cam("c1", { videoEnabled: true, isOnline: true }),
        cam("c2", { videoEnabled: true, isOnline: true }),
      ],
      "video",
    ),
    true,
  );
});

test("bulkEnableDisabled: 任一未开 → 可点", () => {
  assert.equal(
    bulkEnableDisabled(
      [
        cam("c1", { videoEnabled: true, isOnline: true }),
        cam("c2", { videoEnabled: false, isOnline: true }),
      ],
      "video",
    ),
    false,
  );
});

test("bulkEnableDisabled: 全离线 → disabled", () => {
  assert.equal(
    bulkEnableDisabled(
      [
        cam("c1", { videoEnabled: false, isOnline: false }),
        cam("c2", { videoEnabled: false, isOnline: false }),
      ],
      "video",
    ),
    true,
  );
});

test("bulkEnableDisabled: 离线相机不参与判定", () => {
  assert.equal(
    bulkEnableDisabled(
      [
        cam("c1", { videoEnabled: true, isOnline: false }),
        cam("c2", { videoEnabled: false, isOnline: true }),
      ],
      "video",
    ),
    false,
  );
});

test("bulkEnableDisabled: audio 模态独立", () => {
  const cameras = [
    cam("c1", { videoEnabled: true, audioEnabled: true, isOnline: true }),
  ];
  assert.equal(bulkEnableDisabled(cameras, "video"), true);
  assert.equal(bulkEnableDisabled(cameras, "audio"), true);
});

test("bulkDisableDisabled: 全关 → disabled", () => {
  assert.equal(
    bulkDisableDisabled(
      [
        cam("c1", { videoEnabled: false, isOnline: true }),
        cam("c2", { videoEnabled: false, isOnline: true }),
      ],
      "video",
    ),
    true,
  );
});

test("bulkDisableDisabled: 任一开着 → 可点", () => {
  assert.equal(
    bulkDisableDisabled(
      [
        cam("c1", { videoEnabled: false, isOnline: true }),
        cam("c2", { videoEnabled: true, isOnline: true }),
      ],
      "video",
    ),
    false,
  );
});

test("bulkDisableDisabled: 全离线 → disabled", () => {
  assert.equal(
    bulkDisableDisabled([cam("c1", { videoEnabled: true, isOnline: false })], "video"),
    true,
  );
});

test("rowToggleDisabled: 离线 → true", () => {
  assert.equal(rowToggleDisabled(cam("c1", { isOnline: false })), true);
});

test("rowToggleDisabled: 在线 → false", () => {
  assert.equal(rowToggleDisabled(cam("c1", { isOnline: true })), false);
});