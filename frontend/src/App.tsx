import { Suspense, lazy } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { getToken } from "./api";
import { Layout } from "./components/Layout";
import { DialogProvider } from "./context/DialogContext";
import { PeriodProvider } from "./context/PeriodContext";
import { AdminShell } from "./components/AdminShell";

const Login = lazy(() => import("./pages/Login").then((m) => ({ default: m.Login })));
const Register = lazy(() => import("./pages/Register").then((m) => ({ default: m.Register })));
const Dashboard = lazy(() => import("./pages/Dashboard").then((m) => ({ default: m.Dashboard })));
const NewExpense = lazy(() => import("./pages/NewExpense").then((m) => ({ default: m.NewExpense })));
const FixedExpenses = lazy(() =>
  import("./pages/FixedExpenses").then((m) => ({ default: m.FixedExpenses })),
);
const Incomes = lazy(() => import("./pages/Incomes").then((m) => ({ default: m.Incomes })));
const Categories = lazy(() => import("./pages/Categories").then((m) => ({ default: m.Categories })));
const NewIncome = lazy(() => import("./pages/NewIncome").then((m) => ({ default: m.NewIncome })));
const Goals = lazy(() => import("./pages/Goals").then((m) => ({ default: m.Goals })));
const GoalDetail = lazy(() => import("./pages/GoalDetail").then((m) => ({ default: m.GoalDetail })));
const Cards = lazy(() => import("./pages/Cards").then((m) => ({ default: m.Cards })));
const Spenders = lazy(() => import("./pages/Spenders").then((m) => ({ default: m.Spenders })));
const Debtors = lazy(() => import("./pages/Debtors").then((m) => ({ default: m.Debtors })));
const CardDetail = lazy(() => import("./pages/CardDetail").then((m) => ({ default: m.CardDetail })));
const CardImportPreview = lazy(() =>
  import("./pages/CardImportPreview").then((m) => ({ default: m.CardImportPreview })),
);
const PersonUsageDetail = lazy(() =>
  import("./pages/PersonUsageDetail").then((m) => ({ default: m.PersonUsageDetail })),
);
const PersonUsageList = lazy(() =>
  import("./pages/PersonUsageList").then((m) => ({ default: m.PersonUsageList })),
);
const Investments = lazy(() => import("./pages/Investments").then((m) => ({ default: m.Investments })));
const Trips = lazy(() => import("./pages/Trips").then((m) => ({ default: m.Trips })));
const TripDetail = lazy(() => import("./pages/TripDetail").then((m) => ({ default: m.TripDetail })));
const AdminGestao = lazy(() => import("./pages/AdminGestao").then((m) => ({ default: m.AdminGestao })));

function RequireAuth() {
  if (!getToken()) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}

export function App() {
  return (
    <DialogProvider>
      <Suspense fallback={<div className="padded muted">Carregando...</div>}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route element={<RequireAuth />}>
            <Route
              element={
                <PeriodProvider>
                  <Layout />
                </PeriodProvider>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="despesa" element={<NewExpense />} />
              <Route path="gastos-fixos" element={<FixedExpenses />} />
              <Route path="receitas" element={<Incomes />} />
              <Route path="categorias" element={<Categories />} />
              <Route path="receitas/nova" element={<NewIncome />} />
              <Route path="orcamento" element={<Navigate to="/" replace />} />
              <Route path="metas" element={<Goals />} />
              <Route path="metas/:id" element={<GoalDetail />} />
              <Route path="cartoes" element={<Cards />} />
              <Route path="cartoes/pessoas" element={<Spenders />} />
              <Route path="devedores" element={<Debtors />} />
              <Route path="cartoes/:id" element={<CardDetail />} />
              <Route path="cartoes/:id/importar/preview" element={<CardImportPreview />} />
              <Route path="dashboard/pessoas" element={<PersonUsageList />} />
              <Route path="dashboard/uso-pessoa/:personRef" element={<PersonUsageDetail />} />
              <Route path="transferencia" element={<Navigate to="/" replace />} />
              <Route path="relatorios" element={<Navigate to="/" replace />} />
              <Route path="investimentos" element={<Investments />} />
              <Route path="viagens" element={<Trips />} />
              <Route path="viagens/:id" element={<TripDetail />} />
              <Route path="admin" element={<AdminShell />}>
                <Route index element={<Navigate to="gestao" replace />} />
                <Route path="gestao" element={<AdminGestao />} />
                <Route path="usuarios" element={<Navigate to="gestao" replace />} />
              </Route>
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </DialogProvider>
  );
}
