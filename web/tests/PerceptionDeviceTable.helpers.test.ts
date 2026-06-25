/**
 * PerceptionDeviceTable 纯函数 helper 单测
 *
 * 组件行为本身需要 DOM（vitest config 是 node 环境，无法 render），
 * 抽 helpers 出来测：排序、批量按钮 disabled 计算、行 toggle disabled 计算。
 */
import { describe, it, expect } from "vitest";
import type { ScopeCamera } from "@/lib/types";
import {
  bulkDisableDisabled,
  bulkEnableDisabled,
  rowToggleDisabled,
  sortCamerasByDid,
} from "@/components/PerceptionDeviceTable.helpers";

function cam(
  did: string,
  over: Partial<ScopeCamera> = {},
): ScopeCamera {
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

describe("sortCamerasByDid", () => {
  it("按 did 升序稳定排序", () => {
    const input = [cam("c3"), cam("c1"), cam("c2")];
    expect(sortCamerasByDid(input).map((c) => c.did)).toEqual([
      "c1",
      "c2",
      "c3",
    ]);
  });

  it("不动原数组（pure）", () => {
    const input = [cam("c3"), cam("c1")];
    const sorted = sortCamerasByDid(input);
    expect(input.map((c) => c.did)).toEqual(["c3", "c1"]);
    expect(sorted.map((c) => c.did)).toEqual(["c1", "c3"]);
  });

  it("空数组 → 空数组", () => {
    expect(sortCamerasByDid([])).toEqual([]);
  });
});

describe("bulkEnableDisabled", () => {
  it("所有在线相机 video 都开了 → 「全部开启」disabled", () => {
    const cameras = [
      cam("c1", { videoEnabled: true, isOnline: true }),
      cam("c2", { videoEnabled: true, isOnline: true }),
    ];
    expect(bulkEnableDisabled(cameras, "video")).toBe(true);
  });

  it("任一在线相机 video 未开 → 「全部开启」可点", () => {
    const cameras = [
      cam("c1", { videoEnabled: true, isOnline: true }),
      cam("c2", { videoEnabled: false, isOnline: true }),
    ];
    expect(bulkEnableDisabled(cameras, "video")).toBe(false);
  });

  it("全部离线 → 「全部开启」disabled（无可作用相机）", () => {
    const cameras = [
      cam("c1", { videoEnabled: false, isOnline: false }),
      cam("c2", { videoEnabled: false, isOnline: false }),
    ];
    expect(bulkEnableDisabled(cameras, "video")).toBe(true);
  });

  it("离线相机不参与判定（即使全开也 disabled）", () => {
    // 离线相机 videoEnabled=true 但 offline,不参与 enable 计数
    // 在线相机全关 → 可 enable
    const cameras = [
      cam("c1", { videoEnabled: true, isOnline: false }),
      cam("c2", { videoEnabled: false, isOnline: true }),
    ];
    expect(bulkEnableDisabled(cameras, "video")).toBe(false);
  });

  it("audio 模态独立判断（不影响 video 按钮）", () => {
    const cameras = [
      cam("c1", { videoEnabled: true, audioEnabled: true, isOnline: true }),
    ];
    expect(bulkEnableDisabled(cameras, "video")).toBe(true);
    expect(bulkEnableDisabled(cameras, "audio")).toBe(true);
  });
});

describe("bulkDisableDisabled", () => {
  it("所有在线相机 video 都关了 → 「全部关闭」disabled", () => {
    const cameras = [
      cam("c1", { videoEnabled: false, isOnline: true }),
      cam("c2", { videoEnabled: false, isOnline: true }),
    ];
    expect(bulkDisableDisabled(cameras, "video")).toBe(true);
  });

  it("任一在线相机 video 开着 → 「全部关闭」可点", () => {
    const cameras = [
      cam("c1", { videoEnabled: false, isOnline: true }),
      cam("c2", { videoEnabled: true, isOnline: true }),
    ];
    expect(bulkDisableDisabled(cameras, "video")).toBe(false);
  });

  it("全部离线 → 「全部关闭」disabled", () => {
    const cameras = [
      cam("c1", { videoEnabled: true, isOnline: false }),
    ];
    expect(bulkDisableDisabled(cameras, "video")).toBe(true);
  });
});

describe("rowToggleDisabled", () => {
  it("离线相机 → 禁 toggle", () => {
    expect(rowToggleDisabled(cam("c1", { isOnline: false }))).toBe(true);
  });

  it("在线相机 → 不禁 toggle", () => {
    expect(rowToggleDisabled(cam("c1", { isOnline: true }))).toBe(false);
  });
});