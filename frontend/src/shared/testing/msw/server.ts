import * as mswNodeModule from "msw/node";

import * as handlersModule from "./handlers";

export const server = mswNodeModule.setupServer(...handlersModule.handlers);
