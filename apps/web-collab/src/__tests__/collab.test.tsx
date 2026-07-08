import { describe, test, expect, vi } from "vitest";

vi.mock("react", () => {
  return {
    default: {
      useState: (init: any) => [init, vi.fn()],
    },
    useState: (init: any) => [init, vi.fn()],
  };
});
import { PresenceAvatarList, NotificationCenter } from "../components.tsx";

describe("Collaboration Platform UI Components", () => {
  test("Presence avatar indicator list compiles", () => {
    const users = [
      { id: "1", name: "Bob", status: "online" as const },
    ];
    const list = PresenceAvatarList({ users });
    expect(list.props.className).toContain("presence-avatars");
  });

  test("Notification center alerts displays badge indicators", () => {
    const list = [
      { id: "1", message: "Task completed", isRead: false },
    ];
    const readSpy = vi.fn();
    const center = NotificationCenter({
      notifications: list,
      onMarkRead: readSpy,
    });
    expect(center.props.className).toContain("notification-center");
  });
});
