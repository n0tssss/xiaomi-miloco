/**
 * 感知设备列表（per-camera × per-modality 矩阵）
 *
 * 位置：HeroNow 下方，替代 v1 的「miloco 未感知设备」benchCams 列表。
 *
 * 行为：
 * - 始终列出所有米家摄像头（含离线 / 全关）
 * - 每行两路开关：摄像头感知（video）+ 音频感知（audio）
 * - 顶部 4 个批量按钮：全部开启视频 / 全部关闭视频 / 全部开启音频 / 全部关闭音频
 * - 离线相机行灰显、toggle 禁用（与 miot toggle_camera 上限校验同口径）
 * - 离线相机不参与批量按钮的范围
 */

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { ScopeCamera } from "@/lib/types";
import {
  toggleScopeCamera,
  type CameraToggleItem,
} from "@/api";
import { toast } from "./Toast";

interface Props {
  cameras: ScopeCamera[];
  onChanged: () => void;
}

type Modality = "video" | "audio";

export function PerceptionDeviceTable({ cameras, onChanged }: Props) {
  const { t } = useTranslation();
  const [singleBusy, setSingleBusy] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);

  const sorted = useMemo(
    () => [...cameras].sort((a, b) => a.did < b.did ? -1 : a.did > b.did ? 1 : 0),
    [cameras],
  );

  // 批量按钮范围 = 在线相机（离线无法 enable,跟 miot toggle_camera 同口径）
  const onlineCameras = useMemo(
    () => sorted.filter((c) => c.isOnline),
    [sorted],
  );

  const runSingle = async (
    did: string,
    modality: Modality,
    next: boolean,
  ) => {
    if (bulkBusy || singleBusy.has(did)) return;
    setSingleBusy((s) => new Set(s).add(did));
    try {
      const item: CameraToggleItem =
        modality === "video"
          ? { did, videoEnabled: next }
          : { did, audioEnabled: next };
      await toggleScopeCamera([item]);
      onChanged();
    } catch (e) {
      toast(e instanceof Error ? e.message : t("common.switchFailed"), "warn");
    } finally {
      setSingleBusy((s) => {
        const n = new Set(s);
        n.delete(did);
        return n;
      });
    }
  };

  const runBulk = async (modality: Modality, next: boolean) => {
    if (bulkBusy) return;
    setBulkBusy(true);
    try {
      const items: CameraToggleItem[] = onlineCameras.map((c) =>
        modality === "video"
          ? { did: c.did, videoEnabled: next }
          : { did: c.did, audioEnabled: next },
      );
      await toggleScopeCamera(items);
      onChanged();
    } catch (e) {
      toast(e instanceof Error ? e.message : t("common.switchFailed"), "warn");
    } finally {
      setBulkBusy(false);
    }
  };

  return (
    <section
      className="mt-4 rounded-xl bg-bg-secondary border border-border shadow-sm anim-in"
      aria-labelledby="perception-table-title"
    >
      <div className="flex items-baseline justify-between px-5 pt-4 pb-3 flex-wrap gap-2">
        <h2
          id="perception-table-title"
          className="text-title text-text-primary"
        >
          {t("hero.table.title")}
          <span className="text-caption-mono text-text-tertiary font-normal ml-2">
            {cameras.length}
          </span>
        </h2>
        {cameras.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <BulkButton
              label={t("hero.table.bulkVideoAllOn")}
              disabled={bulkBusy || onlineCameras.every((c) => c.videoEnabled)}
              onClick={() => runBulk("video", true)}
            />
            <BulkButton
              label={t("hero.table.bulkVideoAllOff")}
              disabled={bulkBusy || onlineCameras.every((c) => !c.videoEnabled)}
              onClick={() => runBulk("video", false)}
            />
            <BulkButton
              label={t("hero.table.bulkAudioAllOn")}
              disabled={bulkBusy || onlineCameras.every((c) => c.audioEnabled)}
              onClick={() => runBulk("audio", true)}
            />
            <BulkButton
              label={t("hero.table.bulkAudioAllOff")}
              disabled={bulkBusy || onlineCameras.every((c) => !c.audioEnabled)}
              onClick={() => runBulk("audio", false)}
            />
          </div>
        )}
      </div>

      {cameras.length === 0 ? (
        <div className="text-body text-text-secondary py-10 px-5 text-center">
          {t("hero.table.empty")}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-body">
            <thead>
              <tr className="text-caption text-text-tertiary border-b border-border">
                <th className="text-left font-normal px-5 py-2">
                  {t("hero.table.headerDevice")}
                </th>
                <th className="text-left font-normal px-3 py-2 hidden sm:table-cell">
                  {t("hero.table.headerRoom")}
                </th>
                <th className="text-center font-normal px-3 py-2">
                  {t("hero.table.headerVideo")}
                </th>
                <th className="text-center font-normal px-3 py-2">
                  {t("hero.table.headerAudio")}
                </th>
                <th className="text-right font-normal px-5 py-2">
                  {t("hero.table.headerActions")}
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((c) => {
                const offline = !c.isOnline;
                const busy = bulkBusy || singleBusy.has(c.did);
                return (
                  <tr
                    key={c.did}
                    className={`border-b border-border last:border-b-0 ${
                      offline ? "opacity-50" : ""
                    }`}
                  >
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-text-primary truncate">
                          {c.name}
                        </span>
                        {offline && (
                          <span className="text-caption text-warning shrink-0">
                            · {t("hero.table.offlineHint")}
                          </span>
                        )}
                      </div>
                      {/* mobile: room 跟在名字下方 */}
                      {c.roomName && (
                        <div className="text-caption text-text-tertiary truncate sm:hidden">
                          {c.roomName}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-3 text-text-secondary truncate hidden sm:table-cell">
                      {c.roomName ?? ""}
                    </td>
                    <td className="px-3 py-3 text-center">
                      <ModalitySwitch
                        checked={c.videoEnabled}
                        disabled={offline || busy}
                        onChange={(next) => runSingle(c.did, "video", next)}
                        ariaLabel={c.name}
                        modality="video"
                      />
                    </td>
                    <td className="px-3 py-3 text-center">
                      <ModalitySwitch
                        checked={c.audioEnabled}
                        disabled={offline || busy}
                        onChange={(next) => runSingle(c.did, "audio", next)}
                        ariaLabel={c.name}
                        modality="audio"
                      />
                    </td>
                    <td className="px-5 py-3 text-right">
                      <span className="text-caption text-text-tertiary">
                        {offline ? "—" : c.connected ? "LIVE" : ""}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function BulkButton({
  label,
  disabled,
  onClick,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="text-caption px-2.5 py-1 rounded-md bg-bg-primary border border-border hover:border-border-strong hover:text-text-primary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
    >
      {label}
    </button>
  );
}

function ModalitySwitch({
  checked,
  disabled,
  onChange,
  ariaLabel,
  modality,
}: {
  checked: boolean;
  disabled: boolean;
  onChange: (next: boolean) => void;
  ariaLabel: string;
  modality: Modality;
}) {
  const { t } = useTranslation();
  const labelText = checked ? t("hero.table.on") : t("hero.table.off");
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={`${modality === "video" ? t("hero.table.headerVideo") : t("hero.table.headerAudio")} · ${ariaLabel}`}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-[14px] w-[26px] shrink-0 rounded-full transition-colors shadow-sm focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:outline-none disabled:opacity-40 disabled:cursor-not-allowed ${
        checked ? "bg-brand-primary" : "bg-black/60"
      }`}
    >
      <span
        className={`absolute top-0.5 left-0.5 inline-block h-2.5 w-2.5 rounded-full bg-white shadow-sm transition-transform ${
          checked ? "translate-x-[12px]" : "translate-x-0"
        }`}
      />
      <span className="sr-only">{labelText}</span>
    </button>
  );
}