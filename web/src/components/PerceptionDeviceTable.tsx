/**
 * 感知设备列表（per-camera × per-modality，状态展示 + 操作分列）
 *
 * 列布局（v3 重构）：
 *   设备 | 视频感知 | 音频感知 | 操作
 *                          ├─ 视频开关
 *                          ├─ 音频开关
 *                          └─ 整设备主开关（视频+音频一键 ON/OFF）
 *
 * 主开关行为：
 * - on  ↔  视频 + 音频 都启用
 * - off ↔  视频 + 音频 都禁用
 * - mid ↔  二者状态不一致（视觉上一中杠标识，用户可一键回滚）
 * - 点击主开关:
 *     - 当前 on / mid → 都关
 *     - 当前 off → 都开
 *
 * 列表范围：所有米家摄像头（含离线 / 全关 / 已超 MAX_ENABLED 上限的），
 *           替代 v1 的「未感知设备」benchCams 列表。
 * 离线相机行灰显，所有 toggle 禁用（与 miot toggle_camera 上限同口径）。
 *
 * 顶部批量按钮：4 个模态级（视频 on/off / 音频 on/off）+ 2 个主开关级（全员启/暂停）。
 */

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { ScopeCamera } from "@/lib/types";
import {
  toggleScopeCamera,
  type CameraToggleItem,
} from "@/api";
import { toast } from "./Toast";
import {
  sortCamerasByDid,
  onlineCameras as onlineCamerasFn,
  bulkEnableDisabled,
  bulkDisableDisabled,
  rowToggleDisabled,
  masterSwitchState,
  type MasterState,
  bulkMasterEnableDisabled,
  bulkMasterDisableDisabled,
} from "./PerceptionDeviceTable.helpers";

interface Props {
  cameras: ScopeCamera[];
  onChanged: () => void;
}

type Modality = "video" | "audio";

