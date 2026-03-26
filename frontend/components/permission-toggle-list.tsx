"use client";

import type { PermissionRule } from "@/lib/types";

type PermissionToggleListProps = {
  rules: PermissionRule[];
  onToggle: (rule: PermissionRule) => Promise<void>;
};

export function PermissionToggleList({ rules, onToggle }: PermissionToggleListProps) {
  return (
    <div className="permission-list">
      {rules.map((rule) => (
        <label className="permission-row" key={rule.tool_name}>
          <div>
            <strong>{rule.tool_name}</strong>
            <p>
              Risk <span className={`risk-tag risk-${rule.risk_level}`}>{rule.risk_level}</span>
            </p>
          </div>
          <input
            type="checkbox"
            checked={rule.is_allowed}
            onChange={() => onToggle({ ...rule, is_allowed: !rule.is_allowed })}
          />
        </label>
      ))}
    </div>
  );
}

