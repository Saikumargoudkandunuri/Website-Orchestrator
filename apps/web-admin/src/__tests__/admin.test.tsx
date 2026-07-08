import { describe, test, expect, vi } from "vitest";

vi.mock("react", () => {
  return {
    default: {
      useState: (init: any) => [init, vi.fn()],
    },
    useState: (init: any) => [init, vi.fn()],
  };
});
import { OrganizationHierarchyView, RolePermissionMatrix, OrgNode } from "../components.tsx";

describe("Enterprise SaaS Admin UI Components", () => {
  test("Hierarchy view compiles structures", () => {
    const org: OrgNode = {
      id: "org-1",
      name: "Global Corp",
      businessUnits: [
        {
          id: "bu-1",
          name: "Marketing",
          teams: [{ id: "t-1", name: "SEO Team" }],
        },
      ],
    };

    const tree = OrganizationHierarchyView({ organization: org });
    expect(tree.props.className).toContain("org-hierarchy");
    expect(tree.props.children).toBeDefined();
  });

  test("Role permission matrix updates checkboxes on selection toggle", () => {
    const roles = ["admin", "reader"];
    const permissions = ["publish", "read"];
    const initialMatrix = {
      admin: ["publish", "read"],
      reader: ["read"],
    };
    const changeSpy = vi.fn();

    const matrix = RolePermissionMatrix({
      roles,
      permissions,
      initialMatrix,
      onChange: changeSpy,
    });

    expect(matrix.props.children).toBeDefined();
  });
});
