import { LogOut } from "lucide-react";

import { navigationForUser, navRouteFor, type AppRoute } from "../routes/navigation";
import type { CurrentUser } from "../types/platform";

export function TopNav({ route, user, onLogout }: { route: AppRoute; user: CurrentUser; onLogout: () => void }) {
  const activeRoute = navRouteFor(route);
  const items = navigationForUser(user);
  return (
    <header className="top-nav">
      <a className="top-nav__brand" href="#test-run">
        <strong>石化智云智能功能测试平台</strong>
      </a>
      <nav className="top-nav__links" aria-label="主导航">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <a className={activeRoute === item.id ? "top-nav__item top-nav__item--active" : "top-nav__item"} href={`#${item.id}`} key={item.id}>
              <Icon size={16} />
              <span>{item.label}</span>
            </a>
          );
        })}
      </nav>
      <div className="top-nav__user">
        <span>{user.display_name || user.username}</span>
        <span className="role-pill">{roleLabel(user.role)}</span>
        <button className="icon-button" type="button" onClick={onLogout} title="退出登录">
          <LogOut size={16} />
        </button>
      </div>
    </header>
  );
}

function roleLabel(role: string): string {
  if (role === "admin") return "管理员";
  if (role === "owner") return "项目负责人";
  return "测试用户";
}
