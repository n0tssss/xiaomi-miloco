/**
 * PerceptionDeviceTable 的纯函数 helper —— 抽出来便于 vitest 单测。
 *
 * 不导出 React hook、不依赖 i18n，组件和测试都用同一个函数避免实现飘移。
 */

import type { ScopeCamera } from "@/lib/types";

/** 按 did 升序稳定排序（toggle 单行不重排其它行）。 */
export function sortCamerasByDid(cameras: ScopeCamera[]): ScopeCamera[] {
  return [...cameras].sort((a, b) =>
    a.did < b.did ? -1 : a.did > b.did ? 1 : 0,
  );
}

/** 批量按钮范围 = 在线相机（离线无法 enable,跟 miot toggle_camera 同口径）。 */
export function onlineCameras(cameras: ScopeCamera[]): ScopeCamera[] {
  return cameras.filter((c) => c.isOnline);
}

/** 检测「全部开启 X」按钮是否该置灰 —— 所有在线相机都开了该模态。 */
export function bulkEnableDisabled(
  cameras: ScopeCamera[],
  modality: "video" | "audio",
): boolean {
  const online = onlineCameras(cameras);
  if (online.length === 0) return true;
  return online.every((c) =>
    modality === "video" ? c.videoEnabled : c.audioEnabled,
  );
}

/** 检测「全部关闭 X」按钮是否该置灰 —— 所有在线相机都关了。 */
export function bulkDisableDisabled(
  cameras: ScopeCamera[],
  modality: "video" | "audio",
): boolean {
  const online = onlineCameras(cameras);
  if (online.length === 0) return true;
  return online.every((c) =>
    modality === "video" ? !c.videoEnabled : !c.audioEnabled,
  );
}

/** 表格单行 toggle 是否该置灰：离线相机任何修改都被禁止。 */
export function rowToggleDisabled(camera: ScopeCamera): boolean {
  return !camera.isOnline;
}