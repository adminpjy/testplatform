import { navigationItems, navRouteFor, type AppRoute } from "../routes/navigation";

export function TopNav({ route }: { route: AppRoute }) {
  const activeRoute = navRouteFor(route);
  return (
    <header className="top-nav">
      <a className="top-nav__brand" href="#test-run">
        <strong>石化智云智能功能测试平台</strong>
      </a>
      <nav className="top-nav__links" aria-label="主导航">
        {navigationItems.map((item) => {
          const Icon = item.icon;
          return (
            <a className={activeRoute === item.id ? "top-nav__item top-nav__item--active" : "top-nav__item"} href={`#${item.id}`} key={item.id}>
              <Icon size={16} />
              <span>{item.label}</span>
            </a>
          );
        })}
      </nav>
    </header>
  );
}