export function PerceptionDeviceTable({ cameras, onChanged }: Props) {
  const { t } = useTranslation();
  const [singleBusy, setSingleBusy] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);

  const sorted = useMemo(() => sortCamerasByDid(cameras), [cameras]);
  const online = useMemo(() => onlineCamerasFn(cameras), [cameras]);

  const runSingle = async (
    did: string,
    modality: Modality,
    next: boolean,
  ) => {
    if (bulkBusy || singleBusy.has(did)) return;
    const cam = sorted.find((c) => c.did === did);
    if (!cam) return;
    // v1 back-compat: in_use 必填,需据 current + next 推
    const otherEnabled =
      modality === "video" ? cam.audioEnabled : cam.videoEnabled;
    const newInUse = next || otherEnabled;
    setSingleBusy((s) => new Set(s).add(did));
    try {
      const item: CameraToggleItem = {
        did,
        inUse: newInUse,
        ...(modality === "video"
          ? { videoEnabled: next }
          : { audioEnabled: next }),
      };
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

  /** 主开关:on/mid → 全关;off → 全开 */
  const runMaster = async (c: ScopeCamera) => {
    if (bulkBusy || singleBusy.has(c.did) || rowToggleDisabled(c)) return;
    const nextEnabled = !(c.videoEnabled || c.audioEnabled);
    setSingleBusy((s) => new Set(s).add(c.did));
    try {
      await toggleScopeCamera([
        { did: c.did, videoEnabled: nextEnabled, audioEnabled: nextEnabled, inUse: nextEnabled },
      ]);
      onChanged();
    } catch (e) {
      toast(e instanceof Error ? e.message : t("common.switchFailed"), "warn");
    } finally {
      setSingleBusy((s) => {
        const n = new Set(s);
        n.delete(c.did);
        return n;
      });
    }
  };

  const runBulk = async (kind: "video" | "audio" | "master", next: boolean) => {
    if (bulkBusy) return;
    setBulkBusy(true);
    try {
      const items: CameraToggleItem[] = online.map((c) => {
        if (kind === "master") {
          return { did: c.did, videoEnabled: next, audioEnabled: next, inUse: next };
        }
        // v1 back-compat: in_use 必填,据 current + next 推
        return kind === "video"
          ? { did: c.did, videoEnabled: next, inUse: next || c.audioEnabled }
          : { did: c.did, audioEnabled: next, inUse: c.videoEnabled || next };
      });
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
              disabled={bulkBusy || bulkEnableDisabled(cameras, "video")}
              onClick={() => runBulk("video", true)}
            />
            <BulkButton
              label={t("hero.table.bulkVideoAllOff")}
              disabled={bulkBusy || bulkDisableDisabled(cameras, "video")}
              onClick={() => runBulk("video", false)}
            />
            <BulkButton
              label={t("hero.table.bulkAudioAllOn")}
              disabled={bulkBusy || bulkEnableDisabled(cameras, "audio")}
              onClick={() => runBulk("audio", true)}
            />
            <BulkButton
              label={t("hero.table.bulkAudioAllOff")}
              disabled={bulkBusy || bulkDisableDisabled(cameras, "audio")}
              onClick={() => runBulk("audio", false)}
            />
            <BulkButton
              label={t("hero.table.bulkMasterAllOn")}
              disabled={bulkBusy || bulkMasterEnableDisabled(cameras)}
              onClick={() => runBulk("master", true)}
            />
            <BulkButton
              label={t("hero.table.bulkMasterAllOff")}
              disabled={bulkBusy || bulkMasterDisableDisabled(cameras)}
              onClick={() => runBulk("master", false)}
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
                <th className="text-center font-normal px-3 py-2 hidden sm:table-cell">
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
                const offline = rowToggleDisabled(c);
                const busy = bulkBusy || singleBusy.has(c.did);
                const master = masterSwitchState(c);
                return (
                  <tr
                    key={c.did}
                    className={`border-b border-border last:border-b-0 ${
                      offline ? "opacity-50" : ""
                    }`}
                  >
                    {/* 设备列:名称 + (room/离线) subline */}
                    <td className="px-5 py-3">
                      <div className="flex items-baseline gap-2">
                        <span className="text-text-primary truncate">
                          {c.name}
                        </span>
                        {c.roomName && (
                          <span className="text-caption text-text-tertiary truncate">
                            · {c.roomName}
                          </span>
                        )}
                      </div>
                      {offline && (
                        <div className="text-caption text-warning mt-0.5">
                          {t("hero.table.offlineHint")}
                        </div>
                      )}
                    </td>

                    {/* 视频感知:开关直接在此列 */}
                    <td className="px-3 py-3 text-center hidden sm:table-cell">
                      <ModalitySwitch
                        checked={c.videoEnabled}
                        disabled={offline || busy}
                        onChange={(next) => runSingle(c.did, "video", next)}
                        ariaLabel={`${c.name} · ${t("hero.table.headerVideo")}`}
                      />
                    </td>

                    {/* 音频感知:开关直接在此列 */}
                    <td className="px-3 py-3 text-center">
                      <ModalitySwitch
                        checked={c.audioEnabled}
                        disabled={offline || busy}
                        onChange={(next) => runSingle(c.did, "audio", next)}
                        ariaLabel={`${c.name} · ${t("hero.table.headerAudio")}`}
                      />
                    </td>

                    {/* 操作列:整设备主开关 */}
                    <td className="px-5 py-3 text-right">
                      <MasterSwitch
                        state={master}
                        disabled={offline || busy}
                        onClick={() => runMaster(c)}
                        ariaLabel={`${c.name} · ${t("hero.table.headerMaster")}`}
                      />
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

/* ── 子组件 ─────────────────────────────────────────────── */

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
}: {
  checked: boolean;
  disabled: boolean;
  onChange: (next: boolean) => void;
  ariaLabel: string;
}) {
  const { t } = useTranslation();
  const labelText = checked ? t("hero.table.on") : t("hero.table.off");
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={`${ariaLabel} · ${labelText}`}
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

/**
 * 整设备主开关 — 三态 on / off / mid
 *
 * - 点击:on/mid → 都关;off → 都开(等价于向 backend 发一对 video=audio=next 的 PUT)
 * - 视觉:on 同 ModalitySwitch;off 同;mid 在圆点位置覆盖一短横杠"半开"
 */
function MasterSwitch({
  state,
  disabled,
  onClick,
  ariaLabel,
}: {
  state: MasterState;
  disabled: boolean;
  onClick: () => void;
  ariaLabel: string;
}) {
  const { t } = useTranslation();
  const isOn = state === "on";
  const isMid = state === "mid";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={isOn}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={onClick}
      title={t(
        isOn
          ? "hero.table.masterHintOn"
          : isMid
          ? "hero.table.masterHintMid"
          : "hero.table.masterHintOff",
      )}
      className={`relative inline-flex h-[14px] w-[26px] shrink-0 rounded-full transition-colors shadow-sm focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:outline-none disabled:opacity-40 disabled:cursor-not-allowed ${
        isOn ? "bg-brand-primary" : "bg-black/60"
      }`}
    >
      {isMid ? (
        <span
          className="absolute top-1/2 -translate-y-1/2 left-1/2 -translate-x-1/2 inline-block h-[2px] w-3 rounded-full bg-white"
          aria-hidden
        />
      ) : (
        <span
          className={`absolute top-0.5 left-0.5 inline-block h-2.5 w-2.5 rounded-full bg-white shadow-sm transition-transform ${
            isOn ? "translate-x-[12px]" : "translate-x-0"
          }`}
        />
      )}
      <span className="sr-only">
        {isOn ? t("hero.table.masterOnLabel") : t("hero.table.masterOffLabel")}
      </span>
    </button>
  );
}
