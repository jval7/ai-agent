import * as reactDomModule from "react-dom/client";

import * as appModule from "@adapters/inbound/react/app/App";
import "@adapters/inbound/react/styles/index.css";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("Root element not found");
}

reactDomModule.createRoot(rootElement).render(<appModule.App />);
