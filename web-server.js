const express = require("express");
const path = require("path");

const app = express();
const port = Number(process.env.PORT || 8080);
const host = process.env.HOST || "0.0.0.0";
const staticPath = path.join(__dirname, "frontened", "dist");

app.use(express.static(staticPath));
app.use((_req, res) => {
  res.sendFile(path.join(staticPath, "index.html"));
});

app.listen(port, host, () => {
  console.log(`Web app is available at http://${host}:${port}`);
});
