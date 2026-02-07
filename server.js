const express = require("express");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;

// Sert tous les fichiers du dossier
app.use(express.static(__dirname));

// Page principale = demo.html
app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "demo.html"));
});

app.listen(PORT, () => {
  console.log("Server running on port " + PORT);
});