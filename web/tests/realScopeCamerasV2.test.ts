/**
 * 契约测试 — /api/miot/scope/cameras v2 (per-modality 字段)
 *
 * 覆盖:
 * - realListScopeCameras:BackendScopeCamera → ScopeCamera 字段映射(含 v2 新增 video_enabled/audio_enabled)
 * - realToggleScopeCamera:items → PUT request body snake_case 字段
 *
 * 不连真 backend:vi 拦截 fetch,伪造 NormalResponse 形状;afterEach 还原原 fetch.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { realListScopeCameras, realToggleScopeCamera } from "@/api/real";

const originalFetch = globalThis.fetch;

afterEach(() => {
  vi.restoreAllMocks();
  globalThis.fetch = originalFetch;
});

describe("realListScopeCameras — /api/miot/scope/cameras v2 契约", () => {
  it("BackendScopeCamera → ScopeCamera 字段映射（含 v2 模态字段）", async () => {
    globalThis.fetch = vi.fn(async () =>
      new Response(
        JSON.stringify({
          code: 0,
          message: "ok",
          data: [
            {
              did: "c1",
              name: "客厅",
              room_name: "客厅",
              is_online: true,
              in_use: true,
              connected: true,
              video_enabled: true,
              audio_enabled: false,
            },
            {
              did: "c2",
              name: null,
              room_name: null,
              is_online: false,
              in_use: false,
              connected: false,
              video_enabled: false,
              audio_enabled: false,
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    const cams = await realListScopeCameras();

    expect(cams).toEqual([
      {
        did: "c1",
        name: "客厅",
        roomName: "客厅",
        isOnline: true,
        inUse: true,
        connected: true,
        videoEnabled: true,
        audioEnabled: false,
      },
      {
        did: "c2",
        name: "c2", // null fallback → did
        roomName: undefined,
        isOnline: false,
        inUse: false,
        connected: false,
        videoEnabled: false,
        audioEnabled: false,
      },
    ]);
  });

  it("name 为 null 时回退到 did", async () => {
    globalThis.fetch = vi.fn(async () =>
      new Response(
        JSON.stringify({
          code: 0,
          message: "ok",
          data: [
            {
              did: "fallback",
              name: null,
              room_name: null,
              is_online: true,
              in_use: true,
              connected: false,
              video_enabled: true,
              audio_enabled: true,
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    const cams = await realListScopeCameras();
    expect(cams[0].name).toBe("fallback");
  });
});

describe("realToggleScopeCamera — /api/miot/scope/cameras PUT v2 契约", () => {
  it("单 videoEnabled 字段 → PUT body 含 video_enabled (snake_case)", async () => {
    const captured: { url?: string; init?: RequestInit } = {};
    globalThis.fetch = vi.fn(async (url, init) => {
      captured.url = typeof url === "string" ? url : url.toString();
      captured.init = init;
      return new Response(JSON.stringify({ code: 0, message: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as unknown as typeof fetch;

    await realToggleScopeCamera([
      { did: "c1", videoEnabled: false },
    ]);

    expect(captured.url).toContain("/api/miot/scope/cameras");
    expect(captured.init?.method).toBe("PUT");
    const body = JSON.parse(captured.init?.body as string);
    expect(body).toEqual({
      items: [
        {
          did: "c1",
          in_use: undefined,
          video_enabled: false,
          audio_enabled: undefined,
        },
      ],
    });
  });

  it("双模态显式给 → PUT body 双字段都 snake_case", async () => {
    const captured: { init?: RequestInit } = {};
    globalThis.fetch = vi.fn(async (_url, init) => {
      captured.init = init;
      return new Response(JSON.stringify({ code: 0, message: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as unknown as typeof fetch;

    await realToggleScopeCamera([
      { did: "c1", videoEnabled: true, audioEnabled: false },
      { did: "c2", videoEnabled: false, audioEnabled: true },
    ]);

    const body = JSON.parse(captured.init?.body as string);
    expect(body).toEqual({
      items: [
        { did: "c1", in_use: undefined, video_enabled: true, audio_enabled: false },
        { did: "c2", in_use: undefined, video_enabled: false, audio_enabled: true },
      ],
    });
  });

  it("只给 inUse → 双模态同值（便捷别名）", async () => {
    const captured: { init?: RequestInit } = {};
    globalThis.fetch = vi.fn(async (_url, init) => {
      captured.init = init;
      return new Response(JSON.stringify({ code: 0, message: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as unknown as typeof fetch;

    await realToggleScopeCamera([{ did: "c1", inUse: false }]);

    const body = JSON.parse(captured.init?.body as string);
    expect(body.items[0]).toEqual({
      did: "c1",
      in_use: false,
      video_enabled: undefined,
      audio_enabled: undefined,
    });
  });
});