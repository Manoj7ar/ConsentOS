"use client";

import { useEffect, useState } from "react";

import { fetchApproval } from "@/lib/api";
import { StatusPill } from "@/components/status-pill";
import { getDisplayErrorMessage } from "@/lib/error-display";

type ApprovalBannerProps = {
  activityId: number;
  onResolved?: (activityId: number) => void;
};

const TERMINAL_STATUSES = new Set(["approved", "rejected", "completed", "failed"]);

export function ApprovalBanner({ activityId, onResolved }: ApprovalBannerProps) {
  const [status, setStatus] = useState("pending");
  const [detail, setDetail] = useState("Approval requested on your phone.");
  const [mode, setMode] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const timer = setInterval(async () => {
      try {
        const response = await fetchApproval(activityId);
        if (!active) {
          return;
        }
        setStatus(response.status);
        setDetail(response.detail ?? "Awaiting response.");
        setMode(response.mode ?? null);
        if (TERMINAL_STATUSES.has(response.status)) {
          clearInterval(timer);
          onResolved?.(activityId);
        }
      } catch (error) {
        if (active) {
          setStatus("failed");
          setDetail(getDisplayErrorMessage(error));
          clearInterval(timer);
        }
      }
    }, 3000);

    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [activityId, onResolved]);

  return (
    <div className="approval-banner">
      <div>
        <strong>Approval Required</strong>
        <p>{detail}</p>
        {mode ? <p className="muted">Mode: {mode}</p> : null}
      </div>
      <StatusPill status={status} />
    </div>
  );
}
