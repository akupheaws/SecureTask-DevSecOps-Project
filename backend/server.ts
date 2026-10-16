import { app } from "./app.js";
import { migrate, pool } from "./db.js";
await migrate();
const server = app.listen(Number(process.env.PORT || 3000), "0.0.0.0", () =>
  console.log("Secure Task By Akuphe listening on port " + (process.env.PORT || 3000)),
);
process.on("SIGTERM", () =>
  server.close(() => {
    void pool.end().then(() => process.exit(0));
  }),
);
