import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { api } from "./api";
import { type Lang } from "./i18n";
import BrandMark from "./components/BrandMark";
import Landing from "./components/Landing";
import Login from "./components/Login";
import Dashboard from "./components/Dashboard";

type Gate = "checking" | "locked" | "open";
type View = "landing" | "app";

function Aurora() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      <div className="aurora-blob -top-40 left-[6%] h-[34rem] w-[34rem] bg-heat-warm/25" />
      <div
        className="aurora-blob -right-44 top-[18%] h-[38rem] w-[38rem] bg-heat-cool/20"
        style={{ animationDelay: "-9s", animationDuration: "32s" }}
      />
      <div
        className="aurora-blob -bottom-52 left-[28%] h-[36rem] w-[36rem] bg-heat-hot/20"
        style={{ animationDelay: "-17s", animationDuration: "38s" }}
      />
    </div>
  );
}

export default function App() {
  const [lang, setLang] = useState<Lang>("id");
  const [view, setView] = useState<View>("landing");
  const [gate, setGate] = useState<Gate>("checking");

  useEffect(() => {
    api
      .health()
      .then((h) => setGate(h.auth ? "locked" : "open"))
      .catch(() => setGate("locked"));
  }, []);

  if (view === "landing") {
    return (
      <div className="relative min-h-screen">
        <Aurora />
        <Landing lang={lang} setLang={setLang} onEnter={() => setView("app")} />
      </div>
    );
  }

  if (gate === "checking") {
    return (
      <div className="relative grid min-h-screen place-items-center">
        <Aurora />
        <div className="relative z-10 flex flex-col items-center gap-4">
          <BrandMark className="h-14 w-14" />
          <Loader2 className="h-5 w-5 animate-spin text-heat-hot" />
        </div>
      </div>
    );
  }

  if (gate === "locked") {
    return (
      <div className="relative min-h-screen">
        <Aurora />
        <Login lang={lang} onDone={() => setGate("open")} onBack={() => setView("landing")} />
      </div>
    );
  }

  return (
    <div className="relative min-h-screen">
      <Aurora />
      <div className="relative z-10">
        <Dashboard lang={lang} setLang={setLang} onHome={() => setView("landing")} />
      </div>
    </div>
  );
}
