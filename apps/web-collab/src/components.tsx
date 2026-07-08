import React, { useState } from "react";

export interface UserPresence {
  id: string;
  name: string;
  avatarUrl?: string;
  status: "online" | "offline" | "away";
}

export interface PresenceAvatarListProps {
  users: UserPresence[];
}

export const PresenceAvatarList: React.FC<PresenceAvatarListProps> = ({
  users,
}) => {
  return (
    <div className="presence-avatars flex items-center -space-x-2">
      {users.map((u) => (
        <div
          key={u.id}
          className="relative group w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-white text-xs font-bold"
          title={`${u.name} (${u.status})`}
        >
          {u.name.substring(0, 2).toUpperCase()}
          <span className={`absolute bottom-0 right-0 block h-2.5 w-2.5 rounded-full ring-2 ring-slate-900 ${
            u.status === "online" ? "bg-green-500" :
            u.status === "away" ? "bg-yellow-500" :
            "bg-slate-500"
          }`} />
        </div>
      ))}
    </div>
  );
};

export interface NotificationItem {
  id: string;
  message: string;
  isRead: boolean;
}

export interface NotificationCenterProps {
  notifications: NotificationItem[];
  onMarkRead: (id: string) => void;
}

export const NotificationCenter: React.FC<NotificationCenterProps> = ({
  notifications,
  onMarkRead,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const unreadCount = notifications.filter((n) => !n.isRead).length;

  return (
    <div className="notification-center relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative bg-slate-850 hover:bg-slate-800 text-white rounded p-2 text-sm transition-colors"
      >
        Alerts
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 bg-violet-600 text-white text-[10px] px-1 rounded-full font-bold">
            {unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-slate-900 border border-slate-850 rounded shadow-xl z-20 text-white p-4">
          <div className="font-bold border-b border-slate-800 pb-2 mb-2">Notifications</div>
          <div className="space-y-2">
            {notifications.length === 0 ? (
              <div className="text-xs text-slate-500">No alerts found.</div>
            ) : (
              notifications.map((n) => (
                <div key={n.id} className="flex justify-between items-start text-xs border-b border-slate-850 pb-2">
                  <span className={n.isRead ? "text-slate-400" : "font-semibold"}>{n.message}</span>
                  {!n.isRead && (
                    <button
                      onClick={() => onMarkRead(n.id)}
                      className="text-[10px] text-violet-400 hover:text-violet-300 font-bold ml-2 shrink-0"
                    >
                      Read
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
