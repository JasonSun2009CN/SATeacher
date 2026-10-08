import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/ui";
import ImportPage from "./pages/ImportPage";
import AnswerKeyPage from "./pages/AnswerKeyPage";
import PracticePage from "./pages/PracticePage";
import ResultPage from "./pages/ResultPage";
import SettingsPage from "./pages/SettingsPage";

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<ImportPage />} />
          <Route path="/doc/:id/answers" element={<AnswerKeyPage />} />
          <Route path="/doc/:id/practice" element={<PracticePage />} />
          <Route path="/session/:sid/result" element={<ResultPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}
