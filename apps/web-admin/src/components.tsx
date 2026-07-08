import React, { useState } from "react";

export interface TeamNode {
  id: string;
  name: string;
}

export interface BusinessUnitNode {
  id: string;
  name: string;
  teams: TeamNode[];
}

export interface OrgNode {
  id: string;
  name: string;
  businessUnits: BusinessUnitNode[];
}

export interface OrganizationHierarchyViewProps {
  organization: OrgNode;
}

export const OrganizationHierarchyView: React.FC<OrganizationHierarchyViewProps> = ({
  organization,
}) => {
  return (
    <div className="org-hierarchy p-4 bg-slate-900 text-white rounded">
      <h2 className="text-xl font-bold mb-2">{organization.name} Hierarchy</h2>
      <div className="pl-4 border-l border-slate-700 space-y-4">
        {organization.businessUnits.map((bu) => (
          <div key={bu.id} className="business-unit">
            <h3 className="text-md font-semibold text-violet-400">{bu.name}</h3>
            <div className="pl-4 border-l border-slate-800 space-y-2 mt-1">
              {bu.teams.map((t) => (
                <div key={t.id} className="team text-sm text-slate-300">
                  {t.name}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export interface RolePermissionMatrixProps {
  roles: string[];
  permissions: string[];
  initialMatrix: Record<string, string[]>; // mapping role -> list of permissions
  onChange: (role: string, permission: string, checked: boolean) => void;
}

export const RolePermissionMatrix: React.FC<RolePermissionMatrixProps> = ({
  roles,
  permissions,
  initialMatrix,
  onChange,
}) => {
  const [matrix, setMatrix] = useState<Record<string, string[]>>(initialMatrix);
  const handleToggle = (role: string, perm: string) => {
    const list = matrix[role] || [];
    const checked = list.includes(perm);
    const updated = checked ? list.filter((p) => p !== perm) : [...list, perm];
    const newMatrix = { ...matrix, [role]: updated };
    setMatrix(newMatrix);
    onChange(role, perm, !checked);
  };

  return (
    <table className="min-w-full bg-slate-950 text-white rounded border border-slate-800">
      <thead>
        <tr className="border-b border-slate-800">
          <th className="p-3 text-left">Permission / Scope</th>
          {roles.map((r) => (
            <th key={r} className="p-3 text-center capitalize">{r}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {permissions.map((p) => (
          <tr key={p} className="border-b border-slate-900">
            <td className="p-3 text-sm text-slate-400 font-mono">{p}</td>
            {roles.map((r) => {
              const checked = (matrix[r] || []).includes(p);
              return (
                <td key={r} className="p-3 text-center">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => handleToggle(r, p)}
                    className="h-4 w-4 rounded border-slate-700 text-violet-600 focus:ring-violet-500"
                  />
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
};
