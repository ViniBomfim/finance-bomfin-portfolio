import { Outlet } from "react-router-dom";

export function AdminShell() {
  return (
    <div className="padded admin-shell">
      <div className="page-head">
        <h1>Gestão</h1>
      </div>
      <Outlet />
    </div>
  );
}
